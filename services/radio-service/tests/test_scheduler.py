import json
from datetime import UTC, datetime

from google.api_core import exceptions as gcloud_exceptions
from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.scheduler import TickScheduler

END_AT = datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC)


class FakeTasksClient:
    def __init__(self, raise_already_exists: bool = False) -> None:
        self.created: list[dict] = []
        self._raise_already_exists = raise_already_exists

    def queue_path(self, project: str, location: str, queue: str) -> str:
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request: dict) -> object:
        if self._raise_already_exists:
            raise gcloud_exceptions.AlreadyExists("task exists")
        self.created.append(request)
        return object()


def _settings() -> Settings:
    return Settings(
        project_id="pulsefm-test",
        station_doc="station/current",
        songs_collection="songs",
        tick_url="https://radio.invalid/tick",
        queue_name="radio-queue",
        queue_location="us-central1",
        tick_service_account="tick@pulsefm-test.iam.gserviceaccount.com",
        pool_size=20,
    )


def test_schedule_creates_a_deterministically_named_oidc_task() -> None:
    client = FakeTasksClient()

    created = TickScheduler(client, _settings()).schedule(
        song_id="a", end_at=END_AT, version=8
    )

    assert created is True
    request = client.created[0]
    task = request["task"]
    assert task["name"].endswith("/tasks/tick-a-1785240232-8")
    assert task["http_request"]["url"] == "https://radio.invalid/tick"
    assert task["http_request"]["oidc_token"]["service_account_email"] == (
        "tick@pulsefm-test.iam.gserviceaccount.com"
    )
    assert json.loads(task["http_request"]["body"]) == {"version": 8}
    assert task["schedule_time"] == END_AT


def test_schedule_treats_an_existing_task_as_success() -> None:
    client = FakeTasksClient(raise_already_exists=True)

    created = TickScheduler(client, _settings()).schedule(
        song_id="a", end_at=END_AT, version=8
    )

    assert created is False
