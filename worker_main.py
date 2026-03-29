"""
Sniper Worker — FastAPI Application
=====================================
Headless bot triggered by Google Cloud Tasks to execute Lazada purchases.

Endpoints:
    POST /execute  — Run a sniper mission for one account
    GET  /health   — Health check
"""

import logging
import time

from fastapi import FastAPI, HTTPException, Request

from worker.config import worker_settings
from worker.schemas import ExecuteRequest, ExecuteResponse
from worker.storage_manager import fetch_session, upload_screenshot
from worker.sniper import execute_snipe
from worker.firestore_logger import log_execution, update_mission_status

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sniper Worker",
    description="Headless Lazada shopping bot — triggered by Cloud Tasks",
    version="1.0.0",
)


# ─── Middleware: Log Cloud Tasks headers ──────────────────────────────────────

@app.middleware("http")
async def log_cloud_tasks_headers(request: Request, call_next):
    """Log Cloud Tasks metadata for debugging."""
    task_name = request.headers.get("X-CloudTasks-TaskName", "—")
    queue_name = request.headers.get("X-CloudTasks-QueueName", "—")
    if task_name != "—":
        logger.info(f"☁️ Cloud Task: {task_name} | Queue: {queue_name}")
    response = await call_next(request)
    return response


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check for Cloud Run."""
    return {
        "status": "ok",
        "service": "sniper-worker",
        "project": worker_settings.GCP_PROJECT_ID,
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """
    Execute a sniper mission for a single account.

    Called by Cloud Tasks at the scheduled time.
    1. Fetch session from GCS
    2. Launch headless browser
    3. Navigate, select variants, checkout
    4. Upload screenshots to GCS + log results to Firestore
    """
    start_time = time.time()

    logger.info(f"\n{'='*60}")
    logger.info(f"  🎯 MISSION: {request.mission_id}")
    logger.info(f"  👤 ACCOUNT: {request.account_id}")
    logger.info(f"  🔗 URL: {request.product_url}")
    logger.info(f"  📦 VARIANTS: {len(request.variants)}")
    logger.info(f"{'='*60}\n")

    try:
        # 1. Fetch session from GCS
        logger.info("🔐 Fetching session from GCS…")
        session_data = fetch_session(request.account_id)

        # 2. Execute the snipe
        logger.info("🚀 Launching sniper…")
        result = await execute_snipe(request, session_data)

        # 3. Upload screenshots to GCS
        gcs_screenshots = []
        for ss_path in result.screenshots:
            try:
                gcs_uri = upload_screenshot(ss_path, request.mission_id, request.account_id)
                gcs_screenshots.append(gcs_uri)
            except Exception as e:
                logger.warning(f"Screenshot upload failed: {e}")
                gcs_screenshots.append(ss_path)  # keep local path as fallback
        result.screenshots = gcs_screenshots

        duration = time.time() - start_time

        # 4. Log to Firestore
        try:
            log_execution(
                mission_id=request.mission_id,
                account_id=request.account_id,
                status=result.status,
                orders_placed=result.orders_placed,
                screenshots=result.screenshots,
                error="; ".join(result.errors) if result.errors else None,
                duration_seconds=round(duration, 2),
                ai_usage_count=result.ai_usage_count,
                ai_logs=result.ai_logs,
            )

            # Update mission-level status if all done
            if result.status in ("success", "failed"):
                update_mission_status(request.mission_id, result.status)

        except Exception as e:
            logger.error(f"Firestore logging failed: {e}", exc_info=True)

        logger.info(f"\n{'='*60}")
        logger.info(f"  📊 RESULT: {result.status.upper()}")
        logger.info(f"  🛒 Orders: {result.orders_placed}")
        logger.info(f"  🤖 AI Assists: {result.ai_usage_count}")
        logger.info(f"  ⏱️ Duration: {duration:.2f}s")
        logger.info(f"{'='*60}\n")

        return ExecuteResponse(
            mission_id=request.mission_id,
            account_id=request.account_id,
            status=result.status,
            orders_placed=result.orders_placed,
            screenshots=result.screenshots,
            error="; ".join(result.errors) if result.errors else None,
            duration_seconds=round(duration, 2),
            ai_usage_count=result.ai_usage_count,
            ai_logs=result.ai_logs,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"💀 Fatal worker error: {e}", exc_info=True)

        # Still try to log failure
        try:
            log_execution(
                mission_id=request.mission_id,
                account_id=request.account_id,
                status="failed",
                error=str(e),
                duration_seconds=round(duration, 2),
            )
            update_mission_status(request.mission_id, "failed")
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=str(e))


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("worker_main:app", host="0.0.0.0", port=8081, reload=True)
