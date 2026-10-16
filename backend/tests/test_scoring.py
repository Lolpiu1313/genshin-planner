import pytest

from core.constants import MAX_ROLL, OFF_SET_FACTOR
from core.scoring import Artifact, Build, potential, rolls, score
from tests.helpers import simulate_upgrades

HU_TAO = Build(
    weights={"critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5, "atk_": 0.25},
    sets=["CrimsonWitchOfFlames", "ShimenawasReminiscence"],
    main_stats={"sands": ["hp_", "eleMas"], "goblet": ["pyro_dmg_"], "circlet": ["critRate_", "critDMG_"]},
)
SUPPORT = Build(
    weights={"enerRech_": 1, "hp_": 0.75},
    sets=["NoblesseOblige"],
    main_stats={"sands": ["enerRech_", "hp_"], "goblet": ["hp_"], "circlet": ["heal_"]},
)


def sands(**kw) -> Artifact:
    base = dict(set_key="CrimsonWitchOfFlames", slot="sands", main_stat="hp_", level=20,
                substats={"critRate_": 3.89 * 6, "critDMG_": 7.77, "eleMas": 23.31, "atk_": 5.83})
    return Artifact(**(base | kw))


def test_rolls():
    assert rolls("critRate_", 3.89) == pytest.approx(1)
    assert rolls("critDMG_", 15.54) == pytest.approx(2)


def test_perfect_piece_scores_100():
    assert score(sands(), HU_TAO) == pytest.approx(100)


def test_wrong_main_stat_scores_zero():
    assert score(sands(main_stat="atk_"), HU_TAO) == 0


def test_off_set_penalty():
    assert score(sands(set_key="GladiatorsFinale"), HU_TAO) == pytest.approx(100 * OFF_SET_FACTOR)


def test_lower_ranked_set_scores_less():
    top = score(sands(), HU_TAO)
    second = score(sands(set_key="ShimenawasReminiscence"), HU_TAO)
    assert OFF_SET_FACTOR * top < second < top


def test_flower_main_always_matches():
    flower = sands(slot="flower", main_stat="hp")
    assert score(flower, HU_TAO) > 0


def test_maxed_potential_equals_score():
    art = sands(substats={"critRate_": 7.0, "critDMG_": 14.0, "hp": 500, "def": 40})
    assert potential(art, HU_TAO) == pytest.approx(score(art, HU_TAO))


def test_upgrade_count_includes_partial_level():
    a = sands(level=0, substats={"critRate_": 3.5, "critDMG_": 7.0, "hp": 250, "def": 20})
    assert potential(sands(level=3, substats=a.substats), HU_TAO) == pytest.approx(potential(a, HU_TAO))
    assert potential(sands(level=4, substats=a.substats), HU_TAO) < potential(a, HU_TAO)


def test_unactivated_substat_is_known_first_upgrade():
    subs = {"critRate_": 3.5, "critDMG_": 7.0, "def": 20}
    hidden = sands(level=0, substats=subs, unactivated={"eleMas": 21})
    active = sands(level=4, substats=subs | {"eleMas": 21})
    assert potential(hidden, HU_TAO) == pytest.approx(potential(active, HU_TAO))
    assert score(hidden, HU_TAO) < score(active, HU_TAO)


def test_potential_matches_simulation():
    art = sands(level=0, substats={"critRate_": 3.11, "eleMas": 18.65, "def": 20.83})
    assert simulate_upgrades(art, HU_TAO, 20_000, seed=1).mean() == pytest.approx(potential(art, HU_TAO), rel=0.02)


def test_max_roll_values_come_from_game_data():
    assert MAX_ROLL["critRate_"] == 3.89
    assert MAX_ROLL["hp"] == 298.75


def test_potential_of_a_piece_without_substats():
    # every order of the four missing lines leads to the same sets, so this must stay quick and exact
    art = sands(level=0, substats={})
    assert simulate_upgrades(art, HU_TAO, 20_000, seed=3).mean() == pytest.approx(potential(art, HU_TAO), rel=0.03)
