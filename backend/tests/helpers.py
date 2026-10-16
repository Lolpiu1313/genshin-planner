from dataclasses import replace

import numpy as np

from core.constants import MAX_LEVEL, SUBSTAT_PICK_WEIGHTS, SUBSTAT_ROLLS, UPGRADE_STEP
from core.scoring import Artifact, Build, score


def simulate_upgrades(art: Artifact, build: Build, n: int, seed: int) -> np.ndarray:
    """Final scores of `n` levellings played out roll by roll, to check the exact calculations against."""
    rng = np.random.default_rng(seed)
    max_level = MAX_LEVEL[art.rarity]
    out = np.empty(n)
    for k in range(n):
        subs = dict(art.substats)
        upgrades = max_level // UPGRADE_STEP - art.level // UPGRADE_STEP
        if art.unactivated and upgrades:
            subs |= art.unactivated
            upgrades -= 1
        for _ in range(upgrades):
            if len(subs) < 4:
                pool = [s for s in SUBSTAT_PICK_WEIGHTS if s not in subs and s != art.main_stat]
                p = np.array([SUBSTAT_PICK_WEIGHTS[s] for s in pool], dtype=float)
                stat = pool[rng.choice(len(pool), p=p / p.sum())]
                subs[stat] = 0.0
            else:
                stat = list(subs)[rng.integers(4)]
            subs[stat] += rng.choice(SUBSTAT_ROLLS[art.rarity][stat])
        out[k] = score(replace(art, level=max_level, substats=subs, unactivated={}), build)
    return out


# trimmed Enka.Network /api/uid response: one character with one artifact and a weapon
ENKA = {
    "playerInfo": {"nickname": "Tester"},
    "avatarInfoList": [{
        "avatarId": 10000046,
        "propMap": {"4001": {"type": 4001, "ival": "90", "val": "90"}},
        "fightPropMap": {"1": 15552.3, "4": 715.0, "7": 876.0, "2000": 34000.0, "2001": 1200.0, "2002": 1000.0,
                         "20": 0.7, "22": 2.0, "23": 1.1, "28": 100.0, "40": 0.616},
        "equipList": [
            {"itemId": 1, "reliquary": {"level": 21, "mainPropId": 10004, "appendPropIdList": [501204, 501204, 501224, 501051]},
             "flat": {"setId": 15006, "rankLevel": 5, "equipType": "EQUIP_SHOES",
                      "reliquaryMainstat": {"mainPropId": "FIGHT_PROP_HP_PERCENT", "statValue": 46.6},
                      "reliquarySubstats": []}},
            {"itemId": 2, "weapon": {"level": 90}, "flat": {}},
        ],
    }],
}
