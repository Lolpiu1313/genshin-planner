from dataclasses import dataclass

from core.constants import EXP_PER_POINT, MAX_LEVEL, UPGRADE_STEP
from core.markov import Plan, UpgradeChain
from core.scoring import Artifact, Build, score


@dataclass
class Advice:
    action: str  # "upgrade", "step", "skip" or "done" when already maxed
    stop: int | None  # level to stop at and check again
    score: float
    equipped: float
    plan: Plan


def advise(artifact: Artifact, build: Build, equipped: Artifact | None, exp_per_point: float = EXP_PER_POINT) -> Advice:
    """Whether to level the artifact, by the optimal stopping policy against the equipped piece."""
    bar = score(equipped, build) if equipped else 0.0
    plan = UpgradeChain(artifact, build).plan(bar, exp_per_point)
    now = score(artifact, build)
    max_level = MAX_LEVEL[artifact.rarity]
    if artifact.level >= max_level:
        return Advice("done", None, now, bar, plan)
    if not plan.go:
        return Advice("skip", None, now, bar, plan)
    # if no roll can make stopping better, go straight to max; otherwise look again at the next +4
    if plan.reach_max > 1 - 1e-9:
        return Advice("upgrade", max_level, now, bar, plan)
    return Advice("step", (artifact.level // UPGRADE_STEP + 1) * UPGRADE_STEP, now, bar, plan)
