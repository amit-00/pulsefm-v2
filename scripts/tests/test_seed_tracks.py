import subprocess
from pathlib import Path

import pytest

from scripts.seed_tracks import SeedTrack, build_song_document, probe_duration_ms, slugify


def test_slugify_produces_a_cloud_tasks_safe_id() -> None:
    assert slugify("Nightshift Drift") == "nightshift-drift"
    assert slugify("Pale  Signal!!") == "pale-signal"


def test_slugify_rejects_a_name_with_no_usable_characters() -> None:
    with pytest.raises(ValueError, match="no usable characters"):
        slugify("!!!")


def test_build_song_document_marks_the_track_ready() -> None:
    track = SeedTrack(
        song_id="nightshift-drift",
        title="Nightshift Drift",
        artist="Sable Unit",
        descriptor="melancholic",
        duration_ms=232000,
        source_path="/tmp/nightshift.m4a",
    )

    document = build_song_document(track)

    assert document["status"] == "ready"
    assert document["objectPath"] == "tracks/nightshift-drift.m4a"
    assert document["durationMs"] == 232000
    assert document["playCount"] == 0
    assert document["title"] == "Nightshift Drift"


def test_probe_duration_ms_reports_a_missing_ffprobe_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        probe_duration_ms(Path("/tmp/nightshift.m4a"))


def test_probe_duration_ms_reports_missing_duration_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResult:
        stdout = '{"format": {}}'

    def fake_run(*args: object, **kwargs: object) -> FakeResult:
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="nightshift.m4a"):
        probe_duration_ms(Path("/tmp/nightshift.m4a"))
