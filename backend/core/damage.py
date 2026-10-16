"""Relative damage of a character, from how its talents scale.

Every talent's hit is a sum of coefficient x stat (ATK, Max HP, DEF or EM, as read from the
game's talent labels), multiplied by average crit, the DMG bonus and, for vaporize/melt
builds, the EM reaction bonus. Talent multipliers' absolute size, enemy defence and
resistance cancel out when comparing two states of the same character, so only ratios
between results mean anything.
"""

import re
from dataclasses import dataclass, field

from core.constants import (
    AMP_EM_FACTOR, AMP_EM_OFFSET, EM_WEIGHT, FIXED_MAIN, INITIAL_SUBSTATS, MAIN_STAT_VALUES, MAIN_STATS, MAX_LEVEL,
    MAX_ROLL, NUM_UPGRADES, REFERENCE_PIECES, REFERENCE_STATS, REFERENCE_WEAPON_ATK, SLOTS, SUBSTATS,
)
from core.scoring import Artifact, Build
from core.talents import Scaling

SCALING = ("atk", "hp", "def")
DAMAGE_STATS = ("atk", "atk_", "hp", "hp_", "def", "def_", "eleMas", "critRate_", "critDMG_")
TALENT_NAMES = {"normal attack": "normal", "na": "normal", "skill": "skill", "burst": "burst"}


@dataclass
class Formula:
    hits: dict[str, dict[str, float]]  # talent -> stat -> summed coefficient
    dmg_key: str
    reaction: bool
    conversions: dict[str, float] = field(default_factory=dict)  # stat -> share of it added to ATK
    emphasis: dict[str, float] = field(default_factory=dict)  # talent -> how much it counts


def damage_key(build: Build, element: str) -> str:
    """The DMG bonus the build cares about: physical if its goblet asks for it, else the element's."""
    goblet = build.main_stats.get("goblet", [])
    if "physical_dmg_" in goblet and f"{element.lower()}_dmg_" not in goblet:
        return "physical_dmg_"
    return f"{element.lower()}_dmg_"


def talent_keys(priority: list[str]) -> list[str]:
    """Talent priority labels from genshin-builds.com as talent keys, in order."""
    keys = [TALENT_NAMES.get(p.strip().lower()) for p in priority]
    return list(dict.fromkeys(k for k in keys if k))


def formula(build: Build, element: str, scalings: list[Scaling], priority: list[str]) -> Formula:
    """Damage formula of a build; falls back to its main scaling stat when no talent data exists."""
    hits: dict[str, dict[str, float]] = {}
    conversions: dict[str, float] = {}
    for s in scalings:
        if s.kind == "damage":
            hits.setdefault(s.talent, {})[s.stat] = s.coef
        else:
            conversions[s.stat] = conversions.get(s.stat, 0) + s.coef
    if not hits:
        hits = {"all": {max(SCALING, key=lambda s: build.weights.get(f"{s}_", 0)): 1.0}}
    # talents levelled first do most of the damage; each step down counts half as much
    order = [t for t in talent_keys(priority) if t in hits] + [t for t in hits if t not in talent_keys(priority)]
    emphasis = {t: 1 / 2**i for i, t in enumerate(order)}
    return Formula(hits, damage_key(build, element), build.weights.get("eleMas", 0) >= EM_WEIGHT, conversions, emphasis)


def talent_damage(stats: dict[str, float], f: Formula) -> dict[str, float]:
    atk = stats["atk"] + sum(share * stats.get(s, 0) for s, share in f.conversions.items())
    crit = 1 + min(stats.get("critRate_", 0), 100) / 100 * stats.get("critDMG_", 0) / 100
    bonus = 1 + stats.get(f.dmg_key, 0) / 100
    em = stats.get("eleMas", 0)
    amp = 1 + AMP_EM_FACTOR * em / (em + AMP_EM_OFFSET) if f.reaction else 1
    return {
        t: sum(coef * (atk if stat == "atk" else stats.get(stat, 0)) for stat, coef in hit.items()) * crit * bonus * amp
        for t, hit in f.hits.items()
    }


def relative_gain(f: Formula, before: dict[str, float], after: dict[str, float]) -> float:
    """Damage change from `before` to `after` stats, e.g. 0.05 for +5%, weighting talents by emphasis."""
    b, a = talent_damage(before, f), talent_damage(after, f)
    used = {t: w for t, w in f.emphasis.items() if b.get(t, 0) > 0}
    if not used:
        return 0.0
    return sum(w * a[t] / b[t] for t, w in used.items()) / sum(used.values()) - 1


def apply(stats: dict[str, float], delta: dict[str, float], sign: int = 1) -> dict[str, float]:
    """Stats after adding (or removing) artifact stats; percent ATK/HP/DEF apply to the base value."""
    out = dict(stats)
    for key, value in delta.items():
        if key in ("hp_", "atk_", "def_"):
            flat = key[:-1]
            out[flat] += sign * stats[f"base_{flat}"] * value / 100
        else:
            out[key] = out.get(key, 0) + sign * value
    return out


def artifact_stats(a: Artifact) -> dict[str, float]:
    """Stats an artifact gives at its current level: main stat plus active substats."""
    stats = dict(a.substats)
    stats[a.main_stat] = stats.get(a.main_stat, 0) + MAIN_STAT_VALUES[a.rarity][a.main_stat][a.level]
    return stats


def swap_gain(f: Formula, stats: dict[str, float], old: Artifact | None, new: Artifact) -> float:
    """Damage change from replacing `old` (currently equipped) with `new`."""
    after = stats if old is None else apply(stats, artifact_stats(old), -1)
    return relative_gain(f, stats, apply(after, artifact_stats(new)))


def roll_weights(f: Formula, stats: dict[str, float]) -> dict[str, float]:
    """What one max roll of each damage stat is worth at these stats, the best one being 1."""
    gains = {s: relative_gain(f, stats, apply(stats, {s: MAX_ROLL[s]})) for s in DAMAGE_STATS}
    top = max(gains.values())
    if top <= 0:
        return {}
    return {s: round(g / top, 4) for s, g in gains.items() if g > 0}


def reference_stats(base: dict[str, float], ascension: tuple[str, float]) -> dict[str, float]:
    """Stats of a typically built character, for those without imported in-game stats."""
    pct = REFERENCE_STATS
    stats = {
        "base_hp": base["hp"],
        "base_atk": base["atk"] + REFERENCE_WEAPON_ATK,
        "base_def": base["def"],
        "hp": base["hp"] * (1 + pct["hp_"] / 100) + REFERENCE_PIECES["hp"],
        "atk": (base["atk"] + REFERENCE_WEAPON_ATK) * (1 + pct["atk_"] / 100) + REFERENCE_PIECES["atk"],
        "def": base["def"] * (1 + pct["def_"] / 100),
        **{k: v for k, v in pct.items() if not re.fullmatch(r"(hp|atk|def)_", k)},
    }
    stat, value = ascension
    return apply(stats, {stat: value})


def _roll_gain(f: Formula, stats: dict[str, float], stat: str, value: float) -> float:
    return relative_gain(f, stats, apply(stats, {stat: value}))


def ideal_stats(f: Formula, naked: dict[str, float], build: Build) -> dict[str, float]:
    """Stats with five flawless +20 pieces, built greedily one main stat and one roll at a time."""
    stats = dict(naked)
    for slot in SLOTS:
        options = [FIXED_MAIN[slot]] if slot in FIXED_MAIN else build.main_stats.get(slot) or list(MAIN_STATS[slot])
        main = max(options, key=lambda m: _roll_gain(f, stats, m, MAIN_STAT_VALUES[5][m][MAX_LEVEL[5]]))
        stats = apply(stats, {main: MAIN_STAT_VALUES[5][main][MAX_LEVEL[5]]})
        candidates = [s for s in SUBSTATS if s != main]
        subs = sorted(candidates, key=lambda s: _roll_gain(f, stats, s, MAX_ROLL[s]), reverse=True)[:INITIAL_SUBSTATS]
        for s in subs:
            stats = apply(stats, {s: MAX_ROLL[s]})
        # each upgrade goes where it adds the most now, so diminishing returns are respected
        for _ in range(NUM_UPGRADES[5]):
            best = max(subs, key=lambda s: _roll_gain(f, stats, s, MAX_ROLL[s]))
            stats = apply(stats, {best: MAX_ROLL[best]})
    return stats


def build_quality(f: Formula, stats: dict[str, float], worn: list[Artifact], build: Build) -> float:
    """Damage the worn artifacts add, as a share of what flawless ones would add: 0 with none, 1 when ideal.

    Measuring the artifacts' own contribution keeps weapon and base stats out of the score, and judging
    by damage rather than by per-roll weights doesn't discount rolls the build already relies on.
    """
    naked = stats
    for a in worn:
        naked = apply(naked, artifact_stats(a), -1)
    best = relative_gain(f, naked, ideal_stats(f, naked, build))
    if best <= 0:
        return 0.0
    return max(min(relative_gain(f, naked, stats) / best, 1.0), 0.0)


def is_damage_build(name: str) -> bool:
    """Builds judged by damage; supports and transformative reaction drivers keep the site's weights."""
    return bool(re.search(r"DPS|DAMAGE|NUKE|DRIVER", name, re.I)) and not re.search(r"BLOOM|BURGEON", name, re.I)


def build_weights(site: dict[str, float], f: Formula, stats: dict[str, float]) -> dict[str, float]:
    """Damage stats weighted by the formula; the rest (Energy Recharge) as the site ranks it."""
    derived = roll_weights(f, stats)
    return {**{k: v for k, v in site.items() if k not in DAMAGE_STATS}, **derived} if derived else site
