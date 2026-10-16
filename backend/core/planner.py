from dataclasses import dataclass, field

import numpy as np

from core.constants import CONDENSED_CONFIDENCE, EXTRA_DROP_CHANCE
from core.scoring import Build
from core.simulate import build_score, drop_pool

POOL = 10_000
OUTCOMES = 100
CONTENDERS = 3


@dataclass
class QueueEntry:
    key: str
    build: Build
    state: list[float]  # best on-set then best off-set potential per slot
    target: float
    priority: int = 1

    @property
    def weight(self) -> float:
        # priority 1 is the top of the queue; each step down counts for less
        return 1 / max(self.priority, 1)


@dataclass
class DomainValue:
    domain: str
    value: float
    gains: dict[str, float] = field(default_factory=dict)


@dataclass
class Recommendation:
    best: DomainValue
    ranking: list[DomainValue]
    condensed: bool
    stay_share: float

    @property
    def focus(self) -> str | None:
        """The character the recommended run mostly helps."""
        gains = self.best.gains
        return max(gains, key=gains.__getitem__) if gains else None


def run_gain(pool: np.ndarray, state: np.ndarray, target: float) -> float:
    """Expected build score gain from one domain run, capped at the target."""
    current = build_score(state)
    if current >= target:
        return 0.0
    single = (np.minimum(build_score(np.maximum(pool, state)), target) - current).mean()
    return float(single * (1 + EXTRA_DROP_CHANCE))


def _rank(queue: list[QueueEntry], pools: dict[str, list[np.ndarray]], states: list[np.ndarray]) -> list[DomainValue]:
    ranking = []
    for domain, per_char in pools.items():
        gains = {q.key: run_gain(p, s, q.target) for q, p, s in zip(queue, per_char, states, strict=True)}
        value = sum(q.weight * gains[q.key] for q in queue)
        ranking.append(DomainValue(domain, value, gains))
    return sorted(ranking, key=lambda d: d.value, reverse=True)


def candidate_domains(queue: list[QueueEntry], domains: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """Domains that drop at least one set some queued build asks for."""
    wanted = {s for q in queue for s in q.build.sets}
    return {d: sets for d, sets in domains.items() if wanted & set(sets)}


def recommend(queue: list[QueueEntry], domains: dict[str, tuple[str, str]], seed: int | None = None) -> Recommendation | None:
    """Pick the domain with the highest priority-weighted expected gain for the next run."""
    candidates = candidate_domains(queue, domains)
    if not queue or not candidates:
        return None
    base = np.random.SeedSequence(seed)
    seeds = dict(zip(candidates, base.spawn(len(candidates)), strict=True))
    pools = {
        d: [drop_pool(q.build, sets, POOL, seeds[d]) for q in queue]
        for d, sets in candidates.items()
    }
    states = [np.array(q.state) for q in queue]
    ranking = _rank(queue, pools, states)
    best = ranking[0]
    if best.value == 0:
        return Recommendation(best, ranking, condensed=False, stay_share=0.0)

    # condensed commits two runs to one domain: check the pick survives what the first run might drop;
    # only the closest contenders can realistically overtake it after a single run
    contenders = {d.domain: pools[d.domain] for d in ranking[:CONTENDERS]}
    rng = np.random.default_rng(base.spawn(1)[0])
    stay = 0
    for i in rng.integers(POOL, size=OUTCOMES):
        after = [np.maximum(s, p[i]) for s, p in zip(states, pools[best.domain], strict=True)]
        stay += _rank(queue, contenders, after)[0].domain == best.domain
    share = stay / OUTCOMES
    return Recommendation(best, ranking, condensed=share >= CONDENSED_CONFIDENCE, stay_share=share)
