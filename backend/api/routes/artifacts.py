from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from api.deps import DbSession
from api.schemas import (
    AdviceOut, ArtifactIn, ArtifactOut, EquippedPiece, ImportResult, NextRoll, ScoredArtifact, ScoreOut,
)
from api.scores import (
    build_formula, build_ratio, equipped_on, equipped_score, load_builds, pick_build, piece_scores, score_artifact,
    to_core, to_out,
)
from core.advice import advise
from core.constants import EXP_PER_POINT, MAX_LEVEL
from core.damage import apply, artifact_stats, swap_gain
from db.models import Artifact, ArtifactSet, ArtifactSubstat, Character, FarmSession, OwnedCharacter

router = APIRouter(prefix="/artifacts")


def _substats(data: ArtifactIn) -> list[ArtifactSubstat]:
    # active is set explicitly: on update the old rows are replaced by new ones with the same key,
    # which SQLAlchemy turns into an UPDATE that would skip the column default
    subs = [ArtifactSubstat(stat=s.key, value=s.value, active=True) for s in data.substats]
    return subs + [ArtifactSubstat(stat=s.key, value=s.value, active=False) for s in data.unactivated]


def _build(data: ArtifactIn, set_: ArtifactSet, source: str) -> Artifact:
    return Artifact(set=set_, slot=data.slot, main_stat=data.main_stat, level=data.level,
                    rarity=data.rarity, substats=_substats(data), source=source)


def _set(session: Session, key: str) -> ArtifactSet:
    set_ = session.scalar(select(ArtifactSet).where(ArtifactSet.key == key))
    if set_ is None:
        raise HTTPException(422, f"unknown set {key}")
    return set_


def _get(session: Session, artifact_id: int) -> Artifact:
    art = session.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(404, "artifact not found")
    return art


@router.get("", response_model=list[ArtifactOut])
def list_artifacts(session: DbSession):
    rows = session.scalars(select(Artifact).options(
        selectinload(Artifact.set), selectinload(Artifact.substats), selectinload(Artifact.wearer)
    ).order_by(Artifact.id.desc()))
    return [to_out(a) for a in rows]


@router.post("", response_model=ScoredArtifact, status_code=201)
def add_artifact(session: DbSession, data: ArtifactIn, character: str | None = None, session_id: int | None = None):
    art = _build(data, _set(session, data.set_key), "manual")
    if session_id is not None:
        if session.get(FarmSession, session_id) is None:
            raise HTTPException(404, "session not found")
        art.session_id = session_id
    session.add(art)
    session.commit()
    return ScoredArtifact(**to_out(art).model_dump(), scores=score_artifact(art, load_builds(session), character))


@router.put("/{artifact_id}", response_model=ArtifactOut)
def update_artifact(session: DbSession, artifact_id: int, data: ArtifactIn):
    """Replace an artifact's stats, e.g. after levelling it."""
    art = _get(session, artifact_id)
    art.set = _set(session, data.set_key)
    art.slot, art.main_stat, art.level, art.rarity = data.slot, data.main_stat, data.level, data.rarity
    art.substats = _substats(data)
    session.commit()
    return to_out(art)


@router.get("/{artifact_id}/advice", response_model=AdviceOut)
def get_advice(session: DbSession, artifact_id: int, character: str | None = None, build_id: int | None = None,
               exp_per_point: Annotated[float, Query(gt=0)] = EXP_PER_POINT):
    """Should this artifact be levelled for the character, and what would equipping it change."""
    art = _get(session, artifact_id)
    farm = session.get(FarmSession, art.session_id) if art.session_id else None
    if character is not None:
        char = session.scalar(select(Character).where(Character.key == character))
    elif farm is not None:
        char, build_id = farm.character, build_id or farm.build_id
    else:
        raise HTTPException(422, "say which character the artifact is for")
    if char is None:
        raise HTTPException(404, "character not found")

    builds = load_builds(session)
    worn = equipped_on(session, char.id)
    build, core = pick_build([bc for bc in builds if bc[0].character_id == char.id], worn, build_id)
    piece = to_core(art)
    old = worn.get(art.slot)
    # a piece the character already wears is compared with itself: no gain, nothing to beat
    old_core = to_core(old) if old is not None else None
    tip = advise(piece, core, old_core, exp_per_point)
    plan = tip.plan

    owned = session.get(OwnedCharacter, char.id)
    build_now = with_now = with_pot = gain = None
    if owned is not None:
        pieces = {slot: to_core(a) for slot, a in worn.items()}
        f = build_formula(build, core)
        build_now, kind = equipped_score(build, core, owned.stats, pieces)
        # stats as if the new piece replaced the worn one, at its current level
        swapped = apply(owned.stats, artifact_stats(old_core), -1) if old_core else owned.stats
        swapped = apply(swapped, artifact_stats(piece))
        with_now, _ = equipped_score(build, core, swapped, pieces | {art.slot: piece})
        if kind == "pieces":
            # with piece scores the expected score at max is known; a damage figure would need its final rolls
            with_pot = build_ratio(piece_scores(worn, core) | {art.slot: plan.expected})
        gain = round(swap_gain(f, owned.stats, old_core, piece), 4)

    return AdviceOut(
        character_key=char.key,
        character=char.name,
        build=build.name,
        action=tip.action,
        stop=tip.stop,
        level=art.level,
        max_level=MAX_LEVEL[art.rarity],
        score=round(tip.score, 1),
        potential=round(plan.expected, 1),
        beat_chance=round(plan.beat_chance, 3),
        expected_gain=round(plan.gain, 2),
        value=round(plan.value),
        reach_max=round(plan.reach_max, 3),
        keep_after_next=round(plan.keep_after_next, 3),
        success=round(plan.success, 3),
        exp_next=plan.exp_next,
        exp_expected=round(plan.exp_expected),
        next_rolls=[NextRoll(stat=stat, chance=round(p, 3), keep=round(keep, 3)) for stat, p, keep in plan.next_rolls],
        equipped=EquippedPiece(set_key=old.set.key, main_stat=old.main_stat, level=old.level,
                               score=round(tip.equipped, 1)) if old_core else None,
        build_score=build_now,
        build_score_with=with_now,
        build_score_potential=with_pot,
        dmg_gain=gain,
        best=score_artifact(art, builds).overall,
    )


@router.get("/{artifact_id}/score", response_model=ScoreOut)
def get_score(session: DbSession, artifact_id: int, character: str | None = None):
    return score_artifact(_get(session, artifact_id), load_builds(session), character)


@router.delete("/{artifact_id}", status_code=204)
def delete_artifact(session: DbSession, artifact_id: int):
    session.delete(_get(session, artifact_id))
    session.commit()


@router.post("/import", response_model=ImportResult)
def import_good(session: DbSession, data: Annotated[dict, Body()]):
    """Replace previously imported artifacts with those from a GOOD export."""
    if data.get("format") != "GOOD":
        raise HTTPException(422, "not a GOOD file")
    sets = {s.key: s for s in session.scalars(select(ArtifactSet))}

    session.execute(delete(Artifact).where(Artifact.source == "good"))
    imported = skipped = 0
    for raw in data.get("artifacts", []):
        try:
            art = ArtifactIn(
                set_key=raw["setKey"], slot=raw["slotKey"], main_stat=raw["mainStatKey"],
                level=raw["level"], rarity=raw["rarity"],
                substats=[s for s in raw.get("substats", []) if s.get("key")],
                unactivated=[s for s in raw.get("unactivatedSubstats", []) if s.get("key")],
            )
        except (KeyError, ValidationError):
            skipped += 1
            continue
        if art.set_key not in sets:
            skipped += 1
            continue
        session.add(_build(art, sets[art.set_key], "good"))
        imported += 1
    session.commit()
    return ImportResult(imported=imported, skipped=skipped)
