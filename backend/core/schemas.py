# backend/core/schemas.py
"""
Strict Pydantic schemas for agent task params.
Used by the kernel to validate packet.params before dispatch.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BaseAgentParams(BaseModel):
    """Common params many agents accept (all optional)."""
    project_id: Optional[str] = None
    campaign_id: Optional[str] = None
    niche: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # Allow context_id, request_id, etc. from main/kernel


class EmptyParams(BaseModel):
    """No params (health_check, cleanup, analytics_audit)."""
    model_config = ConfigDict(extra="allow")


# --- pSEO workers (campaign_id optional; kernel/context may inject) ---
class ScoutParams(BaseAgentParams):
    pass


class StrategistParams(BaseAgentParams):
    pass


class WriterParams(BaseAgentParams):
    pass


class CriticParams(BaseAgentParams):
    pass


class LibrarianParams(BaseAgentParams):
    pass


class MediaParams(BaseAgentParams):
    pass


class UtilityParams(BaseAgentParams):
    pass


class PublisherParams(BaseAgentParams):
    limit: int = Field(default=2, ge=1, le=100)


# --- pSEO manager ---
class ManagerParams(BaseAgentParams):
    action: str = Field(default="dashboard_stats")
    settings: Optional[Dict[str, Any]] = None
    ids: Optional[List[str]] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    draft_id: Optional[str] = None
    content: Optional[str] = None


# --- Lead Gen ---
class SalesParams(BaseAgentParams):
    action: str = Field(default="instant_call")
    lead_id: Optional[str] = None


class ReactivatorParams(BaseAgentParams):
    limit: int = Field(default=20, ge=1, le=500)


class LeadScorerParams(BaseModel):
    lead_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    campaign_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class LeadGenManagerParams(BaseAgentParams):
    action: str = Field(default="dashboard_stats")
    lead_id: Optional[str] = None


# --- System ops ---
class LogUsageParams(BaseAgentParams):
    resource: str = Field(..., min_length=1)
    quantity: float = Field(..., ge=0)


class SystemOpsManagerParams(BaseModel):
    action: str = Field(default="run_diagnostics")
    project_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


# --- Onboarding ---
class OnboardingParams(BaseModel):
    action: str = Field(default="compile_profile")
    identity: Optional[Dict[str, Any]] = None
    modules: Optional[List[str]] = None
    project_id: Optional[str] = None
    module: Optional[str] = None
    name: Optional[str] = None
    step: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    history: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


# --- Task -> Schema map (must match AgentRegistry.DIRECTORY keys) ---
TASK_SCHEMA_MAP = {
    "onboarding": OnboardingParams,
    "manager": ManagerParams,
    "scout_anchors": ScoutParams,
    "strategist_run": StrategistParams,
    "write_pages": WriterParams,
    "critic_review": CriticParams,
    "librarian_link": LibrarianParams,
    "enhance_media": MediaParams,
    "enhance_utility": UtilityParams,
    "publish": PublisherParams,
    "analytics_audit": EmptyParams,
    "lead_gen_manager": LeadGenManagerParams,
    "sales_agent": SalesParams,
    "reactivator_agent": ReactivatorParams,
    "lead_scorer": LeadScorerParams,
    "system_ops_manager": SystemOpsManagerParams,
    "health_check": EmptyParams,
    "log_usage": LogUsageParams,
    "cleanup": EmptyParams,
}
