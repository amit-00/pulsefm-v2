from datetime import UTC, datetime

from pulsefm_models.station import CurrentSong, NextUp, StateResponse


def _current() -> CurrentSong:
    return CurrentSong(
        song_id="song-1",
        title="Nightshift Drift",
        artist="Sable Unit",
        descriptor="melancholic",
        url="https://cdn.example/tracks/song-1.m4a",
        start_at=datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC),
        duration_ms=232000,
    )


def test_state_response_serialises_to_camel_case() -> None:
    response = StateResponse(
        server_time=datetime(2026, 7, 28, 12, 1, 0, tzinfo=UTC),
        current=_current(),
        next_up=NextUp(song_id="song-2", status="fallback"),
    )

    payload = response.model_dump(by_alias=True, mode="json")

    assert payload["serverTime"] == "2026-07-28T12:01:00.000Z"
    assert payload["current"]["songId"] == "song-1"
    assert payload["current"]["durationMs"] == 232000
    assert payload["current"]["startAt"] == "2026-07-28T12:00:00.000Z"
    assert payload["next"] == {"songId": "song-2", "status": "fallback"}


def test_next_up_allows_absent_song() -> None:
    payload = NextUp(song_id=None, status="generating").model_dump(by_alias=True, mode="json")

    assert payload == {"songId": None, "status": "generating"}


def test_state_response_preserves_sub_second_precision() -> None:
    response = StateResponse(
        server_time=datetime(2026, 7, 28, 12, 1, 0, 123456, tzinfo=UTC),
        current=_current(),
        next_up=NextUp(song_id="song-2", status="fallback"),
    )

    payload = response.model_dump(by_alias=True, mode="json")

    # microseconds truncate to milliseconds, not to whole seconds
    assert payload["serverTime"] == "2026-07-28T12:01:00.123Z"
