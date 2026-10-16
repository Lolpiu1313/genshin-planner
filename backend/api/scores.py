from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.schemas import ArtifactOut, BuildScore, ScoreOut, Substat
from core import damage, scoring
from core.constants import SLOTS
from core.talents import Scaling
from db.models import Artifact, BuildSet, Character, CharBuild, OwnedCharacter

TOP_N = 5


def character_stats(char: Character, owned: OwnedCharacter | None) -> dict[str, float] | None:
    """The character's in-game stats from Enka, else those of a typically built one."""
    if owned is not None:
        return owned.stats
    if char.base_atk is None:
        return None
    base = {"hp": char.base_hp, "atk": char.base_atk, "def": char.base_def}
    return damage.reference_stats(base, (char.ascension_stat, char.ascension_value))


def build_formula(build: CharBuild, core: scoring.Build) -> damage.Formula:
    char = build.character
    scalings = [Scaling(s.talent, s.kind, s.stat, s.coef) for s in char.scalings]
    return damage.formula(core, char.element, scalings, build.talent_priority)


def weights_source(build: CharBuild, owned: bool) -> str:
    """Where a build's weights come from: the player's stats, a typical build, or the site's ranking."""
    if not damage.is_damage_build(build.name) or build.character.base_atk is None:
        return "site"
    return "enka" if owned else "reference"


def load_builds(session: Session) -> list[tuple[CharBuild, scoring.Build]]:
    """Every build, with damage stats weighted by the character's own damage formula where it applies."""
    rows = session.scalars(select(CharBuild).options(
        selectinload(CharBuild.character).selectinload(Character.scalings),
        selectinload(CharBuild.weights),
        selectinload(CharBuild.sets).selectinload(BuildSet.set),
    ))
    owned = {o.character_id: o for o in session.scalars(select(OwnedCharacter))}
    out = []
    for b in rows:
        core = scoring.Build(
            weights={w.stat: w.weight for w in b.weights},
            sets=[s.set.key for s in b.sets],
            main_stats={"sands": b.sands_main, "goblet": b.goblet_main, "circlet": b.circlet_main},
        )
        stats = character_stats(b.character, owned.get(b.character_id))
        if stats is not None and damage.is_damage_build(b.name):
            core.weights = damage.build_weights(core.weights, build_formula(b, core), stats)
        out.append((b, core))
    return out


def load_inventory(session: Session) -> list[scoring.Artifact]:
    rows = session.scalars(select(Artifact).options(selectinload(Artifact.set), selectinload(Artifact.substats)))
    return [to_core(a) for a in rows]


def equipped_on(session: Session, character_id: int) -> dict[str, Artifact]:
    """Artifacts the character wears according to the last Enka import, by slot."""
    rows = session.scalars(select(Artifact).options(selectinload(Artifact.set), selectinload(Artifact.substats))
                           .where(Artifact.equipped_by == character_id))
    return {a.slot: a for a in rows}


def pick_build(builds: list[tuple[CharBuild, scoring.Build]], worn: dict[str, Artifact],
               build_id: int | None = None) -> tuple[CharBuild, scoring.Build]:
    """The requested build, else the one the worn artifacts fit best, else the first."""
    if build_id is not None:
        return next((b, core) for b, core in builds if b.id == build_id)
    if not worn:
        return builds[0]
    pieces = [to_core(a) for a in worn.values()]
    return max(builds, key=lambda bc: sum(scoring.score(p, bc[1]) for p in pieces))


def piece_scores(worn: dict[str, Artifact], core: scoring.Build) -> dict[str, float]:
    return {slot: scoring.score(to_core(a), core) for slot, a in worn.items()}


def equipped_score(build: CharBuild, core: scoring.Build, stats: dict[str, float],
                   worn: dict[str, scoring.Artifact]) -> tuple[float, str]:
    """Build score out of 1 and how it was measured: by damage for damage builds, else by piece scores."""
    if damage.is_damage_build(build.name) and build.character.base_atk is not None:
        quality = damage.build_quality(build_formula(build, core), stats, list(worn.values()), core)
        return round(quality, 3), "damage"
    return build_ratio({slot: scoring.score(a, core) for slot, a in worn.items()}), "pieces"


def build_ratio(scores: dict[str, float]) -> float:
    """Build score as a share of a perfect build: 1 means every slot holds a flawless piece."""
    return round(sum(scores.values()) / len(SLOTS) / 100, 3)


def to_core(a: Artifact) -> scoring.Artifact:
    return scoring.Artifact(
        set_key=a.set.key,
        slot=a.slot,
        main_stat=a.main_stat,
        level=a.level,
        rarity=a.rarity,
        substats={s.stat: s.value for s in a.substats if s.active},
        unactivated={s.stat: s.value for s in a.substats if not s.active},
    )


def to_out(a: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=a.id, set_key=a.set.key, slot=a.slot, main_stat=a.main_stat, level=a.level, rarity=a.rarity,
        substats=[Substat(key=s.stat, value=s.value) for s in a.substats if s.active],
        unactivated=[Substat(key=s.stat, value=s.value) for s in a.substats if not s.active],
        source=a.source, equipped_by=a.wearer.key if a.wearer else None, obtained_at=a.obtained_at,
    )


def score_artifact(a: Artifact, builds: list[tuple[CharBuild, scoring.Build]], character: str | None = None) -> ScoreOut:
    art = to_core(a)
    results = sorted((BuildScore(
        character_key=b.character.key,
        character=b.character.name,
        build=b.name,
        score=round(scoring.score(art, core), 1),
        potential=round(scoring.potential(art, core), 1),
    ) for b, core in builds), key=lambda r: r.potential, reverse=True)

    top: list[BuildScore] = []
    for r in results:
        # one entry per character, their best build
        if all(t.character_key != r.character_key for t in top):
            top.append(r)
        if len(top) == TOP_N:
            break
    mine = next((r for r in results if r.character_key == character), None)
    return ScoreOut(overall=results[0] if results else None, top=top, character=mine)
