"""Generate short sine-wave WAV fixtures for the Task 17 local verification.

The local bring-up has no ffmpeg and no real audio on this machine (see the
task-17 brief, blocker 2). Browsers play WAV natively, so a few seconds of a
pure tone per track — different pitches so a changeover is audible — is
enough to verify sync. Uses only the Python stdlib (`wave`), so it needs no
project dependencies: `python3 scripts/dev_gen_tones.py`.

Output goes to client/public/tracks/, which is gitignored: these are
generated fixtures, not source.
"""

import math
import struct
import wave
from pathlib import Path

from scripts.dev_fixtures import DEV_TRACKS, TRACKS_SUBDIR, DevTrack

SAMPLE_RATE = 44100
AMPLITUDE = 0.4
FADE_MS = 80

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "client" / "public" / TRACKS_SUBDIR


def _samples(freq_hz: float, duration_s: float) -> list[int]:
    total = int(SAMPLE_RATE * duration_s)
    fade_samples = int(SAMPLE_RATE * FADE_MS / 1000)
    samples: list[int] = []
    for i in range(total):
        value = AMPLITUDE * math.sin(2 * math.pi * freq_hz * i / SAMPLE_RATE)
        if i < fade_samples:
            value *= i / fade_samples
        elif i > total - fade_samples:
            value *= (total - i) / fade_samples
        samples.append(int(value * 32767))
    return samples


def write_wav(path: Path, track: DevTrack) -> int:
    """Write the tone and return its actual duration in milliseconds."""
    samples = _samples(track.freq_hz, track.duration_s)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return round(len(samples) / SAMPLE_RATE * 1000)


def main() -> None:
    for track in DEV_TRACKS:
        path = OUTPUT_DIR / f"{track.song_id}.wav"
        duration_ms = write_wav(path, track)
        print(f"wrote {path} ({duration_ms} ms, {track.freq_hz} Hz)")


if __name__ == "__main__":
    main()
