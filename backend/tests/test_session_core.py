import numpy as np
import pytest

from core.advice import advise
from core.constants import EXP_PER_POINT, FODDER_REFUND, LEVEL_EXP, MAIN_STAT_VALUES
from core.damage import artifact_stats
from core.enka import parse
from core.markov import UpgradeChain
from core.scoring import Artifact, Build, potential, score
from tests.helpers import ENKA, simulate_upgrades

HU_TAO = Build(
    weights={"critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5, "atk_": 0.25},
    sets=["CrimsonWitchOfFlames"],
    main_stats={"sands": ["hp_", "eleMas"], "goblet": ["pyro_dmg_"], "circlet": ["critRate_", "critDMG_"]},
)
STATS = {
    "base_hp": 15552, "base_atk": 715, "base_def": 876, "hp": 34000, "atk": 1200, "def": 1000,
    "critRate_": 70.0, "critDMG_": 200.0, "eleMas": 100.0, "enerRech_": 110.0, "pyro_dmg_": 61.6,
}

def circlet(**kw) -> Artifact:
    base = dict(set_key="CrimsonWitchOfFlames", slot="circlet", main_stat="critDMG_", level=0,
                substats={"critRate_": 3.5, "hp_": 5.3, "eleMas": 19, "def": 23})
    return Artifact(**(base | kw))


def equipped_scoring(target: float) -> Artifact:
    """A maxed circlet with only crit rate, sized to score `target`."""
    unit = score(circlet(level=20, substats={"critRate_": 1.0}), HU_TAO)
    return circlet(level=20, substats={"critRate_": target / unit})


def simulate_policy(art: Artifact, bar: float, go: list[dict], n: int, seed: int) -> dict[str, np.ndarray]:
    """Play `go` out by sampling the chain's transitions: final score, whether it got maxed, and EXP spent."""
    rng = np.random.default_rng(seed)
    chain = UpgradeChain(art, HU_TAO)
    levels = [art.level, *chain.checkpoints]
    out = {"score": np.zeros(n), "maxed": np.zeros(n), "exp": np.zeros(n)}
    for k in range(n):
        state = chain.start()
        for i in range(len(go)):
            if not go[i][state]:
                break
            out["exp"][k] += sum(LEVEL_EXP[art.rarity][levels[i]:levels[i + 1]])
            moves = chain._next(state[0], i == 0)
            _, new, inc, _ = moves[rng.choice(len(moves), p=[q for *_, q in moves])]
            state = (new, round(state[1] + inc, 6))
        else:
            out["maxed"][k] = 1
        out["score"][k] = chain.score(state[1])
    return out


def test_parse_enka():
    profile = parse(ENKA)
    assert profile.nickname == "Tester"
    char = profile.characters[0]
    assert (char.avatar_id, char.level) == (10000046, 90)
    assert char.stats["critRate_"] == pytest.approx(70)
    assert char.stats["pyro_dmg_"] == pytest.approx(61.6)
    art = char.artifacts[0]
    assert (art.slot, art.main_stat, art.level, art.set_id) == ("sands", "hp_", 20, 15006)
    assert art.substats["critRate_"] == pytest.approx(7.78)
    assert set(art.substats) == {"critRate_", "critDMG_", "atk"}


def test_artifact_stats_use_main_stat_by_level():
    assert artifact_stats(circlet())["critDMG_"] == MAIN_STAT_VALUES[5]["critDMG_"][0]
    assert artifact_stats(circlet(level=20))["critDMG_"] == pytest.approx(62.2)


def test_advice():
    junk = circlet(main_stat="atk_", substats={"def": 19, "atk": 16, "hp": 250, "enerRech_": 5})
    assert advise(junk, HU_TAO, None).action == "skip"

    great = circlet(substats={"critRate_": 3.9, "hp_": 5.8, "eleMas": 23, "atk_": 5.8})
    weak_equipped = circlet(level=20, substats={"def": 60, "atk": 40, "enerRech_": 10, "hp": 500})
    assert advise(great, HU_TAO, weak_equipped).action == "upgrade"

    strong_equipped = circlet(level=20, substats={"critRate_": 19, "hp_": 10, "eleMas": 40, "atk_": 5})
    mid = advise(circlet(), HU_TAO, strong_equipped)
    assert mid.action in ("step", "skip")
    assert mid.plan.beat_chance < 0.5

    assert advise(circlet(level=20), HU_TAO, None).action == "done"


def test_step_stops_at_next_roll():
    # against a decent equipped piece the gamble is worth starting but not worth finishing on every path
    a = advise(circlet(level=5), HU_TAO, equipped_scoring(45))
    assert a.action == "step"
    assert a.stop == 8
    assert 0 < a.plan.reach_max < 1


def test_next_roll_breakdown():
    # two wanted lines and two unwanted: hits on the unwanted ones make continuing less attractive
    art = circlet(substats={"critRate_": 3.5, "eleMas": 21, "def": 19, "hp": 299})
    plan = UpgradeChain(art, HU_TAO).plan(45.0)
    rolls = {s: (p, keep) for s, p, keep in plan.next_rolls}
    assert set(rolls) == {"critRate_", "eleMas", "def", "hp"}
    assert sum(p for p, _ in rolls.values()) == pytest.approx(1)
    assert rolls["critRate_"][1] >= rolls["def"][1]
    assert sum(p * keep for p, keep in rolls.values()) == pytest.approx(plan.keep_after_next)


def test_upgrade_goes_to_max():
    a = advise(circlet(), HU_TAO, None)
    assert a.action == "upgrade"
    assert a.stop == 20
    assert a.plan.reach_max == pytest.approx(1)


def test_cheaper_exp_means_more_gambling():
    art, bar = circlet(), 65.0
    plans = [UpgradeChain(art, HU_TAO).plan(bar, rate) for rate in (2_500, 10_000, 40_000)]
    assert [p.go for p in plans] == [False, False, True]
    assert plans[0].reach_max <= plans[1].reach_max <= plans[2].reach_max


def test_optimal_policy_beats_fixed_ones():
    art, bar, rate = circlet(), 55.0, EXP_PER_POINT
    plan = UpgradeChain(art, HU_TAO).plan(bar, rate)
    always = rate * plan.gain - (1 - FODDER_REFUND) * sum(LEVEL_EXP[5][:20])
    assert plan.value >= max(always, 0)
    # and its value is what following it actually earns
    go, value = UpgradeChain(art, HU_TAO).policy(bar, rate)
    assert value == pytest.approx(plan.value)
    outcomes = simulate_policy(art, bar, go, n=20_000, seed=3)
    net = rate * np.maximum(outcomes["score"] - bar, 0) * outcomes["maxed"] - (1 - FODDER_REFUND) * outcomes["exp"]
    assert net.mean() == pytest.approx(plan.value, rel=0.05)


def test_markov_expected_value_is_exact():
    for art in (circlet(), circlet(substats={"critRate_": 3.1, "eleMas": 21, "def": 19}),
                circlet(substats={"critRate_": 3.1, "eleMas": 21, "def": 19}, unactivated={"hp_": 4.7}),
                circlet(level=12), circlet(rarity=4, level=4)):
        dist = UpgradeChain(art, HU_TAO).final()
        assert sum(dist.values()) == pytest.approx(1)
        assert sum(s * p for s, p in dist.items()) == pytest.approx(potential(art, HU_TAO), abs=1e-4)


def test_markov_odds_match_simulation():
    art = circlet(substats={"critRate_": 3.1, "eleMas": 21, "def": 19})
    bar = 50.0
    outcomes = simulate_upgrades(art, HU_TAO, n=20_000, seed=2)
    assert UpgradeChain(art, HU_TAO).plan(bar).beat_chance == pytest.approx((outcomes > bar).mean(), abs=0.015)


def test_recheck_policy():
    art = circlet()
    plan = UpgradeChain(art, HU_TAO).plan(55.0)
    full_cost = sum(LEVEL_EXP[5][:20])
    assert plan.success <= plan.beat_chance
    assert 0 < plan.exp_expected <= full_cost
    assert plan.exp_next == sum(LEVEL_EXP[5][:4])

    hopeless = UpgradeChain(art, HU_TAO).plan(99.0)
    assert not hopeless.go
    assert hopeless.success == 0
    assert hopeless.exp_expected == 0
    assert hopeless.value == 0


def test_maxed_piece_plan():
    plan = UpgradeChain(circlet(level=20), HU_TAO).plan(0)
    assert plan.exp_next == 0
    assert plan.beat_chance == plan.success
