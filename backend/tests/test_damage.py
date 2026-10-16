import pytest

from core.damage import (
    apply, artifact_stats, build_quality, formula, ideal_stats, reference_stats, relative_gain, roll_weights, swap_gain,
    talent_keys,
)
from core.scoring import Artifact, Build
from core.talents import Scaling, parse

HU_TAO_TALENTS = {
    "normal": {"labels": ["1-Hit DMG|{param1:F1P}", "Charged Attack Stamina Cost|{param2:F1}"],
               "values": {"param1": 0.84, "param2": 25}},
    "skill": {"labels": ["Activation Cost|{param1:P} Current HP", "ATK Increase|{param2:F2P} Max HP",
                         "Blood Blossom DMG|{param3:P}", "Duration|{param4:F1}s"],
              "values": {"param1": 0.3, "param2": 0.0626, "param3": 1.152, "param4": 9}},
    "burst": {"labels": ["Skill DMG|{param1:P}", "Skill HP Regeneration|{param2:F2P} Max HP"],
              "values": {"param1": 4.94, "param2": 0.102}},
}
STATS = {
    "base_hp": 15552, "base_atk": 715, "base_def": 876, "hp": 34000, "atk": 1200, "def": 1000,
    "critRate_": 70.0, "critDMG_": 200.0, "eleMas": 100.0, "enerRech_": 110.0, "pyro_dmg_": 61.6,
}
BUILD = Build(weights={"critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5}, main_stats={"goblet": ["pyro_dmg_"]})


def hu_tao(priority=("Normal Attack", "Skill", "Burst")):
    return formula(BUILD, "Pyro", parse(HU_TAO_TALENTS), list(priority))


@pytest.mark.parametrize("template, values, expected", [
    ("{param1:F1P}", {"param1": 0.5}, [("atk", 0.5)]),
    ("{param1:F1P} Max HP", {"param1": 0.1}, [("hp", 0.1)]),
    ("{param1:F1P} ATK+{param2:F1P} Elemental Mastery", {"param1": 1, "param2": 2}, [("atk", 1), ("eleMas", 2)]),
    ("{param1:F1P}×3", {"param1": 0.2}, [("atk", 0.6)]),
    ("{param1:P}/{param2:P}", {"param1": 1, "param2": 3}, [("atk", 0.5), ("atk", 1.5)]),
    ("{param1:F1}s", {"param1": 9}, []),
])
def test_label_terms(template, values, expected):
    talents = {"skill": {"labels": [f"Skill DMG|{template}"], "values": values}}
    got = sorted((s.stat, s.coef) for s in parse(talents))
    want = {}
    for stat, coef in expected:
        want[stat] = want.get(stat, 0) + coef
    assert got == sorted((k, round(v, 6)) for k, v in want.items())


def test_parse_hu_tao():
    scalings = set(parse(HU_TAO_TALENTS))
    assert Scaling("skill", "atk", "hp", 0.0626) in scalings
    assert Scaling("skill", "damage", "atk", 1.152) in scalings
    assert Scaling("burst", "damage", "atk", 4.94) in scalings
    # healing, costs and durations are not hits
    assert not any(s.stat == "hp" and s.kind == "damage" for s in scalings)


def test_named_hit_without_dmg_and_generic_chain_skipped():
    neuvillette = {"normal": {"labels": ["1-Hit DMG|{param1:F1P}", "Charged Attack: Equitable Judgment|{param2:F2P} Max HP",
                                         "HP Loss|{param3:F1P} Max HP/{param4:F1}s"],
                              "values": {"param1": 0.9, "param2": 0.14, "param3": 0.08, "param4": 0.5}}}
    assert parse(neuvillette) == [Scaling("normal", "damage", "hp", 0.14)]


def test_talent_keys():
    assert talent_keys(["Normal Attack", "Skill", "Burst"]) == ["normal", "skill", "burst"]
    assert talent_keys(["NA", "some note", "Skill"]) == ["normal", "skill"]


def test_conversion_makes_hp_worth_more_than_atk():
    w = roll_weights(hu_tao(), STATS)
    assert w["hp_"] > w["atk_"] > 0
    assert max(w.values()) == 1


def test_crit_balance_moves_the_weights():
    low_rate = roll_weights(hu_tao(), STATS | {"critRate_": 30.0, "critDMG_": 250.0})
    low_dmg = roll_weights(hu_tao(), STATS | {"critRate_": 90.0, "critDMG_": 100.0})
    assert low_rate["critRate_"] > low_rate["critDMG_"]
    assert low_dmg["critDMG_"] > low_dmg["critRate_"]


def test_crit_rate_is_capped():
    assert roll_weights(hu_tao(), STATS | {"critRate_": 100.0}).get("critRate_") is None


def test_relative_gain_and_swap():
    f = hu_tao()
    assert relative_gain(f, STATS, STATS) == pytest.approx(0)
    old = Artifact("CrimsonWitchOfFlames", "circlet", "critDMG_", {"def": 60, "atk": 40}, level=20)
    new = Artifact("CrimsonWitchOfFlames", "circlet", "critDMG_", {"critRate_": 14, "hp_": 10}, level=20)
    assert swap_gain(f, STATS, old, new) > 0.05
    assert swap_gain(f, STATS, new, new) == pytest.approx(0)


def test_emphasis_follows_talent_priority():
    f = hu_tao(("Burst", "Skill", "Normal Attack"))
    assert f.emphasis["burst"] > f.emphasis["skill"] > f.emphasis["normal"]


def test_fallback_without_talent_data():
    f = formula(BUILD, "Pyro", [], [])
    assert f.hits == {"all": {"hp": 1.0}}


def test_reference_stats_apply_ascension():
    stats = reference_stats({"hp": 15552, "atk": 106, "def": 876}, ("critDMG_", 88.4))
    assert stats["critDMG_"] == pytest.approx(120 + 88.4)
    assert stats["hp"] > 15552


def test_build_quality_bounds():
    f = hu_tao()
    build = Build(weights=BUILD.weights, main_stats={"sands": ["hp_"], "goblet": ["pyro_dmg_"], "circlet": ["critRate_"]})
    assert build_quality(f, STATS, [], build) == 0
    # five strong real pieces still fall short of the ideal set built from the same starting stats
    pieces = [
        Artifact("CrimsonWitchOfFlames", "flower", "hp", {"critRate_": 10, "critDMG_": 20, "hp_": 10, "eleMas": 40}, level=20),
        Artifact("CrimsonWitchOfFlames", "plume", "atk", {"critRate_": 10, "critDMG_": 20, "hp_": 10, "eleMas": 40}, level=20),
        Artifact("CrimsonWitchOfFlames", "sands", "hp_", {"critRate_": 10, "critDMG_": 20, "eleMas": 40, "atk_": 5}, level=20),
        Artifact("CrimsonWitchOfFlames", "goblet", "pyro_dmg_", {"critRate_": 10, "critDMG_": 20, "hp_": 10, "eleMas": 40}, level=20),
        Artifact("CrimsonWitchOfFlames", "circlet", "critRate_", {"critDMG_": 30, "hp_": 10, "eleMas": 40, "atk_": 5}, level=20),
    ]
    worn = STATS
    for a in pieces:
        worn = apply(worn, artifact_stats(a))
    assert 0.5 < build_quality(f, worn, pieces, build) <= 1
    assert relative_gain(f, STATS, ideal_stats(f, STATS, build)) >= relative_gain(f, STATS, worn)


def test_build_quality_rewards_a_better_piece():
    f, build = hu_tao(), Build(weights=BUILD.weights, main_stats={"circlet": ["critRate_", "critDMG_"]})
    junk = Artifact("CrimsonWitchOfFlames", "circlet", "critDMG_", {"def": 60, "atk": 40}, level=20)
    good = Artifact("CrimsonWitchOfFlames", "circlet", "critDMG_", {"critRate_": 14, "hp_": 10}, level=20)
    with_junk = apply(STATS, artifact_stats(junk))
    with_good = apply(STATS, artifact_stats(good))
    assert build_quality(f, with_good, [good], build) > build_quality(f, with_junk, [junk], build) > 0
