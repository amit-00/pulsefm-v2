from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pulsefm_station_api.main import build_app

SERVER_TIME = datetime(2026, 7, 28, 12, 1, 0, tzinfo=UTC)

STATION = {
    "songId": "song-1",
    "startAt": datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
    "endAt": datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC),
    "durationMs": 232000,
    "nextSongId": "song-2",
    "nextStatus": "fallback",
    "version": 3,
}

SONGS = {
    "song-1": {
        "title": "Nightshift Drift",
        "artist": "Sable Unit",
        "descriptor": "melancholic",
        "objectPath": "tracks/song-1.m4a",
    },
    "song-2": {
        "title": "Pale Signal",
        "artist": "Wire Kite",
        "descriptor": "hypnotic",
        "objectPath": "tracks/song-2.m4a",
        "durationMs": 180000,
    },
}


class FakeRepository:
    def __init__(self, station: dict | None, songs: dict[str, dict]) -> None:
        self.station = station
        self.songs = songs

    def get_station(self) -> dict | None:
        return self.station

    def get_song(self, song_id: str) -> dict | None:
        return self.songs.get(song_id)


def _client(repository: FakeRepository) -> TestClient:
    return TestClient(
        build_app(
            repository,
            cdn_base_url="https://cdn.pulsefm.app",
            state_max_age_seconds=1,
            clock=lambda: SERVER_TIME,
        )
    )


def test_healthz_reports_ok() -> None:
    response = _client(FakeRepository(None, {})).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_state_returns_the_snapshot() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["serverTime"] == "2026-07-28T12:01:00Z"
    assert payload["current"]["songId"] == "song-1"
    assert payload["current"]["url"] == "https://cdn.pulsefm.app/tracks/song-1.m4a"
    assert payload["next"] == {"songId": "song-2", "status": "fallback"}


def test_state_is_publicly_cacheable_for_one_second() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/state")

    assert response.headers["cache-control"] == "public, max-age=1"


def test_state_returns_503_before_the_station_is_bootstrapped() -> None:
    response = _client(FakeRepository(None, {})).get("/v1/state")

    assert response.status_code == 503
    assert "not started" in response.json()["detail"]


def test_state_returns_503_when_the_song_document_is_missing() -> None:
    response = _client(FakeRepository(STATION, {})).get("/v1/state")

    assert response.status_code == 503


def test_queue_returns_current_then_next() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/queue")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["songId"] for item in items] == ["song-1", "song-2"]
    assert items[1]["url"] == "https://cdn.pulsefm.app/tracks/song-2.m4a"


def test_queue_omits_a_next_song_whose_document_is_absent() -> None:
    response = _client(FakeRepository(STATION, {"song-1": SONGS["song-1"]})).get("/v1/queue")

    assert [item["songId"] for item in response.json()["items"]] == ["song-1"]
