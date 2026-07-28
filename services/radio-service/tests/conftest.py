import os
import uuid

import pytest
from google.cloud import firestore
from pulsefm_radio_service.config import Settings

REQUIRES_EMULATOR = "FIRESTORE_EMULATOR_HOST environment variable is not set"


@pytest.fixture
def settings() -> Settings:
    """Each test gets its own collection namespace so runs cannot collide."""
    suffix = uuid.uuid4().hex[:8]
    return Settings(
        project_id="pulsefm-test",
        station_doc=f"station_{suffix}/current",
        songs_collection=f"songs_{suffix}",
        tick_url="https://radio.invalid/tick",
        queue_name="radio-queue",
        queue_location="us-central1",
        tick_service_account="tick@pulsefm-test.iam.gserviceaccount.com",
        pool_size=20,
    )


@pytest.fixture
def firestore_client(settings: Settings) -> firestore.Client:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip(REQUIRES_EMULATOR)
    return firestore.Client(project=settings.project_id)
