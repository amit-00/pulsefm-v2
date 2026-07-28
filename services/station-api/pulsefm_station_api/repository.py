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
