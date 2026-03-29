"""
Sniper Worker — Firestore Logger
==================================
Logs mission execution results back to Firestore.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud import firestore

from worker.config import worker_settings

logger = logging.getLogger(__name__)

_db: firestore.Client | None = None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=worker_settings.GCP_PROJECT_ID)
    return _db


def log_execution(
    mission_id: str,
    account_id: str,
    status: str,
    orders_placed: int = 0,
    screenshots: list[str] | None = None,
    error: Optional[str] = None,
    duration_seconds: float = 0.0,
    ai_usage_count: int = 0,
    ai_logs: list[str] | None = None,
) -> None:
    """
    Log the execution result as a sub-document under the mission.

    Structure:
      missions/{mission_id}/executions/{account_id}
    """
    db = _get_db()
    doc_ref = (
        db.collection(worker_settings.FIRESTORE_COLLECTION)
        .document(mission_id)
        .collection("executions")
        .document(account_id)
    )

    doc_data = {
        "account_id": account_id,
        "status": status,
        "orders_placed": orders_placed,
        "screenshots": screenshots or [],
        "error": error,
        "duration_seconds": duration_seconds,
        "ai_usage_count": ai_usage_count,
        "ai_logs": ai_logs or [],
        "executed_at": firestore.SERVER_TIMESTAMP,
    }

    doc_ref.set(doc_data)
    logger.info(f"Execution logged → missions/{mission_id}/executions/{account_id} [{status}]")


def update_mission_status(mission_id: str, status: str) -> None:
    """Update the top-level mission status (e.g. 'completed', 'failed')."""
    db = _get_db()
    doc_ref = db.collection(worker_settings.FIRESTORE_COLLECTION).document(mission_id)
    doc_ref.update({"status": status, "updated_at": firestore.SERVER_TIMESTAMP})
    logger.info(f"Mission {mission_id} status → {status}")
