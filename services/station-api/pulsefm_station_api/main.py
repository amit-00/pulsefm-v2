"""Public read API.

Every response is identical for every listener, which is what lets /v1/state
sit behind a shared cache. Nothing per-user may ever enter this payload.
"""

import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from pulsefm_models.station import CurrentSong, QueueResponse, StateResponse

from pulsefm_station_api.config import settings_from_env
from pulsefm_station_api.repository import StationReadRepository
from pulsefm_station_api.snapshot import MissingSongError, build_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class Repository(Protocol):
    def get_station(self) -> dict | None: ...
    def get_song(self, song_id: str) -> dict | None: ...


def build_app(
    repository: Repository,
    audio_base_url: str,
    state_max_age_seconds: int,
    clock: Clock,
    allowed_origins: list[str],
) -> FastAPI:
    app = FastAPI(title="pulsefm-station-api")
    cache_control = f"public, max-age={state_max_age_seconds}"

    # Closed unless explicitly configured: only attach CORS when the
    # deployment named at least one allowed origin. The endpoint is
    # anonymous and must stay publicly cacheable, so credentials are never
    # allowed and only GET is exposed.
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["GET"],
            allow_credentials=False,
        )

    def _load_state() -> StateResponse:
        station = repository.get_station()
        if station is None:
            raise HTTPException(
                status_code=503,
                detail="The station has not started yet. Try again shortly.",
            )
        try:
            return build_state(
                station=station,
                song=repository.get_song(station["songId"]),
                audio_base_url=audio_base_url,
                server_time=clock(),
            )
        except MissingSongError as error:
            logger.error("Inconsistent station state: %s", error)
            raise HTTPException(
                status_code=503, detail="The station is in an inconsistent state."
            ) from error

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/state")
    def state(response: Response) -> StateResponse:
        response.headers["Cache-Control"] = cache_control
        return _load_state()

    @app.get("/v1/queue")
    def queue(response: Response) -> QueueResponse:
        response.headers["Cache-Control"] = cache_control
        current_state = _load_state()
        items: list[CurrentSong] = [current_state.current]

        next_song_id = current_state.next_up.song_id
        if next_song_id is not None:
            next_song = repository.get_song(next_song_id)
            if next_song is not None:
                items.append(
                    CurrentSong(
                        song_id=next_song_id,
                        title=next_song["title"],
                        artist=next_song["artist"],
                        descriptor=next_song["descriptor"],
                        url=f"{audio_base_url.rstrip('/')}/{next_song['objectPath'].lstrip('/')}",
                        start_at=current_state.current.end_at,
                        end_at=current_state.current.end_at,
                        duration_ms=int(next_song.get("durationMs", 0)),
                    )
                )

        return QueueResponse(items=items)

    return app


def _build_default_app() -> FastAPI:
    settings = settings_from_env()
    repository = StationReadRepository(
        firestore.Client(project=settings.project_id), settings
    )
    return build_app(
        repository,
        audio_base_url=settings.audio_base_url,
        state_max_age_seconds=settings.state_max_age_seconds,
        clock=lambda: datetime.now(tz=UTC),
        allowed_origins=settings.allowed_origins,
    )


app: FastAPI | None = None

if os.getenv("PULSEFM_EAGER_APP", "1") == "1" and os.getenv("PROJECT_ID"):
    app = _build_default_app()
