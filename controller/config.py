"""
Mission Controller API — Configuration
=======================================
Loads settings from .env using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore vars not defined here (e.g. SECRET_ID_ACC_*)
    )

    # GCP
    GCP_PROJECT_ID: str
    GCP_REGION: str = "asia-southeast1"

    # Firestore
    FIRESTORE_COLLECTION: str = "missions"

    # Cloud Tasks
    QUEUE_NAME: str = "bot-mission-queue"
    WORKER_URL: str  # Cloud Run worker endpoint

    @property
    def cloud_tasks_queue_path(self) -> str:
        """Fully qualified Cloud Tasks queue path."""
        return (
            f"projects/{self.GCP_PROJECT_ID}"
            f"/locations/{self.GCP_REGION}"
            f"/queues/{self.QUEUE_NAME}"
        )


settings = Settings()
