import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SLOTS = ("flower", "plume", "sands", "goblet", "circlet")
FIXED_MAIN = {"flower": "hp", "plume": "atk"}

SUBSTATS = ("hp", "hp_", "atk", "atk_", "def", "def_", "eleMas", "enerRech_", "critRate_", "critDMG_")

ELEMENT_DMG = tuple(f"{e}_dmg_" for e in ("pyro", "hydro", "electro", "cryo", "anemo", "geo", "dendro", "physical"))
MAIN_STATS = {
    "flower": ("hp",),
    "plume": ("atk",),
    "sands": ("hp_", "atk_", "def_", "eleMas", "enerRech_"),
    "goblet": ("hp_", "atk_", "def_", "eleMas") + ELEMENT_DMG,
    "circlet": ("hp_", "atk_", "def_", "eleMas", "critRate_", "critDMG_", "heal_"),
}

# odds of a stat being picked when a new substat is added (from Genshin Optimizer)
SUBSTAT_PICK_WEIGHTS = {
    "hp": 6, "atk": 6, "def": 6,
    "hp_": 4, "atk_": 4, "def_": 4, "eleMas": 4, "enerRech_": 4,
    "critRate_": 3, "critDMG_": 3,
}

UPGRADE_STEP = 4
NUM_UPGRADES = {3: 3, 4: 4, 5: 5}
MAX_LEVEL = {r: n * UPGRADE_STEP for r, n in NUM_UPGRADES.items()}
INITIAL_SUBSTATS = 4

PROP_KEYS = {
    "FIGHT_PROP_HP": "hp",
    "FIGHT_PROP_HP_PERCENT": "hp_",
    "FIGHT_PROP_ATTACK": "atk",
    "FIGHT_PROP_ATTACK_PERCENT": "atk_",
    "FIGHT_PROP_DEFENSE": "def",
    "FIGHT_PROP_DEFENSE_PERCENT": "def_",
    "FIGHT_PROP_ELEMENT_MASTERY": "eleMas",
    "FIGHT_PROP_CHARGE_EFFICIENCY": "enerRech_",
    "FIGHT_PROP_CRITICAL": "critRate_",
    "FIGHT_PROP_CRITICAL_HURT": "critDMG_",
    "FIGHT_PROP_HEAL_ADD": "heal_",
    "FIGHT_PROP_PHYSICAL_ADD_HURT": "physical_dmg_",
    "FIGHT_PROP_FIRE_ADD_HURT": "pyro_dmg_",
    "FIGHT_PROP_ELEC_ADD_HURT": "electro_dmg_",
    "FIGHT_PROP_WATER_ADD_HURT": "hydro_dmg_",
    "FIGHT_PROP_GRASS_ADD_HURT": "dendro_dmg_",
    "FIGHT_PROP_WIND_ADD_HURT": "anemo_dmg_",
    "FIGHT_PROP_ROCK_ADD_HURT": "geo_dmg_",
    "FIGHT_PROP_ICE_ADD_HURT": "cryo_dmg_",
}


def game_value(key: str, value: float) -> float:
    """Convert a game data value to GOOD units: percent stats are 3.9 in GOOD, 0.039 in the game."""
    return round(value * 100 if key.endswith("_") else value, 4)


def _load_affixes() -> dict[int, tuple[int, str, float]]:
    data = json.loads((DATA_DIR / "ReliquaryAffixExcelConfigData.json").read_text())
    return {
        row["id"]: (row["depotId"] // 100, PROP_KEYS[row["propType"]], game_value(PROP_KEYS[row["propType"]], row["propValue"]))
        for row in data if row["propType"] in PROP_KEYS
    }


def _load_main_values() -> dict[int, dict[str, list[float]]]:
    data = json.loads((DATA_DIR / "ReliquaryLevelExcelConfigData.json").read_text())
    values: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in sorted((r for r in data if "rank" in r), key=lambda r: r["level"]):
        for p in row["addProps"]:
            if p["propType"] in PROP_KEYS:
                key = PROP_KEYS[p["propType"]]
                values[row["rank"]][key].append(game_value(key, p["value"]))
    return values


# substat roll ids as used in Enka's appendPropIdList: id -> (rarity, stat, value)
AFFIXES = _load_affixes()

# possible values of a single substat roll, per rarity, low to high
SUBSTAT_ROLLS: dict[int, dict[str, list[float]]] = defaultdict(dict)
for _rarity, _key, _value in AFFIXES.values():
    if _rarity in (3, 4, 5):
        SUBSTAT_ROLLS[_rarity].setdefault(_key, []).append(_value)
for _stats in SUBSTAT_ROLLS.values():
    for _rolls in _stats.values():
        _rolls.sort()
MAX_ROLL = {k: v[-1] for k, v in SUBSTAT_ROLLS[5].items()}

# main stat value per rarity and artifact level (index 0 is +0)
MAIN_STAT_VALUES = _load_main_values()


def _load_exp() -> dict[int, list[int]]:
    data = json.loads((DATA_DIR / "ReliquaryLevelExcelConfigData.json").read_text())
    exp: dict[int, list[int]] = defaultdict(list)
    for row in sorted((r for r in data if "rank" in r), key=lambda r: r["level"]):
        exp[row["rank"]].append(row.get("exp", 0))
    return exp


# EXP needed to go from each artifact level to the next, per rarity (index 0 is +0 -> +1)
LEVEL_EXP = _load_exp()

# main stat odds per slot (Genshin Optimizer / wiki Artifact/Distribution)
MAIN_STAT_ODDS = {
    "flower": {"hp": 1},
    "plume": {"atk": 1},
    "sands": {"hp_": 80, "atk_": 80, "def_": 80, "eleMas": 30, "enerRech_": 30},
    "goblet": {"hp_": 77, "atk_": 77, "def_": 76, "eleMas": 10} | {k: 20 for k in ELEMENT_DMG},
    "circlet": {"hp_": 22, "atk_": 22, "def_": 22, "eleMas": 4, "critRate_": 10, "critDMG_": 10, "heal_": 10},
}

# a substat roll is 70/80/90/100% of the max value, each equally likely
ROLL_TIERS = (0.7, 0.8, 0.9, 1.0)

RESIN_PER_RUN = 20
CONDENSED_RESIN = 40
RESIN_REGEN_MINUTES = 8
RESIN_PER_DAY = 24 * 60 // RESIN_REGEN_MINUTES

# tier IV domain at AR 45+: one 5-star per run plus a chance of a second (mean 1.065)
EXTRA_DROP_CHANCE = 0.065
FOUR_SUBSTAT_CHANCE = 0.2

# a levelled artifact fed to another returns 80% of the EXP spent on it
FODDER_REFUND = 0.8

# scoring heuristics, tuned by hand rather than taken from the game
PRIORITY_STEP = 0.25        # weight drop per tier in a build's substat priority list
PRIORITY_MIN = 0.25
FLAT_FACTOR = 0.35          # a max flat roll is worth about a third of a % roll at typical base stats
OFF_SET_FACTOR = 0.7        # off-set pieces still work as the "+1" in 4+1
SET_RANK_STEP = 0.05        # each step down a build's recommended set list is worth a bit less
WRONG_MAIN_FACTOR = 0.0     # a sands/goblet/circlet with the wrong main stat is unusable for the build
CONDENSED_CONFIDENCE = 0.8  # share of next-run outcomes after which the same domain must still be best

# upgrade advice: what one point of piece score is worth in EXP, the trade-off the stopping rule optimises
EXP_PER_POINT = 10_000

# damage estimate
EM_WEIGHT = 0.5             # builds weighting EM at least this much are treated as reaction builds
# amplifying reaction (vaporize/melt) bonus from EM: 2.78 * EM / (EM + 1400)
AMP_EM_FACTOR = 2.78
AMP_EM_OFFSET = 1400

# a typically built level 90 character, used to derive stat weights for characters
# without imported in-game stats: a 4-star weapon's base ATK, flower and plume main
# stats, and the rest of the artifacts as totals
REFERENCE_WEAPON_ATK = 565
REFERENCE_PIECES = {"hp": 4780, "atk": 311}
REFERENCE_STATS = {
    "hp_": 40.0, "atk_": 40.0, "def_": 15.0,
    "critRate_": 55.0, "critDMG_": 120.0, "eleMas": 60.0, "enerRech_": 130.0,
    "pyro_dmg_": 46.6, "hydro_dmg_": 46.6, "electro_dmg_": 46.6, "cryo_dmg_": 46.6,
    "anemo_dmg_": 46.6, "geo_dmg_": 46.6, "dendro_dmg_": 46.6, "physical_dmg_": 46.6,
}
