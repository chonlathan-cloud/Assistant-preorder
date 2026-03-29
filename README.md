# 🔐 Lazada Sniper Bot — GCP Serverless Edition

> Automated shopping bot for Lazada, running on Google Cloud Platform.

---

## 📁 Project Structure

```
Assistant-preorder/
├── auth_extractor.py          # Phase 1: Session cookie extractor
├── main.py                    # Phase 2: Mission Controller API (FastAPI)
├── controller/
│   ├── config.py              #   Settings from .env (pydantic-settings)
│   ├── schemas.py             #   Pydantic request/response models
│   └── services.py            #   Firestore + Cloud Tasks logic
├── worker_main.py             # Phase 3: Sniper Worker API (FastAPI)
├── worker/
│   ├── config.py              #   Worker settings from .env
│   ├── schemas.py             #   Execute request/response models
│   ├── secret_manager.py      #   Fetch sessions from Secret Manager
│   ├── sniper.py              #   Core bot logic (Playwright)
│   └── firestore_logger.py    #   Log results to Firestore
├── Dockerfile                 # Cloud Run: Mission Controller
├── Dockerfile.worker          # Cloud Run: Sniper Worker
├── requirements.txt           # All Python dependencies
├── sessions/                  # (gitignored) Extracted session files
├── .env                       # Environment variables
└── planing.md                 # Project roadmap (Thai)
```

---

## Phase 1 — Session Extractor

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

python auth_extractor.py              # Account 1
python auth_extractor.py --account 2  # Account 2
```

Upload to Secret Manager:
```bash
gcloud secrets create LAZ_SESSION_1 --data-file=sessions/session_acc_1.json
gcloud secrets create LAZ_SESSION_2 --data-file=sessions/session_acc_2.json
```

---

## Phase 2 — Mission Controller API

```bash
python main.py                        # → http://localhost:8080/docs
```

Create a mission:
```bash
curl -X POST http://localhost:8080/create-mission \
  -H "Content-Type: application/json" \
  -d '{
    "product_url": "https://www.lazada.co.th/products/i123456789.html",
    "variants": [{"name": "Classic Black", "qty": 10}],
    "schedule_time": "2026-04-01T19:00:00+07:00",
    "accounts": ["acc_1", "acc_2"]
  }'
```

---

## Phase 3 — Sniper Worker

### Run Locally
```bash
python worker_main.py                 # → http://localhost:8081/docs
```

### Test Execute Endpoint
```bash
curl -X POST http://localhost:8081/execute \
  -H "Content-Type: application/json" \
  -d '{
    "mission_id": "abc123",
    "account_id": "acc_1",
    "product_url": "https://www.lazada.co.th/products/i123456789.html",
    "variants": [{"name": "Classic Black", "qty": 2}]
  }'
```

### Deploy to Cloud Run
```bash
# Build & push worker image
gcloud builds submit --tag gcr.io/project001-489710/sniper-worker -f Dockerfile.worker .

# Deploy as private (Cloud Tasks authenticated)
gcloud run deploy sniper-worker \
  --image gcr.io/project001-489710/sniper-worker \
  --region asia-southeast1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --no-allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=project001-489710,GCP_REGION=asia-southeast1,FIRESTORE_COLLECTION=missions,SECRET_ID_ACC_1=LAZ_SESSION_1,SECRET_ID_ACC_2=LAZ_SESSION_2,PAGE_LOAD_TIMEOUT=30000,MAX_RETRY=3"
```

> ⚠️ After deploying, update `WORKER_URL` in `.env` with the Cloud Run URL and redeploy the Mission Controller.

---

## ⚠️ Security Notes

- **Never commit** `sessions/*.json` or `.env` to git.
- Lazada cookies expire every **1–2 days** — re-run the extractor before each sale.
- Deploy the Worker as **private** (`--no-allow-unauthenticated`) — only Cloud Tasks (with OIDC) can trigger it.
