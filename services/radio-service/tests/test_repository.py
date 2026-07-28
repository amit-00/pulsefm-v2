from datetime import UTC, datetime

import pytest
from google.cloud import firestore
from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.logic import CandidateSong, plan_rotation
from pulsefm_radio_service.repository import StationRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


def _seed_song(
    client: firestore.Client,
    settings: Settings,
    song_id: str,
    *,
    duration_ms: int,
    play_count: int,
    status: str = "ready",
) -> None:
    client.collection(settings.songs_collection).document(song_id).set(
        {
            "status": status,
            "durationMs": duration_ms,
            "playCount": play_count,
            "lastPlayedAt": NOW,
            "title": f"Title {song_id}",
            "artist": "Sable Unit",
            "descriptor": "melancholic",
            "objectPath": f"tracks/{song_id}.m4a",
        }
    )


def test_list_pool_returns_ready_songs_least_played_first(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "b", duration_ms=2000, play_count=5)
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=1)
    repo = StationRepository(firestore_client, settings)

    pool = repo.list_pool(limit=10)

    assert pool == [CandidateSong("a", 1000), CandidateSong("b", 2000)]


def test_list_pool_excludes_songs_that_are_not_ready(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=0)
    _seed_song(
        firestore_client, settings, "b", duration_ms=2000, play_count=0, status="generating"
    )
    repo = StationRepository(firestore_client, settings)

    assert [c.song_id for c in repo.list_pool(limit=10)] == ["a"]


def test_bootstrap_creates_the_station_document(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=0)
    repo = StationRepository(firestore_client, settings)
    plan = plan_rotation(
        promoted=CandidateSong("a", 1000), pool=[], now=NOW, current_version=0
    )

    assert repo.bootstrap(plan) is True

    station = repo.get_station()
    assert station is not None
    assert station["songId"] == "a"
    assert station["version"] == 1


def test_bootstrap_is_refused_once_the_station_exists(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=0)
    repo = StationRepository(firestore_client, settings)
    plan = plan_rotation(
        promoted=CandidateSong("a", 1000), pool=[], now=NOW, current_version=0
    )
    repo.bootstrap(plan)

    assert repo.bootstrap(plan) is False


def test_rotate_applies_a_newer_version(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=0)
    _seed_song(firestore_client, settings, "b", duration_ms=2000, play_count=0)
    repo = StationRepository(firestore_client, settings)
    repo.bootstrap(
        plan_rotation(promoted=CandidateSong("a", 1000), pool=[], now=NOW, current_version=0)
    )

    applied = repo.rotate(
        plan_rotation(
            promoted=CandidateSong("b", 2000),
            pool=[CandidateSong("a", 1000)],
            now=NOW,
            current_version=1,
        )
    )

    assert applied is True
    station = repo.get_station()
    assert station is not None
    assert station["songId"] == "b"
    assert station["version"] == 2


def test_rotate_rejects_a_stale_version(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=0)
    _seed_song(firestore_client, settings, "b", duration_ms=2000, play_count=0)
    repo = StationRepository(firestore_client, settings)
    repo.bootstrap(
        plan_rotation(promoted=CandidateSong("a", 1000), pool=[], now=NOW, current_version=0)
    )
    repo.rotate(
        plan_rotation(
            promoted=CandidateSong("b", 2000), pool=[], now=NOW, current_version=1
        )
    )

    replayed = repo.rotate(
        plan_rotation(
            promoted=CandidateSong("b", 2000), pool=[], now=NOW, current_version=1
        )
    )

    assert replayed is False
    station = repo.get_station()
    assert station is not None
    assert station["version"] == 2


def test_rotate_increments_the_play_counter(
    firestore_client: firestore.Client, settings: Settings
) -> None:
    _seed_song(firestore_client, settings, "a", duration_ms=1000, play_count=3)
    repo = StationRepository(firestore_client, settings)
    repo.bootstrap(
        plan_rotation(promoted=CandidateSong("a", 1000), pool=[], now=NOW, current_version=0)
    )

    song = repo.get_song("a")
    assert song is not None
    assert song["playCount"] == 4
