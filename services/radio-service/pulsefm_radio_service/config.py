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
