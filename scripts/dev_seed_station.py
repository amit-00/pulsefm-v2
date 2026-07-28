"""Seed the Firestore emulator with the Task 17 dev fixtures.

The real scripts/seed_tracks.py needs a GCS bucket to upload into. The local
verification harness has no bucket — audio is served straight out of
client/public/tracks/ by the Vite dev server (see the task-17 brief,
blocker 3) — so this writes the song documents directly, reading each
track's true duration back off the WAV file `dev_gen_tones.py` wrote, rather
than trusting the nominal duration in dev_fixtures.py.

Run after dev_gen_tones.py and with FIRESTORE_EMULATOR_HOST set:

    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 python3 -m scripts.dev_seed_station
"""

import os
import wave
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore

from scripts.dev_fixtures import DEV_TRACKS, TRACKS_SUBDIR, DevTrack

TRACKS_DIR = Path(__file__).resolve().parent.parent / "client" / "public" / TRACKS_SUBDIR
PROJECT_ID = "pulsefm-local"
SONGS_COLLECTION = "songs"
STATION_DOC = "station/current"


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        return round(handle.getnframes() / handle.getframerate() * 1000)


def _song_document(track: DevTrack, duration_ms: int) -> dict:
    return {
        "status": "ready",
        "title": track.title,
        "artist": track.artist,
        "descriptor": track.descriptor,
        "objectPath": f"{TRACKS_SUBDIR}/{track.song_id}.wav",
        "durationMs": duration_ms,
        "playCount": 0,
        "lastPlayedAt": datetime(1970, 1, 1, tzinfo=UTC),
        "pollId": None,
    }


def main() -> None:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        raise SystemExit(
            "FIRESTORE_EMULATOR_HOST is not set. Start the emulator first and export it, "
            "e.g. FIRESTORE_EMULATOR_HOST=127.0.0.1:8080"
        )

    client = firestore.Client(project=PROJECT_ID)

    # A leftover station doc from a previous run would let /bootstrap no-op
    # against fixtures that no longer exist.
    client.document(STATION_DOC).delete()

    for track in DEV_TRACKS:
        wav_path = TRACKS_DIR / f"{track.song_id}.wav"
        if not wav_path.exists():
            raise SystemExit(f"{wav_path} does not exist. Run scripts/dev_gen_tones.py first.")

        duration_ms = _wav_duration_ms(wav_path)
        client.collection(SONGS_COLLECTION).document(track.song_id).set(
            _song_document(track, duration_ms)
        )
        print(f"seeded {track.song_id} ({duration_ms} ms)")

    print(f"\n{len(DEV_TRACKS)} tracks seeded. Now POST /bootstrap on the dev radio-service.")


if __name__ == "__main__":
    main()
