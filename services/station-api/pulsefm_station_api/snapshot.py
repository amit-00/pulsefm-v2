"""Pure assembly of the /v1/state payload.

No Firestore, no clock, no request context — the caller supplies all three.
That keeps URL composition and field mapping testable without an emulator.
"""

from datetime import datetime

from pulsefm_models.station import CurrentSong, NextUp, StateResponse


class MissingSongError(LookupError):
    """The station references a song document that does not exist."""


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
            url=f"{audio_base_url.rstrip('/')}/{song['objectPath'].lstrip('/')}",
            start_at=station["startAt"],
            end_at=station["endAt"],
            duration_ms=int(station["durationMs"]),
        ),
        next_up=NextUp(
            song_id=station.get("nextSongId"),
            status=station.get("nextStatus", "fallback"),
        ),
    )
