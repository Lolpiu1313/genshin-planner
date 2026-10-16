"""What a character's damage scales on, read from the game's talent labels.

A label looks like "Tri-Karma Purification DMG|{param3:F1P} ATK+{param4:F1P} Elemental Mastery":
a name, then a template where each percentage parameter is followed by the stat it scales
on (no stat means ATK). Labels like "ATK Increase|{param2:F2P} Max HP" are conversions
that raise ATK by a share of another stat while the talent is active.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

STATS = {"": "atk", "ATK": "atk", "Max HP": "hp", "DEF": "def", "Elemental Mastery": "eleMas"}
TALENTS = ("normal", "skill", "burst")

PARAM = re.compile(r"\{(param\d+):([^}]*)\}")
TIMES = re.compile(r"[×x]\s*(\d+)")
NOT_DAMAGE = re.compile(
    r"\b(Bonus|Increase|Reduction|Decrease|RES|Heal|Healing|Regen|Regeneration|Shield|Absorption|Cost|Consumption|Restored)\b",
    re.I,
)
NOT_HIT = re.compile(r"\b(Loss|Gain|Limit|Threshold|Maximum|Duration|Interval|Stamina|Energy)\b", re.I)
CONVERSION = re.compile(r"\bATK (Increase|Bonus)\b")
EXPLICIT = re.compile(r"\}\s*(ATK|Max HP|DEF|Elemental Mastery)\b")


@dataclass(frozen=True)
class Scaling:
    talent: str  # normal, skill or burst
    kind: str    # "damage": adds coef x stat to the hit; "atk": adds coef x stat to ATK
    stat: str
    coef: float


def _terms(template: str, values: dict[str, float]) -> list[tuple[str, float]]:
    """(stat, coefficient) pairs in one value template, multi-hits counted and alternatives averaged."""
    # "X/X" lists alternatives (e.g. low/high plunge); "X/s" is a unit, not an alternative
    parts = [p for p in re.split(r"/(?=\s*\{)", template)]
    out: list[tuple[str, float]] = []
    for part in parts:
        group = 1
        if m := re.fullmatch(r"\s*\((.*)\)\s*[×x]\s*(\d+)\s*", part):
            part, group = m.group(1), int(m.group(2))
        for chunk in part.split("+"):
            m = PARAM.search(chunk)
            if not m or "P" not in m.group(2) or m.group(1) not in values:
                continue
            rest = chunk[m.end():]
            times = TIMES.search(rest)
            stat = STATS.get(TIMES.sub("", rest).strip())
            if stat is None:
                # scales on something else (current HP, Bond of Life, ...): not a stat artifacts give
                continue
            hits = int(times.group(1)) if times else 1
            out.append((stat, values[m.group(1)] * hits * group / len(parts)))
    return out


def _is_damage(name: str, template: str) -> bool:
    if NOT_DAMAGE.search(name) or NOT_HIT.search(name):
        return False
    # some hits are named without "DMG", e.g. "Charged Attack: Equitable Judgment|... Max HP"
    return "DMG" in name or EXPLICIT.search(template) is not None


def parse(talents: dict[str, dict]) -> list[Scaling]:
    """Damage and ATK-conversion scalings of one character, summed per talent and stat."""
    totals: dict[tuple[str, str, str], float] = defaultdict(float)
    for talent, data in talents.items():
        hits = []
        for label in data["labels"]:
            name, _, template = label.partition("|")
            if CONVERSION.search(name):
                for stat, coef in _terms(template, data["values"]):
                    if stat != "atk":
                        totals[(talent, "atk", stat)] += coef
            elif _is_damage(name, template):
                hits.append(template)
        # a talent's hits with a stat spelled out are the character's own mechanic (Neuvillette's
        # charged attack on HP); the generic ATK chain next to them is what gets skipped in play
        special = [t for t in hits if EXPLICIT.search(t)]
        for template in special or hits:
            for stat, coef in _terms(template, data["values"]):
                totals[(talent, "damage", stat)] += coef
    return [Scaling(t, k, s, round(c, 6)) for (t, k, s), c in totals.items()]
