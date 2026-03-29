"""
Mission Controller API — Service Layer
=======================================
Business logic for Firestore persistence and Cloud Tasks scheduling.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

import google.auth
from google.cloud import firestore, tasks_v2, storage
from google.protobuf import timestamp_pb2

from controller.config import settings
from controller.schemas import CreateMissionRequest, TaskInfo

logger = logging.getLogger(__name__)

# ─── GCP Clients (lazy singletons) ──────────────────────────────────────────

_firestore_client: firestore.Client | None = None
_tasks_client: tasks_v2.CloudTasksClient | None = None
_storage_client: storage.Client | None = None
_service_account_email: str | None = None


def _get_firestore_client() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=settings.GCP_PROJECT_ID)
    return _firestore_client


def _get_tasks_client() -> tasks_v2.CloudTasksClient:
    global _tasks_client
    if _tasks_client is None:
        _tasks_client = tasks_v2.CloudTasksClient()
    return _tasks_client


def _get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
    return _storage_client


def _get_service_account_email() -> str:
    """
    Get the service account email for OIDC token.
    Uses google.auth.default() — works with:
      - Impersonated credentials (local dev)
      - Attached Service Account (Cloud Run)
    """
    global _service_account_email
    if _service_account_email is None:
        credentials, project = google.auth.default()
        _service_account_email = getattr(credentials, "service_account_email", None)
        if not _service_account_email:
            # Fallback: try signer_email (impersonated credentials)
            _service_account_email = getattr(credentials, "signer_email", None)
        if not _service_account_email:
            raise RuntimeError(
                "Cannot determine service account email from credentials. "
                "Ensure you are using a Service Account or impersonated credentials."
            )
        logger.info(f"Using service account: {_service_account_email}")
    return _service_account_email


# ─── Cloud Storage Operations ───────────────────────────────────────────────────

def generate_signed_url(blob_path: str, bucket_name: str = "kyc_id_cards", expiration_minutes: int = 15) -> str:
    """Generate a V4 signed URL for downloading a blob."""
    storage_client = _get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    # Strip gs:// prefix if passed by accident
    if blob_path.startswith("gs://"):
        parts = blob_path.split("/")
        if len(parts) >= 4:
            bucket_name = parts[2]
            blob_path = "/".join(parts[3:])
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET",
    )
    return url


# ─── Firestore Operations ────────────────────────────────────────────────────────────────

def save_mission(request: CreateMissionRequest) -> str:
    """
    Save mission data to Firestore.
    Returns the auto-generated document ID (mission_id).
    """
    db = _get_firestore_client()
    collection = db.collection(settings.FIRESTORE_COLLECTION)

    doc_data = {
        "product_url": request.product_url,
        "variants": [v.model_dump() for v in request.variants],
        "schedule_time": request.schedule_time.isoformat(),
        "accounts": request.accounts,
        "status": "scheduled",
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    _, doc_ref = collection.add(doc_data)
    logger.info(f"Mission saved → {doc_ref.id}")
    return doc_ref.id


def get_all_missions() -> list[dict]:
    db = _get_firestore_client()
    docs = db.collection(settings.FIRESTORE_COLLECTION).order_by("created_at", direction=firestore.Query.DESCENDING).limit(50).stream()
    
    missions = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        # Convert DatetimeWithNanoseconds to ISO string
        if "created_at" in data and hasattr(data["created_at"], "isoformat"):
            data["created_at"] = data["created_at"].isoformat()
        if "schedule_time" in data and hasattr(data["schedule_time"], "isoformat"):
            data["schedule_time"] = data["schedule_time"].isoformat()
        missions.append(data)
    return missions


def get_mission_executions(mission_id: str) -> list[dict]:
    db = _get_firestore_client()
    docs = db.collection(settings.FIRESTORE_COLLECTION).document(mission_id).collection("executions").stream()
    
    executions = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if "executed_at" in data and hasattr(data["executed_at"], "isoformat"):
            data["executed_at"] = data["executed_at"].isoformat()
        executions.append(data)
    return executions


# ─── Cloud Tasks ──────────────────────────────────────────────────────────────

def create_task_for_account(
    mission_id: str,
    account_id: str,
    request: CreateMissionRequest,
) -> TaskInfo:
    """
    Create a single Cloud Task targeting the Worker service.
    One task per account.
    """
    client = _get_tasks_client()
    sa_email = _get_service_account_email()

    # Build the payload the Worker will receive
    payload = {
        "mission_id": mission_id,
        "account_id": account_id,
        "product_url": request.product_url,
        "variants": [v.model_dump() for v in request.variants],
    }

    # Convert schedule_time to protobuf Timestamp
    schedule_ts = timestamp_pb2.Timestamp()
    schedule_dt = request.schedule_time.astimezone(timezone.utc)
    schedule_ts.FromDatetime(schedule_dt)

    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=settings.WORKER_URL,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=  "backend-runtime@project001-489710.iam.gserviceaccount.com",
                audience=settings.WORKER_URL,
            ),
        ),
        schedule_time=schedule_ts,
    )

    created_task = client.create_task(
        parent=settings.cloud_tasks_queue_path,
        task=task,
    )

    task_short_name = created_task.name.split("/")[-1]
    logger.info(f"Cloud Task created → {task_short_name} for {account_id}")

    return TaskInfo(
        account_id=account_id,
        task_name=created_task.name,
        scheduled_time=request.schedule_time.isoformat(),
    )


def schedule_mission(request: CreateMissionRequest) -> tuple[str, list[TaskInfo]]:
    """
    End-to-end: save mission to Firestore, then create one Cloud Task per account.
    Returns (mission_id, list_of_task_infos).
    """
    # 1. Persist to Firestore
    mission_id = save_mission(request)

    # 2. Create a Cloud Task for each account
    task_infos: list[TaskInfo] = []
    for account_id in request.accounts:
        info = create_task_for_account(mission_id, account_id, request)
        task_infos.append(info)

    logger.info(f"Mission {mission_id} → {len(task_infos)} tasks scheduled")
    return mission_id, task_infos
