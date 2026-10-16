from dataclasses import dataclass, field

from core.constants import (
    FIXED_MAIN, INITIAL_SUBSTATS, MAX_LEVEL, MAX_ROLL, NUM_UPGRADES, OFF_SET_FACTOR, SET_RANK_STEP, SLOTS,
    SUBSTAT_PICK_WEIGHTS, SUBSTAT_ROLLS, SUBSTATS, UPGRADE_STEP, WRONG_MAIN_FACTOR,
)


@dataclass
class Artifact:
    set_key: str
    slot: str
    main_stat: str
    substats: dict[str, float]
    level: int = 0
    rarity: int = 5
    # 4th substat shown greyed out on 3-line pieces; it activates at the first upgrade
    unactivated: dict[str, float] = field(default_factory=dict)


@dataclass
class Build:
    weights: dict[str, float]
    sets: list[str] = field(default_factory=list)
    main_stats: dict[str, list[str]] = field(default_factory=dict)


def rolls(stat: str, value: float) -> float:
    """Substat value expressed in max 5-star rolls."""
    return value / MAX_ROLL[stat]


def substat_value(substats: dict[str, float], weights: dict[str, float]) -> float:
    return sum(rolls(s, v) * weights.get(s, 0) for s, v in substats.items())


def max_substat_value(weights: dict[str, float], main_stat: str) -> float:
    """Best possible weighted rolls on a 5-star +20 piece with this main stat."""
    top = sorted((weights.get(s, 0) for s in SUBSTATS if s != main_stat), reverse=True)
    return sum(top[:INITIAL_SUBSTATS]) + NUM_UPGRADES[5] * top[0]


def set_factor(set_key: str, build: Build) -> float:
    """Multiplier for a piece's set: 1 for the build's top set, less further down its list."""
    if set_key not in build.sets:
        return OFF_SET_FACTOR
    return max(1 - SET_RANK_STEP * build.sets.index(set_key), OFF_SET_FACTOR)


def piece_factor(artifact: Artifact, build: Build) -> float:
    """Multiplier for the artifact's set and main stat fit with the build."""
    f = set_factor(artifact.set_key, build)
    if artifact.slot not in FIXED_MAIN and artifact.main_stat not in build.main_stats.get(artifact.slot, []):
        f *= WRONG_MAIN_FACTOR
    return f


def _to_score(value: float, artifact: Artifact, build: Build) -> float:
    best = max_substat_value(build.weights, artifact.main_stat)
    if best == 0:
        return 0.0
    return 100 * min(value / best, 1.0) * piece_factor(artifact, build)


def score(artifact: Artifact, build: Build) -> float:
    """Current score 0-100 of an artifact for a build."""
    return _to_score(substat_value(artifact.substats, build.weights), artifact, build)


def _mean_roll(stat: str, rarity: int) -> float:
    values = SUBSTAT_ROLLS[rarity][stat]
    return sum(values) / len(values) / MAX_ROLL[stat]


def _expected_gain(subs: frozenset[str], main: str, weights: dict[str, float], rarity: int, upgrades: int) -> float:
    gain = {s: weights.get(s, 0) * _mean_roll(s, rarity) for s in SUBSTATS}
    # the same substat set is reached through many orders of additions, so each is solved once
    memo: dict[tuple[frozenset[str], int], float] = {}

    def expected(subs: frozenset[str], upgrades: int) -> float:
        if upgrades == 0:
            return 0.0
        if len(subs) >= INITIAL_SUBSTATS:
            # one of the four existing substats is upgraded uniformly at random
            return upgrades * sum(gain[s] for s in subs) / len(subs)
        key = (subs, upgrades)
        if key not in memo:
            # the upgrade adds a new substat, picked by weight among those not already present
            pool = {s: w for s, w in SUBSTAT_PICK_WEIGHTS.items() if s not in subs and s != main}
            total = sum(pool.values())
            memo[key] = sum(w / total * (gain[s] + expected(subs | {s}, upgrades - 1)) for s, w in pool.items())
        return memo[key]

    return expected(subs, upgrades)


def potential(artifact: Artifact, build: Build) -> float:
    """Expected score 0-100 once the artifact is levelled to max."""
    # upgrades land on every multiple of 4, so a +3 piece still has all of them ahead
    upgrades = MAX_LEVEL[artifact.rarity] // UPGRADE_STEP - artifact.level // UPGRADE_STEP
    subs = artifact.substats
    if artifact.unactivated and upgrades:
        subs = subs | artifact.unactivated
        upgrades -= 1
    value = substat_value(subs, build.weights) + _expected_gain(
        frozenset(subs), artifact.main_stat, build.weights, artifact.rarity, upgrades
    )
    return _to_score(value, artifact, build)


def best_per_slot(artifacts: list[Artifact], build: Build) -> tuple[list[float], list[float]]:
    """Highest potential per slot among on-set and among off-set artifacts, in SLOTS order."""
    on, off = dict.fromkeys(SLOTS, 0.0), dict.fromkeys(SLOTS, 0.0)
    for a in artifacts:
        best = on if a.set_key in build.sets else off
        best[a.slot] = max(best[a.slot], potential(a, build))
    return list(on.values()), list(off.values())


def combine(on: list[float], off: list[float]) -> list[float]:
    """Pieces the build would equip: on-set everywhere plus at most one off-set piece (4+1)."""
    used = list(on)
    k = max(range(len(on)), key=lambda i: off[i] - on[i])
    if off[k] > on[k]:
        used[k] = off[k]
    return used

