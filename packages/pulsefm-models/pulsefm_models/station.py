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
