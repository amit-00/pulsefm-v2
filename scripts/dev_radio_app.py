"""Dev-only radio-service ASGI app: real Firestore (emulator), no-op scheduler.

Task 17's local bring-up has no GCP project and no Cloud Tasks queue, so the
real `TickScheduler` (which needs OIDC credentials to schedule an HTTP push)
would fail at import or at call time. `build_app(repository, scheduler,
clock)` in pulsefm_radio_service.main already takes the scheduler as a
parameter for exactly this reason — this harness supplies a logging no-op
instead of patching main.py. Rotation is then driven by hand: POST /tick.

Deliberately does not set PROJECT_ID in the environment, so importing
pulsefm_radio_service.main does not trip its `_build_default_app()` eager-init
guard (which would construct a real, credential-requiring CloudTasksClient).

Run: uv run uvicorn scripts.dev_radio_app:app --port 8001
Requires FIRESTORE_EMULATOR_HOST in the environment.
"""

import logging
import os
from datetime import UTC, datetime

from google.cloud import firestore
from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.main import build_app
from pulsefm_radio_service.repository import StationRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dev_radio_app")

PROJECT_ID = "pulsefm-local"


class NoOpScheduler:
    """Logs what Cloud Tasks would have scheduled instead of calling it.

    There is no queue and no service account locally, so nothing actually
    fires at `end_at` — rotate the station by hand with
    `curl -X POST localhost:8001/tick -d '{"version": N}'`.
    """

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        logger.info(
            "would schedule tick: song_id=%s end_at=%s version=%s "
            '(drive it by hand: POST /tick {"version": %s})',
            song_id,
            end_at.isoformat(),
            version,
            version,
        )
        return True


def _settings() -> Settings:
    return Settings(
        project_id=PROJECT_ID,
        station_doc=os.getenv("STATION_DOC", "station/current"),
        songs_collection=os.getenv("SONGS_COLLECTION", "songs"),
        tick_url="http://unused.invalid/tick",
        queue_name="dev-queue",
        queue_location="us-central1",
        tick_service_account="dev@unused.invalid",
        pool_size=int(os.getenv("POOL_SIZE", "20")),
    )


if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
    raise RuntimeError("FIRESTORE_EMULATOR_HOST must be set to run the dev radio-service app.")

_settings_value = _settings()
_repository = StationRepository(
    firestore.Client(project=_settings_value.project_id), _settings_value
)
app = build_app(_repository, NoOpScheduler(), clock=lambda: datetime.now(tz=UTC))
