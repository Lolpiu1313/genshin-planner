from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from core.constants import (
    EXTRA_DROP_CHANCE, FIXED_MAIN, FOUR_SUBSTAT_CHANCE, INITIAL_SUBSTATS, MAIN_STAT_ODDS, NUM_UPGRADES,
    RESIN_PER_DAY, RESIN_PER_RUN, ROLL_TIERS, SLOTS, SUBSTAT_PICK_WEIGHTS, SUBSTATS, WRONG_MAIN_FACTOR,
)
from core.scoring import Build, max_substat_value, set_factor

CHUNK = 100
POOL = 200_000
MAX_ROLLS = INITIAL_SUBSTATS + NUM_UPGRADES[5]


@dataclass
class Estimate:
    runs: np.ndarray  # runs needed per simulation, inf if not reached
    max_runs: int

    def resin(self, q: float) -> float:
        return float(np.quantile(self.runs, q) * RESIN_PER_RUN)

    def days(self, q: float) -> float:
        return self.resin(q) / RESIN_PER_DAY

    @property
    def reached(self) -> float:
        return float(np.isfinite(self.runs).mean())


class _Domain:
    """Precomputed tables for scoring simulated drops against one build."""

    def __init__(self, build: Build, sets: tuple[str, str]):
        self.mains: list[str] = sorted({m for odds in MAIN_STAT_ODDS.values() for m in odds})
        self.weights = np.array([build.weights.get(s, 0.0) for s in SUBSTATS])
        self.pick = np.array([SUBSTAT_PICK_WEIGHTS[s] for s in SUBSTATS], dtype=float)

        # every (slot, main stat) pair as one outcome, so a single draw picks both
        slots, mains, probs, factor = [], [], [], []
        for i, slot in enumerate(SLOTS):
            odds = MAIN_STAT_ODDS[slot]
            total = sum(odds.values())
            for m, w in odds.items():
                ok = slot in FIXED_MAIN or m in build.main_stats.get(slot, [])
                slots.append(i)
                mains.append(self.mains.index(m))
                probs.append(w / total / len(SLOTS))
                factor.append(1.0 if ok else WRONG_MAIN_FACTOR)
        self.slot_of = np.array(slots)
        self.main_of = np.array(mains)
        self.cdf = np.cumsum(probs)
        self.factor = np.array(factor)

        # a substat can't repeat the main stat
        self.excluded = np.array([[s == m for s in SUBSTATS] for m in self.mains])
        self.best = np.array([max_substat_value(build.weights, m) for m in self.mains])
        self.on_set = np.array([s in build.sets for s in sets])
        self.set_factor = np.array([set_factor(s, build) for s in sets])

    def drops(self, rng: np.random.Generator, count: int) -> np.ndarray:
        """Score `count` simulated drops at +20 as (count, 2 * slots) states, zero outside the drop's column."""
        pair = np.minimum(np.searchsorted(self.cdf, rng.random(count)), len(self.cdf) - 1)
        main = self.main_of[pair]

        # weighted pick of four distinct substats via the Gumbel top-k trick
        u = np.maximum(rng.random((count, len(SUBSTATS)), dtype=np.float32), np.finfo(np.float32).tiny)
        keys = np.log(self.pick) - np.log(-np.log(u))
        keys[self.excluded[main]] = -np.inf
        subs = np.argpartition(-keys, INITIAL_SUBSTATS, axis=-1)[:, :INITIAL_SUBSTATS]

        # each sub gets one roll, then upgrades land on a random sub; a 3-line piece
        # spends its first upgrade unlocking the fourth sub, so it gets one fewer
        upgrades = rng.integers(INITIAL_SUBSTATS, size=(count, NUM_UPGRADES[5]))
        upgrades[rng.random(count) >= FOUR_SUBSTAT_CHANCE, -1] = -1
        targets = np.hstack([np.broadcast_to(np.arange(INITIAL_SUBSTATS), (count, INITIAL_SUBSTATS)), upgrades])

        tiers = np.asarray(ROLL_TIERS)[rng.integers(len(ROLL_TIERS), size=(count, MAX_ROLLS))]
        stat = np.take_along_axis(subs, np.clip(targets, 0, None), -1)
        value = (self.weights[stat] * tiers * (targets >= 0)).sum(-1)

        best = self.best[main]
        ratio = np.divide(value, best, out=np.zeros_like(value), where=best > 0)
        which = rng.integers(2, size=count)
        on_set = self.on_set[which]
        score = 100 * np.minimum(ratio, 1) * self.factor[pair] * self.set_factor[which]
        out = np.zeros((count, 2 * len(SLOTS)))
        out[np.arange(count), self.slot_of[pair] + len(SLOTS) * ~on_set] = score
        return out


def build_score(state: np.ndarray) -> np.ndarray:
    """Build score from (..., 2 * slots) states: best on-set piece per slot, then best off-set.

    The build equips on-set pieces everywhere plus at most one off-set piece (4+1).
    """
    on, off = state[..., :len(SLOTS)], state[..., len(SLOTS):]
    return (on.sum(-1) + np.maximum((off - on).max(-1), 0)) / len(SLOTS)


def drop_pool(build: Build, sets: tuple[str, str], size: int, seed: int | None = None) -> np.ndarray:
    """Scores of `size` simulated domain drops at +20, as (size, 2 * slots) states.

    The same seed yields the same physical drops for every build, so pools for
    different characters can be compared drop by drop.
    """
    return _Domain(build, sets).drops(np.random.default_rng(seed), size)


def _progress(build: Build, sets: tuple[str, str], n: int, rng: np.random.Generator,
              start: np.ndarray | None) -> Iterator[np.ndarray]:
    """Yield build scores after each run, CHUNK runs at a time."""
    # drops are resampled from a large pool of exactly simulated ones, which is far cheaper
    # than generating every artifact and statistically the same at this pool size
    pool = _Domain(build, sets).drops(rng, POOL)
    best = np.tile(start if start is not None else np.zeros(2 * len(SLOTS)), (n, 1))
    while True:
        per_run = pool[rng.integers(POOL, size=(n, CHUNK))]
        extra = rng.random((n, CHUNK)) < EXTRA_DROP_CHANCE
        per_run[extra] = np.maximum(per_run[extra], pool[rng.integers(POOL, size=int(extra.sum()))])
        running = np.maximum(np.maximum.accumulate(per_run, axis=1), best[:, None, :])
        best = running[:, -1]
        yield build_score(running)


def estimate(build: Build, sets: tuple[str, str], target: float, start: np.ndarray | None = None,
             n: int = 10_000, max_runs: int = 3000, seed: int | None = None) -> Estimate:
    """Distribution of domain runs needed until the build score reaches `target`.

    `start` is the current inventory as on-set bests followed by off-set bests per slot.
    """
    rng = np.random.default_rng(seed)
    runs = np.full(n, np.inf)
    done = 0
    for chunk in _progress(build, sets, n, rng, start):
        hit = chunk >= target
        first = np.where(hit.any(1), hit.argmax(1) + done + 1, np.inf)
        runs = np.minimum(runs, first)
        done += CHUNK
        # p90 is the highest quantile reported, so stop once nearly everyone got there
        if np.isfinite(runs).mean() >= 0.95 or done >= max_runs:
            break
    if start is not None and build_score(start) >= target:
        runs[:] = 0
    return Estimate(runs=runs, max_runs=done)


def scores_after(build: Build, sets: tuple[str, str], runs: int, n: int = 10_000,
                 seed: int | None = None) -> np.ndarray:
    """Build score of each simulation after `runs` domain runs from an empty inventory."""
    rng = np.random.default_rng(seed)
    if runs == 0:
        return np.zeros(n)
    for i, chunk in enumerate(_progress(build, sets, n, rng, None)):
        if (i + 1) * CHUNK >= runs:
            return chunk[:, runs - i * CHUNK - 1]
    raise AssertionError


def percentile(actual: float, simulated: np.ndarray) -> float:
    """Share of simulated players (0-100) doing no better than `actual`."""
    return float((simulated <= actual).mean() * 100)
