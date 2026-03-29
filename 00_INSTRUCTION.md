# Project Title: Lazada Sniper Bot (GCP Serverless Edition)

## Objective:
Build an automated shopping bot for Lazada (Target: Rally Movement brand) that can handle high-concurrency (40-50 units) across 2 accounts, running on Google Cloud Platform.

## Architecture:
- Frontend: Streamlit (Cloud Run)
- Backend Worker: Python + Playwright + Playwright-stealth (Cloud Run)
- Database: Firestore (To store mission configs)
- Scheduler: Cloud Tasks (For millisecond-precision triggering)
- Auth: Session Cookies (Stored in Secret Manager)
- AI Fallback: Vertex AI (Gemini 3 Flash) for visual element detection.

## Key Features:
1. High-speed "Buy Now" execution using Hybrid Browser Automation.
2. Parallel execution for multiple accounts.
3. QR Code/Bank Transfer payment method (Waiting for manual payment).
4. Auto-retry loop to handle quantity limits per order.
5. Notification via Gmail/Line when order is placed.