from datetime import UTC, datetime

import pytest
from pulsefm_station_api.snapshot import MissingSongError, build_state

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

SONG = {
    "title": "Nightshift Drift",
    "artist": "Sable Unit",
    "descriptor": "melancholic",
    "objectPath": "tracks/song-1.m4a",
}


def test_build_state_composes_the_cdn_url() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        audio_base_url="https://cdn.pulsefm.app",
        server_time=SERVER_TIME,
    )

    assert state.current.url == "https://cdn.pulsefm.app/tracks/song-1.m4a"


def test_build_state_tolerates_a_trailing_slash_on_the_base_url() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        audio_base_url="https://cdn.pulsefm.app/",
        server_time=SERVER_TIME,
    )

    assert state.current.url == "https://cdn.pulsefm.app/tracks/song-1.m4a"


def test_build_state_carries_song_metadata_and_next_up() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        audio_base_url="https://cdn.pulsefm.app",
        server_time=SERVER_TIME,
    )

    assert state.current.title == "Nightshift Drift"
    assert state.current.artist == "Sable Unit"
    assert state.current.duration_ms == 232000
    assert state.next_up.song_id == "song-2"
    assert state.next_up.status == "fallback"
    assert state.server_time == SERVER_TIME


def test_build_state_rejects_a_song_document_that_is_missing() -> None:
    with pytest.raises(MissingSongError, match="song-1"):
        build_state(
            station=STATION,
            song=None,
            audio_base_url="https://cdn.pulsefm.app",
            server_time=SERVER_TIME,
        )
