import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_id: str
    station_doc: str
    songs_collection: str
    cdn_base_url: str
    state_max_age_seconds: int
    allowed_origins: list[str]


def _parse_allowed_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def settings_from_env() -> Settings:
    return Settings(
        project_id=os.environ["PROJECT_ID"],
        station_doc=os.getenv("STATION_DOC", "station/current"),
        songs_collection=os.getenv("SONGS_COLLECTION", "songs"),
        cdn_base_url=os.environ["CDN_BASE_URL"],
        state_max_age_seconds=int(os.getenv("STATE_MAX_AGE_SECONDS", "1")),
        # Closed unless explicitly configured: an empty list means no
        # Access-Control-Allow-Origin header is ever emitted.
        allowed_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS", "")),
    )
