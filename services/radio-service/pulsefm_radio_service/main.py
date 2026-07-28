"""HTTP surface for the rotation clock.

Handlers do wiring only: read state, call the pure core, persist, chain the
next task. Every decision lives in logic.py.
"""

import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from fastapi import FastAPI, HTTPException
from google.cloud import firestore, tasks_v2
from pydantic import BaseModel

from pulsefm_radio_service.config import settings_from_env
from pulsefm_radio_service.logic import (
    CandidateSong,
    RotationPlan,
    is_stale_version,
    plan_rotation,
    resolve_promoted,
)
from pulsefm_radio_service.repository import StationRepository
from pulsefm_radio_service.scheduler import TickScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class Repository(Protocol):
    def get_station(self) -> dict | None: ...
    def list_pool(self, limit: int) -> list[CandidateSong]: ...
    def rotate(self, plan: RotationPlan) -> bool: ...
    def bootstrap(self, plan: RotationPlan) -> bool: ...


class Scheduler(Protocol):
    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool: ...


class TickRequest(BaseModel):
    version: int


def build_app(repository: Repository, scheduler: Scheduler, clock: Clock) -> FastAPI:
    app = FastAPI(title="pulsefm-radio-service")
    pool_limit = 20

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/bootstrap")
    def bootstrap() -> dict[str, object]:
        pool = repository.list_pool(limit=pool_limit)
        promoted = resolve_promoted(pool, None)
        if promoted is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot start the station: no ready songs in Firestore. "
                "Run scripts/seed_tracks.py first.",
            )

        plan = plan_rotation(promoted=promoted, pool=pool, now=clock(), current_version=0)
        if not repository.bootstrap(plan):
            return {"status": "already-running"}

        # Schedule the tick with plan.version + 1, not plan.version: by the
        # time the task fires, station.version == plan.version (this
        # rotation already landed), so is_stale_version's `<=` guard would
        # reject a tick carrying plan.version as a replay. plan.version + 1
        # is the version the *next* rotation will create, which is exactly
        # what the successor tick must claim to pass the guard.
        # scheduler.schedule returns False only when it caught AlreadyExists
        # (see TickScheduler.schedule's docstring) — an equivalent task
        # already exists and will fire, so this is the idempotency
        # guarantee working, not a stall. scheduler.py already logs that
        # case at INFO; nothing further to report here. A genuine failure
        # raises instead and propagates to the caller.
        scheduler.schedule(song_id=plan.song_id, end_at=plan.end_at, version=plan.version + 1)
        logger.info("Station started on %s until %s", plan.song_id, plan.end_at)
        return {"status": "started", "songId": plan.song_id, "version": plan.version}

    @app.post("/tick")
    def tick(request: TickRequest) -> dict[str, object]:
        station = repository.get_station()
        if station is None:
            raise HTTPException(
                status_code=409,
                detail="Station is not bootstrapped. POST /bootstrap first.",
            )

        current_version = int(station.get("version", 0))
        if is_stale_version(request.version, current_version):
            logger.info(
                "Ignoring stale tick: requested v%s, current v%s",
                request.version,
                current_version,
            )
            return {"status": "stale", "version": current_version}

        pool = repository.list_pool(limit=pool_limit)
        promoted = resolve_promoted(pool, station.get("nextSongId"))
        if promoted is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot rotate: no ready songs in Firestore.",
            )

        plan = plan_rotation(
            promoted=promoted, pool=pool, now=clock(), current_version=current_version
        )
        if not repository.rotate(plan):
            logger.info("Lost the rotation race for v%s", plan.version)
            return {"status": "lost-race", "version": current_version}

        # Schedule with plan.version + 1 — see the matching comment in
        # /bootstrap. scheduler.schedule returning False means an equivalent
        # task already existed (idempotency working, not a stall); see the
        # matching comment in /bootstrap for why nothing further is logged
        # here.
        scheduler.schedule(song_id=plan.song_id, end_at=plan.end_at, version=plan.version + 1)
        logger.info("Rotated to %s until %s (v%s)", plan.song_id, plan.end_at, plan.version)
        return {"status": "rotated", "songId": plan.song_id, "version": plan.version}

    return app


def _build_default_app() -> FastAPI:
    settings = settings_from_env()
    repository = StationRepository(firestore.Client(project=settings.project_id), settings)
    scheduler = TickScheduler(tasks_v2.CloudTasksClient(), settings)
    return build_app(repository, scheduler, clock=lambda: datetime.now(tz=UTC))


app: FastAPI | None = None

if os.getenv("PULSEFM_EAGER_APP", "1") == "1" and os.getenv("PROJECT_ID"):
    app = _build_default_app()
