"""Shared track definitions for the Task 17 local verification harness.

Throwaway dev tooling only — not used by any production code path.
`dev_gen_tones.py` writes the WAV fixtures these describe, and
`dev_seed_station.py` seeds the Firestore emulator with matching song
documents. Keeping the list in one place stops the two scripts from
silently drifting apart (same song ids, same track count).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DevTrack:
    song_id: str
    title: str
    artist: str
    descriptor: str
    freq_hz: float
    duration_s: float


# Three distinct pitches, sized generously (12-15 min) rather than the 20-30s
# originally planned: boundaries are forced by hand with POST /tick
# regardless of length, but each browser-automation round trip (screenshot,
# JS eval, click) has multiple seconds of real latency, and a handful of them
# in sequence must not run past the end of the track under test.
DEV_TRACKS: list[DevTrack] = [
    DevTrack("tone-a", "Tone A / Middle C", "Dev Harness", "sine", 261.63, 900),
    DevTrack("tone-b", "Tone B / E Above Middle C", "Dev Harness", "sine", 329.63, 720),
    DevTrack("tone-c", "Tone C / G Above Middle C", "Dev Harness", "sine", 392.00, 800),
]

TRACKS_SUBDIR = "tracks"
