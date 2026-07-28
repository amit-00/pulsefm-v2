"""Pure decision core for song rotation.

No Firestore, no network, no wall clock. Every function here is deterministic
given its arguments, which is what makes rotation testable at all: the same
logic living inside a Firestore transaction cannot be exercised without an
emulator, and the interesting cases (stale versions, exhausted pools) are the
hardest ones to provoke through I/O.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pulsefm_models.station import NextStatus


@dataclass(frozen=True)
class CandidateSong:
    song_id: str
    duration_ms: int


@dataclass(frozen=True)
class RotationPlan:
    song_id: str
    start_at: datetime
    end_at: datetime
    duration_ms: int
    next_song_id: str
    next_status: NextStatus
    version: int


def is_stale_version(request_version: int, current_version: int) -> bool:
    """Cloud Tasks delivers at least once; a replayed tick must be a no-op."""
    return request_version <= current_version


def select_following(pool: list[CandidateSong], exclude_song_id: str) -> CandidateSong | None:
    """Pick the song to queue after `exclude_song_id`.

    The pool arrives already ordered by the repository (least played, least
    recently played first), so the first eligible entry is the right one.
    """
    for candidate in pool:
        if candidate.song_id != exclude_song_id:
            return candidate
    return None


def resolve_promoted(
    pool: list[CandidateSong], preferred_song_id: str | None
) -> CandidateSong | None:
    """Prefer the queued song; fall back to the pool head when it is gone.

    A song can leave the pool between being queued and being promoted, so the
    queued id is a preference, never a guarantee.
    """
    if preferred_song_id is not None:
        for candidate in pool:
            if candidate.song_id == preferred_song_id:
                return candidate
    return pool[0] if pool else None


def plan_rotation(
    *,
    promoted: CandidateSong,
    pool: list[CandidateSong],
    now: datetime,
    current_version: int,
) -> RotationPlan:
    """Promote `promoted` to now-playing and choose what follows it."""
    if promoted.duration_ms <= 0:
        raise ValueError(
            f"duration_ms must be positive, got {promoted.duration_ms} "
            f"for song {promoted.song_id!r}"
        )

    # A single-song station replays that song rather than stalling. Slice 1 is
    # seeded with several tracks, so this is a degenerate-case guard only.
    following = select_following(pool, exclude_song_id=promoted.song_id) or promoted

    return RotationPlan(
        song_id=promoted.song_id,
        start_at=now,
        end_at=now + timedelta(milliseconds=promoted.duration_ms),
        duration_ms=promoted.duration_ms,
        next_song_id=following.song_id,
        next_status="fallback",
        version=current_version + 1,
    )


def build_tick_task_id(song_id: str, end_at: datetime, version: int) -> str:
    """Deterministic Cloud Tasks name so duplicate scheduling is rejected by ID.

    Cloud Tasks accepts only letters, digits, hyphens, and underscores, so
    song ids must stay within that alphabet.
    """
    return f"tick-{song_id}-{int(end_at.timestamp())}-{version}"
