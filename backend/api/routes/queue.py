from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.deps import DbSession
from api.schemas import BuildOut, QueueIn, QueueOut
from api.scores import load_builds, load_inventory, weights_source
from core.constants import SLOTS
from core.scoring import best_per_slot, combine
from db.models import BuildQueue, Character, OwnedCharacter

router = APIRouter(prefix="/queue")


def load_queue(session: Session) -> list[BuildQueue]:
    return list(session.scalars(
        select(BuildQueue).options(selectinload(BuildQueue.character).selectinload(Character.builds))
        .order_by(BuildQueue.priority)
    ))


def queue_build(entry: BuildQueue):
    # the queued build may have been replaced by a data re-import
    return entry.build or entry.character.builds[0]


@router.get("", response_model=list[QueueOut])
def list_queue(session: DbSession):
    cores = {b.id: core for b, core in load_builds(session)}
    inventory = load_inventory(session)
    owned = set(session.scalars(select(OwnedCharacter.character_id)))
    out = []
    for entry in load_queue(session):
        build = queue_build(entry)
        core = cores[build.id]
        slots = combine(*best_per_slot(inventory, core))
        out.append(QueueOut(
            character_key=entry.character.key,
            character=entry.character.name,
            build_id=build.id,
            build=build.name,
            builds=[BuildOut.model_validate(b) for b in entry.character.builds],
            priority=entry.priority,
            target_score=entry.target_score,
            current=round(sum(slots) / len(slots), 1),
            slots={s: round(v, 1) for s, v in zip(SLOTS, slots, strict=True)},
            weights=core.weights,
            weights_source=weights_source(build, entry.character_id in owned),
        ))
    return out


@router.post("", status_code=204)
def save_entry(session: DbSession, data: QueueIn):
    """Add a character to the queue or update its build, priority or target."""
    char = session.scalar(select(Character).where(Character.key == data.character_key))
    if char is None:
        raise HTTPException(404, "character not found")
    if data.build_id is not None and data.build_id not in {b.id for b in char.builds}:
        raise HTTPException(422, "build does not belong to this character")

    entry = session.get(BuildQueue, char.id)
    if entry is None:
        last = session.scalar(select(func.max(BuildQueue.priority))) or 0
        entry = BuildQueue(character=char, priority=last + 1)
        session.add(entry)
    if data.priority is not None:
        entry.priority = data.priority
    entry.build_id = data.build_id or entry.build_id
    entry.target_score = data.target_score
    session.commit()


@router.delete("/{character_key}", status_code=204)
def remove_entry(session: DbSession, character_key: str):
    entry = session.scalar(select(BuildQueue).join(Character).where(Character.key == character_key))
    if entry is None:
        raise HTTPException(404, "character not in queue")
    session.delete(entry)
    session.commit()
