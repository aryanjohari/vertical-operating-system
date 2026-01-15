from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

# ==========================================
# 1. THE UNIVERSAL ENVELOPE (Input)
# ==========================================
class AgentInput(BaseModel):
    """
    The standard packet sent to ANY agent.
    You never change this class, only the 'params' dictionary inside it.
    """
    task: str = Field(..., description="The command name (e.g., 'scrape_leads', 'write_blog')")
    user_id: str = Field("admin", description="Who is asking? (Used for RLS/Permissions)")
    
    # The Flexible Payload - Put ANYTHING here
    params: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Dynamic arguments (e.g., {'city': 'Auckland', 'niche': 'Plumber'})"
    )
    
    # Request ID for tracking logs
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

# ==========================================
# 2. THE UNIVERSAL RECEIPT (Output)
# ==========================================
class AgentOutput(BaseModel):
    """
    The standard response from ANY agent.
    """
    status: str = Field(..., description="'success' or 'error'")
    data: Any = Field(default=None, description="The actual result (List, JSON, String, etc.)")
    message: str = Field(..., description="Human readable summary for the UI")
    timestamp: datetime = Field(default_factory=datetime.now)

# ==========================================
# 3. THE UNIVERSAL MEMORY (Database Record)
# ==========================================
class Entity(BaseModel):
    """
    A standard format for saving things (Leads, Jobs, Tenders) to the DB.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = Field(..., description="The User ID (RLS)")
    
    # What is this? (e.g., "lead", "job_listing", "tender")
    entity_type: str 
    
    # The Core Data
    name: str = Field(..., description="Name of person/company/job")
    primary_contact: Optional[str] = Field(None, description="Email or Phone or URL")
    
    # Extra Context (e.g., {"rating": 4.5, "salary": "$100k"})
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=datetime.now)