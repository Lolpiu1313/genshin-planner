from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.deps import DbSession
from api.schemas import CharacterOut, DomainOut, SetOut
from core.constants import SUBSTAT_ROLLS
from db.models import ArtifactSet, BuildSet, Character, CharBuild, Domain

router = APIRouter()


@router.get("/characters", response_model=list[CharacterOut])
def list_characters(session: DbSession):
    return session.scalars(select(Character).options(
        selectinload(Character.builds).selectinload(CharBuild.sets).selectinload(BuildSet.set)
    ).order_by(Character.name)).all()


@router.get("/domains", response_model=list[DomainOut])
def list_domains(session: DbSession):
    return session.scalars(select(Domain).options(selectinload(Domain.sets)).order_by(Domain.name)).all()


@router.get("/rolls", response_model=dict[int, dict[str, list[float]]])
def list_rolls():
    """The four values a substat can roll, per rarity: what a fresh piece's lines can be."""
    return {r: SUBSTAT_ROLLS[r] for r in (4, 5)}


@router.get("/sets", response_model=list[SetOut])
def list_sets(session: DbSession):
    return session.scalars(select(ArtifactSet).order_by(ArtifactSet.name)).all()
