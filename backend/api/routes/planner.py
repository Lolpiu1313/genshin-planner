import math
from typing import Annotated

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from api.deps import DbSession
from api.routes.queue import load_queue, queue_build
from api.schemas import (
    Bin, CharacterGain, DomainChoice, DomainOut, EstimateOut, Luck, Quantiles, RecommendationOut, ResinIn, ResinOut,
)
from api.scores import load_builds, load_inventory
from core import planner, simulate
from core.constants import CONDENSED_RESIN, RESIN_PER_RUN, SLOTS
from core.scoring import best_per_slot, combine
from db.models import Character, Domain, ResinLog

router = APIRouter()

SIMULATIONS = 4000
BINS = 30
SEED = 0  # fixed so the recommendation doesn't flip between near-equal domains on every refresh
CLOSE = 0.03


def _histogram(values: np.ndarray, scale: float = 1) -> list[Bin]:
    values = values[np.isfinite(values)] * scale
    if len(values) == 0:
        return []
    counts, edges = np.histogram(values, bins=BINS, range=(values.min(), np.quantile(values, 0.99)))
    return [Bin(x=round(float(e), 1), count=int(c)) for e, c in zip(edges[:-1], counts, strict=True)]


def _quantiles(fn) -> Quantiles:
    def q(p: float) -> float | None:
        v = fn(p)
        return None if math.isinf(v) else round(v, 1)
    return Quantiles(p25=q(0.25), median=q(0.5), p75=q(0.75), p90=q(0.9))


@router.get("/planner/estimate/{character_key}", response_model=EstimateOut)
def estimate(session: DbSession, character_key: str, target: Annotated[float, Query(gt=0, le=100)] = 45,
             build_id: int | None = None):
    char = session.scalar(select(Character).where(Character.key == character_key))
    if char is None:
        raise HTTPException(404, "character not found")
    builds = [(b, core) for b, core in load_builds(session) if b.character_id == char.id]
    if build_id is not None:
        builds = [(b, core) for b, core in builds if b.id == build_id]
    if not builds:
        raise HTTPException(404, "build not found")
    build, core = builds[0]

    domain = next((s.set.domain for s in build.sets if s.set.domain), None)
    if domain is None:
        raise HTTPException(422, "none of this build's sets drop from a domain")
    domain_sets = tuple(s.key for s in domain.sets)

    on, off = best_per_slot(load_inventory(session), core)
    slots = combine(on, off)
    current = sum(slots) / len(slots)

    est = simulate.estimate(core, domain_sets, target, start=np.array(on + off), n=SIMULATIONS)

    spent = session.scalar(select(func.sum(ResinLog.resin_spent)).where(ResinLog.domain_id == domain.id)) or 0
    luck = None
    if spent:
        sims = simulate.scores_after(core, domain_sets, spent // RESIN_PER_RUN, n=SIMULATIONS)
        luck = Luck(resin_spent=spent, percentile=round(simulate.percentile(current, sims), 1), histogram=_histogram(sims))

    return EstimateOut(
        character=char.name,
        build=build.name,
        domain=DomainOut.model_validate(domain),
        target=target,
        current=round(current, 1),
        slots={s: round(v, 1) for s, v in zip(SLOTS, slots, strict=True)},
        resin=_quantiles(est.resin),
        days=_quantiles(est.days),
        reached=round(est.reached, 3),
        max_resin=est.max_runs * RESIN_PER_RUN,
        histogram=_histogram(est.runs, RESIN_PER_RUN),
        luck=luck,
    )


@router.get("/planner/recommendation", response_model=RecommendationOut | None)
def recommendation(session: DbSession):
    queue = load_queue(session)
    if not queue:
        return None
    cores = {b.id: core for b, core in load_builds(session)}
    inventory = load_inventory(session)
    entries = []
    for q in queue:
        core = cores[queue_build(q).id]
        on, off = best_per_slot(inventory, core)
        entries.append(planner.QueueEntry(q.character.key, core, on + off, q.target_score, q.priority))

    domains = {d.key: d for d in session.scalars(select(Domain).options(selectinload(Domain.sets)))}
    rec = planner.recommend(entries, {k: tuple(s.key for s in d.sets) for k, d in domains.items()}, seed=SEED)
    if rec is None:
        return None

    names = {q.character.key: q.character.name for q in queue}
    alternatives = [DomainChoice(key=d.domain, name=domains[d.domain].name, value=round(d.value, 3))
                    for d in rec.ranking[1:4]]
    return RecommendationOut(
        domain=DomainOut.model_validate(domains[rec.best.domain]),
        value=round(rec.best.value, 3),
        condensed=rec.condensed,
        stay_share=rec.stay_share,
        focus=names.get(rec.focus) if rec.best.value > 0 else None,
        close=bool(alternatives) and rec.best.value > 0 and alternatives[0].value >= rec.best.value * (1 - CLOSE),
        gains=[CharacterGain(character_key=q.character.key, character=q.character.name, priority=q.priority,
                             gain=round(rec.best.gains[q.character.key], 3)) for q in queue],
        alternatives=alternatives,
    )


def _resin_out(log: ResinLog) -> ResinOut:
    return ResinOut(id=log.id, domain_key=log.domain.key, resin_spent=log.resin_spent,
                    condensed=log.condensed, date=log.date)


@router.post("/resin", response_model=ResinOut, status_code=201)
def log_resin(session: DbSession, data: ResinIn):
    domain = session.scalar(select(Domain).where(Domain.key == data.domain_key))
    if domain is None:
        raise HTTPException(422, f"unknown domain {data.domain_key}")
    per_run = CONDENSED_RESIN if data.condensed else RESIN_PER_RUN
    log = ResinLog(domain=domain, resin_spent=data.runs * per_run, condensed=data.condensed)
    session.add(log)
    session.commit()
    return _resin_out(log)
