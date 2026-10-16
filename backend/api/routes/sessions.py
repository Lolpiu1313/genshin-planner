from collections import Counter

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import DbSession
from api.schemas import DomainOut, RunIn, RunOut, SessionIn, SessionOut
from api.scores import equipped_on, load_builds, pick_build, to_out
from core.constants import CONDENSED_RESIN
from db.models import Character, CharBuild, Domain, FarmSession, ResinLog

router = APIRouter(prefix="/sessions")


def active_session(session: Session) -> FarmSession | None:
    return session.scalar(select(FarmSession).where(FarmSession.ended_at.is_(None)).order_by(FarmSession.id.desc()))


def _get(session: Session, session_id: int) -> FarmSession:
    farm = session.get(FarmSession, session_id)
    if farm is None:
        raise HTTPException(404, "session not found")
    return farm


def _domain(session: Session, key: str) -> Domain:
    domain = session.scalar(select(Domain).where(Domain.key == key))
    if domain is None:
        raise HTTPException(422, f"unknown domain {key}")
    return domain


def default_domain(build: CharBuild, worn: dict) -> Domain | None:
    """Domain of the set the character mostly wears, else of the build's top set."""
    counts = Counter(a.set.domain for a in worn.values() if a.set.domain)
    if counts:
        return counts.most_common(1)[0][0]
    return next((s.set.domain for s in build.sets if s.set.domain), None)


def to_session_out(farm: FarmSession) -> SessionOut:
    build = farm.build or farm.character.builds[0]
    return SessionOut(
        id=farm.id,
        character_key=farm.character.key,
        character=farm.character.name,
        build_id=build.id,
        build=build.name,
        domain=DomainOut.model_validate(farm.domain),
        started_at=farm.started_at,
        ended_at=farm.ended_at,
        runs=[RunOut(id=r.id, domain_key=r.domain.key, domain=r.domain.name, resin=r.resin_spent,
                     five_stars=r.five_stars or 0, date=r.date) for r in farm.runs],
        resin=sum(r.resin_spent for r in farm.runs),
        five_stars=sum(r.five_stars or 0 for r in farm.runs),
        artifacts=[to_out(a) for a in farm.artifacts],
    )


@router.post("", response_model=SessionOut, status_code=201)
def start(session: DbSession, data: SessionIn):
    char = session.scalar(select(Character).where(Character.key == data.character_key))
    if char is None:
        raise HTTPException(404, "character not found")
    builds = [bc for bc in load_builds(session) if bc[0].character_id == char.id]
    if data.build_id is not None and data.build_id not in {b.id for b, _ in builds}:
        raise HTTPException(422, "build does not belong to this character")
    worn = equipped_on(session, char.id)
    build, _ = pick_build(builds, worn, data.build_id)

    domain = _domain(session, data.domain_key) if data.domain_key else default_domain(build, worn)
    if domain is None:
        raise HTTPException(422, "pick a domain: none of this build's sets drop from one")

    if previous := active_session(session):
        previous.ended_at = func.now()
    farm = FarmSession(character=char, build=build, domain=domain)
    session.add(farm)
    session.commit()
    return to_session_out(farm)


@router.get("/active", response_model=SessionOut | None)
def get_active(session: DbSession):
    farm = active_session(session)
    return to_session_out(farm) if farm else None


@router.post("/{session_id}/runs", response_model=SessionOut, status_code=201)
def add_run(session: DbSession, session_id: int, data: RunIn):
    """Log a finished domain run; without a domain it counts toward the session's own."""
    farm = _get(session, session_id)
    if farm.ended_at is not None:
        raise HTTPException(409, "session already ended")
    domain = _domain(session, data.domain_key) if data.domain_key else farm.domain
    session.add(ResinLog(domain=domain, resin_spent=data.resin, condensed=data.resin >= CONDENSED_RESIN,
                         five_stars=data.five_stars, session_id=farm.id))
    session.commit()
    session.refresh(farm)
    return to_session_out(farm)


@router.post("/{session_id}/end", response_model=SessionOut)
def end(session: DbSession, session_id: int):
    farm = _get(session, session_id)
    if farm.ended_at is None:
        farm.ended_at = func.now()
        session.commit()
        session.refresh(farm)
    return to_session_out(farm)
