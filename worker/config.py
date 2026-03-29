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

    # Secret Manager — session secret names
    SECRET_ID_ACC_1: str = "LAZ_SESSION_1"
    SECRET_ID_ACC_2: str = "LAZ_SESSION_2"

    # Bot tuning
    PAGE_LOAD_TIMEOUT: int = 30000  # ms
    MAX_RETRY: int = 3

    # Flash-sale polling
    FLASH_POLL_INTERVAL_MS: int = 500   # poll every 500ms
    FLASH_POLL_TIMEOUT_S: int = 60      # give up after 60s

    # Screenshots directory (inside container)
    SCREENSHOT_DIR: str = "/tmp/screenshots"

    def get_secret_id(self, account_id: str) -> str:
        """Map account_id → Secret Manager secret name."""
        mapping = {
            "acc_1": self.SECRET_ID_ACC_1,
            "acc_2": self.SECRET_ID_ACC_2,
        }
        secret_id = mapping.get(account_id)
        if not secret_id:
            raise ValueError(
                f"Unknown account_id '{account_id}'. "
                f"Expected one of: {list(mapping.keys())}"
            )
        return secret_id


worker_settings = WorkerSettings()
