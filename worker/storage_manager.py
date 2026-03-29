"""
Sniper Worker — GCS Storage Manager
=====================================
Download session JSONs from GCS and upload screenshots/results back.
"""

import json
import logging
from pathlib import Path
from typing import Any

from google.cloud import storage

from worker.config import worker_settings

logger = logging.getLogger(__name__)

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=worker_settings.GCP_PROJECT_ID)
    return _client


def _get_bucket() -> storage.Bucket:
    return _get_client().bucket(worker_settings.GCS_BUCKET_NAME)


def fetch_session(account_id: str) -> dict[str, Any]:
    """
    Download the session JSON for a given account from GCS.

    Returns the parsed JSON containing:
      - storage_state: Playwright cookies & origins
      - lazada_local_storage: full localStorage dump
    """
    blob_name = worker_settings.get_session_blob_name(account_id)
    bucket = _get_bucket()
    blob = bucket.blob(blob_name)

    logger.info(f"Downloading session: gs://{worker_settings.GCS_BUCKET_NAME}/{blob_name}")
    payload = blob.download_as_text(encoding="utf-8")

    session_data = json.loads(payload)
    cookies_count = len(session_data.get("storage_state", {}).get("cookies", []))
    logger.info(f"Session loaded for {account_id} — {cookies_count} cookies")
    return session_data


def upload_screenshot(local_path: str, mission_id: str, account_id: str) -> str:
    """
    Upload a screenshot to GCS under results/{mission_id}/{account_id}/.

    Returns the gs:// URI of the uploaded file.
    """
    bucket = _get_bucket()
    filename = Path(local_path).name
    blob_path = f"{worker_settings.GCS_RESULTS_FOLDER}/{mission_id}/{account_id}/{filename}"
    blob = bucket.blob(blob_path)

    blob.upload_from_filename(local_path, content_type="image/png")

    gcs_uri = f"gs://{worker_settings.GCS_BUCKET_NAME}/{blob_path}"
    logger.info(f"📤 Screenshot uploaded → {gcs_uri}")
    return gcs_uri
