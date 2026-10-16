import numpy as np
import pytest

from core.planner import QueueEntry, candidate_domains, recommend, run_gain
from core.scoring import Build
from core.simulate import drop_pool

HU_TAO = Build(
    weights={"critRate_": 1, "critDMG_": 1, "eleMas": 0.75, "hp_": 0.5, "atk_": 0.25},
    sets=["CrimsonWitchOfFlames", "ShimenawasReminiscence"],
    main_stats={"sands": ["hp_", "eleMas"], "goblet": ["pyro_dmg_"], "circlet": ["critRate_", "critDMG_"]},
)
RAIDEN = Build(
    weights={"enerRech_": 1, "critRate_": 1, "critDMG_": 1, "atk_": 0.5},
    sets=["EmblemOfSeveredFate"],
    main_stats={"sands": ["enerRech_", "atk_"], "goblet": ["electro_dmg_", "atk_"], "circlet": ["critRate_", "critDMG_"]},
)
DOMAINS = {
    "Zhou": ("CrimsonWitchOfFlames", "Lavawalker"),
    "Momiji": ("EmblemOfSeveredFate", "ShimenawasReminiscence"),
    "Guyun": ("ArchaicPetra", "RetracingBolide"),
}
EMPTY = [0.0] * 10
DONE = [70.0] * 5 + [0.0] * 5


def test_run_gain():
    pool = drop_pool(HU_TAO, DOMAINS["Zhou"], 5000, seed=1)
    empty = run_gain(pool, np.array(EMPTY), 50)
    halfway = run_gain(pool, np.array([30.0] * 5 + [0.0] * 5), 50)
    assert empty > halfway > 0
    assert run_gain(pool, np.array(DONE), 50) == 0


def test_gain_is_capped_at_target():
    pool = drop_pool(HU_TAO, DOMAINS["Zhou"], 5000, seed=1)
    assert run_gain(pool, np.array([45.0] * 5 + [0.0] * 5), 45.5) <= 0.5 * 1.07


def test_candidates_drop_a_wanted_set():
    assert set(candidate_domains([QueueEntry("HuTao", HU_TAO, EMPTY, 50)], DOMAINS)) == {"Zhou", "Momiji"}


def test_recommends_the_domain_of_the_unfinished_character():
    queue = [QueueEntry("HuTao", HU_TAO, DONE, 50, 1), QueueEntry("Raiden", RAIDEN, EMPTY, 50, 2)]
    rec = recommend(queue, DOMAINS, seed=1)
    assert rec.best.domain == "Momiji"
    assert rec.focus == "Raiden"
    assert rec.best.gains["HuTao"] == 0


def test_priority_breaks_the_tie():
    first = recommend([QueueEntry("HuTao", HU_TAO, EMPTY, 50, 1), QueueEntry("Raiden", RAIDEN, EMPTY, 50, 5)],
                      DOMAINS, seed=1)
    flipped = recommend([QueueEntry("HuTao", HU_TAO, EMPTY, 50, 5), QueueEntry("Raiden", RAIDEN, EMPTY, 50, 1)],
                        DOMAINS, seed=1)
    assert first.focus == "HuTao"
    assert flipped.focus == "Raiden"


def test_condensed_when_one_domain_clearly_wins():
    rec = recommend([QueueEntry("Raiden", RAIDEN, EMPTY, 60)], DOMAINS, seed=1)
    assert rec.condensed
    assert rec.stay_share == pytest.approx(1)


def test_everyone_done():
    rec = recommend([QueueEntry("HuTao", HU_TAO, DONE, 50)], DOMAINS, seed=1)
    assert rec.best.value == 0
    assert not rec.condensed


def test_empty_queue():
    assert recommend([], DOMAINS) is None
