# backend/modules/system_ops/models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class UsageRecord(BaseModel):
    """
    Tracks resource usage and costs for billing.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = Field(..., description="Project identifier")
    resource_type: str = Field(..., description="Resource type (e.g., 'twilio_voice', 'gemini_token')")
    quantity: float = Field(..., description="Quantity used (e.g., minutes, tokens)")
    cost_usd: float = Field(..., description="Cost in USD")
    timestamp: datetime = Field(default_factory=datetime.now)

class SystemHealthStatus(BaseModel):
    """
    System health status report.
    """
    status: str = Field(..., description="Overall status: 'healthy' or 'critical'")
    database_ok: bool = Field(..., description="Database connectivity check")
    twilio_ok: bool = Field(..., description="Twilio API connectivity check")
    gemini_ok: bool = Field(..., description="Google Gemini API connectivity check")
    disk_space_ok: bool = Field(..., description="Disk space availability check")
