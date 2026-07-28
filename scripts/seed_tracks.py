"""Seed the fallback pool with pre-generated tracks.

Slice 1 has no generation, so every song the station plays comes from here.
Run once against a fresh project, before POST /bootstrap.

Usage:
    uv run python -m scripts.seed_tracks --bucket pulsefm-v2-songs --dir ./seed-audio

Each .m4a in --dir becomes one song. Duration is read with ffprobe.
"""

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore, storage

ARTISTS = ["Sable Unit", "Wire Kite", "Low Ember", "Paper Transit"]
DESCRIPTORS = ["melancholic", "hypnotic", "groovy", "ethereal", "laidback"]


@dataclass(frozen=True)
class SeedTrack:
    song_id: str
    title: str
    artist: str
    descriptor: str
    duration_ms: int
    source_path: str


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot build a song id from {name!r}: no usable characters")
    return slug


def probe_duration_ms(path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    seconds = float(json.loads(result.stdout)["format"]["duration"])
    return int(seconds * 1000)


def build_song_document(track: SeedTrack) -> dict:
    return {
        "status": "ready",
        "title": track.title,
        "artist": track.artist,
        "descriptor": track.descriptor,
        "objectPath": f"tracks/{track.song_id}.m4a",
        "durationMs": track.duration_ms,
        "playCount": 0,
        "lastPlayedAt": datetime(1970, 1, 1, tzinfo=UTC),
        "pollId": None,
    }


def discover_tracks(directory: Path) -> list[SeedTrack]:
    tracks: list[SeedTrack] = []
    for index, path in enumerate(sorted(directory.glob("*.m4a"))):
        title = path.stem.replace("-", " ").replace("_", " ").title()
        tracks.append(
            SeedTrack(
                song_id=slugify(path.stem),
                title=title,
                artist=ARTISTS[index % len(ARTISTS)],
                descriptor=DESCRIPTORS[index % len(DESCRIPTORS)],
                duration_ms=probe_duration_ms(path),
                source_path=str(path),
            )
        )
    return tracks


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the PulseFM fallback pool.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--project", default=None)
    parser.add_argument("--songs-collection", default="songs")
    args = parser.parse_args()

    tracks = discover_tracks(args.dir)
    if not tracks:
        raise SystemExit(f"No .m4a files found in {args.dir}")

    bucket = storage.Client(project=args.project).bucket(args.bucket)
    firestore_client = firestore.Client(project=args.project)

    for track in tracks:
        blob = bucket.blob(f"tracks/{track.song_id}.m4a")
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.content_type = "audio/mp4"
        blob.upload_from_filename(track.source_path)

        firestore_client.collection(args.songs_collection).document(track.song_id).set(
            build_song_document(track)
        )
        print(f"seeded {track.song_id} ({track.duration_ms} ms)")

    print(f"\n{len(tracks)} tracks seeded. Now: curl -X POST <radio-service>/bootstrap")


if __name__ == "__main__":
    main()
