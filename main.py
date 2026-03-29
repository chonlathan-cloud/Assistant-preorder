"""
Mission Controller API
======================
FastAPI application for scheduling Lazada shopping bot missions.

Endpoints:
    POST /create-mission  — Schedule a new purchase mission
    GET  /health          — Health check
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from controller.config import settings
from controller.schemas import CreateMissionRequest, CreateMissionResponse
from controller.services import schedule_mission, get_all_missions, get_mission_executions, generate_signed_url

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Lazada Sniper Controller",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "ok",
        "project": settings.GCP_PROJECT_ID,
        "region": settings.GCP_REGION,
        "queue": settings.QUEUE_NAME,
    }


@app.get("/missions")
async def list_missions():
    """List all missions, sorted by creation time."""
    try:
        missions = get_all_missions()
        return {"missions": missions}
    except Exception as e:
        logger.error(f"List missions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/missions/{mission_id}/results")
async def list_mission_results(mission_id: str):
    """Get the execution results for a specific mission."""
    try:
        executions = get_mission_executions(mission_id)
        return {"mission_id": mission_id, "executions": executions}
    except Exception as e:
        logger.error(f"Get mission results error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signed-url")
async def get_signed_url(path: str):
    """Generate a signed URL for a GCS blob."""
    try:
        url = generate_signed_url(path)
        return {"signed_url": url}
    except Exception as e:
        logger.error(f"Signed URL error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-mission", response_model=CreateMissionResponse)
async def create_mission(request: CreateMissionRequest):
    """
    Create a new shopping mission.

    1. Saves mission config to Firestore.
    2. Creates one Cloud Task per account, scheduled at `schedule_time`.
    3. Each task will POST to the Worker (Cloud Run) with mission details.
    """
    try:
        logger.info(
            f"New mission: {len(request.accounts)} accounts × "
            f"{len(request.variants)} variants @ {request.schedule_time}"
        )

        mission_id, task_infos = schedule_mission(request)

        return CreateMissionResponse(
            mission_id=mission_id,
            status="scheduled",
            tasks_created=len(task_infos),
            tasks=task_infos,
        )

    except Exception as e:
        logger.error(f"Failed to create mission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
