"""Firestore access for station state.

`rotate` and `bootstrap` are transactional and guarded by a monotonic version.
Cloud Tasks delivers at least once and Cloud Run may run several instances, so
both a replayed tick and two concurrent instances must converge on one winner.
"""

from datetime import UTC, datetime

from google.cloud import firestore

from pulsefm_radio_service.config import Settings
from pulsefm_radio_service.logic import CandidateSong, RotationPlan


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
                if plan.version <= int(existing.get("version", 0)):
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
