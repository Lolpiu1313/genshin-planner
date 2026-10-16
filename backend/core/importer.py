import json
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import talents
from core.constants import DATA_DIR, FLAT_FACTOR, PRIORITY_MIN, PRIORITY_STEP
from core.damage import talent_keys
from db.models import ArtifactSet, BuildSet, Character, CharBuild, Domain, StatWeight, TalentScaling
from db.session import SessionLocal

STAT_NAMES = {
    "hp": "hp", "hp%": "hp_", "atk": "atk", "atk%": "atk_", "def": "def", "def%": "def_",
    "elemental mastery": "eleMas", "energy recharge": "enerRech_",
    "crit rate": "critRate_", "crit dmg": "critDMG_", "healing bonus": "heal_",
}
CRIT = {"critRate_", "critDMG_"}


def good_key(name: str) -> str:
    """Convert a display name to its GOOD key, e.g. "Gladiator's Finale" -> "GladiatorsFinale"."""
    words = re.split(r"[\s-]+", name)
    return "".join(re.sub(r"[^A-Za-z0-9]", "", w[:1].upper() + w[1:]) for w in words)


def stat_keys(name: str) -> list[str]:
    """Map a stat label from genshin-builds.com to GOOD keys."""
    name = name.strip().lower()
    if name == "crit":
        return sorted(CRIT)
    if name.endswith(" dmg bonus"):
        return [name.removesuffix(" dmg bonus") + "_dmg_"]
    return [STAT_NAMES[name]]


def ascension(stat: str, value: float) -> tuple[str, float]:
    """An ascension stat as a GOOD key and value; "ATK", "HP" and "DEF" there mean percentages."""
    key = {"atk": "atk_", "hp": "hp_", "def": "def_"}.get(stat.lower()) or stat_keys(stat)[0]
    return key, round(value * 100 if key.endswith("_") else value, 4)


def priority_weights(priority: list[str]) -> dict[str, float]:
    """Turn an ordered substat priority list into weights between PRIORITY_MIN and 1."""
    tiers: list[list[str]] = []
    for name in priority:
        keys = stat_keys(name)
        # sites list CRIT Rate and CRIT DMG one after another, but they are equally important
        if tiers and set(keys) <= CRIT and set(tiers[-1]) <= CRIT:
            tiers[-1] += keys
        else:
            tiers.append(keys)

    weights: dict[str, float] = {}
    for i, tier in enumerate(tiers):
        for key in tier:
            weights.setdefault(key, max(1 - PRIORITY_STEP * i, PRIORITY_MIN))
    for flat in ("hp", "atk", "def"):
        if flat not in weights and flat + "_" in weights:
            weights[flat] = weights[flat + "_"] * FLAT_FACTOR
    return weights


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text())


def _upsert(session: Session, model, key: str, **fields):
    obj = session.scalar(select(model).where(model.key == key))
    if obj is None:
        obj = model(key=key)
        session.add(obj)
    for k, v in fields.items():
        setattr(obj, k, v)
    return obj


def _by_slug(objs) -> dict:
    # genshin-builds slugs are snake_case and sometimes split words differently ("oceanhued_clam")
    return {o.key.lower(): o for o in objs}


def _clean(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", text).split())


def import_builds(session: Session, data: dict[str, list[dict]]) -> int:
    chars = _by_slug(session.scalars(select(Character)))
    sets = _by_slug(session.scalars(select(ArtifactSet)))
    count = 0
    for slug, builds in data.items():
        char = chars.get(slug.replace("_", ""))
        if char is None:
            continue
        char.builds = []
        for b in builds:
            # entries like "18atk_set" mean "any set with that 2pc bonus" and are skipped
            ranked = []
            for combo in b["sets"]:
                for s in combo:
                    obj = sets.get(s.replace("_", ""))
                    if obj and obj not in ranked:
                        ranked.append(obj)
            mains = {slot: [k for n in b["stats"].get(slot, []) for k in stat_keys(n)]
                     for slot in ("sands", "goblet", "circlet")}
            char.builds.append(CharBuild(
                name=_clean(b["name"]),
                sands_main=mains["sands"],
                goblet_main=mains["goblet"],
                circlet_main=mains["circlet"],
                talent_priority=talent_keys(b.get("talent_priority") or []),
                sets=[BuildSet(set=s, rank=i) for i, s in enumerate(ranked)],
                weights=[StatWeight(stat=k, weight=w) for k, w in priority_weights(b["stats_priority"]).items()],
            ))
            count += 1
    return count


def import_all(session: Session) -> dict[str, int]:
    """Load characters, artifact sets, domains and builds from data/ into the database."""
    chars = [c for c in _load("characters.json") if c["element"] != "None"]
    talent_data = _load("talents.json")
    for c in chars:
        stat, value = ascension(c["ascension"]["stat"], c["ascension"]["value"])
        char = _upsert(session, Character, good_key(c["name"]),
                       game_id=c["id"], name=c["name"], element=c["element"], weapon_type=c["weapon"],
                       base_hp=c["base"]["hp"], base_atk=c["base"]["atk"], base_def=c["base"]["def"],
                       ascension_stat=stat, ascension_value=value)
        char.scalings = [TalentScaling(talent=s.talent, kind=s.kind, stat=s.stat, coef=s.coef)
                         for s in talents.parse(talent_data.get(c["name"], {}))]

    sets = {}
    for a in _load("artifacts.json"):
        sets[a["name"]] = _upsert(session, ArtifactSet, good_key(a["name"]), game_id=a["id"], name=a["name"])

    # each entrance has several difficulty tiers; the 5-star rewards are the domain's two sets
    rewards = defaultdict(set)
    for d in _load("domains.json"):
        rewards[d["entrance"]].update(r["name"] for r in d["rewards"] if r["rarity"] == 5)

    for entrance, set_names in rewards.items():
        domain = _upsert(session, Domain, good_key(entrance), name=entrance)
        for name in set_names:
            sets[name].domain = domain

    session.flush()
    builds = import_builds(session, _load("builds.json"))
    session.commit()
    return {"characters": len(chars), "sets": len(sets), "domains": len(rewards), "builds": builds}


if __name__ == "__main__":
    with SessionLocal() as session:
        counts = import_all(session)
    print(", ".join(f"{n} {k}" for k, n in counts.items()))
