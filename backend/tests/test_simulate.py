import numpy as np
import pytest

from core.constants import MAIN_STAT_ODDS
from core.scoring import Build
from core.simulate import _Domain, build_score, estimate, percentile, scores_after

HU_TAO = Build(
    weights={"critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5, "atk_": 0.25, "hp": 0.175, "atk": 0.0875},
    sets=["CrimsonWitchOfFlames", "ShimenawasReminiscence"],
    main_stats={"sands": ["hp_", "eleMas"], "goblet": ["pyro_dmg_"], "circlet": ["critRate_", "critDMG_"]},
)
SETS = ("CrimsonWitchOfFlames", "Lavawalker")


def test_drops_follow_main_stat_odds():
    drops = _Domain(HU_TAO, SETS).drops(np.random.default_rng(0), 200_000)
    sands = MAIN_STAT_ODDS["sands"]
    usable = {
        "flower": 1, "plume": 1,
        "sands": (sands["hp_"] + sands["eleMas"]) / sum(sands.values()),
        "goblet": MAIN_STAT_ODDS["goblet"]["pyro_dmg_"] / sum(MAIN_STAT_ODDS["goblet"].values()),
        "circlet": 0.2,
    }
    assert (drops.max(1) > 0).mean() == pytest.approx(sum(usable.values()) / 5, abs=0.005)
    assert drops.max() <= 100
    assert ((drops > 0).sum(1) <= 1).all()
    assert drops.shape[1] == 10


def test_seed_is_reproducible():
    a = estimate(HU_TAO, SETS, 40, n=500, seed=3).runs
    b = estimate(HU_TAO, SETS, 40, n=500, seed=3).runs
    assert np.array_equal(a, b)


def test_higher_target_needs_more_resin():
    low = estimate(HU_TAO, SETS, 35, n=2000, seed=1)
    high = estimate(HU_TAO, SETS, 50, n=2000, seed=1)
    assert low.resin(0.5) < high.resin(0.5)
    assert low.resin(0.25) <= low.resin(0.5) <= low.resin(0.75) <= low.resin(0.9)


def test_starting_inventory_shortens_estimate():
    empty = estimate(HU_TAO, SETS, 45, n=2000, seed=1)
    halfway = estimate(HU_TAO, SETS, 45, start=np.r_[np.full(5, 40.0), np.zeros(5)], n=2000, seed=1)
    assert halfway.resin(0.5) < empty.resin(0.5)


def test_already_at_target():
    assert estimate(HU_TAO, SETS, 30, start=np.r_[np.full(5, 60.0), np.zeros(5)], n=100, seed=1).resin(0.9) == 0


def test_scores_grow_with_runs():
    early = np.median(scores_after(HU_TAO, SETS, 30, n=2000, seed=1))
    late = np.median(scores_after(HU_TAO, SETS, 300, n=2000, seed=1))
    assert 0 < early < late < 100


def test_build_score_allows_one_off_set_piece():
    on = np.array([50, 50, 50, 50, 0.0])
    off = np.array([60, 60, 0, 0, 40.0])
    # only the biggest off-set upgrade is used: the empty circlet gets the 40
    assert build_score(np.r_[on, off]) == pytest.approx((200 + 40) / 5)
    assert build_score(np.r_[np.zeros(5), np.full(5, 50.0)]) == pytest.approx(10)


def test_off_set_domain_alone_cannot_complete_a_build():
    off_only = estimate(HU_TAO, ("GladiatorsFinale", "WanderersTroupe"), 30, n=500, max_runs=500, seed=1)
    assert off_only.reached == 0


def test_percentile():
    sims = np.arange(100.0)
    assert percentile(49.5, sims) == 50
    assert percentile(-1, sims) == 0
