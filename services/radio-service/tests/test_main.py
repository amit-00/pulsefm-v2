import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pulsefm_radio_service.logic import CandidateSong, RotationPlan
from pulsefm_radio_service.main import build_app

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self, station: dict | None, pool: list[CandidateSong]) -> None:
        self.station = station
        self.pool = pool
        self.rotated: list[RotationPlan] = []
        self.bootstrapped: list[RotationPlan] = []
        self.rotate_result = True
        self.bootstrap_result = True

    def get_station(self) -> dict | None:
        return self.station

    def list_pool(self, limit: int) -> list[CandidateSong]:
        return self.pool

    def rotate(self, plan: RotationPlan) -> bool:
        self.rotated.append(plan)
        return self.rotate_result

    def bootstrap(self, plan: RotationPlan) -> bool:
        self.bootstrapped.append(plan)
        return self.bootstrap_result


class FakeScheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, datetime, int]] = []

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        self.scheduled.append((song_id, end_at, version))
        return True


class DedupSchedulerStub:
    """Mirrors TickScheduler when an equivalent task already existed."""

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        return False


class RaisingSchedulerStub:
    """Mirrors TickScheduler when create_task raises something other than
    AlreadyExists — an unexpected error that must not be swallowed."""

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        raise RuntimeError("cloud tasks unavailable")


def _client(repository: FakeRepository, scheduler: FakeScheduler) -> TestClient:
    return TestClient(build_app(repository, scheduler, clock=lambda: NOW))


def test_healthz_reports_ok() -> None:
    client = _client(FakeRepository(None, []), FakeScheduler())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bootstrap_starts_the_station_and_schedules_the_first_tick() -> None:
    repository = FakeRepository(None, [CandidateSong("a", 232000), CandidateSong("b", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/bootstrap")

    assert response.status_code == 200
    assert response.json() == {"status": "started", "songId": "a", "version": 1}
    assert scheduler.scheduled == [
        ("a", datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC), 1)
    ]


def test_bootstrap_fails_when_the_pool_is_empty() -> None:
    response = _client(FakeRepository(None, []), FakeScheduler()).post("/bootstrap")

    assert response.status_code == 503
    assert "no ready songs" in response.json()["detail"]


def test_bootstrap_is_a_no_op_when_the_station_already_runs() -> None:
    repository = FakeRepository(None, [CandidateSong("a", 1000)])
    repository.bootstrap_result = False

    response = _client(repository, FakeScheduler()).post("/bootstrap")

    assert response.status_code == 200
    assert response.json()["status"] == "already-running"


def test_tick_rotates_to_the_queued_song_and_chains_the_next_tick() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 180000), CandidateSong("a", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert response.json() == {"status": "rotated", "songId": "b", "version": 2}
    assert repository.rotated[0].song_id == "b"
    assert repository.rotated[0].next_song_id == "a"
    assert scheduler.scheduled == [
        ("b", datetime(2026, 7, 28, 12, 3, 0, tzinfo=UTC), 2)
    ]


def test_tick_with_a_stale_version_is_a_no_op() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 5}
    repository = FakeRepository(station, [CandidateSong("b", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 5})

    assert response.status_code == 200
    assert response.json() == {"status": "stale", "version": 5}
    assert repository.rotated == []
    assert scheduler.scheduled == []


def test_tick_loses_the_rotation_race_without_scheduling() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 1000)])
    repository.rotate_result = False
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert response.json()["status"] == "lost-race"
    assert scheduler.scheduled == []


def test_tick_before_bootstrap_reports_no_station() -> None:
    response = _client(FakeRepository(None, []), FakeScheduler()).post(
        "/tick", json={"version": 1}
    )

    assert response.status_code == 409
    assert "not bootstrapped" in response.json()["detail"]


def test_tick_falls_back_when_the_queued_song_left_the_pool() -> None:
    station = {"songId": "a", "nextSongId": "gone", "version": 1}
    repository = FakeRepository(station, [CandidateSong("c", 5000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert repository.rotated[0].song_id == "c"


def test_tick_logs_an_error_when_scheduling_does_not_create_a_task(
    caplog: pytest.LogCaptureFixture,
) -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 180000), CandidateSong("a", 1000)])

    with caplog.at_level(logging.ERROR):
        response = _client(repository, DedupSchedulerStub()).post("/tick", json={"version": 2})

    # The rotation itself still succeeded — a missing successor tick must
    # not be reported as a request failure.
    assert response.status_code == 200
    assert response.json()["status"] == "rotated"
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert "b" in caplog.text
    assert "2" in caplog.text


def test_bootstrap_logs_an_error_when_scheduling_does_not_create_a_task(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = FakeRepository(None, [CandidateSong("a", 232000)])

    with caplog.at_level(logging.ERROR):
        response = _client(repository, DedupSchedulerStub()).post("/bootstrap")

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_tick_scheduling_failure_surfaces_rather_than_being_swallowed() -> None:
    """An unexpected exception from schedule() (anything but AlreadyExists)
    must propagate: the rotation write is already durable, and Cloud Tasks
    retrying this delivery is the recovery path, not a caught-and-ignored
    error here."""
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 180000), CandidateSong("a", 1000)])

    client = _client(repository, RaisingSchedulerStub())

    with pytest.raises(RuntimeError, match="cloud tasks unavailable"):
        client.post("/tick", json={"version": 2})

    assert repository.rotated[0].song_id == "b"


def test_bootstrap_scheduling_failure_surfaces_rather_than_being_swallowed() -> None:
    repository = FakeRepository(None, [CandidateSong("a", 232000)])

    client = _client(repository, RaisingSchedulerStub())

    with pytest.raises(RuntimeError, match="cloud tasks unavailable"):
        client.post("/bootstrap")

    assert repository.bootstrapped[0].song_id == "a"
