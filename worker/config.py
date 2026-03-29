"""
Sniper Worker — Configuration
==============================
Loads settings from .env using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Worker-specific settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GCP
    GCP_PROJECT_ID: str
    GCP_REGION: str = "asia-southeast1"

    # Firestore
    FIRESTORE_COLLECTION: str = "missions"

    # GCS — session files & results
    GCS_BUCKET_NAME: str = "kyc_id_cards"
    SESSION_FILE_ACC_1: str = "session_acc_1.json"
    SESSION_FILE_ACC_2: str = "session_acc_2.json"
    GCS_RESULTS_FOLDER: str = "results"

    # Bot tuning
    PAGE_LOAD_TIMEOUT: int = 30000  # ms
    MAX_RETRY: int = 3

    # Flash-sale polling
    FLASH_POLL_INTERVAL_MS: int = 500   # poll every 500ms
    FLASH_POLL_TIMEOUT_S: int = 60      # give up after 60s

    # Screenshots directory (inside container)
    SCREENSHOT_DIR: str = "/tmp/screenshots"

    def get_session_blob_name(self, account_id: str) -> str:
        """Map account_id → GCS blob name for the session file."""
        mapping = {
            "acc_1": self.SESSION_FILE_ACC_1,
            "acc_2": self.SESSION_FILE_ACC_2,
        }
        blob_name = mapping.get(account_id)
        if not blob_name:
            raise ValueError(
                f"Unknown account_id '{account_id}'. "
                f"Expected one of: {list(mapping.keys())}"
            )
        return blob_name


worker_settings = WorkerSettings()
