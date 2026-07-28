# PulseFM v2 — Slices 0 & 1: Foundations and the Playback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed radio station that rotates through a seeded set of tracks on a server-driven clock, with a React player that joins mid-song in sync with every other listener.

**Architecture:** Two Python services on Cloud Run. `radio-service` (internal ingress) owns the rotation clock, driven by self-chaining Cloud Tasks; it is the only writer of station state. `station-api` (public) serves a single cacheable snapshot document. A Vite/React SPA on Firebase Hosting polls that snapshot, computes a server-clock offset, and seeks into an `.m4a` served from a public GCS bucket behind Cloud CDN.

**Tech Stack:** Python 3.12, FastAPI, uv workspace, Firestore, Cloud Tasks, Cloud Run, Terraform, Vite, React 19, TypeScript, Tailwind CSS v4, Vitest, Firebase Hosting.

**Design source:** `docs/superpowers/specs/2026-07-28-pulsefm-v2-design.md`. Slices 0 and 1 only.

## Global Constraints

- **Python 3.12.** `requires-python = ">=3.12"` in every package.
- **No polls, no voting, no auth, no Modal in this plan.** The poll panel, Firebase Auth, API Gateway, and generation land in slices 2–3. Do not build them. The nav renders `HOW IT WORKS` and `LOGIN` as static anchors for design fidelity only.
- **The waveform uses the handoff's deterministic `amp()` profile, not a WebAudio analyser.** The analyser is slice 4. The bucket CORS configuration is still built here, because the analyser needs it and infrastructure is slice 0's job.
- **Design tokens are exact.** `--color-canvas: #DEDDD8`, `--color-bone: #EDECE7`, `--color-ink: #111111`, `--color-paper: #F2F1EF`, `--color-accent: #D6252B`, `--color-accent-on-ink: #FF7A7E`.
- **Copy is exact.** Brand `PULSE FM`. Desktop nav `HOW IT WORKS` then `LOGIN`. Mobile nav `LOGIN` only. Desktop sub-label is `{ARTIST} / WAVEFORM STEREO` uppercase. Mobile stage label is `WAVEFORM / STEREO`.
- **Typography.** Doto (400/600/800) for uppercase micro-labels and numerals only; Helvetica Neue for titles and body. Doto is self-hosted, never loaded from Google Fonts at runtime.
- **`GET /v1/state` sets `Cache-Control: public, max-age=1`** and is identical for every listener. It must never contain per-user data.
- **All timestamps are UTC ISO-8601 with milliseconds and a `Z` suffix**, both in Firestore and on the wire.
- **JSON on the wire is camelCase.** Python is snake_case. Pydantic alias generators bridge the two; never hand-write camelCase in Python identifiers.
- **Naming.** Python packages `pulsefm_<name>`, distributions `pulsefm-<name>`, service directories `services/<name>`.
- **Commit after every task.** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `infra:`).

## File Structure

```
pulsefm-v2/
├── pyproject.toml                  uv workspace root + shared pytest config
├── .github/workflows/ci.yml        unit tests, integration tests, client tests
├── packages/
│   └── pulsefm-models/             wire models shared by both services
│       └── pulsefm_models/station.py
├── services/
│   ├── radio-service/
│   │   └── pulsefm_radio_service/
│   │       ├── config.py           env-derived settings
│   │       ├── logic.py            PURE decision core — no I/O, no Firestore
│   │       ├── repository.py       Firestore reads + version-guarded rotate
│   │       ├── scheduler.py        Cloud Tasks tick chaining
│   │       └── main.py             FastAPI handlers, wiring only
│   └── station-api/
│       └── pulsefm_station_api/
│           ├── config.py
│           ├── repository.py       Firestore reads
│           ├── snapshot.py         PURE snapshot assembly
│           └── main.py
├── client/
│   └── src/
│       ├── lib/{clock,format,pollDiff,api}.ts    pure, unit-tested
│       ├── hooks/{useStation,useAudioSlots}.ts
│       ├── components/{Player,Waveform,TransportSheet,Header,PlayGlyph,ProgressRail}.tsx
│       └── styles/tokens.css
├── terraform/
│   ├── {versions,providers,variables,apis,outputs}.tf
│   ├── firestore.tf, artifact_registry.tf, service_accounts.tf, iam.tf
│   ├── storage.tf                  bucket + CORS + CDN backend
│   └── cloud_run.tf, cloudtasks.tf
└── scripts/seed_tracks.py
```

The split that matters: `logic.py` and `snapshot.py` contain every decision and zero I/O. They are unit-testable without an emulator, a network, or a clock. v1 extracted this logic only after it proved untestable inline inside a Firestore transaction — this plan starts there.

---

### Task 1: Repo scaffold, uv workspace, and CI

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `packages/pulsefm-models/pyproject.toml`
- Create: `packages/pulsefm-models/pulsefm_models/__init__.py`
- Test: `packages/pulsefm-models/tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a `uv` workspace where `uv run pytest packages/ services/` works, and a CI workflow other tasks extend.

- [ ] **Step 1: Write the failing test**

`packages/pulsefm-models/tests/test_smoke.py`:

```python
def test_package_imports() -> None:
    import pulsefm_models

    assert pulsefm_models.__name__ == "pulsefm_models"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/ -v`
Expected: FAIL — no workspace, no `pyproject.toml`.

- [ ] **Step 3: Create the workspace root**

`pyproject.toml`:

```toml
# Rootdir-level pytest config so multi-directory runs (packages + services) share
# settings; per-package configs only apply when pytest's rootdir resolves there.
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires the Firestore emulator (FIRESTORE_EMULATOR_HOST)",
]

[tool.uv.workspace]
members = ["services/*", "packages/*"]

[tool.uv.sources]
pulsefm-models = { workspace = true }

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

`.gitignore`:

```
__pycache__/
*.egg-info/
.venv/
.pytest_cache/
.ruff_cache/
node_modules/
dist/
.env
.env.*
!.env.example
.terraform/
*.tfstate
*.tfstate.*
.firebase/
```

- [ ] **Step 4: Create the models package**

`packages/pulsefm-models/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pulsefm-models"
version = "0.1.0"
description = "Shared wire models for PulseFM services."
requires-python = ">=3.12"
dependencies = ["pydantic>=2.9"]

[tool.setuptools.packages.find]
where = ["."]
include = ["pulsefm_models*"]

[dependency-groups]
dev = ["pytest>=8.0"]
```

`packages/pulsefm-models/pulsefm_models/__init__.py`: empty file.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv sync --all-packages && uv run pytest packages/ -v`
Expected: PASS.

- [ ] **Step 6: Add CI**

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  python-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - name: Sync workspace
        run: uv sync --all-packages
      - name: Lint
        run: uv run ruff check .
      - name: Unit tests
        run: uv run pytest packages/ services/ -v -m "not integration"
```

- [ ] **Step 7: Verify lint and tests pass locally**

Run: `uv run ruff check . && uv run pytest packages/ services/ -v -m "not integration"`
Expected: both PASS. `services/` is empty, which pytest reports as no tests collected — that is fine.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .github packages
git commit -m "chore: scaffold uv workspace, models package, and CI"
```

---

### Task 2: Wire models

**Files:**
- Create: `packages/pulsefm-models/pulsefm_models/station.py`
- Modify: `packages/pulsefm-models/pulsefm_models/__init__.py`
- Test: `packages/pulsefm-models/tests/test_station.py`

**Interfaces:**
- Consumes: Task 1's workspace.
- Produces: `CamelModel`, `CurrentSong`, `NextUp`, `StateResponse`, `QueueResponse`. Every service serialises with `model_dump(by_alias=True, mode="json")`.

- [ ] **Step 1: Write the failing test**

`packages/pulsefm-models/tests/test_station.py`:

```python
from datetime import UTC, datetime

from pulsefm_models.station import CurrentSong, NextUp, StateResponse


def _current() -> CurrentSong:
    return CurrentSong(
        song_id="song-1",
        title="Nightshift Drift",
        artist="Sable Unit",
        descriptor="melancholic",
        url="https://cdn.example/tracks/song-1.m4a",
        start_at=datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC),
        duration_ms=232000,
    )


def test_state_response_serialises_to_camel_case() -> None:
    response = StateResponse(
        server_time=datetime(2026, 7, 28, 12, 1, 0, tzinfo=UTC),
        current=_current(),
        next_up=NextUp(song_id="song-2", status="fallback"),
    )

    payload = response.model_dump(by_alias=True, mode="json")

    assert payload["serverTime"] == "2026-07-28T12:01:00Z"
    assert payload["current"]["songId"] == "song-1"
    assert payload["current"]["durationMs"] == 232000
    assert payload["current"]["startAt"] == "2026-07-28T12:00:00Z"
    assert payload["next"] == {"songId": "song-2", "status": "fallback"}


def test_next_up_allows_absent_song() -> None:
    payload = NextUp(song_id=None, status="generating").model_dump(by_alias=True, mode="json")

    assert payload == {"songId": None, "status": "generating"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/pulsefm-models/tests/test_station.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulsefm_models.station'`.

- [ ] **Step 3: Write the implementation**

`packages/pulsefm-models/pulsefm_models/station.py`:

```python
"""Wire models shared by station-api and radio-service.

Python stays snake_case; JSON on the wire is camelCase. The alias generator is
the only place that mapping lives — never hand-write camelCase identifiers.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel


def _iso_z(value: datetime) -> str:
    """Render as UTC ISO-8601 with a Z suffix, which JS Date parses natively."""
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_iso_z, return_type=str, when_used="json")]

NextStatus = Literal["generating", "ready", "fallback"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CurrentSong(CamelModel):
    song_id: str
    title: str
    artist: str
    descriptor: str
    url: str
    start_at: UtcDatetime
    end_at: UtcDatetime
    duration_ms: int


class NextUp(CamelModel):
    song_id: str | None
    status: NextStatus


class StateResponse(CamelModel):
    server_time: UtcDatetime
    current: CurrentSong
    next_up: NextUp = Field(alias="next")


class QueueResponse(CamelModel):
    items: list[CurrentSong]
```

`packages/pulsefm-models/pulsefm_models/__init__.py`:

```python
from pulsefm_models.station import (
    CamelModel,
    CurrentSong,
    NextStatus,
    NextUp,
    QueueResponse,
    StateResponse,
)

__all__ = [
    "CamelModel",
    "CurrentSong",
    "NextStatus",
    "NextUp",
    "QueueResponse",
    "StateResponse",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/pulsefm-models/tests/ -v`
Expected: PASS (3 tests, including the smoke test).

- [ ] **Step 5: Commit**

```bash
git add packages/pulsefm-models
git commit -m "feat(models): add station wire models with camelCase aliases"
```

---

### Task 3: radio-service pure decision core

This is the most important task in the plan. Every rotation decision lives here as a pure function so it can be tested without Firestore, without a clock, and without a network. v1 extracted this only after it proved untestable inline.

**Files:**
- Create: `services/radio-service/pyproject.toml`
- Create: `services/radio-service/pulsefm_radio_service/__init__.py`
- Create: `services/radio-service/pulsefm_radio_service/logic.py`
- Test: `services/radio-service/tests/test_logic.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `CandidateSong(song_id: str, duration_ms: int)` — frozen dataclass
  - `RotationPlan(song_id, start_at, end_at, duration_ms, next_song_id, next_status, version)` — frozen dataclass
  - `is_stale_version(request_version: int, current_version: int) -> bool`
  - `select_following(pool: list[CandidateSong], exclude_song_id: str) -> CandidateSong | None`
  - `plan_rotation(*, promoted, pool, now, current_version) -> RotationPlan`
  - `build_tick_task_id(song_id: str, end_at: datetime, version: int) -> str`

- [ ] **Step 1: Write the failing tests**

`services/radio-service/tests/test_logic.py`:

```python
from datetime import UTC, datetime

import pytest

from pulsefm_radio_service.logic import (
    CandidateSong,
    build_tick_task_id,
    is_stale_version,
    plan_rotation,
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest services/radio-service/tests/test_logic.py -v`
Expected: FAIL — the package does not exist.

- [ ] **Step 3: Create the service package**

`services/radio-service/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pulsefm-radio-service"
version = "0.1.0"
description = "PulseFM rotation clock and station state owner."
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "google-cloud-firestore>=2.19",
  "google-cloud-tasks>=2.17",
  "pulsefm-models",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["pulsefm_radio_service*"]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "httpx>=0.28"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`services/radio-service/pulsefm_radio_service/__init__.py`: empty file.

- [ ] **Step 4: Write the implementation**

`services/radio-service/pulsefm_radio_service/logic.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest services/radio-service/tests/test_logic.py -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit**

```bash
git add services/radio-service
git commit -m "feat(radio): add pure rotation decision core"
```

---

### Task 4: radio-service Firestore repository

**Files:**
- Create: `services/radio-service/pulsefm_radio_service/config.py`
- Create: `services/radio-service/pulsefm_radio_service/repository.py`
- Test: `services/radio-service/tests/conftest.py`
- Test: `services/radio-service/tests/test_repository.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `CandidateSong`, `RotationPlan` from Task 3.
- Produces:
  - `Settings` with `project_id`, `station_doc`, `songs_collection`, `tick_url`, `queue_name`, `queue_location`, `tick_service_account`, `pool_size`
  - `StationRepository(client, settings)` with `get_station() -> dict | None`, `list_pool(limit) -> list[CandidateSong]`, `get_song(song_id) -> dict | None`, `rotate(plan) -> bool`, `bootstrap(plan) -> bool`

- [ ] **Step 1: Write the failing tests**

`services/radio-service/tests/conftest.py`:

```python
import os
import uuid

import pytest
from google.cloud import firestore

from pulsefm_radio_service.config import Settings

REQUIRES_EMULATOR = "FIRESTORE_EMULATOR_HOST environment variable is not set"


@pytest.fixture
def settings() -> Settings:
    """Each test gets its own collection namespace so runs cannot collide."""
    suffix = uuid.uuid4().hex[:8]
    return Settings(
        project_id="pulsefm-test",
        station_doc=f"station_{suffix}/current",
        songs_collection=f"songs_{suffix}",
        tick_url="https://radio.invalid/tick",
        queue_name="radio-queue",
        queue_location="us-central1",
        tick_service_account="tick@pulsefm-test.iam.gserviceaccount.com",
        pool_size=20,
    )


@pytest.fixture
def firestore_client(settings: Settings) -> firestore.Client:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip(REQUIRES_EMULATOR)
    return firestore.Client(project=settings.project_id)
```

`services/radio-service/tests/test_repository.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest services/radio-service/tests/test_repository.py -v -m integration`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulsefm_radio_service.config'`.

- [ ] **Step 3: Write the config**

`services/radio-service/pulsefm_radio_service/config.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_id: str
    station_doc: str
    songs_collection: str
    tick_url: str
    queue_name: str
    queue_location: str
    tick_service_account: str
    pool_size: int


def settings_from_env() -> Settings:
    return Settings(
        project_id=os.environ["PROJECT_ID"],
        station_doc=os.getenv("STATION_DOC", "station/current"),
        songs_collection=os.getenv("SONGS_COLLECTION", "songs"),
        tick_url=os.environ["TICK_URL"],
        queue_name=os.getenv("RADIO_QUEUE_NAME", "radio-queue"),
        queue_location=os.getenv("RADIO_QUEUE_LOCATION", "us-central1"),
        tick_service_account=os.environ["TICK_SERVICE_ACCOUNT"],
        pool_size=int(os.getenv("POOL_SIZE", "20")),
    )
```

- [ ] **Step 4: Write the repository**

`services/radio-service/pulsefm_radio_service/repository.py`:

```python
"""Firestore access for station state.

`rotate` and `bootstrap` are transactional and guarded by a monotonic version.
Cloud Tasks delivers at least once and Cloud Run may run several instances, so
both a replayed tick and two concurrent instances must converge on one winner.
"""

from datetime import UTC, datetime

from google.cloud import firestore

from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.logic import CandidateSong, RotationPlan, is_stale_version


class StationRepository:
    def __init__(self, client: firestore.Client, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def _station_ref(self) -> firestore.DocumentReference:
        return self._client.document(self._settings.station_doc)

    def _song_ref(self, song_id: str) -> firestore.DocumentReference:
        return self._client.collection(self._settings.songs_collection).document(song_id)

    def get_station(self) -> dict | None:
        snapshot = self._station_ref().get()
        return snapshot.to_dict() if snapshot.exists else None

    def get_song(self, song_id: str) -> dict | None:
        snapshot = self._song_ref(song_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list_pool(self, limit: int) -> list[CandidateSong]:
        """Ready songs, least played and least recently played first."""
        query = (
            self._client.collection(self._settings.songs_collection)
            .where(filter=firestore.FieldFilter("status", "==", "ready"))
            .order_by("playCount")
            .order_by("lastPlayedAt")
            .limit(limit)
        )
        pool: list[CandidateSong] = []
        for document in query.stream():
            data = document.to_dict() or {}
            duration_ms = data.get("durationMs")
            if not isinstance(duration_ms, int) or duration_ms <= 0:
                continue
            pool.append(CandidateSong(song_id=document.id, duration_ms=duration_ms))
        return pool

    def bootstrap(self, plan: RotationPlan) -> bool:
        """Create the station document. Returns False if it already exists."""
        return self._apply(plan, require_absent=True)

    def rotate(self, plan: RotationPlan) -> bool:
        """Apply a rotation. Returns False if the plan's version is stale."""
        return self._apply(plan, require_absent=False)

    def _apply(self, plan: RotationPlan, *, require_absent: bool) -> bool:
        station_ref = self._station_ref()
        song_ref = self._song_ref(plan.song_id)

        @firestore.transactional
        def apply(transaction: firestore.Transaction) -> bool:
            snapshot = station_ref.get(transaction=transaction)
            if require_absent and snapshot.exists:
                return False
            if not require_absent:
                if not snapshot.exists:
                    return False
                existing = snapshot.to_dict() or {}
                # Delegate to the pure core rather than re-deriving the
                # comparison: logic.py owns staleness semantics and is the
                # only copy with unit tests behind it.
                if is_stale_version(plan.version, int(existing.get("version", 0))):
                    return False

            transaction.set(
                station_ref,
                {
                    "songId": plan.song_id,
                    "startAt": plan.start_at,
                    "endAt": plan.end_at,
                    "durationMs": plan.duration_ms,
                    "nextSongId": plan.next_song_id,
                    "nextStatus": plan.next_status,
                    "version": plan.version,
                },
            )
            transaction.update(
                song_ref,
                {
                    "playCount": firestore.Increment(1),
                    "lastPlayedAt": datetime.now(tz=UTC),
                },
            )
            return True

        return apply(self._client.transaction())
```

- [ ] **Step 5: Run the tests against the emulator**

Run:

```bash
npx -y firebase-tools emulators:exec --only firestore --project pulsefm-test \
  "uv run pytest services/radio-service/tests/test_repository.py -v -m integration"
```

Expected: PASS (7 tests).

- [ ] **Step 6: Add the integration job to CI**

Append to `.github/workflows/ci.yml`:

```yaml
  python-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - name: Sync workspace
        run: uv sync --all-packages
      - name: Integration tests against the Firestore emulator
        run: |
          npx -y firebase-tools emulators:exec --only firestore --project pulsefm-test \
            "uv run pytest packages/ services/ -v -m integration"
```

- [ ] **Step 7: Verify unit tests still skip cleanly without the emulator**

Run: `uv run pytest services/radio-service -v -m "not integration"`
Expected: PASS — the 8 logic tests run, the repository tests are deselected.

- [ ] **Step 8: Commit**

```bash
git add services/radio-service .github/workflows/ci.yml
git commit -m "feat(radio): add version-guarded Firestore station repository"
```

---

### Task 5: radio-service Cloud Tasks scheduler

**Files:**
- Create: `services/radio-service/pulsefm_radio_service/scheduler.py`
- Test: `services/radio-service/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `Settings` from Task 4, `build_tick_task_id` from Task 3.
- Produces: `TickScheduler(client, settings)` with `schedule(*, song_id, end_at, version) -> bool`. Returns `False` when the task already exists, which is a success, not an error.

- [ ] **Step 1: Write the failing tests**

`services/radio-service/tests/test_scheduler.py`:

```python
import json
from datetime import UTC, datetime

from google.api_core import exceptions as gcloud_exceptions

from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.scheduler import TickScheduler

END_AT = datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC)


class FakeTasksClient:
    def __init__(self, raise_already_exists: bool = False) -> None:
        self.created: list[dict] = []
        self._raise_already_exists = raise_already_exists

    def queue_path(self, project: str, location: str, queue: str) -> str:
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request: dict) -> object:
        if self._raise_already_exists:
            raise gcloud_exceptions.AlreadyExists("task exists")
        self.created.append(request)
        return object()


def _settings() -> Settings:
    return Settings(
        project_id="pulsefm-test",
        station_doc="station/current",
        songs_collection="songs",
        tick_url="https://radio.invalid/tick",
        queue_name="radio-queue",
        queue_location="us-central1",
        tick_service_account="tick@pulsefm-test.iam.gserviceaccount.com",
        pool_size=20,
    )


def test_schedule_creates_a_deterministically_named_oidc_task() -> None:
    client = FakeTasksClient()

    created = TickScheduler(client, _settings()).schedule(
        song_id="a", end_at=END_AT, version=8
    )

    assert created is True
    request = client.created[0]
    task = request["task"]
    assert task["name"].endswith("/tasks/tick-a-1785240232-8")
    assert task["http_request"]["url"] == "https://radio.invalid/tick"
    assert task["http_request"]["oidc_token"]["service_account_email"] == (
        "tick@pulsefm-test.iam.gserviceaccount.com"
    )
    assert json.loads(task["http_request"]["body"]) == {"version": 8}
    assert task["schedule_time"] == END_AT


def test_schedule_treats_an_existing_task_as_success() -> None:
    client = FakeTasksClient(raise_already_exists=True)

    created = TickScheduler(client, _settings()).schedule(
        song_id="a", end_at=END_AT, version=8
    )

    assert created is False
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest services/radio-service/tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulsefm_radio_service.scheduler'`.

- [ ] **Step 3: Write the implementation**

`services/radio-service/pulsefm_radio_service/scheduler.py`:

```python
"""Cloud Tasks scheduling for the self-chaining rotation clock.

Task names are deterministic, so a duplicate schedule is rejected by Cloud
Tasks itself rather than producing two ticks for one song boundary.
"""

import json
import logging
from datetime import datetime

from google.api_core import exceptions as gcloud_exceptions

from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.logic import build_tick_task_id

logger = logging.getLogger(__name__)


class TickScheduler:
    def __init__(self, client: object, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        """Schedule the tick that ends the currently playing song.

        Returns True when this call created the task, False when an equivalent
        task already existed. Both outcomes are successes.
        """
        parent = self._client.queue_path(
            self._settings.project_id,
            self._settings.queue_location,
            self._settings.queue_name,
        )
        task_id = build_tick_task_id(song_id, end_at, version)
        task = {
            "name": f"{parent}/tasks/{task_id}",
            "schedule_time": end_at,
            "http_request": {
                "http_method": "POST",
                "url": self._settings.tick_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"version": version}).encode("utf-8"),
                "oidc_token": {
                    "service_account_email": self._settings.tick_service_account,
                    "audience": self._settings.tick_url,
                },
            },
        }

        try:
            self._client.create_task(request={"parent": parent, "task": task})
        except gcloud_exceptions.AlreadyExists:
            logger.info("Tick task %s already scheduled; nothing to do", task_id)
            return False
        return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/radio-service/tests/test_scheduler.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add services/radio-service
git commit -m "feat(radio): add idempotent Cloud Tasks tick scheduler"
```

---

### Task 6: radio-service HTTP surface

> **Amended after review.** `resolve_promoted` was originally specified as a
> private helper inside `main.py`. Selecting which song gets promoted is a
> rotation decision, and this task's own constraint is that handlers contain
> none — so it belongs in `logic.py` beside `select_following`, with its own
> unit tests. Task 3 shipped before this was caught, so Task 6 adds the
> function and its tests to `logic.py`.


**Files:**
- Create: `services/radio-service/pulsefm_radio_service/main.py`
- Test: `services/radio-service/tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 3–5.
- Produces: a FastAPI `app` with `GET /healthz`, `POST /bootstrap`, `POST /tick`. `build_app(repository, scheduler, clock)` is exported for tests so no global state is required.

- [ ] **Step 1: Write the failing tests**

`services/radio-service/tests/test_main.py`:

```python
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from pulsefm_radio_service.logic import CandidateSong, RotationPlan
from pulsefm_radio_service.main import build_app

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self, station: dict | None, pool: list[CandidateSong]) -> None:
        self.station = station
        self.pool = pool
        self.rotated: list[RotationPlan] = []
        self.bootstrapped: list[RotationPlan] = []
        self.rotate_result = True
        self.bootstrap_result = True

    def get_station(self) -> dict | None:
        return self.station

    def list_pool(self, limit: int) -> list[CandidateSong]:
        return self.pool

    def rotate(self, plan: RotationPlan) -> bool:
        self.rotated.append(plan)
        return self.rotate_result

    def bootstrap(self, plan: RotationPlan) -> bool:
        self.bootstrapped.append(plan)
        return self.bootstrap_result


class FakeScheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, datetime, int]] = []

    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool:
        self.scheduled.append((song_id, end_at, version))
        return True


def _client(repository: FakeRepository, scheduler: FakeScheduler) -> TestClient:
    return TestClient(build_app(repository, scheduler, clock=lambda: NOW))


def test_healthz_reports_ok() -> None:
    client = _client(FakeRepository(None, []), FakeScheduler())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bootstrap_starts_the_station_and_schedules_the_first_tick() -> None:
    repository = FakeRepository(None, [CandidateSong("a", 232000), CandidateSong("b", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/bootstrap")

    assert response.status_code == 200
    assert response.json() == {"status": "started", "songId": "a", "version": 1}
    assert scheduler.scheduled == [
        ("a", datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC), 1)
    ]


def test_bootstrap_fails_when_the_pool_is_empty() -> None:
    response = _client(FakeRepository(None, []), FakeScheduler()).post("/bootstrap")

    assert response.status_code == 503
    assert "no ready songs" in response.json()["detail"]


def test_bootstrap_is_a_no_op_when_the_station_already_runs() -> None:
    repository = FakeRepository(None, [CandidateSong("a", 1000)])
    repository.bootstrap_result = False

    response = _client(repository, FakeScheduler()).post("/bootstrap")

    assert response.status_code == 200
    assert response.json()["status"] == "already-running"


def test_tick_rotates_to_the_queued_song_and_chains_the_next_tick() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 180000), CandidateSong("a", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert response.json() == {"status": "rotated", "songId": "b", "version": 2}
    assert repository.rotated[0].song_id == "b"
    assert repository.rotated[0].next_song_id == "a"
    assert scheduler.scheduled == [
        ("b", datetime(2026, 7, 28, 12, 3, 0, tzinfo=UTC), 2)
    ]


def test_tick_with_a_stale_version_is_a_no_op() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 5}
    repository = FakeRepository(station, [CandidateSong("b", 1000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 5})

    assert response.status_code == 200
    assert response.json() == {"status": "stale", "version": 5}
    assert repository.rotated == []
    assert scheduler.scheduled == []


def test_tick_loses_the_rotation_race_without_scheduling() -> None:
    station = {"songId": "a", "nextSongId": "b", "version": 1}
    repository = FakeRepository(station, [CandidateSong("b", 1000)])
    repository.rotate_result = False
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert response.json()["status"] == "lost-race"
    assert scheduler.scheduled == []


def test_tick_before_bootstrap_reports_no_station() -> None:
    response = _client(FakeRepository(None, []), FakeScheduler()).post(
        "/tick", json={"version": 1}
    )

    assert response.status_code == 409
    assert "not bootstrapped" in response.json()["detail"]


def test_tick_falls_back_when_the_queued_song_left_the_pool() -> None:
    station = {"songId": "a", "nextSongId": "gone", "version": 1}
    repository = FakeRepository(station, [CandidateSong("c", 5000)])
    scheduler = FakeScheduler()

    response = _client(repository, scheduler).post("/tick", json={"version": 2})

    assert response.status_code == 200
    assert repository.rotated[0].song_id == "c"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest services/radio-service/tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulsefm_radio_service.main'`.

- [ ] **Step 3: Write the implementation**

`services/radio-service/pulsefm_radio_service/main.py`:

```python
"""HTTP surface for the rotation clock.

Handlers do wiring only: read state, call the pure core, persist, chain the
next task. Every decision lives in logic.py.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from fastapi import FastAPI, HTTPException
from google.cloud import firestore, tasks_v2
from pydantic import BaseModel

from pulsefm_radio_service.config import settings_from_env
from pulsefm_radio_service.logic import (
    CandidateSong,
    RotationPlan,
    is_stale_version,
    plan_rotation,
    resolve_promoted,
)
from pulsefm_radio_service.repository import StationRepository
from pulsefm_radio_service.scheduler import TickScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class Repository(Protocol):
    def get_station(self) -> dict | None: ...
    def list_pool(self, limit: int) -> list[CandidateSong]: ...
    def rotate(self, plan: RotationPlan) -> bool: ...
    def bootstrap(self, plan: RotationPlan) -> bool: ...


class Scheduler(Protocol):
    def schedule(self, *, song_id: str, end_at: datetime, version: int) -> bool: ...


class TickRequest(BaseModel):
    version: int


def build_app(repository: Repository, scheduler: Scheduler, clock: Clock) -> FastAPI:
    app = FastAPI(title="pulsefm-radio-service")
    pool_limit = 20

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/bootstrap")
    def bootstrap() -> dict[str, object]:
        pool = repository.list_pool(limit=pool_limit)
        promoted = resolve_promoted(pool, None)
        if promoted is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot start the station: no ready songs in Firestore. "
                "Run scripts/seed_tracks.py first.",
            )

        plan = plan_rotation(promoted=promoted, pool=pool, now=clock(), current_version=0)
        if not repository.bootstrap(plan):
            return {"status": "already-running"}

        scheduler.schedule(song_id=plan.song_id, end_at=plan.end_at, version=plan.version)
        logger.info("Station started on %s until %s", plan.song_id, plan.end_at)
        return {"status": "started", "songId": plan.song_id, "version": plan.version}

    @app.post("/tick")
    def tick(request: TickRequest) -> dict[str, object]:
        station = repository.get_station()
        if station is None:
            raise HTTPException(
                status_code=409,
                detail="Station is not bootstrapped. POST /bootstrap first.",
            )

        current_version = int(station.get("version", 0))
        if is_stale_version(request.version, current_version):
            logger.info(
                "Ignoring stale tick: requested v%s, current v%s",
                request.version,
                current_version,
            )
            return {"status": "stale", "version": current_version}

        pool = repository.list_pool(limit=pool_limit)
        promoted = resolve_promoted(pool, station.get("nextSongId"))
        if promoted is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot rotate: no ready songs in Firestore.",
            )

        plan = plan_rotation(
            promoted=promoted, pool=pool, now=clock(), current_version=current_version
        )
        if not repository.rotate(plan):
            logger.info("Lost the rotation race for v%s", plan.version)
            return {"status": "lost-race", "version": current_version}

        scheduler.schedule(song_id=plan.song_id, end_at=plan.end_at, version=plan.version)
        logger.info("Rotated to %s until %s (v%s)", plan.song_id, plan.end_at, plan.version)
        return {"status": "rotated", "songId": plan.song_id, "version": plan.version}

    return app


def _build_default_app() -> FastAPI:
    settings = settings_from_env()
    repository = StationRepository(firestore.Client(project=settings.project_id), settings)
    scheduler = TickScheduler(tasks_v2.CloudTasksClient(), settings)
    return build_app(repository, scheduler, clock=lambda: datetime.now(tz=UTC))


app = _build_default_app()
```

Note: `app = _build_default_app()` runs at import, so tests must import `build_app` and never the module-level `app`. The tests above do exactly that; `_build_default_app` requires environment variables that are absent in CI.

- [ ] **Step 4: Guard the module-level app so imports do not explode in tests**

Replace the last two lines of `main.py` with:

```python
app: FastAPI | None = None

if os.getenv("PULSEFM_EAGER_APP", "1") == "1" and os.getenv("PROJECT_ID"):
    app = _build_default_app()
```

and add `import os` to the imports. The Dockerfile sets `PROJECT_ID`, so production builds the real app; tests import `build_app` directly and never trip the constructor.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest services/radio-service/tests/test_main.py -v`
Expected: PASS (9 tests).

- [ ] **Step 6: Run the whole unit suite**

Run: `uv run pytest packages/ services/ -v -m "not integration"`
Expected: PASS (22 tests).

- [ ] **Step 7: Commit**

```bash
git add services/radio-service
git commit -m "feat(radio): add bootstrap and tick endpoints"
```

---

### Task 7: station-api

**Files:**
- Create: `services/station-api/pyproject.toml`
- Create: `services/station-api/pulsefm_station_api/__init__.py`
- Create: `services/station-api/pulsefm_station_api/config.py`
- Create: `services/station-api/pulsefm_station_api/snapshot.py`
- Create: `services/station-api/pulsefm_station_api/repository.py`
- Create: `services/station-api/pulsefm_station_api/main.py`
- Test: `services/station-api/tests/test_snapshot.py`
- Test: `services/station-api/tests/test_main.py`

**Interfaces:**
- Consumes: `StateResponse`, `CurrentSong`, `NextUp`, `QueueResponse` from Task 2.
- Produces: `GET /healthz`, `GET /v1/state`, `GET /v1/queue`. `build_state(station, song, cdn_base_url, server_time) -> StateResponse` is pure and lives in `snapshot.py`.

- [ ] **Step 1: Write the failing tests for the pure assembler**

`services/station-api/tests/test_snapshot.py`:

```python
from datetime import UTC, datetime

import pytest

from pulsefm_station_api.snapshot import MissingSongError, build_state

SERVER_TIME = datetime(2026, 7, 28, 12, 1, 0, tzinfo=UTC)

STATION = {
    "songId": "song-1",
    "startAt": datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
    "endAt": datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC),
    "durationMs": 232000,
    "nextSongId": "song-2",
    "nextStatus": "fallback",
    "version": 3,
}

SONG = {
    "title": "Nightshift Drift",
    "artist": "Sable Unit",
    "descriptor": "melancholic",
    "objectPath": "tracks/song-1.m4a",
}


def test_build_state_composes_the_cdn_url() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        cdn_base_url="https://cdn.pulsefm.app",
        server_time=SERVER_TIME,
    )

    assert state.current.url == "https://cdn.pulsefm.app/tracks/song-1.m4a"


def test_build_state_tolerates_a_trailing_slash_on_the_base_url() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        cdn_base_url="https://cdn.pulsefm.app/",
        server_time=SERVER_TIME,
    )

    assert state.current.url == "https://cdn.pulsefm.app/tracks/song-1.m4a"


def test_build_state_carries_song_metadata_and_next_up() -> None:
    state = build_state(
        station=STATION,
        song=SONG,
        cdn_base_url="https://cdn.pulsefm.app",
        server_time=SERVER_TIME,
    )

    assert state.current.title == "Nightshift Drift"
    assert state.current.artist == "Sable Unit"
    assert state.current.duration_ms == 232000
    assert state.next_up.song_id == "song-2"
    assert state.next_up.status == "fallback"
    assert state.server_time == SERVER_TIME


def test_build_state_rejects_a_song_document_that_is_missing() -> None:
    with pytest.raises(MissingSongError, match="song-1"):
        build_state(
            station=STATION,
            song=None,
            cdn_base_url="https://cdn.pulsefm.app",
            server_time=SERVER_TIME,
        )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest services/station-api/tests/test_snapshot.py -v`
Expected: FAIL — package does not exist.

- [ ] **Step 3: Create the package and config**

`services/station-api/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pulsefm-station-api"
version = "0.1.0"
description = "PulseFM public read API."
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "google-cloud-firestore>=2.19",
  "pulsefm-models",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["pulsefm_station_api*"]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "httpx>=0.28"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`services/station-api/pulsefm_station_api/__init__.py`: empty file.

`services/station-api/pulsefm_station_api/config.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_id: str
    station_doc: str
    songs_collection: str
    cdn_base_url: str
    state_max_age_seconds: int


def settings_from_env() -> Settings:
    return Settings(
        project_id=os.environ["PROJECT_ID"],
        station_doc=os.getenv("STATION_DOC", "station/current"),
        songs_collection=os.getenv("SONGS_COLLECTION", "songs"),
        cdn_base_url=os.environ["CDN_BASE_URL"],
        state_max_age_seconds=int(os.getenv("STATE_MAX_AGE_SECONDS", "1")),
    )
```

Also add `pulsefm-station-api = { workspace = true }` and `pulsefm-radio-service = { workspace = true }` under `[tool.uv.sources]` in the root `pyproject.toml`.

- [ ] **Step 4: Write the pure assembler**

`services/station-api/pulsefm_station_api/snapshot.py`:

```python
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
    cdn_base_url: str,
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
            url=f"{cdn_base_url.rstrip('/')}/{song['objectPath'].lstrip('/')}",
            start_at=station["startAt"],
            end_at=station["endAt"],
            duration_ms=int(station["durationMs"]),
        ),
        next_up=NextUp(
            song_id=station.get("nextSongId"),
            status=station.get("nextStatus", "fallback"),
        ),
    )
```

- [ ] **Step 5: Run the snapshot tests to verify they pass**

Run: `uv run pytest services/station-api/tests/test_snapshot.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Write the failing tests for the HTTP surface**

`services/station-api/tests/test_main.py`:

```python
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from pulsefm_station_api.main import build_app

SERVER_TIME = datetime(2026, 7, 28, 12, 1, 0, tzinfo=UTC)

STATION = {
    "songId": "song-1",
    "startAt": datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
    "endAt": datetime(2026, 7, 28, 12, 3, 52, tzinfo=UTC),
    "durationMs": 232000,
    "nextSongId": "song-2",
    "nextStatus": "fallback",
    "version": 3,
}

SONGS = {
    "song-1": {
        "title": "Nightshift Drift",
        "artist": "Sable Unit",
        "descriptor": "melancholic",
        "objectPath": "tracks/song-1.m4a",
    },
    "song-2": {
        "title": "Pale Signal",
        "artist": "Wire Kite",
        "descriptor": "hypnotic",
        "objectPath": "tracks/song-2.m4a",
        "durationMs": 180000,
    },
}


class FakeRepository:
    def __init__(self, station: dict | None, songs: dict[str, dict]) -> None:
        self.station = station
        self.songs = songs

    def get_station(self) -> dict | None:
        return self.station

    def get_song(self, song_id: str) -> dict | None:
        return self.songs.get(song_id)


def _client(repository: FakeRepository) -> TestClient:
    return TestClient(
        build_app(
            repository,
            cdn_base_url="https://cdn.pulsefm.app",
            state_max_age_seconds=1,
            clock=lambda: SERVER_TIME,
        )
    )


def test_healthz_reports_ok() -> None:
    response = _client(FakeRepository(None, {})).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_state_returns_the_snapshot() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["serverTime"] == "2026-07-28T12:01:00Z"
    assert payload["current"]["songId"] == "song-1"
    assert payload["current"]["url"] == "https://cdn.pulsefm.app/tracks/song-1.m4a"
    assert payload["next"] == {"songId": "song-2", "status": "fallback"}


def test_state_is_publicly_cacheable_for_one_second() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/state")

    assert response.headers["cache-control"] == "public, max-age=1"


def test_state_returns_503_before_the_station_is_bootstrapped() -> None:
    response = _client(FakeRepository(None, {})).get("/v1/state")

    assert response.status_code == 503
    assert "not started" in response.json()["detail"]


def test_state_returns_503_when_the_song_document_is_missing() -> None:
    response = _client(FakeRepository(STATION, {})).get("/v1/state")

    assert response.status_code == 503


def test_queue_returns_current_then_next() -> None:
    response = _client(FakeRepository(STATION, SONGS)).get("/v1/queue")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["songId"] for item in items] == ["song-1", "song-2"]
    assert items[1]["url"] == "https://cdn.pulsefm.app/tracks/song-2.m4a"


def test_queue_omits_a_next_song_whose_document_is_absent() -> None:
    response = _client(FakeRepository(STATION, {"song-1": SONGS["song-1"]})).get("/v1/queue")

    assert [item["songId"] for item in response.json()["items"]] == ["song-1"]
```

- [ ] **Step 7: Run it to verify it fails**

Run: `uv run pytest services/station-api/tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulsefm_station_api.main'`.

- [ ] **Step 8: Write the repository and HTTP surface**

`services/station-api/pulsefm_station_api/repository.py`:

```python
"""Read-only Firestore access. station-api never writes station state."""

from google.cloud import firestore

from pulsefm_station_api.config import Settings


class StationReadRepository:
    def __init__(self, client: firestore.Client, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def get_station(self) -> dict | None:
        snapshot = self._client.document(self._settings.station_doc).get()
        return snapshot.to_dict() if snapshot.exists else None

    def get_song(self, song_id: str) -> dict | None:
        snapshot = (
            self._client.collection(self._settings.songs_collection).document(song_id).get()
        )
        return snapshot.to_dict() if snapshot.exists else None
```

`services/station-api/pulsefm_station_api/main.py`:

```python
"""Public read API.

Every response is identical for every listener, which is what lets /v1/state
sit behind a shared cache. Nothing per-user may ever enter this payload.
"""

import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response
from google.cloud import firestore

from pulsefm_models.station import CurrentSong, QueueResponse, StateResponse
from pulsefm_station_api.config import settings_from_env
from pulsefm_station_api.repository import StationReadRepository
from pulsefm_station_api.snapshot import MissingSongError, build_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class Repository(Protocol):
    def get_station(self) -> dict | None: ...
    def get_song(self, song_id: str) -> dict | None: ...


def build_app(
    repository: Repository,
    cdn_base_url: str,
    state_max_age_seconds: int,
    clock: Clock,
) -> FastAPI:
    app = FastAPI(title="pulsefm-station-api")
    cache_control = f"public, max-age={state_max_age_seconds}"

    def _load_state() -> StateResponse:
        station = repository.get_station()
        if station is None:
            raise HTTPException(
                status_code=503,
                detail="The station has not started yet. Try again shortly.",
            )
        try:
            return build_state(
                station=station,
                song=repository.get_song(station["songId"]),
                cdn_base_url=cdn_base_url,
                server_time=clock(),
            )
        except MissingSongError as error:
            logger.error("Inconsistent station state: %s", error)
            raise HTTPException(
                status_code=503, detail="The station is in an inconsistent state."
            ) from error

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/state")
    def state(response: Response) -> StateResponse:
        response.headers["Cache-Control"] = cache_control
        return _load_state()

    @app.get("/v1/queue")
    def queue(response: Response) -> QueueResponse:
        response.headers["Cache-Control"] = cache_control
        current_state = _load_state()
        items: list[CurrentSong] = [current_state.current]

        next_song_id = current_state.next_up.song_id
        if next_song_id is not None:
            next_song = repository.get_song(next_song_id)
            if next_song is not None:
                items.append(
                    CurrentSong(
                        song_id=next_song_id,
                        title=next_song["title"],
                        artist=next_song["artist"],
                        descriptor=next_song["descriptor"],
                        url=f"{cdn_base_url.rstrip('/')}/{next_song['objectPath'].lstrip('/')}",
                        start_at=current_state.current.end_at,
                        end_at=current_state.current.end_at,
                        duration_ms=int(next_song.get("durationMs", 0)),
                    )
                )

        return QueueResponse(items=items)

    return app


def _build_default_app() -> FastAPI:
    settings = settings_from_env()
    repository = StationReadRepository(
        firestore.Client(project=settings.project_id), settings
    )
    return build_app(
        repository,
        cdn_base_url=settings.cdn_base_url,
        state_max_age_seconds=settings.state_max_age_seconds,
        clock=lambda: datetime.now(tz=UTC),
    )


app: FastAPI | None = None

if os.getenv("PULSEFM_EAGER_APP", "1") == "1" and os.getenv("PROJECT_ID"):
    app = _build_default_app()
```

Note on `/v1/queue`: the next item's `start_at` and `end_at` both carry the current song's `end_at`. The window is not yet known — it is decided at rotation — and the client uses only `songId`, `title`, `artist`, and `url` from queue items.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest services/station-api/tests/ -v`
Expected: PASS (11 tests).

- [ ] **Step 10: Run the whole unit suite**

Run: `uv run ruff check . && uv run pytest packages/ services/ -v -m "not integration"`
Expected: PASS (33 tests).

- [ ] **Step 11: Commit**

```bash
git add services/station-api pyproject.toml
git commit -m "feat(station-api): serve cacheable /v1/state and /v1/queue"
```

---

### Task 8: Dockerfiles

**Files:**
- Create: `services/radio-service/Dockerfile`
- Create: `services/station-api/Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: both service packages.
- Produces: images that listen on `$PORT` and answer `GET /healthz`.

- [ ] **Step 1: Write the ignore file**

`.dockerignore`:

```
**/__pycache__/
**/*.egg-info/
**/.venv/
**/.pytest_cache/
**/.ruff_cache/
client/
terraform/
docs/
design_handoff_pulse_fm_player/
.git/
.github/
```

- [ ] **Step 2: Write the radio-service Dockerfile**

`services/radio-service/Dockerfile`:

```dockerfile
# Build context is the repository root so the workspace package is available:
#   docker build -f services/radio-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY packages/pulsefm-models /app/packages/pulsefm-models
COPY services/radio-service /app/services/radio-service

RUN pip install --no-cache-dir /app/packages/pulsefm-models \
 && pip install --no-cache-dir /app/services/radio-service

EXPOSE 8080

CMD exec uvicorn pulsefm_radio_service.main:app --host 0.0.0.0 --port ${PORT}
```

- [ ] **Step 3: Write the station-api Dockerfile**

`services/station-api/Dockerfile`:

```dockerfile
# Build context is the repository root:
#   docker build -f services/station-api/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY packages/pulsefm-models /app/packages/pulsefm-models
COPY services/station-api /app/services/station-api

RUN pip install --no-cache-dir /app/packages/pulsefm-models \
 && pip install --no-cache-dir /app/services/station-api

EXPOSE 8080

CMD exec uvicorn pulsefm_station_api.main:app --host 0.0.0.0 --port ${PORT}
```

- [ ] **Step 4: Build both images and verify health**

Run:

```bash
docker build -f services/station-api/Dockerfile -t pulsefm-station-api:dev .
docker run --rm -d --name station-api-smoke -p 8080:8080 \
  -e PROJECT_ID=pulsefm-test \
  -e CDN_BASE_URL=https://cdn.example \
  -e GOOGLE_CLOUD_PROJECT=pulsefm-test \
  pulsefm-station-api:dev
sleep 3 && curl -sf localhost:8080/healthz && docker stop station-api-smoke
```

Expected: `{"status":"ok"}`, then the container stops.

- [ ] **Step 5: Repeat for radio-service**

Run:

```bash
docker build -f services/radio-service/Dockerfile -t pulsefm-radio-service:dev .
docker run --rm -d --name radio-smoke -p 8081:8080 \
  -e PROJECT_ID=pulsefm-test \
  -e TICK_URL=https://radio.invalid/tick \
  -e TICK_SERVICE_ACCOUNT=tick@pulsefm-test.iam.gserviceaccount.com \
  pulsefm-radio-service:dev
sleep 3 && curl -sf localhost:8081/healthz && docker stop radio-smoke
```

Expected: `{"status":"ok"}`.

- [ ] **Step 6: Commit**

```bash
git add .dockerignore services/*/Dockerfile
git commit -m "infra: containerise radio-service and station-api"
```

---

### Task 9: Terraform foundations

**Files:**
- Create: `terraform/versions.tf`, `providers.tf`, `variables.tf`, `apis.tf`, `firestore.tf`, `artifact_registry.tf`, `service_accounts.tf`, `terraform.tfvars.example`

**Interfaces:**
- Consumes: nothing.
- Produces: enabled APIs, a Firestore database, an Artifact Registry repository, and three service accounts referenced by Tasks 10–11 as `google_service_account.radio`, `.station_api`, `.tick_invoker`.

- [ ] **Step 1: Write versions and providers**

`terraform/versions.tf`:

```hcl
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
```

`terraform/providers.tf`:

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}
```

`terraform/variables.tf`:

```hcl
variable "project_id" {
  type        = string
  description = "GCP project id hosting PulseFM v2."
}

variable "region" {
  type        = string
  description = "Region for Cloud Run, Cloud Tasks, and Artifact Registry. Does NOT govern Firestore — see firestore_location."
  default     = "us-central1"
}

variable "firestore_location" {
  type        = string
  description = "Firestore location. Deliberately separate from var.region: location_id is ForceNew, so changing it destroys and recreates the database."
  default     = "us-central1"
}

variable "songs_bucket_name" {
  type        = string
  description = "Globally unique name for the public audio bucket."
}

variable "client_origins" {
  type        = list(string)
  description = "Origins allowed to read audio with CORS (needed by the slice 4 analyser)."
  default     = ["http://localhost:5173"]
}
```

`terraform/terraform.tfvars.example`:

```hcl
project_id         = "pulsefm-v2"
region             = "us-central1"
firestore_location = "us-central1"
songs_bucket_name = "pulsefm-v2-songs"
client_origins    = ["http://localhost:5173", "https://pulsefm-v2.web.app"]
```

- [ ] **Step 2: Enable the APIs**

`terraform/apis.tf`:

```hcl
locals {
  services = [
    "run.googleapis.com",
    "firestore.googleapis.com",
    "cloudtasks.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  service            = each.value
  disable_on_destroy = false
}
```

- [ ] **Step 3: Add Firestore and Artifact Registry**

`terraform/firestore.tf`:

```hcl
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  # location_id is ForceNew: changing it destroys and recreates the database,
  # taking every song and station document with it.
  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.enabled]
}

# list_pool orders by playCount then lastPlayedAt with a status equality filter,
# which Firestore cannot serve from single-field indexes.
resource "google_firestore_index" "songs_pool" {
  database   = google_firestore_database.default.name
  collection = "songs"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "playCount"
    order      = "ASCENDING"
  }
  fields {
    field_path = "lastPlayedAt"
    order      = "ASCENDING"
  }
}
```

`terraform/artifact_registry.tf`:

```hcl
resource "google_artifact_registry_repository" "services" {
  repository_id = "pulsefm"
  location      = var.region
  format        = "DOCKER"
  description   = "PulseFM v2 service images."

  depends_on = [google_project_service.enabled]
}
```

- [ ] **Step 4: Add the service accounts**

`terraform/service_accounts.tf`:

```hcl
resource "google_service_account" "radio" {
  account_id   = "pulsefm-radio"
  display_name = "PulseFM radio-service runtime"

  depends_on = [google_project_service.enabled]
}

resource "google_service_account" "station_api" {
  account_id   = "pulsefm-station-api"
  display_name = "PulseFM station-api runtime"

  depends_on = [google_project_service.enabled]
}

# Cloud Tasks mints OIDC tokens as this identity to call radio-service /tick.
resource "google_service_account" "tick_invoker" {
  account_id   = "pulsefm-tick-invoker"
  display_name = "PulseFM Cloud Tasks tick invoker"

  depends_on = [google_project_service.enabled]
}
```

- [ ] **Step 5: Validate**

Run: `cd terraform && terraform init -backend=false && terraform validate && terraform fmt -check`
Expected: `Success! The configuration is valid.` and no formatting diff.

- [ ] **Step 6: Commit**

```bash
git add terraform
git commit -m "infra: add Terraform foundations — APIs, Firestore, registry, service accounts"
```

---

### Task 10: Terraform storage, CORS, and CDN

**Files:**
- Create: `terraform/storage.tf`
- Create: `terraform/outputs.tf`

**Interfaces:**
- Consumes: `var.songs_bucket_name`, `var.client_origins`, `google_project_service.enabled`.
- Produces: output `cdn_base_url`, consumed by Task 11 as `CDN_BASE_URL` and by Task 12's seed script.

- [ ] **Step 1: Write the bucket, CORS, and CDN**

`terraform/storage.tf`:

```hcl
resource "google_storage_bucket" "songs" {
  name          = var.songs_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  # The analyser (slice 4) reads audio through WebAudio, which requires the
  # element to be crossOrigin="anonymous" and the response to carry CORS
  # headers. Without this the analyser silently returns zeros.
  cors {
    origin          = var.client_origins
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Range", "Content-Range", "Accept-Ranges"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.enabled]
}

# Audio is world-readable by design: unauthenticated listening is a product
# requirement, so signed URLs would add cost and defeat shared caching without
# protecting anything. See spec D1.
resource "google_storage_bucket_iam_member" "songs_public_read" {
  bucket = google_storage_bucket.songs.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_backend_bucket" "songs" {
  name        = "pulsefm-songs-backend"
  bucket_name = google_storage_bucket.songs.name
  enable_cdn  = true

  # Tracks are write-once and the uploader stamps each object with
  # `Cache-Control: public, max-age=31536000, immutable`. Deferring to that
  # keeps cache lifetime defined in one place — the thing that knows the
  # content never changes — instead of a CDN cap that silently overrides it.
  cdn_policy {
    cache_mode        = "USE_ORIGIN_HEADERS"
    negative_caching  = true
    serve_while_stale = 86400
  }
}

resource "google_compute_global_address" "cdn" {
  name = "pulsefm-cdn-ip"

  # The other compute resources reach compute.googleapis.com transitively via
  # the bucket; this one references nothing, so it needs the edge declared.
  depends_on = [google_project_service.enabled]
}

resource "google_compute_url_map" "cdn" {
  name            = "pulsefm-cdn"
  default_service = google_compute_backend_bucket.songs.id
}

resource "google_compute_target_http_proxy" "cdn" {
  name    = "pulsefm-cdn-proxy"
  url_map = google_compute_url_map.cdn.id
}

resource "google_compute_global_forwarding_rule" "cdn" {
  name       = "pulsefm-cdn-rule"
  target     = google_compute_target_http_proxy.cdn.id
  ip_address = google_compute_global_address.cdn.address
  port_range = "80"
}
```

`terraform/outputs.tf`:

```hcl
output "cdn_base_url" {
  value       = "http://${google_compute_global_address.cdn.address}"
  description = "Base URL for audio objects. Slice 4 puts a managed certificate and domain in front of this."
}

output "songs_bucket_name" {
  value       = google_storage_bucket.songs.name
  description = "Bucket holding encoded tracks."
}
```

The CDN is plain HTTP against a bare IP for slices 0–1. A domain and a managed TLS certificate arrive with the Firebase Hosting domain in slice 4; browsers block mixed content, so local development uses the bucket URL directly (see Task 12).

- [ ] **Step 2: Validate**

Run: `cd terraform && terraform validate && terraform fmt -check`
Expected: valid, no diff.

- [ ] **Step 3: Apply and record the outputs**

Run: `cd terraform && terraform apply`
Expected: applies cleanly; `terraform output cdn_base_url` prints an `http://<ip>` URL.

- [ ] **Step 4: Commit**

```bash
git add terraform
git commit -m "infra: add public songs bucket with CORS behind Cloud CDN"
```

---

### Task 11: Terraform Cloud Run, Cloud Tasks, and IAM

**Files:**
- Create: `terraform/cloudtasks.tf`
- Create: `terraform/cloud_run.tf`
- Create: `terraform/iam.tf`
- Modify: `terraform/outputs.tf`

**Interfaces:**
- Consumes: service accounts (Task 9), `cdn_base_url` (Task 10).
- Produces: outputs `station_api_url` and `radio_service_url`.

- [ ] **Step 1: Write the queue**

`terraform/cloudtasks.tf`:

```hcl
resource "google_cloud_tasks_queue" "radio" {
  name     = "radio-queue"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 5
  }

  # A tick that fails is superseded by the next one; long retry storms would
  # only replay stale versions, which the version guard already discards.
  retry_config {
    max_attempts       = 5
    min_backoff        = "1s"
    max_backoff        = "10s"
    max_retry_duration = "60s"
  }

  depends_on = [google_project_service.enabled]
}
```

- [ ] **Step 2: Write the Cloud Run services**

`terraform/cloud_run.tf`:

```hcl
locals {
  image_base = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.services.repository_id}"
}

resource "google_cloud_run_v2_service" "radio" {
  name     = "radio-service"
  location = var.region

  # The control plane that spends money on GPUs is unreachable from the
  # internet; Cloud Tasks reaches it over internal ingress with OIDC.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.radio.email
    timeout         = "120s"

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${local.image_base}/radio-service:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "TICK_URL"
        value = "${google_cloud_run_v2_service.radio.uri}/tick"
      }
      env {
        name  = "TICK_SERVICE_ACCOUNT"
        value = google_service_account.tick_invoker.email
      }
      env {
        name  = "RADIO_QUEUE_NAME"
        value = google_cloud_tasks_queue.radio.name
      }
      env {
        name  = "RADIO_QUEUE_LOCATION"
        value = var.region
      }
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_cloud_run_v2_service" "station_api" {
  name     = "station-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.station_api.email
    timeout         = "30s"

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "${local.image_base}/station-api:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CDN_BASE_URL"
        value = "http://${google_compute_global_address.cdn.address}"
      }
    }
  }

  depends_on = [google_project_service.enabled]
}
```

`TICK_URL` references the service's own `uri`, which Terraform resolves after creation. If the provider reports a self-reference cycle, apply once with `TICK_URL` set to a placeholder, then set it to `"${google_cloud_run_v2_service.radio.uri}/tick"` and apply again. Record whichever path was needed in the slice's editorial post.

- [ ] **Step 3: Write IAM**

`terraform/iam.tf`:

```hcl
# Both services read Firestore; only radio-service writes it.
resource "google_project_iam_member" "radio_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.radio.email}"
}

resource "google_project_iam_member" "station_api_firestore_read" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.station_api.email}"
}

resource "google_project_iam_member" "radio_enqueue" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.radio.email}"
}

# radio-service creates tasks that run as the tick invoker, which requires
# impersonation rights on that account.
resource "google_service_account_iam_member" "radio_acts_as_tick_invoker" {
  service_account_id = google_service_account.tick_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.radio.email}"
}

# The only identity allowed to invoke radio-service.
resource "google_cloud_run_v2_service_iam_member" "tick_invoker" {
  name     = google_cloud_run_v2_service.radio.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tick_invoker.email}"
}

# station-api is public in slices 0-1. Slice 3 replaces allUsers with the API
# Gateway service account.
resource "google_cloud_run_v2_service_iam_member" "station_api_public" {
  name     = google_cloud_run_v2_service.station_api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

Append to `terraform/outputs.tf`:

```hcl
output "station_api_url" {
  value       = google_cloud_run_v2_service.station_api.uri
  description = "Public base URL for the read API."
}

output "radio_service_url" {
  value       = google_cloud_run_v2_service.radio.uri
  description = "Internal base URL for the rotation clock."
}
```

- [ ] **Step 4: Validate**

Run: `cd terraform && terraform validate && terraform fmt -check`
Expected: valid, no diff.

- [ ] **Step 5: Build, push, and apply**

Run:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/pulsefm"
docker build -f services/radio-service/Dockerfile -t "${IMAGE_BASE}/radio-service:latest" .
docker build -f services/station-api/Dockerfile -t "${IMAGE_BASE}/station-api:latest" .
docker push "${IMAGE_BASE}/radio-service:latest"
docker push "${IMAGE_BASE}/station-api:latest"
cd terraform && terraform apply
```

Expected: both services deploy. `curl -sf "$(terraform output -raw station_api_url)/healthz"` returns `{"status":"ok"}`.

- [ ] **Step 6: Commit**

```bash
git add terraform
git commit -m "infra: deploy radio-service and station-api with Cloud Tasks chaining"
```

---

### Task 12: Seed the fallback pool

Day one has no songs. Without this, `/bootstrap` returns 503 and nothing else in slice 1 can be exercised.

**Files:**
- Create: `scripts/seed_tracks.py`
- Create: `scripts/README.md`

**Interfaces:**
- Consumes: the bucket and Firestore from Tasks 9–10.
- Produces: `songs/{songId}` documents with `status: ready`, and objects at `tracks/{songId}.m4a`.

- [ ] **Step 1: Write the failing test for the pure part**

`scripts/tests/test_seed_tracks.py`:

```python
import pytest

from scripts.seed_tracks import SeedTrack, build_song_document, slugify


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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest scripts/tests/ -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the script**

`scripts/seed_tracks.py`:

```python
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
```

`scripts/README.md`:

```markdown
# scripts

## seed_tracks.py

Seeds the fallback pool. Slice 1 has no generation, so this is the only source
of songs. Requires `ffprobe` (part of ffmpeg) on PATH.

```bash
uv run python -m scripts.seed_tracks \
  --bucket "$(cd terraform && terraform output -raw songs_bucket_name)" \
  --dir ./seed-audio \
  --project "$PROJECT_ID"
```

Use at least four tracks of differing lengths so rotation and the fallback
ordering are both observable.
```

Add empty `scripts/__init__.py` and `scripts/tests/__init__.py` so the module is importable as `scripts.seed_tracks`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest scripts/tests/ -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Seed and start the station**

Run:

```bash
uv run python -m scripts.seed_tracks \
  --bucket "$(cd terraform && terraform output -raw songs_bucket_name)" \
  --dir ./seed-audio --project "$PROJECT_ID"

RADIO_URL="$(cd terraform && terraform output -raw radio_service_url)"
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$RADIO_URL/bootstrap"
```

Expected: `{"status":"started","songId":"...","version":1}`.

- [ ] **Step 6: Verify the station rotates on its own**

Run:

```bash
STATION_URL="$(cd terraform && terraform output -raw station_api_url)"
curl -s "$STATION_URL/v1/state" | python -m json.tool
```

Expected: a full snapshot. Wait for the current song's `endAt` to pass, repeat, and confirm `current.songId` and `version` both changed without any manual intervention. **This is the moment the station becomes self-driving — do not proceed until it is confirmed.**

- [ ] **Step 7: Commit**

```bash
git add scripts
git commit -m "feat(scripts): seed the fallback pool from local audio files"
```

---

### Task 13: Client scaffold, tokens, and fonts

**Files:**
- Create: `client/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `firebase.json`, `.firebaserc`
- Create: `client/src/main.tsx`, `client/src/styles/tokens.css`
- Create: `client/src/assets/fonts/` (vendored Doto woff2 files)
- Create: `client/.env.example`

**Interfaces:**
- Consumes: `station_api_url` from Task 11.
- Produces: a running dev server, Tailwind v4 with the handoff's tokens, and self-hosted Doto.

- [ ] **Step 1: Scaffold and install**

Run:

```bash
cd client
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite vitest @vitest/coverage-v8 jsdom \
  @testing-library/react @testing-library/user-event @testing-library/jest-dom
```

- [ ] **Step 2: Configure Vite and Vitest**

`client/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
```

`client/src/test-setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Add to `client/package.json` scripts:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 3: Vendor the Doto font**

Run:

```bash
mkdir -p src/assets/fonts
curl -sL "https://fonts.gstatic.com/s/doto/v2/PbykFmXiEBPT4ITbgNA5Cg.woff2" \
  -o src/assets/fonts/doto-variable.woff2
```

If that URL 404s, open `https://fonts.googleapis.com/css2?family=Doto:wght@400;600;800&display=swap` with a modern browser User-Agent, read the `src: url(...)` value from the returned CSS, and download that. The handoff requires self-hosting; never leave the runtime dependency on Google Fonts.

- [ ] **Step 4: Write the tokens**

`client/src/styles/tokens.css`:

```css
@import "tailwindcss";

@font-face {
  font-family: "Doto";
  src: url("../assets/fonts/doto-variable.woff2") format("woff2-variations");
  font-weight: 400 800;
  font-display: swap;
}

@theme {
  --color-canvas: #DEDDD8;
  --color-bone: #EDECE7;
  --color-ink: #111111;
  --color-paper: #F2F1EF;
  --color-accent: #D6252B;

  /* Lightened accent for use on ink. Present in the prototype markup but
     absent from the handoff's token table — see spec, "New token". */
  --color-accent-on-ink: #FF7A7E;

  --font-sans: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --font-mono: "Doto", ui-monospace, monospace;

  --radius-app: 16px;
  --radius-device: 46px;
  --radius-sheet: 34px;

  --shadow-frame: 0 40px 80px -30px rgb(0 0 0 / 0.35);

  --ease-viz: cubic-bezier(0.4, 0, 0.6, 1);
}

html,
body,
#root {
  height: 100%;
}

body {
  background: var(--color-bone);
  color: var(--color-ink);
  font-family: var(--font-sans);
}
```

`client/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/tokens.css";
import { App } from "./App";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element in index.html");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`client/src/App.tsx` (placeholder replaced in Task 17):

```tsx
export function App() {
  return <div className="font-mono text-[11px] tracking-[0.22em] uppercase">PULSE FM</div>;
}
```

- [ ] **Step 5: Configure the API base URL and Firebase Hosting**

`client/.env.example`:

```
VITE_API_BASE_URL=https://station-api-xxxxx-uc.a.run.app
```

`client/firebase.json`:

```json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [{ "source": "**", "destination": "/index.html" }],
    "headers": [
      {
        "source": "**/*.@(woff2)",
        "headers": [
          { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
        ]
      }
    ]
  }
}
```

`client/.firebaserc`:

```json
{ "projects": { "default": "pulsefm-v2" } }
```

- [ ] **Step 6: Verify the dev server and build**

Run: `npm run dev` — confirm `PULSE FM` renders in Doto (dot-matrix, not a fallback monospace). Then `npm run build`.
Expected: both succeed.

- [ ] **Step 7: Add the client job to CI**

Append to `.github/workflows/ci.yml`:

```yaml
  client:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: client
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: client/package-lock.json
      - run: npm ci
      - run: npm run build
      - run: npm test
```

- [ ] **Step 8: Commit**

```bash
git add client .github/workflows/ci.yml
git commit -m "feat(client): scaffold Vite/React/Tailwind with handoff tokens and self-hosted Doto"
```

---

### Task 14: Client pure library — clock, formatting, snapshot diffing

**Files:**
- Create: `client/src/lib/types.ts`, `clock.ts`, `format.ts`, `pollDiff.ts`, `api.ts`
- Test: `client/src/lib/clock.test.ts`, `format.test.ts`, `pollDiff.test.ts`

**Interfaces:**
- Consumes: the `/v1/state` shape from Task 7.
- Produces:
  - `StateSnapshot`, `CurrentSong`, `NextUp` types
  - `computeOffsetMs(serverTimeIso, receivedAtMs) -> number`
  - `serverNow(offsetMs, nowMs) -> number`
  - `positionMs(startAtIso, offsetMs, nowMs) -> number`
  - `timecode(ms) -> string`
  - `diffSnapshots(prev, next) -> { songChanged, nextSongChanged }`
  - `fetchState(baseUrl, signal) -> Promise<StateSnapshot>`

- [ ] **Step 1: Write the failing tests**

`client/src/lib/clock.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { computeOffsetMs, positionMs, serverNow } from "./clock";

describe("computeOffsetMs", () => {
  it("is positive when the server clock leads the client", () => {
    expect(computeOffsetMs("2026-07-28T12:00:05Z", Date.parse("2026-07-28T12:00:00Z"))).toBe(5000);
  });

  it("is negative when the client clock leads the server", () => {
    expect(computeOffsetMs("2026-07-28T12:00:00Z", Date.parse("2026-07-28T12:00:05Z"))).toBe(-5000);
  });
});

describe("serverNow", () => {
  it("applies the offset to local time", () => {
    expect(serverNow(5000, 1000)).toBe(6000);
  });
});

describe("positionMs", () => {
  const startAt = "2026-07-28T12:00:00Z";

  it("returns elapsed milliseconds against the corrected clock", () => {
    const now = Date.parse("2026-07-28T12:00:30Z");
    expect(positionMs(startAt, 0, now)).toBe(30_000);
  });

  it("corrects a skewed client clock", () => {
    const now = Date.parse("2026-07-28T11:59:30Z");
    expect(positionMs(startAt, 60_000, now)).toBe(30_000);
  });

  it("never returns a negative position", () => {
    const now = Date.parse("2026-07-28T11:59:00Z");
    expect(positionMs(startAt, 0, now)).toBe(0);
  });
});
```

`client/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { timecode } from "./format";

describe("timecode", () => {
  it("pads minutes and seconds to two digits", () => {
    expect(timecode(182_000)).toBe("03:02");
    expect(timecode(232_000)).toBe("03:52");
    expect(timecode(0)).toBe("00:00");
  });

  it("truncates partial seconds rather than rounding up", () => {
    expect(timecode(1999)).toBe("00:01");
  });

  it("clamps negative input to zero", () => {
    expect(timecode(-500)).toBe("00:00");
  });

  it("carries past an hour without a separate hours field", () => {
    expect(timecode(3_660_000)).toBe("61:00");
  });
});
```

`client/src/lib/pollDiff.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { diffSnapshots } from "./pollDiff";
import type { StateSnapshot } from "./types";

const base: StateSnapshot = {
  serverTime: "2026-07-28T12:00:00Z",
  current: {
    songId: "a",
    title: "Nightshift Drift",
    artist: "Sable Unit",
    descriptor: "melancholic",
    url: "https://cdn.example/tracks/a.m4a",
    startAt: "2026-07-28T12:00:00Z",
    endAt: "2026-07-28T12:03:52Z",
    durationMs: 232_000,
  },
  next: { songId: "b", status: "fallback" },
};

describe("diffSnapshots", () => {
  it("reports no change against an identical snapshot", () => {
    expect(diffSnapshots(base, base)).toEqual({ songChanged: false, nextSongChanged: false });
  });

  it("detects a song change by id", () => {
    const next = { ...base, current: { ...base.current, songId: "b" } };
    expect(diffSnapshots(base, next).songChanged).toBe(true);
  });

  it("detects a queued song change", () => {
    const next = { ...base, next: { songId: "c", status: "fallback" as const } };
    expect(diffSnapshots(base, next).nextSongChanged).toBe(true);
  });

  it("treats the first snapshot as a song change", () => {
    expect(diffSnapshots(null, base).songChanged).toBe(true);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd client && npm test`
Expected: FAIL — the modules do not exist.

- [ ] **Step 3: Write the implementation**

`client/src/lib/types.ts`:

```ts
export type NextStatus = "generating" | "ready" | "fallback";

export interface CurrentSong {
  songId: string;
  title: string;
  artist: string;
  descriptor: string;
  url: string;
  startAt: string;
  endAt: string;
  durationMs: number;
}

export interface NextUp {
  songId: string | null;
  status: NextStatus;
}

export interface StateSnapshot {
  serverTime: string;
  current: CurrentSong;
  next: NextUp;
}
```

`client/src/lib/clock.ts`:

```ts
/**
 * Server-clock correction.
 *
 * Every listener seeks to (serverNow - startAt), so a skewed device clock would
 * put that listener out of sync with the station. Background tabs also throttle
 * timers, so local elapsed time drifts; correcting against the server's own
 * timestamp on every poll keeps the audio and the UI honest.
 */

export function computeOffsetMs(serverTimeIso: string, receivedAtMs: number): number {
  return Date.parse(serverTimeIso) - receivedAtMs;
}

export function serverNow(offsetMs: number, nowMs: number = Date.now()): number {
  return nowMs + offsetMs;
}

export function positionMs(
  startAtIso: string,
  offsetMs: number,
  nowMs: number = Date.now(),
): number {
  return Math.max(0, serverNow(offsetMs, nowMs) - Date.parse(startAtIso));
}
```

`client/src/lib/format.ts`:

```ts
/** M:SS timecode. Minutes are not wrapped into hours — the design has no hours field. */
export function timecode(ms: number): string {
  const totalSeconds = Math.floor(Math.max(0, ms) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
```

`client/src/lib/pollDiff.ts`:

```ts
import type { StateSnapshot } from "./types";

export interface SnapshotDiff {
  songChanged: boolean;
  nextSongChanged: boolean;
}

/**
 * Derive UI transitions by comparing consecutive snapshots.
 *
 * Polling gives us state, not events. Diffing recovers the events the UI needs
 * (swap the audio slot, prefetch the next track) without a push channel.
 */
export function diffSnapshots(
  previous: StateSnapshot | null,
  next: StateSnapshot,
): SnapshotDiff {
  if (previous === null) {
    return { songChanged: true, nextSongChanged: true };
  }
  return {
    songChanged: previous.current.songId !== next.current.songId,
    nextSongChanged: previous.next.songId !== next.next.songId,
  };
}
```

`client/src/lib/api.ts`:

```ts
import type { StateSnapshot } from "./types";

export class StationUnavailableError extends Error {
  constructor(status: number) {
    super(`Station API returned ${status}. The station may not have started yet.`);
    this.name = "StationUnavailableError";
  }
}

export async function fetchState(baseUrl: string, signal?: AbortSignal): Promise<StateSnapshot> {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/state`, { signal });
  if (!response.ok) {
    throw new StationUnavailableError(response.status);
  }
  return (await response.json()) as StateSnapshot;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd client && npm test`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add client/src
git commit -m "feat(client): add clock correction, timecode formatting, and snapshot diffing"
```

---

### Task 15: Client hooks — station polling and dual audio slots

**Files:**
- Create: `client/src/hooks/useStation.ts`, `client/src/hooks/useAudioSlots.ts`
- Test: `client/src/hooks/useStation.test.ts`

**Interfaces:**
- Consumes: `fetchState`, `computeOffsetMs`, `diffSnapshots` from Task 14.
- Produces:
  - `useStation(baseUrl) -> { snapshot, offsetMs, error }`
  - `useAudioSlots({ url, startAtIso, offsetMs, isPlaying }) -> { positionMs, durationMs, toggle }`

- [ ] **Step 1: Write the failing test**

`client/src/hooks/useStation.test.ts`:

```ts
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useStation } from "./useStation";

const snapshot = {
  serverTime: "2026-07-28T12:00:00Z",
  current: {
    songId: "a",
    title: "Nightshift Drift",
    artist: "Sable Unit",
    descriptor: "melancholic",
    url: "https://cdn.example/tracks/a.m4a",
    startAt: "2026-07-28T12:00:00Z",
    endAt: "2026-07-28T12:00:10Z",
    durationMs: 10_000,
  },
  next: { songId: "b", status: "fallback" },
};

describe("useStation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse("2026-07-28T12:00:00Z"));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("fetches a snapshot on mount and derives the clock offset", async () => {
    const { result } = renderHook(() => useStation("https://api.example"));

    await waitFor(() => expect(result.current.snapshot).not.toBeNull());
    expect(result.current.snapshot?.current.songId).toBe("a");
    expect(result.current.offsetMs).toBe(0);
  });

  it("polls again after the interval elapses", async () => {
    renderHook(() => useStation("https://api.example"));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(1);
  });

  it("surfaces an error when the station is not started", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 503 })));
    const { result } = renderHook(() => useStation("https://api.example"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd client && npm test`
Expected: FAIL — `useStation` does not exist.

- [ ] **Step 3: Write useStation**

`client/src/hooks/useStation.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchState } from "../lib/api";
import { computeOffsetMs } from "../lib/clock";
import type { StateSnapshot } from "../lib/types";

const POLL_INTERVAL_MS = 2000;
const POLL_JITTER_MS = 500;
const BOUNDARY_WAKE_MS = 300;

export interface StationState {
  snapshot: StateSnapshot | null;
  offsetMs: number;
  error: Error | null;
}

/**
 * Poll the station snapshot.
 *
 * Three things schedule a fetch: a 2s interval with jitter (jitter keeps a
 * thousand listeners from hitting the origin on the same tick), and a wake
 * shortly after the known song boundary so changeovers feel immediate rather
 * than up to a poll-interval late.
 */
export function useStation(baseUrl: string): StationState {
  const [snapshot, setSnapshot] = useState<StateSnapshot | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(async (signal: AbortSignal) => {
    try {
      const received = Date.now();
      const next = await fetchState(baseUrl, signal);
      if (signal.aborted) {
        return next;
      }
      setSnapshot(next);
      setOffsetMs(computeOffsetMs(next.serverTime, received));
      setError(null);
      return next;
    } catch (caught) {
      if (signal.aborted) {
        return null;
      }
      setError(caught instanceof Error ? caught : new Error(String(caught)));
      return null;
    }
  }, [baseUrl]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const schedule = (delayMs: number) => {
      if (cancelled) {
        return;
      }
      timerRef.current = setTimeout(run, Math.max(0, delayMs));
    };

    const run = async () => {
      const next = await poll(controller.signal);
      if (cancelled) {
        return;
      }

      const interval = POLL_INTERVAL_MS + Math.random() * POLL_JITTER_MS;
      if (next === null) {
        schedule(interval);
        return;
      }

      // Wake just after the boundary if it lands sooner than the next interval.
      const received = Date.now();
      const correctedNow = received + computeOffsetMs(next.serverTime, received);
      const untilBoundary =
        Date.parse(next.current.endAt) - correctedNow + BOUNDARY_WAKE_MS;
      schedule(untilBoundary > 0 ? Math.min(interval, untilBoundary) : interval);
    };

    void run();

    return () => {
      cancelled = true;
      controller.abort();
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, [poll]);

  return { snapshot, offsetMs, error };
}
```

- [ ] **Step 4: Write useAudioSlots**

`client/src/hooks/useAudioSlots.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";

import { positionMs as computePositionMs } from "../lib/clock";

interface AudioSlotsOptions {
  url: string | null;
  startAtIso: string | null;
  offsetMs: number;
  durationMs: number;
}

export interface AudioSlots {
  positionMs: number;
  isPlaying: boolean;
  toggle: () => void;
  error: Error | null;
}

/**
 * Two <audio> elements, swapped at each changeover.
 *
 * A single element would have to load the next track at the boundary, which
 * audibly gaps. The idle slot preloads the incoming track so the swap is a
 * play() call on already-buffered audio.
 */
export function useAudioSlots({
  url,
  startAtIso,
  offsetMs,
  durationMs,
}: AudioSlotsOptions): AudioSlots {
  const slotsRef = useRef<[HTMLAudioElement, HTMLAudioElement] | null>(null);
  const activeIndexRef = useRef(0);
  const loadedUrlRef = useRef<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  if (slotsRef.current === null && typeof Audio !== "undefined") {
    const make = () => {
      const element = new Audio();
      element.preload = "auto";
      // Required for the slice 4 WebAudio analyser; harmless before then.
      element.crossOrigin = "anonymous";
      return element;
    };
    slotsRef.current = [make(), make()];
  }

  // Load and seek whenever the track changes.
  useEffect(() => {
    const slots = slotsRef.current;
    if (!slots || url === null || startAtIso === null || url === loadedUrlRef.current) {
      return;
    }

    const nextIndex = (activeIndexRef.current + 1) % 2;
    const incoming = slots[nextIndex];
    const outgoing = slots[activeIndexRef.current];

    incoming.src = url;
    incoming.currentTime = computePositionMs(startAtIso, offsetMs) / 1000;
    loadedUrlRef.current = url;
    activeIndexRef.current = nextIndex;

    outgoing.pause();
    if (isPlaying) {
      incoming.play().catch((caught: unknown) => {
        setError(caught instanceof Error ? caught : new Error(String(caught)));
      });
    }
  }, [url, startAtIso, offsetMs, isPlaying]);

  // Drive the progress rail from the server clock, not from the element, so a
  // paused or buffering element still shows the station's true position.
  useEffect(() => {
    if (startAtIso === null) {
      return;
    }
    const id = setInterval(() => {
      setPosition(Math.min(computePositionMs(startAtIso, offsetMs), durationMs));
    }, 250);
    return () => clearInterval(id);
  }, [startAtIso, offsetMs, durationMs]);

  const toggle = useCallback(() => {
    const slots = slotsRef.current;
    if (!slots || startAtIso === null) {
      return;
    }
    const active = slots[activeIndexRef.current];

    if (isPlaying) {
      active.pause();
      setIsPlaying(false);
      return;
    }

    // Resuming rejoins the live station rather than continuing where it paused.
    active.currentTime = computePositionMs(startAtIso, offsetMs) / 1000;
    active
      .play()
      .then(() => setIsPlaying(true))
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught : new Error(String(caught)));
      });
  }, [isPlaying, offsetMs, startAtIso]);

  return { positionMs: position, isPlaying, toggle, error };
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd client && npm test`
Expected: PASS (16 tests).

- [ ] **Step 6: Commit**

```bash
git add client/src/hooks
git commit -m "feat(client): add station polling and dual-slot audio playback"
```

---

### Task 16: Client components

**Files:**
- Create: `client/src/components/Waveform.tsx`, `PlayGlyph.tsx`, `ProgressRail.tsx`, `Header.tsx`, `TransportSheet.tsx`
- Test: `client/src/components/Waveform.test.tsx`, `Header.test.tsx`

**Interfaces:**
- Consumes: `timecode` from Task 14.
- Produces: `<Waveform bars height progress isPlaying />`, `<PlayGlyph isPlaying />`, `<ProgressRail positionMs durationMs showPlayhead />`, `<Header variant />`, `<TransportSheet ... />`.

- [ ] **Step 1: Write the failing tests**

`client/src/components/Waveform.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Waveform, barAmplitude } from "./Waveform";

describe("barAmplitude", () => {
  it("is deterministic so the profile is stable across renders", () => {
    expect(barAmplitude(7)).toBe(barAmplitude(7));
  });

  it("stays within the handoff's 0.28 to 1.0 range", () => {
    for (let i = 0; i < 60; i += 1) {
      const amplitude = barAmplitude(i);
      expect(amplitude).toBeGreaterThanOrEqual(0.28);
      expect(amplitude).toBeLessThanOrEqual(1);
    }
  });
});

describe("Waveform", () => {
  it("exposes an accessible label rather than announcing 60 bars", () => {
    render(<Waveform bars={60} height={260} progress={0.5} isPlaying />);

    expect(screen.getByRole("img", { name: /waveform/i })).toBeInTheDocument();
  });
});
```

`client/src/components/Header.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Header } from "./Header";

describe("Header", () => {
  it("renders the brand and both desktop nav items", () => {
    render(<Header variant="desktop" />);

    expect(screen.getByText("PULSE FM")).toBeInTheDocument();
    expect(screen.getByText("HOW IT WORKS")).toBeInTheDocument();
    expect(screen.getByText("LOGIN")).toBeInTheDocument();
  });

  it("drops HOW IT WORKS on mobile", () => {
    render(<Header variant="mobile" />);

    expect(screen.getByText("LOGIN")).toBeInTheDocument();
    expect(screen.queryByText("HOW IT WORKS")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd client && npm test`
Expected: FAIL — components do not exist.

- [ ] **Step 3: Write the waveform**

`client/src/components/Waveform.tsx`:

```tsx
import { useEffect, useRef } from "react";

/**
 * Deterministic bar-height profile from the design handoff.
 *
 * Fixed rather than random so the silhouette is stable across renders. Slice 4
 * replaces this with real WebAudio analyser data.
 */
export function barAmplitude(index: number): number {
  const i = index * 1.3;
  return 0.28 + 0.72 * Math.abs(Math.sin(i * 1.7 + Math.cos(i * 0.6)));
}

interface WaveformProps {
  bars: number;
  height: number;
  /** Playback progress through the track, 0 to 1. Drives the playhead bar. */
  progress: number;
  isPlaying: boolean;
  className?: string;
}

const GAP_PX = 3;
const PLAYHEAD_HALF_WIDTH = 0.02;

/**
 * Rendered to a single canvas rather than 60 animated DOM nodes, per the
 * handoff's production note. Honours prefers-reduced-motion by drawing the
 * static paused state.
 */
export function Waveform({ bars, height, progress, isPlaying, className }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const styles = getComputedStyle(document.documentElement);
    const ink = styles.getPropertyValue("--color-ink").trim() || "#111111";
    const accent = styles.getPropertyValue("--color-accent").trim() || "#D6252B";

    let frame = 0;

    const draw = (timestampMs: number) => {
      const ratio = window.devicePixelRatio || 1;
      const cssWidth = canvas.clientWidth;
      canvas.width = cssWidth * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, cssWidth, height);

      const barWidth = (cssWidth - GAP_PX * (bars - 1)) / bars;
      const centre = height / 2;
      const animate = isPlaying && !reduceMotion;

      for (let i = 0; i < bars; i += 1) {
        const position = i / bars;
        let scale = 1;

        if (animate) {
          // mirrorPulse: scaleY .18 -> 1 -> .18, six interleaved tempos with a
          // left-to-right ripple, matching the handoff's keyframe timings.
          const durationS = 1.2 + (i % 6) * 0.09;
          const delayS = i * 0.035;
          const phase = ((timestampMs / 1000 - delayS) / durationS) % 1;
          const eased = 0.5 - 0.5 * Math.cos(2 * Math.PI * (phase < 0 ? phase + 1 : phase));
          scale = 0.18 + 0.82 * eased;
        }

        const barHeight = barAmplitude(i) * height * scale;

        if (position > progress - PLAYHEAD_HALF_WIDTH && position < progress) {
          context.fillStyle = accent;
          context.globalAlpha = 1;
        } else if (position > progress) {
          context.fillStyle = ink;
          context.globalAlpha = 0.22;
        } else {
          context.fillStyle = ink;
          context.globalAlpha = isPlaying ? 1 : 0.5;
        }

        context.fillRect(
          i * (barWidth + GAP_PX),
          centre - barHeight / 2,
          barWidth,
          barHeight,
        );
      }

      context.globalAlpha = 1;
      if (animate) {
        frame = requestAnimationFrame(draw);
      }
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [bars, height, progress, isPlaying]);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label="Waveform visualiser"
      style={{ height }}
      className={`w-full ${className ?? ""}`}
    />
  );
}
```

- [ ] **Step 4: Write the glyph, rail, and header**

`client/src/components/PlayGlyph.tsx`:

```tsx
interface PlayGlyphProps {
  isPlaying: boolean;
}

/** Pure geometry, scaled 0.9x as specified. No icon font. */
export function PlayGlyph({ isPlaying }: PlayGlyphProps) {
  if (isPlaying) {
    return (
      <span className="flex gap-[4.5px]" aria-hidden="true">
        <span className="block w-[3.6px] h-[16.2px] bg-paper" />
        <span className="block w-[3.6px] h-[16.2px] bg-paper" />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className="block ml-1"
      style={{
        borderLeft: "14.4px solid var(--color-paper)",
        borderTop: "9px solid transparent",
        borderBottom: "9px solid transparent",
      }}
    />
  );
}
```

`client/src/components/ProgressRail.tsx`:

```tsx
import { timecode } from "../lib/format";

interface ProgressRailProps {
  positionMs: number;
  durationMs: number;
  showPlayhead: boolean;
  gapClassName: string;
}

export function ProgressRail({
  positionMs,
  durationMs,
  showPlayhead,
  gapClassName,
}: ProgressRailProps) {
  const fraction = durationMs > 0 ? Math.min(1, Math.max(0, positionMs / durationMs)) : 0;
  const percent = fraction * 100;

  return (
    <div className={`flex flex-1 items-center min-w-0 ${gapClassName}`}>
      <span className="font-mono text-[11px] tracking-[0.16em] text-paper/60">
        {timecode(positionMs)}
      </span>
      <div className="relative h-0.5 flex-1 bg-paper/[.18]">
        <div
          className="absolute inset-y-0 left-0 bg-paper"
          style={{ right: `${100 - percent}%` }}
        />
        {showPlayhead && (
          <div
            className="absolute -top-[3px] size-2 rounded-full bg-accent"
            style={{ left: `${percent}%` }}
          />
        )}
      </div>
      <span className="font-mono text-[11px] tracking-[0.16em] text-paper/60">
        {timecode(durationMs)}
      </span>
    </div>
  );
}
```

`client/src/components/Header.tsx`:

```tsx
interface HeaderProps {
  variant: "desktop" | "mobile";
}

/**
 * LOGIN is a static anchor in slices 0-1. Firebase Auth wires it in slice 3,
 * where it becomes LOGOUT for signed-in listeners.
 */
export function Header({ variant }: HeaderProps) {
  const isDesktop = variant === "desktop";

  return (
    <div
      className={`flex items-center justify-between font-mono text-[11px] font-semibold tracking-[0.22em] ${
        isDesktop ? "px-11 pt-[30px]" : "px-7 pt-[26px]"
      }`}
    >
      <span className="flex items-center gap-2">
        <span className="size-1.5 rounded-full bg-accent" />
        <span className="text-ink/45">PULSE FM</span>
      </span>
      <span className="flex items-center gap-[26px]">
        {isDesktop && <span className="text-ink/45">HOW IT WORKS</span>}
        <a
          href="#"
          className="text-ink/45 no-underline tracking-[0.22em] hover:opacity-100"
        >
          LOGIN
        </a>
      </span>
    </div>
  );
}
```

`client/src/components/TransportSheet.tsx`:

```tsx
import { PlayGlyph } from "./PlayGlyph";
import { ProgressRail } from "./ProgressRail";

interface TransportSheetProps {
  variant: "desktop" | "mobile";
  title: string;
  artist: string;
  positionMs: number;
  durationMs: number;
  isPlaying: boolean;
  onToggle: () => void;
}

export function TransportSheet({
  variant,
  title,
  artist,
  positionMs,
  durationMs,
  isPlaying,
  onToggle,
}: TransportSheetProps) {
  const label = isPlaying ? "Pause" : "Play";

  if (variant === "desktop") {
    return (
      <div className="absolute inset-x-0 bottom-0 flex h-[126px] items-center gap-10 bg-ink px-11 text-paper">
        <button
          type="button"
          aria-label={label}
          onClick={onToggle}
          className="grid size-[66px] flex-none cursor-pointer place-items-center rounded-full bg-accent transition-transform duration-150 hover:scale-105"
        >
          <PlayGlyph isPlaying={isPlaying} />
        </button>
        <ProgressRail
          positionMs={positionMs}
          durationMs={durationMs}
          showPlayhead
          gapClassName="gap-4"
        />
      </div>
    );
  }

  return (
    <div className="rounded-t-[34px] rounded-b-[46px] bg-ink px-[30px] pt-[30px] pb-10 text-paper">
      <div className="flex items-center justify-between gap-5">
        <div className="min-w-0">
          <div className="truncate text-[23px] font-medium tracking-[-0.02em]">{title}</div>
          <div className="mt-[7px] font-mono text-[12px] tracking-[0.20em] text-paper/50 uppercase">
            {artist}
          </div>
        </div>
        <button
          type="button"
          aria-label={label}
          onClick={onToggle}
          className="grid size-16 flex-none cursor-pointer place-items-center rounded-full bg-accent transition-transform duration-150 hover:scale-105"
        >
          <PlayGlyph isPlaying={isPlaying} />
        </button>
      </div>
      <div className="mt-[26px]">
        <ProgressRail
          positionMs={positionMs}
          durationMs={durationMs}
          showPlayhead={false}
          gapClassName="gap-3.5"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd client && npm test`
Expected: PASS (21 tests).

- [ ] **Step 6: Commit**

```bash
git add client/src/components
git commit -m "feat(client): add waveform, transport sheet, and header components"
```

---

### Task 17: Wire the player and deploy

**Files:**
- Modify: `client/src/App.tsx`
- Create: `client/src/components/Player.tsx`
- Test: `client/src/components/Player.test.tsx`

**Interfaces:**
- Consumes: everything from Tasks 14–16.
- Produces: the deployed station at the Firebase Hosting URL.

- [ ] **Step 1: Write the failing test**

`client/src/components/Player.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Player } from "./Player";
import type { StateSnapshot } from "../lib/types";

const snapshot: StateSnapshot = {
  serverTime: "2026-07-28T12:01:00Z",
  current: {
    songId: "a",
    title: "Nightshift Drift",
    artist: "Sable Unit",
    descriptor: "melancholic",
    url: "https://cdn.example/tracks/a.m4a",
    startAt: "2026-07-28T12:00:00Z",
    endAt: "2026-07-28T12:03:52Z",
    durationMs: 232_000,
  },
  next: { songId: "b", status: "fallback" },
};

describe("Player", () => {
  it("renders the track identity and the desktop sub-label", () => {
    render(<Player snapshot={snapshot} offsetMs={0} />);

    expect(screen.getByText("Nightshift Drift")).toBeInTheDocument();
    expect(screen.getByText("SABLE UNIT / WAVEFORM STEREO")).toBeInTheDocument();
  });

  it("shows a waiting message before the first snapshot", () => {
    render(<Player snapshot={null} offsetMs={0} />);

    expect(screen.getByText(/tuning in/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd client && npm test`
Expected: FAIL — `Player` does not exist.

- [ ] **Step 3: Write the player**

`client/src/components/Player.tsx`:

```tsx
import { useAudioSlots } from "../hooks/useAudioSlots";
import type { StateSnapshot } from "../lib/types";
import { Header } from "./Header";
import { TransportSheet } from "./TransportSheet";
import { Waveform } from "./Waveform";

interface PlayerProps {
  snapshot: StateSnapshot | null;
  offsetMs: number;
}

export function Player({ snapshot, offsetMs }: PlayerProps) {
  const current = snapshot?.current ?? null;
  const { positionMs, isPlaying, toggle } = useAudioSlots({
    url: current?.url ?? null,
    startAtIso: current?.startAt ?? null,
    offsetMs,
    durationMs: current?.durationMs ?? 0,
  });

  if (current === null) {
    return (
      <div className="grid h-full place-items-center font-mono text-[11px] tracking-[0.22em] text-ink/45 uppercase">
        Tuning in…
      </div>
    );
  }

  const progress = current.durationMs > 0 ? positionMs / current.durationMs : 0;

  return (
    <>
      {/* Mobile: below md */}
      <div className="relative flex h-full flex-col bg-bone text-ink md:hidden">
        <Header variant="mobile" />
        <div className="flex flex-1 flex-col justify-center gap-6">
          <div className="px-[30px] font-mono text-[11px] tracking-[0.22em] text-ink/45">
            WAVEFORM / STEREO
          </div>
          <Waveform bars={30} height={190} progress={progress} isPlaying={isPlaying} />
        </div>
        <TransportSheet
          variant="mobile"
          title={current.title}
          artist={current.artist.toUpperCase()}
          positionMs={positionMs}
          durationMs={current.durationMs}
          isPlaying={isPlaying}
          onToggle={toggle}
        />
      </div>

      {/* Desktop: md and above */}
      <div className="relative hidden h-full flex-col bg-bone text-ink md:flex">
        <Header variant="desktop" />
        <div className="flex flex-1 flex-col items-center justify-center gap-[34px] pb-10">
          <div className="text-center">
            <div className="text-[56px] font-medium tracking-[-0.035em]">{current.title}</div>
            <div className="mt-[14px] font-mono text-[12px] tracking-[0.24em] text-ink/45">
              {`${current.artist} / WAVEFORM STEREO`.toUpperCase()}
            </div>
          </div>
          <Waveform bars={60} height={260} progress={progress} isPlaying={isPlaying} />
        </div>
        <div className="h-[126px]" />
        <TransportSheet
          variant="desktop"
          title={current.title}
          artist={current.artist.toUpperCase()}
          positionMs={positionMs}
          durationMs={current.durationMs}
          isPlaying={isPlaying}
          onToggle={toggle}
        />
      </div>
    </>
  );
}
```

- [ ] **Step 4: Wire App**

`client/src/App.tsx`:

```tsx
import { useStation } from "./hooks/useStation";
import { Player } from "./components/Player";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export function App() {
  const { snapshot, offsetMs, error } = useStation(API_BASE_URL);

  if (error !== null && snapshot === null) {
    return (
      <div className="grid h-full place-items-center px-8 text-center font-mono text-[11px] tracking-[0.22em] text-ink/45 uppercase">
        Station offline — {error.message}
      </div>
    );
  }

  return <Player snapshot={snapshot} offsetMs={offsetMs} />;
}
```

Add to `client/src/vite-env.d.ts`:

```ts
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd client && npm test && npm run build`
Expected: PASS (23 tests), build succeeds.

- [ ] **Step 6: Verify against the live station**

Run:

```bash
cd client
echo "VITE_API_BASE_URL=$(cd ../terraform && terraform output -raw station_api_url)" > .env.local
npm run dev
```

Open the dev server and confirm, in order:

1. The track title, artist sub-label, and timecodes render.
2. Pressing play starts audio **mid-track**, at the station's position — not from 00:00.
3. Opening a second browser window shows the same position within roughly a second.
4. At the song boundary, the title changes and audio swaps without a gap.
5. Resizing below `md` switches to the mobile composition: title moves into the black sheet, the waveform drops to 30 bars, the playhead dot disappears.

**Item 2 is the whole point of slice 1.** Do not proceed until it is confirmed.

- [ ] **Step 7: Deploy**

Run:

```bash
cd client
npm run build
npx firebase-tools deploy --only hosting --project "$PROJECT_ID"
```

Expected: a hosting URL. Repeat the checks from Step 6 against it.

Add the deployed origin to `client_origins` in `terraform/terraform.tfvars` and re-apply, so the bucket's CORS configuration covers it before slice 4 needs it.

- [ ] **Step 8: Commit**

```bash
git add client
git commit -m "feat(client): wire the synchronized player and deploy to Firebase Hosting"
```

---

### Task 18: Slice documentation and the portfolio post

**Files:**
- Create: `README.md`
- Create: `docs/adr/0001-firestore-only-state.md`
- Create: `~/Documents/repos/portfolio/content/projects/pulsefm/posts/04-rebuilding-pulsefm-the-clock-first.md`

**Interfaces:**
- Consumes: everything built above.
- Produces: the repository README, the first v2 ADR, and the slice's editorial post.

- [ ] **Step 1: Write the README**

`README.md`:

```markdown
# PulseFM v2

AI-generated lofi radio. Listeners vote on the vibe of the next track; the
winner is generated and plays when the current track ends.

## Status

Slices 0 and 1 are complete: the station rotates through a seeded pool on a
server-driven clock, and the React player joins mid-song in sync. Polls,
voting, auth, and generation land in slices 2 and 3.

## Layout

- `services/radio-service` — rotation clock, sole writer of station state
- `services/station-api` — public read API
- `packages/pulsefm-models` — shared wire models
- `client` — React SPA on Firebase Hosting
- `terraform` — all infrastructure
- `scripts/seed_tracks.py` — seed the fallback pool
- `docs/superpowers/specs` — design documents
- `docs/adr` — architecture decision records

## Development

```bash
uv sync --all-packages
uv run pytest packages/ services/ -m "not integration"

npx -y firebase-tools emulators:exec --only firestore --project pulsefm-test \
  "uv run pytest packages/ services/ -m integration"

cd client && npm install && npm test && npm run dev
```

## Starting a station from empty

```bash
cd terraform && terraform apply
uv run python -m scripts.seed_tracks --bucket "$(terraform output -raw songs_bucket_name)" --dir ./seed-audio
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(terraform output -raw radio_service_url)/bootstrap"
```

After `/bootstrap`, the station is self-driving: each rotation schedules the
next one via Cloud Tasks.
```

- [ ] **Step 2: Write the ADR**

`docs/adr/0001-firestore-only-state.md`:

```markdown
# 0001. Firestore Only, No Redis

Date: 2026-07-28
Status: Accepted

## Context

v1 ran Memorystore Redis for vote tallies, with an atomic Lua script doing
validation, dedupe, and tally in one round-trip (v1 ADR 0003). It was fast and
correct, but it cost ~$40-60/month fixed for the instance plus a VPC connector,
and it forced every Cloud Run service onto a VPC.

v2 also needs a guarantee v1 achieved through invalidation: when a generation
finishes, the radio service must see the song as available immediately.

## Decision

Use Firestore for everything.

- Vote dedupe is a document create at `polls/{pollId}/votes/{uid}`. A create
  fails if the document exists, so dedupe is atomic without a transaction and
  without single-document write contention.
- Tallies are computed once at poll close into an immutable `tallySnapshot`,
  because the design hides results until the poll closes. There is no live
  tally read path to make fast.
- Firestore is strongly consistent, so the worker's `status: ready` write is
  visible to the radio service's very next read. "Reflect immediately" is the
  store's own guarantee rather than something the application arranges.

## Consequences

- No VPC, no Redis bill, no second datastore to reason about.
- Vote writes are slower than a Redis round-trip (tens of milliseconds against
  sub-millisecond). Irrelevant at one vote per user per poll.
- Rotation correctness now rests on Firestore transactions plus a monotonic
  `version` field rather than on Lua atomicity. Both the replayed-task and the
  concurrent-instance cases are covered by emulator tests.
- If a live tally is ever wanted during an open poll, this decision must be
  revisited: COUNT aggregations on every listener poll would be the wrong
  shape, and a cache would reintroduce the freshness problem Redis solved.
```

- [ ] **Step 3: Write the portfolio post**

Create `~/Documents/repos/portfolio/content/projects/pulsefm/posts/04-rebuilding-pulsefm-the-clock-first.md` with frontmatter `title`, `date: 2026-07-28`, and `excerpt`, following the structure of the existing Huddl posts. Cover, in the author's own voice:

- Why v2 exists: five services and three functions collapsing to two services.
- The playback decision — why discrete tracks beat HLS here, and specifically that HLS buffering desyncs voting from what the listener is hearing.
- Dropping Redis, and how create-only documents replace an atomic Lua script.
- Why the clock was built before the product: slice 1 proves browser audio sync with no polls, no auth, and no GPU in the picture.

Verify it renders at `/projects/pulsefm/posts/04-rebuilding-pulsefm-the-clock-first` and appears under the Editorial sidebar group.

- [ ] **Step 4: Commit both repositories**

```bash
git add README.md docs/adr
git commit -m "docs: add README and ADR 0001 on Firestore-only state"

cd ~/Documents/repos/portfolio
git add content/projects/pulsefm/posts
git commit -m "content(pulsefm): add slice 1 editorial post"
```

Leave the PulseFM doc pages (`index.md`, `architecture.md`, and the rest) alone. Per the spec, they are rewritten once at the end, when the architecture stops moving. Their stale SSE and five-services claims stay for now — deliberately.

---

## Self-Review

**Spec coverage.** D1 (public CDN) → Tasks 10, 12. D2 (Firestore only) → Tasks 4, 18. D3 (two services split by traffic) → Tasks 6, 7, 11. D4 (fallback pool) → Tasks 3, 4, 12. D8 (Cloud Tasks chaining) → Tasks 5, 11. D11 (`Cache-Control`) → Task 7. F3, F4 (duplicate ticks, rotation races) → Tasks 3, 4, 6. F7 (empty pool) → Task 12. F8 (clock skew) → Tasks 14, 15. Frontend stack, `useStation`, dual audio slots, waveform, and Firebase Hosting → Tasks 13–17.

Deliberately out of scope, per the slice table: D5 (Modal), D6/D7 (tallies and reveal), D9 (auth), D10 (titles at generation time — Task 12 assigns seed titles from filenames instead), the vote panel, API Gateway, and the analyser waveform.

**Type consistency.** `CandidateSong(song_id, duration_ms)` and `RotationPlan` are used identically in Tasks 3–6. `build_state` is keyword-only in both its definition and its call sites. `StateSnapshot.next` is the JSON name; `next_up` is the Python field with `alias="next"` — Task 2's test asserts the wire form, Task 7 uses the Python form. Client `positionMs` is imported as `computePositionMs` inside `useAudioSlots` to avoid shadowing the returned property of the same name.

**Known rough edge, called out rather than hidden.** Task 6 Step 3 writes a module-level `app = _build_default_app()` that Step 4 immediately replaces with an environment-guarded version. That ordering is intentional — the test in Step 1 fails for the right reason first — but the implementer should apply Step 4 before running Step 5, not after.
