# 🔐 Lazada Session Extractor

> **Phase 2** of the [Lazada Sniper Bot](./planing.md) — Extract login session for use by the Cloud Run worker.

## Prerequisites

- **Python 3.12+**
- **pip** (or any Python package manager)

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers (first time only)
playwright install chromium
```

## Usage

### Account 1 (default)
```bash
python auth_extractor.py
```
→ Saves to `sessions/session_acc_1.json`

### Account 2
```bash
python auth_extractor.py --account 2
```
→ Saves to `sessions/session_acc_2.json`

### Custom output path
```bash
python auth_extractor.py --output ./my_session.json
```

## What Happens

1. A **Chromium** window opens on the Lazada login page (non‑headless).
2. **Log in manually** — scan QR code, enter credentials, or use any method.
3. After login, click the floating red **💾 Save Session** button (bottom-right).
4. The script exports **cookies + localStorage** to a JSON file and closes the browser.

> ⏱️ The script times out after **15 minutes** of inactivity.

## Output Format

```
sessions/session_acc_1.json
├── storage_state     ← Playwright cookies & origins
├── lazada_local_storage  ← Full localStorage dump
└── extracted_from    ← URL at time of save
```

## Next Step → Upload to Secret Manager

```bash
# Upload session to GCP Secret Manager (Phase 2 continued)
gcloud secrets create LAZ_SESSION_1 --data-file=sessions/session_acc_1.json
gcloud secrets create LAZ_SESSION_2 --data-file=sessions/session_acc_2.json
```

## ⚠️ Security Notes

- **Never commit** `sessions/*.json` to git (already in `.gitignore`).
- Lazada cookies expire every **1–2 days** — re-run before each sale event.
- Store production sessions in **GCP Secret Manager** only.
