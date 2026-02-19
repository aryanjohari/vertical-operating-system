"""
Pydantic models for analytics snapshot payloads.
Used to validate Lead Gen and pSEO responses before persisting to analytics_snapshots.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduledBridge(BaseModel):
    """Nested scheduled_bridge stats."""
    count: int
    total: int
    pct: float


class LeadGenAnalyticsSnapshot(BaseModel):
    """Shape of Lead Gen analytics API response; validate before save."""
    from_: str = Field(..., alias="from")
    to: str
    webhooks_received: int
    avg_lead_score: Optional[float] = None
    scheduled_bridge: ScheduledBridge
    by_source: Optional[Dict[str, int]] = None

    model_config = ConfigDict(populate_by_name=True)


class PerPageRow(BaseModel):
    """Single row in per_page list."""
    url: str
    clicks: int
    impressions: int
    ctr: float


class PseoAnalyticsSnapshot(BaseModel):
    """Shape of pSEO analytics API response; validate before save."""
    from_: str = Field(..., alias="from")
    to: str
    gsc_connected: bool
    organic_clicks: int
    organic_impressions: int
    ctr: float
    filtered_pages_count: int
    per_page: Optional[List[PerPageRow]] = None

    model_config = ConfigDict(populate_by_name=True)


def validate_lead_gen_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return dict suitable for JSON storage (uses 'from' key)."""
    model = LeadGenAnalyticsSnapshot.model_validate(data)
    return model.model_dump(by_alias=True)


def validate_pseo_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return dict suitable for JSON storage (uses 'from' key)."""
    model = PseoAnalyticsSnapshot.model_validate(data)
    return model.model_dump(by_alias=True)
