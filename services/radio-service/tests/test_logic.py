from datetime import UTC, datetime

import pytest
from pulsefm_radio_service.logic import (
    CandidateSong,
    build_tick_task_id,
    is_stale_version,
    plan_rotation,
    resolve_promoted,
    select_following,
)

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


def test_version_at_or_below_current_is_stale() -> None:
    assert is_stale_version(4, 5) is True
    assert is_stale_version(5, 5) is True
    assert is_stale_version(6, 5) is False


def test_select_following_skips_the_song_being_promoted() -> None:
    pool = [CandidateSong("a", 1000), CandidateSong("b", 2000)]

    assert select_following(pool, exclude_song_id="a") == CandidateSong("b", 2000)


def test_select_following_returns_none_when_pool_has_only_the_excluded_song() -> None:
    assert select_following([CandidateSong("a", 1000)], exclude_song_id="a") is None


def test_select_following_returns_none_for_an_empty_pool() -> None:
    assert select_following([], exclude_song_id="a") is None


def test_resolve_promoted_returns_the_preferred_song_when_present() -> None:
    pool = [CandidateSong("a", 1000), CandidateSong("b", 2000)]

    assert resolve_promoted(pool, "b") == CandidateSong("b", 2000)


def test_resolve_promoted_falls_back_to_the_pool_head_when_preferred_is_absent() -> None:
    pool = [CandidateSong("a", 1000), CandidateSong("b", 2000)]

    assert resolve_promoted(pool, "gone") == CandidateSong("a", 1000)


def test_resolve_promoted_returns_none_for_an_empty_pool() -> None:
    assert resolve_promoted([], "a") is None


def test_resolve_promoted_returns_the_pool_head_when_no_preference_is_given() -> None:
    pool = [CandidateSong("a", 1000), CandidateSong("b", 2000)]

    assert resolve_promoted(pool, None) == CandidateSong("a", 1000)


def test_plan_rotation_promotes_and_derives_the_window() -> None:
    plan = plan_rotation(
        promoted=CandidateSong("a", 232000),
        pool=[CandidateSong("a", 232000), CandidateSong("b", 180000)],
        now=NOW,
        current_version=7,
    )

    assert plan.song_id == "a"
    assert plan.start_at == NOW
    assert plan.end_at == datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC)
    assert plan.duration_ms == 232000
    assert plan.next_song_id == "b"
    assert plan.next_status == "fallback"
    assert plan.version == 8


def test_plan_rotation_replays_the_current_song_when_it_is_the_only_one() -> None:
    plan = plan_rotation(
        promoted=CandidateSong("a", 1000),
        pool=[CandidateSong("a", 1000)],
        now=NOW,
        current_version=1,
    )

    assert plan.next_song_id == "a"


def test_plan_rotation_rejects_a_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="duration_ms must be positive"):
        plan_rotation(
            promoted=CandidateSong("a", 0),
            pool=[],
            now=NOW,
            current_version=1,
        )


def test_tick_task_id_is_deterministic_and_version_scoped() -> None:
    end_at = datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC)

    assert build_tick_task_id("a", end_at, 8) == "tick-a-1785240232-8"
    assert build_tick_task_id("a", end_at, 8) == build_tick_task_id("a", end_at, 8)
    assert build_tick_task_id("a", end_at, 9) != build_tick_task_id("a", end_at, 8)
