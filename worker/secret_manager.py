"""
Sniper Worker — Secret Manager Integration
============================================
Fetch Lazada session JSON from Google Cloud Secret Manager.
"""

import json
import logging
from typing import Any

from google.cloud import secretmanager

from worker.config import worker_settings

logger = logging.getLogger(__name__)

_client: secretmanager.SecretManagerServiceClient | None = None


def _get_client() -> secretmanager.SecretManagerServiceClient:
    global _client
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
    return _client


def fetch_session(account_id: str) -> dict[str, Any]:
    """
    Fetch the session JSON for a given account from Secret Manager.

    Returns the parsed JSON containing:
      - storage_state: Playwright cookies & origins
      - lazada_local_storage: full localStorage dump
    """
    client = _get_client()
    secret_id = worker_settings.get_secret_id(account_id)

    # Access the latest version
    name = (
        f"projects/{worker_settings.GCP_PROJECT_ID}"
        f"/secrets/{secret_id}"
        f"/versions/latest"
    )

    logger.info(f"Fetching session secret: {secret_id}")
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("utf-8")

    session_data = json.loads(payload)
    logger.info(
        f"Session loaded for {account_id} — "
        f"{len(session_data.get('storage_state', {}).get('cookies', []))} cookies"
    )
    return session_data
