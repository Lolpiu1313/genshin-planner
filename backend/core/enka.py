from dataclasses import dataclass, field

from core.constants import AFFIXES, PROP_KEYS, game_value

SLOT_OF = {
    "EQUIP_BRACER": "flower",
    "EQUIP_NECKLACE": "plume",
    "EQUIP_SHOES": "sands",
    "EQUIP_RING": "goblet",
    "EQUIP_DRESS": "circlet",
}

# fightPropMap ids; hp/atk/def are the totals the character sees in game
FIGHT_PROPS = {
    "1": "base_hp", "4": "base_atk", "7": "base_def",
    "2000": "hp", "2001": "atk", "2002": "def",
    "20": "critRate_", "22": "critDMG_", "23": "enerRech_", "26": "heal_", "28": "eleMas",
    "30": "physical_dmg_", "40": "pyro_dmg_", "41": "electro_dmg_", "42": "hydro_dmg_",
    "43": "dendro_dmg_", "44": "anemo_dmg_", "45": "geo_dmg_", "46": "cryo_dmg_",
}
LEVEL_PROP = "4001"


@dataclass
class EnkaArtifact:
    set_id: int
    slot: str
    main_stat: str
    level: int
    rarity: int
    substats: dict[str, float]


@dataclass
class EnkaCharacter:
    avatar_id: int
    level: int
    stats: dict[str, float]
    artifacts: list[EnkaArtifact] = field(default_factory=list)


@dataclass
class EnkaProfile:
    nickname: str
    characters: list[EnkaCharacter]


def _substats(item: dict) -> dict[str, float]:
    # appendPropIdList has one id per roll, which gives exact values instead of the rounded display
    subs: dict[str, float] = {}
    ids = item["reliquary"].get("appendPropIdList", [])
    if ids and all(i in AFFIXES for i in ids):
        for i in ids:
            _, key, value = AFFIXES[i]
            subs[key] = round(subs.get(key, 0) + value, 4)
        return subs
    for s in item["flat"].get("reliquarySubstats", []):
        subs[PROP_KEYS[s["appendPropId"]]] = s["statValue"]
    return subs


def _artifact(item: dict) -> EnkaArtifact:
    flat = item["flat"]
    return EnkaArtifact(
        set_id=flat["setId"],
        slot=SLOT_OF[flat["equipType"]],
        main_stat=PROP_KEYS[flat["reliquaryMainstat"]["mainPropId"]],
        level=item["reliquary"]["level"] - 1,
        rarity=flat["rankLevel"],
        substats=_substats(item),
    )


def parse(data: dict) -> EnkaProfile:
    """Characters from an Enka.Network /api/uid response, with stats and equipped artifacts."""
    chars = []
    for a in data.get("avatarInfoList", []):
        stats = {name: game_value(name, a["fightPropMap"].get(pid, 0)) for pid, name in FIGHT_PROPS.items()}
        chars.append(EnkaCharacter(
            avatar_id=a["avatarId"],
            level=int(a["propMap"][LEVEL_PROP]["val"]),
            stats=stats,
            artifacts=[_artifact(e) for e in a.get("equipList", []) if "reliquary" in e],
        ))
    return EnkaProfile(nickname=data.get("playerInfo", {}).get("nickname", ""), characters=chars)
