from datetime import UTC, datetime

import pytest
from pulsefm_station_api.snapshot import (
    InvalidObjectPathError,
    MissingSongError,
    build_state,
    compose_audio_url,
)

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


BUCKET_BASE = "https://storage.googleapis.com/pulsefm-v2-songs"


def test_compose_audio_url_joins_base_and_object_path() -> None:
    assert (
        compose_audio_url(BUCKET_BASE, "tracks/nightshift-drift.m4a")
        == f"{BUCKET_BASE}/tracks/nightshift-drift.m4a"
    )


def test_compose_audio_url_normalises_slashes_at_the_join() -> None:
    assert (
        compose_audio_url(f"{BUCKET_BASE}/", "/tracks/a.m4a")
        == f"{BUCKET_BASE}/tracks/a.m4a"
    )


@pytest.mark.parametrize(
    "object_path",
    [
        "../attacker-bucket/x.m4a",
        "a/../../attacker-bucket/x.m4a",
        "tracks/../../attacker-bucket/x.m4a",
        # Browsers treat these as double-dot segments too, so a substring
        # check for ".." would let all three through.
        "%2e%2e/attacker-bucket/x.m4a",
        "%2E%2e/attacker-bucket/x.m4a",
        ".%2e/attacker-bucket/x.m4a",
    ],
)
def test_compose_audio_url_rejects_traversal_out_of_the_bucket(object_path: str) -> None:
    # The bucket is a path segment of the base URL, so a surviving `..` would
    # resolve to a different bucket entirely once the browser normalises it.
    with pytest.raises(InvalidObjectPathError):
        compose_audio_url(BUCKET_BASE, object_path)


@pytest.mark.parametrize(
    "object_path",
    ["", "/", "https://evil.example/x.m4a", "tracks//a.m4a"],
)
def test_compose_audio_url_rejects_non_relative_paths(object_path: str) -> None:
    with pytest.raises(InvalidObjectPathError):
        compose_audio_url(BUCKET_BASE, object_path)


def test_compose_audio_url_flattens_a_protocol_relative_path_into_the_bucket() -> None:
    # Not a traversal: stripping the leading slashes turns the would-be host
    # into an ordinary path segment, so the URL stays inside the bucket.
    assert (
        compose_audio_url(BUCKET_BASE, "//evil.example/x.m4a")
        == f"{BUCKET_BASE}/evil.example/x.m4a"
    )
