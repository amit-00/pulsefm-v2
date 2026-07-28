"""Dev-only station-api ASGI app: real Firestore (emulator), CORS added.

Reuses pulsefm_station_api.main.build_app unmodified against the Firestore
emulator. The one addition beyond what production needs: CORS. In
production the client and station-api are same-origin-adjacent through
infrastructure this slice doesn't have locally (and, per the Task 17 brief,
is explicitly out of scope to build); here the Vite dev server (5173) and
this API (8000) are genuinely different origins, so the browser's fetch()
in useStation needs an Access-Control-Allow-Origin response header or it
never sees the JSON body. Added by wrapping the app this harness builds,
not by editing services/station-api — nothing under services/ changes.

Run: uv run uvicorn scripts.dev_station_app:app --port 8000
Requires FIRESTORE_EMULATOR_HOST and CDN_BASE_URL in the environment.
"""

import os
from datetime import UTC, datetime

from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from pulsefm_station_api.config import Settings
from pulsefm_station_api.main import build_app
from pulsefm_station_api.repository import StationReadRepository

PROJECT_ID = "pulsefm-local"


def _settings() -> Settings:
    return Settings(
        project_id=PROJECT_ID,
        station_doc=os.getenv("STATION_DOC", "station/current"),
        songs_collection=os.getenv("SONGS_COLLECTION", "songs"),
        cdn_base_url=os.environ["CDN_BASE_URL"],
        state_max_age_seconds=int(os.getenv("STATE_MAX_AGE_SECONDS", "1")),
    )


if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
    raise RuntimeError("FIRESTORE_EMULATOR_HOST must be set to run the dev station-api app.")

_settings_value = _settings()
_repository = StationReadRepository(
    firestore.Client(project=_settings_value.project_id), _settings_value
)
app = build_app(
    _repository,
    cdn_base_url=_settings_value.cdn_base_url,
    state_max_age_seconds=_settings_value.state_max_age_seconds,
    clock=lambda: datetime.now(tz=UTC),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("DEV_CLIENT_ORIGIN", "http://localhost:5173")],
    allow_methods=["GET"],
    allow_headers=["*"],
)
