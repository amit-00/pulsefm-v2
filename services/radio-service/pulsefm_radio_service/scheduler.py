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
