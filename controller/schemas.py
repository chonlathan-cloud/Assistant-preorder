"""
Mission Controller API — Pydantic Schemas
==========================================
Request/response models for the /create-mission endpoint.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, HttpUrl


class VariantItem(BaseModel):
    """A single product variant to purchase."""
    name: str = Field(..., description="Variant name, e.g. 'Classic Black'")
    qty: int = Field(..., ge=1, description="Quantity to purchase")


class CreateMissionRequest(BaseModel):
    """POST /create-mission request body."""
    product_url: str = Field(..., description="Full Lazada product URL")
    variants: List[VariantItem] = Field(..., min_length=1, description="List of variants to buy")
    schedule_time: datetime = Field(..., description="When to execute (ISO 8601)")
    accounts: List[str] = Field(
        ...,
        min_length=1,
        description="Account IDs to use, e.g. ['acc_1', 'acc_2']",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_url": "https://www.lazada.co.th/products/i123456789.html",
                    "variants": [
                        {"name": "Classic Black", "qty": 10},
                        {"name": "Rally Red", "qty": 5},
                    ],
                    "schedule_time": "2026-04-01T19:00:00+07:00",
                    "accounts": ["acc_1", "acc_2"],
                }
            ]
        }
    }


class TaskInfo(BaseModel):
    """Info about a scheduled Cloud Task."""
    account_id: str
    task_name: str
    scheduled_time: str


class CreateMissionResponse(BaseModel):
    """POST /create-mission response body."""
    mission_id: str
    status: str = "scheduled"
    tasks_created: int
    tasks: List[TaskInfo]
