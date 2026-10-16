"""Exact upgrade outcomes of an artifact, as a Markov chain over its substat rolls.

A state is the set of substats plus the weighted roll value so far. Every +4 is one
transition: a 3-line piece gains a new substat (picked by weight), otherwise one of the
four substats gets a roll of 70-100% (each sub and tier equally likely). The score is
linear in the value, so the distribution of final values gives the expected score and
the odds of beating a given piece exactly, without sampling.

Levelling is also a decision process: before every +4 you either stop or pay for the next
roll. Feeding the piece away refunds most of the EXP, so a +4 really costs the rest, and a
maxed piece is worth its score above the equipped one. Backward induction over the chain
gives the stop/continue choice that maximises the expected net value in every state.
"""

from dataclasses import dataclass
from itertools import accumulate

from core.constants import (
    EXP_PER_POINT, FODDER_REFUND, INITIAL_SUBSTATS, LEVEL_EXP, MAX_LEVEL, MAX_ROLL, SUBSTAT_PICK_WEIGHTS,
    SUBSTAT_ROLLS, UPGRADE_STEP,
)
from core.scoring import Artifact, Build, max_substat_value, piece_factor, substat_value

PRECISION = 6

Subs = frozenset[str]
State = tuple[Subs, float]
Move = tuple[str, Subs, float, float]
Dist = dict[float, float]


@dataclass
class Plan:
    expected: float      # expected final score if levelled to max
    beat_chance: float   # chance the final piece beats the bar
    gain: float          # expected score gained over the bar, counting a miss as no gain
    go: bool             # whether levelling to the next +4 is optimal now
    value: float         # expected net value of playing optimally from here, in EXP
    reach_max: float     # chance the optimal policy takes it all the way to max
    keep_after_next: float  # chance the optimal policy still continues after the next roll
    success: float       # chance of ending maxed and better, playing optimally
    exp_next: int        # EXP to the next +4
    exp_expected: float  # EXP expected to be spent, playing optimally
    next_rolls: list[tuple[str, float, float]]  # substat the next +4 hits, its chance, and the share of
                                                # roll sizes after which the policy continues (or, on the
                                                # last +4, the piece ends better)


class UpgradeChain:
    def __init__(self, artifact: Artifact, build: Build):
        self.artifact = artifact
        self.weights = build.weights
        self.rarity = artifact.rarity
        self.best = max_substat_value(build.weights, artifact.main_stat)
        self.factor = piece_factor(artifact, build)
        self.checkpoints = list(range(artifact.level // UPGRADE_STEP * UPGRADE_STEP + UPGRADE_STEP,
                                      MAX_LEVEL[self.rarity] + 1, UPGRADE_STEP))
        self.pick = {s: w for s, w in SUBSTAT_PICK_WEIGHTS.items() if s != artifact.main_stat}
        self._moves_cache: dict[Subs, list[Move]] = {}
        self._remaining_cache: dict[tuple[Subs, int, bool], tuple[list[float], list[float]]] = {}

    def score(self, value: float) -> float:
        if self.best == 0:
            return 0.0
        return 100 * min(value / self.best, 1) * self.factor

    def _roll(self, stat: str) -> list[float]:
        return [self.weights.get(stat, 0) * v / MAX_ROLL[stat] for v in SUBSTAT_ROLLS[self.rarity][stat]]

    def _moves(self, subs: Subs) -> list[Move]:
        """Possible (substat rolled, new subs, value added, probability) for one upgrade."""
        if subs not in self._moves_cache:
            if len(subs) < INITIAL_SUBSTATS:
                pool = {s: w for s, w in self.pick.items() if s not in subs}
                total = sum(pool.values())
                moves = [(s, subs | {s}, inc, w / total / len(SUBSTAT_ROLLS[self.rarity][s]))
                         for s, w in pool.items() for inc in self._roll(s)]
            else:
                moves = [(s, subs, inc, 1 / len(subs) / len(SUBSTAT_ROLLS[self.rarity][s]))
                         for s in sorted(subs) for inc in self._roll(s)]
            self._moves_cache[subs] = moves
        return self._moves_cache[subs]

    def _next(self, subs: Subs, first: bool) -> list[Move]:
        if first and self.artifact.unactivated:
            # the greyed out line is known: it simply activates
            stat = next(iter(self.artifact.unactivated))
            return [(stat, subs | {stat}, substat_value(self.artifact.unactivated, self.weights), 1.0)]
        return self._moves(subs)

    def _step(self, states: dict[State, float], first: bool) -> dict[State, float]:
        out: dict[State, float] = {}
        for (subs, value), p in states.items():
            for _, new, inc, q in self._next(subs, first):
                key = (new, round(value + inc, PRECISION))
                out[key] = out.get(key, 0) + p * q
        return out

    def _remaining(self, subs: Subs, steps: int, first: bool) -> tuple[list[float], list[float]]:
        """Distribution of the value still to come: sorted values and their cumulative probabilities."""
        key = (subs, steps, first)
        if key not in self._remaining_cache:
            states = {(subs, 0.0): 1.0}
            for i in range(steps):
                states = self._step(states, first and i == 0)
            dist: Dist = {}
            for (_, v), p in states.items():
                dist[v] = dist.get(v, 0) + p
            values = sorted(dist)
            self._remaining_cache[key] = values, list(accumulate(dist[v] for v in values))
        return self._remaining_cache[key]

    def start(self) -> State:
        return frozenset(self.artifact.substats), substat_value(self.artifact.substats, self.weights)

    def final(self) -> Dist:
        """Distribution of the final score if levelled to max."""
        subs, value = self.start()
        values, cdf = self._remaining(subs, len(self.checkpoints), True)
        dist: Dist = {}
        for v, c, prev in zip(values, cdf, [0.0] + cdf[:-1], strict=True):
            s = round(self.score(value + v), PRECISION)
            dist[s] = dist.get(s, 0) + c - prev
        return dist

    def _exp(self, level: int, to: int) -> int:
        return sum(LEVEL_EXP[self.rarity][level:to])

    def policy(self, bar: float, exp_per_point: float) -> tuple[list[dict[State, bool]], float]:
        """Optimal continue/stop choice in every reachable state before each +4, and the value of the start."""
        layers = [{self.start(): 1.0}]
        for i in range(len(self.checkpoints)):
            layers.append(self._step(layers[-1], i == 0))
        value = {k: exp_per_point * max(self.score(k[1]) - bar, 0) for k in layers[-1]}
        levels = [self.artifact.level, *self.checkpoints]
        go: list[dict[State, bool]] = []
        for i in reversed(range(len(self.checkpoints))):
            cost = (1 - FODDER_REFUND) * self._exp(levels[i], levels[i + 1])
            prev: dict[State, float] = {}
            choice: dict[State, bool] = {}
            for subs, v in layers[i]:
                cont = sum(q * value[(new, round(v + inc, PRECISION))] for _, new, inc, q in self._next(subs, i == 0)) - cost
                choice[(subs, v)] = cont > 0
                prev[(subs, v)] = max(cont, 0.0)
            go.insert(0, choice)
            value = prev
        return go, value[self.start()]

    def plan(self, bar: float, exp_per_point: float = EXP_PER_POINT) -> Plan:
        """Outcome of levelling to max, and of the optimal stopping policy against `bar`."""
        dist = self.final()
        expected = sum(s * p for s, p in dist.items())
        beat = sum(p for s, p in dist.items() if s > bar)
        gain = sum((s - bar) * p for s, p in dist.items() if s > bar)

        go, value = self.policy(bar, exp_per_point)
        states = {self.start(): 1.0}
        level = self.artifact.level
        exp_spent = 0.0
        keep_next = 0.0
        for i, checkpoint in enumerate(self.checkpoints):
            moving = {k: p for k, p in states.items() if go[i][k]}
            exp_spent += sum(moving.values()) * self._exp(level, checkpoint)
            states = self._step(moving, i == 0)
            if i == 0:
                keep_next = sum(p for k, p in states.items() if go[1][k]) if len(go) > 1 else sum(states.values())
            level = checkpoint
        success = sum(p for (_, v), p in states.items() if self.score(v) > bar)

        return Plan(
            expected=expected,
            beat_chance=beat,
            gain=gain,
            go=bool(go and go[0][self.start()]),
            value=value,
            reach_max=sum(states.values()) if go else 1.0,
            keep_after_next=keep_next,
            success=success,
            exp_next=self._exp(self.artifact.level, self.checkpoints[0]) if self.checkpoints else 0,
            exp_expected=exp_spent,
            next_rolls=self._next_rolls(go, bar),
        )

    def _next_rolls(self, go: list[dict[State, bool]], bar: float) -> list[tuple[str, float, float]]:
        if not go:
            return []
        subs, value = self.start()
        by_stat: dict[str, tuple[float, float]] = {}
        for stat, new, inc, q in self._next(subs, True):
            key = (new, round(value + inc, PRECISION))
            good = go[1][key] if len(go) > 1 else self.score(key[1]) > bar
            p, c = by_stat.get(stat, (0.0, 0.0))
            by_stat[stat] = (p + q, c + q * good)
        return sorted(((s, p, c / p) for s, (p, c) in by_stat.items()), key=lambda r: -r[1])
