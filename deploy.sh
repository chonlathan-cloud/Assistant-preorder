#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & Deploy to Cloud Run via Artifact Registry
# Usage:
#   ./deploy.sh all          # Build + deploy both services
#   ./deploy.sh controller   # Build + deploy controller only
#   ./deploy.sh worker       # Build + deploy worker only
#   ./deploy.sh build        # Build images only (no deploy)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────
PROJECT_ID="project001-489710"
REGION="asia-southeast1"
SERVICE_ACCOUNT="backend-runtime@project001-489710.iam.gserviceaccount.com"

# Artifact Registry
AR_REPO="preorder"
AR_HOST="${REGION}-docker.pkg.dev"
AR_BASE="${AR_HOST}/${PROJECT_ID}/${AR_REPO}"

# Cloud Run services
CONTROLLER_SERVICE="preorder-controller"
WORKER_SERVICE="preorder-worker"

# Images
CONTROLLER_IMAGE="${AR_BASE}/${CONTROLLER_SERVICE}:latest"
WORKER_IMAGE="${AR_BASE}/${WORKER_SERVICE}:latest"

# Resources
MEMORY="2Gi"
CPU="2"
TIMEOUT="300"

# ─── Environment Variables ───────────────────────────────────
# Controller
CONTROLLER_ENV_VARS="GCP_PROJECT_ID=${PROJECT_ID}"
CONTROLLER_ENV_VARS+=",GCP_REGION=${REGION}"
CONTROLLER_ENV_VARS+=",FIRESTORE_COLLECTION=missions"
CONTROLLER_ENV_VARS+=",QUEUE_NAME=bot-mission-queue"
# WORKER_URL will be set after worker deploys (see below)

# Worker
WORKER_ENV_VARS="GCP_PROJECT_ID=${PROJECT_ID}"
WORKER_ENV_VARS+=",GCP_REGION=${REGION}"
WORKER_ENV_VARS+=",FIRESTORE_COLLECTION=missions"
WORKER_ENV_VARS+=",GCS_BUCKET_NAME=kyc_id_cards"
WORKER_ENV_VARS+=",SESSION_FILE_ACC_1=session_acc_1.json"
WORKER_ENV_VARS+=",SESSION_FILE_ACC_2=session_acc_2.json"
WORKER_ENV_VARS+=",PAGE_LOAD_TIMEOUT=30000"
WORKER_ENV_VARS+=",MAX_RETRY=3"

# ─── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

# ─── Functions ───────────────────────────────────────────────

ensure_ar_repo() {
    log "Checking Artifact Registry repo '${AR_REPO}'..."
    if ! gcloud artifacts repositories describe "${AR_REPO}" \
        --project="${PROJECT_ID}" \
        --location="${REGION}" &>/dev/null; then
        log "Creating Artifact Registry repo..."
        gcloud artifacts repositories create "${AR_REPO}" \
            --project="${PROJECT_ID}" \
            --location="${REGION}" \
            --repository-format=docker \
            --description="Lazada Preorder Bot images"
        ok "Artifact Registry repo created"
    else
        ok "Artifact Registry repo exists"
    fi
}

configure_docker_auth() {
    log "Configuring Docker authentication for Artifact Registry..."
    gcloud auth configure-docker "${AR_HOST}" --quiet
    ok "Docker auth configured"
}

build_controller() {
    log "Building controller image..."
    docker build \
        -t "${CONTROLLER_IMAGE}" \
        -f Dockerfile \
        .
    ok "Controller image built: ${CONTROLLER_IMAGE}"
}

build_worker() {
    log "Building worker image (this may take a while — Chromium)..."
    docker build \
        -t "${WORKER_IMAGE}" \
        -f Dockerfile.worker \
        .
    ok "Worker image built: ${WORKER_IMAGE}"
}

push_controller() {
    log "Pushing controller image..."
    docker push "${CONTROLLER_IMAGE}"
    ok "Controller image pushed"
}

push_worker() {
    log "Pushing worker image..."
    docker push "${WORKER_IMAGE}"
    ok "Worker image pushed"
}

deploy_worker() {
    log "Deploying ${WORKER_SERVICE} to Cloud Run..."
    gcloud run deploy "${WORKER_SERVICE}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --image="${WORKER_IMAGE}" \
        --service-account="${SERVICE_ACCOUNT}" \
        --memory="${MEMORY}" \
        --cpu="${CPU}" \
        --timeout="${TIMEOUT}" \
        --no-allow-unauthenticated \
        --set-env-vars="${WORKER_ENV_VARS}" \
        --min-instances=0 \
        --max-instances=4 \
        --quiet
    ok "${WORKER_SERVICE} deployed (private — Cloud Tasks only)"

    # Get the worker URL
    WORKER_URL=$(gcloud run services describe "${WORKER_SERVICE}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --format="value(status.url)")
    ok "Worker URL: ${WORKER_URL}"
    echo "${WORKER_URL}" > .worker_url
}

deploy_controller() {
    # Read worker URL if available
    if [ -f .worker_url ]; then
        WORKER_URL=$(cat .worker_url)
    else
        WORKER_URL=$(gcloud run services describe "${WORKER_SERVICE}" \
            --project="${PROJECT_ID}" \
            --region="${REGION}" \
            --format="value(status.url)" 2>/dev/null || echo "https://WORKER_URL_NOT_SET")
    fi

    local FULL_WORKER_URL="${WORKER_URL}/execute"

    log "Deploying ${CONTROLLER_SERVICE} to Cloud Run..."
    log "WORKER_URL → ${FULL_WORKER_URL}"

    gcloud run deploy "${CONTROLLER_SERVICE}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --image="${CONTROLLER_IMAGE}" \
        --service-account="${SERVICE_ACCOUNT}" \
        --memory="${MEMORY}" \
        --cpu="${CPU}" \
        --timeout="${TIMEOUT}" \
        --allow-unauthenticated \
        --set-env-vars="${CONTROLLER_ENV_VARS},WORKER_URL=${FULL_WORKER_URL}" \
        --min-instances=0 \
        --max-instances=2 \
        --quiet
    ok "${CONTROLLER_SERVICE} deployed (public)"

    CONTROLLER_URL=$(gcloud run services describe "${CONTROLLER_SERVICE}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --format="value(status.url)")
    ok "Controller URL: ${CONTROLLER_URL}"
}

print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  🚀 Deployment Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"

    if [ -f .worker_url ]; then
        echo -e "  Worker:     $(cat .worker_url)"
    fi

    CTRL_URL=$(gcloud run services describe "${CONTROLLER_SERVICE}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --format="value(status.url)" 2>/dev/null || echo "not deployed")
    echo -e "  Controller: ${CTRL_URL}"
    echo -e "  Swagger UI: ${CTRL_URL}/docs"
    echo -e ""
    echo -e "  Project:    ${PROJECT_ID}"
    echo -e "  Region:     ${REGION}"
    echo -e "  SA:         ${SERVICE_ACCOUNT}"
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
}

# ─── Main ────────────────────────────────────────────────────

CMD="${1:-all}"

case "${CMD}" in
    build)
        ensure_ar_repo
        configure_docker_auth
        build_controller
        build_worker
        push_controller
        push_worker
        ok "All images built and pushed!"
        ;;
    controller)
        ensure_ar_repo
        configure_docker_auth
        build_controller
        push_controller
        deploy_controller
        print_summary
        ;;
    worker)
        ensure_ar_repo
        configure_docker_auth
        build_worker
        push_worker
        deploy_worker
        print_summary
        ;;
    all)
        echo -e "${BLUE}"
        echo "  ╔═══════════════════════════════════════════╗"
        echo "  ║  🔫 Lazada Preorder Bot — Full Deploy     ║"
        echo "  ╚═══════════════════════════════════════════╝"
        echo -e "${NC}"

        ensure_ar_repo
        configure_docker_auth

        # Build both
        build_controller
        build_worker

        # Push both
        push_controller
        push_worker

        # Deploy worker first (to get URL for controller)
        deploy_worker
        deploy_controller

        print_summary
        ;;
    *)
        echo "Usage: ./deploy.sh {all|controller|worker|build}"
        exit 1
        ;;
esac
