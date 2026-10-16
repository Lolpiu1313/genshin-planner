import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from core.constants import FLAT_FACTOR
from core.importer import good_key, import_all, priority_weights, stat_keys
from db.models import ArtifactSet, Base, Character, CharBuild, Domain


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.mark.parametrize("name, key", [
    ("Hu Tao", "HuTao"),
    ("Gladiator's Finale", "GladiatorsFinale"),
    ("Ocean-Hued Clam", "OceanHuedClam"),
    ("Echoes of an Offering", "EchoesOfAnOffering"),
    ("A Day Carved From Rising Winds", "ADayCarvedFromRisingWinds"),
])
def test_good_key(name, key):
    assert good_key(name) == key


def test_priority_weights():
    w = priority_weights(["CRIT Rate", "CRIT DMG", "Elemental Mastery", "HP%", "ATK%"])
    assert w == pytest.approx({
        "critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5, "atk_": 0.25,
        "hp": 0.5 * FLAT_FACTOR, "atk": 0.25 * FLAT_FACTOR,
    })


def test_priority_weights_combined_crit():
    w = priority_weights(["Energy Recharge", "CRIT", "HP%"])
    assert (w["enerRech_"], w["critRate_"], w["critDMG_"], w["hp_"]) == (1, 0.75, 0.75, 0.5)


@pytest.mark.parametrize("label, keys", [
    ("Pyro DMG Bonus", ["pyro_dmg_"]),
    ("Physical DMG Bonus", ["physical_dmg_"]),
    ("Crit DMG", ["critDMG_"]),
    ("Healing Bonus", ["heal_"]),
])
def test_stat_keys(label, keys):
    assert stat_keys(label) == keys


def test_import(session):
    import_all(session)

    witch = session.scalar(select(ArtifactSet).where(ArtifactSet.key == "CrimsonWitchOfFlames"))
    assert witch.domain.name == "Hidden Palace of Zhou Formula"
    assert {s.key for s in witch.domain.sets} == {"CrimsonWitchOfFlames", "Lavawalker"}

    hutao = session.scalar(select(Character).where(Character.key == "HuTao"))
    assert (hutao.element, hutao.weapon_type) == ("Pyro", "Polearm")
    build = hutao.builds[0]
    assert build.sets[0].set.key == "CrimsonWitchOfFlames"
    assert "hp_" in build.sands_main
    assert {w.stat: w.weight for w in build.weights}["critRate_"] == 1


def test_import_is_idempotent(session):
    first = import_all(session)
    import_all(session)
    assert session.scalar(select(func.count()).select_from(Domain)) == first["domains"]
    assert session.scalar(select(func.count()).select_from(CharBuild)) == first["builds"]
    for domain in session.scalars(select(Domain)):
        assert len(domain.sets) == 2
