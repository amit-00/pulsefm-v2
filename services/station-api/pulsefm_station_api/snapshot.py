"""Pure assembly of the /v1/state payload.

No Firestore, no clock, no request context — the caller supplies all three.
That keeps URL composition and field mapping testable without an emulator.
"""

import re
from datetime import datetime

from pulsefm_models.station import CurrentSong, NextUp, StateResponse

# One object-path segment: alphanumeric first, then alphanumerics, dot,
# underscore, hyphen. Deliberately an allow-list. A deny-list on ".." would not
# hold — browsers also treat "%2e%2e", ".%2e" and "%2e." as double-dot segments
# (WHATWG URL, ASCII case-insensitive), so a substring check for ".." misses
# three spellings. Excluding "%" sidesteps all of them.
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class MissingSongError(LookupError):
    """The station references a song document that does not exist."""


class InvalidObjectPathError(ValueError):
    """A song's objectPath is not a plain relative path within the bucket."""


def compose_audio_url(audio_base_url: str, object_path: str) -> str:
    """Join the audio base URL with a song's object path.

    The base is `https://storage.googleapis.com/<bucket>`, which puts the
    bucket in a *path segment* rather than the host. A `..` segment therefore
    escapes into the global bucket namespace: browsers remove dot segments
    before fetching, so `<base>/../other-bucket/x` resolves to
    `https://storage.googleapis.com/other-bucket/x` and the player would fetch
    someone else's audio from a URL that still looks like the station's.

    Nothing untrusted writes `objectPath` today — the seed script is the only
    writer and it slugifies. This is the boundary where that assumption would
    break, so it is enforced rather than relied upon.
    """
    path = object_path.lstrip("/")
    if not path or any(not _SEGMENT.fullmatch(segment) for segment in path.split("/")):
        raise InvalidObjectPathError(
            f"objectPath {object_path!r} is not a plain relative path; "
            "each segment must match [A-Za-z0-9][A-Za-z0-9._-]*"
        )
    return f"{audio_base_url.rstrip('/')}/{path}"


def build_state(
    *,
    station: dict,
    song: dict | None,
    audio_base_url: str,
    server_time: datetime,
) -> StateResponse:
    song_id = station["songId"]
    if song is None:
        raise MissingSongError(
            f"Station references song {song_id!r} but no such document exists in Firestore"
        )

    return StateResponse(
        server_time=server_time,
        current=CurrentSong(
            song_id=song_id,
            title=song["title"],
            artist=song["artist"],
            descriptor=song["descriptor"],
            url=compose_audio_url(audio_base_url, song["objectPath"]),
            start_at=station["startAt"],
            end_at=station["endAt"],
            duration_ms=int(station["durationMs"]),
        ),
        next_up=NextUp(
            song_id=station.get("nextSongId"),
            status=station.get("nextStatus", "fallback"),
        ),
    )
