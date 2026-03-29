"""
Sniper Worker — Pydantic Schemas
=================================
Request/response models for the /execute endpoint.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VariantItem(BaseModel):
    """A single variant to purchase."""
    name: str = Field(..., description="Variant display name, e.g. 'Classic Black'")
    qty: int = Field(..., ge=1, description="Quantity to buy")


class ExecuteRequest(BaseModel):
    """POST /execute — payload sent by Cloud Tasks."""
    mission_id: str = Field(..., description="Firestore mission document ID")
    account_id: str = Field(..., description="Account identifier, e.g. 'acc_1'")
    product_url: str = Field(..., description="Full Lazada product URL")
    variants: List[VariantItem] = Field(..., min_length=1)


class ExecuteResponse(BaseModel):
    """POST /execute — response."""
    mission_id: str
    account_id: str
    status: str  # "success" | "failed" | "partial"
    orders_placed: int = 0
    screenshots: List[str] = []
    error: Optional[str] = None
    duration_seconds: float = 0.0
