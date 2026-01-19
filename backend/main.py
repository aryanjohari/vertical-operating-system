# backend/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from backend.core.models import AgentInput, AgentOutput, Entity
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.logger import setup_logging
from backend.routers.voice import voice_router
import logging
import uvicorn
import os
import re

# Initialize logging system BEFORE app initialization
setup_logging()
logger = logging.getLogger("Apex.Main")

# Initialize the App
app = FastAPI(
    title="Apex Sovereign OS", 
    version="1.0",
    description="The Vertical Operating System for Revenue & Automation"
)

# Add CORS middleware to allow Next.js frontend (MVP: allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
def health_check():
    """Ping this to check if the OS is alive."""
    return {
        "status": "online", 
        "system": "Apex Kernel", 
        "version": "1.0",
        "loaded_agents": list(kernel.agents.keys())
    }

@app.post("/api/run", response_model=AgentOutput)
async def run_command(payload: AgentInput):
    """
    The Single Entry Point.
    Receives a Universal Packet -> Dispatches to Kernel -> Returns Result.
    """
    try:
        result = await kernel.dispatch(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoint
class AuthRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None

@app.post("/api/auth/verify", response_model=AuthResponse)
async def verify_auth(request: AuthRequest):
    """Verify user credentials against SQL database."""
    try:
        # Trim whitespace from inputs
        email = request.email.strip()
        password = request.password.strip()
        
        # Debug logging
        logger.info(f"Verifying user: {email}")
        
        is_valid = memory.verify_user(email, password)
        
        if is_valid:
            logger.info(f"Auth success: {email}")
            return AuthResponse(success=True, user_id=email)
        
        # Debug: check if user exists
        logger.warning(f"Auth failed: credentials don't match for {email}")
        return AuthResponse(success=False, user_id=None)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Auth error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Entities endpoint
@app.get("/api/entities")
async def get_entities(
    user_id: str,
    entity_type: Optional[str] = None,
    project_id: Optional[str] = None
):
    """Get entities from SQL database for a specific user (RLS enforced)."""
    try:
        entities = memory.get_entities(tenant_id=user_id, entity_type=entity_type, project_id=project_id)
        return {"entities": entities}
    except Exception as e:
        logger.error(f"Entities error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Lead capture endpoints
class LeadInput(BaseModel):
    user_id: str
    project_id: str
    source: str  # e.g., "Bail Calc - Auckland Central"
    data: Dict[str, Any]  # Flexible dictionary for captured form data

class LeadResponse(BaseModel):
    success: bool
    lead_id: Optional[str] = None
    message: str = "Lead captured successfully"

@app.post("/api/leads", response_model=LeadResponse)
async def create_lead(request: LeadInput):
    """Capture a lead from calculator/contact form and save to SQLite."""
    try:
        # Create Entity for lead
        lead_entity = Entity(
            tenant_id=request.user_id,
            entity_type="lead",
            name=request.source,
            metadata=request.data
        )
        
        # Save to database with project_id
        success = memory.save_entity(lead_entity, project_id=request.project_id)
        
        if success:
            logger.info(f"Captured lead: {request.source} for user {request.user_id}, project {request.project_id}")
            return LeadResponse(success=True, lead_id=lead_entity.id, message="Lead captured successfully")
        else:
            raise HTTPException(status_code=500, detail="Failed to save lead")
    except Exception as e:
        logger.error(f"Leads error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads")
async def get_leads(user_id: str):
    """Get all leads for a specific user (RLS enforced)."""
    try:
        leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
        return {"leads": leads}
    except Exception as e:
        logger.error(f"Error fetching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Projects endpoint
class ProjectInput(BaseModel):
    user_id: str
    name: str
    niche: str

class ProjectResponse(BaseModel):
    success: bool
    project_id: str
    message: str = "Project created successfully"

@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(request: ProjectInput, background_tasks: BackgroundTasks):
    """Create a new project and trigger onboarding agent."""
    try:
        # Generate project_id from niche (sanitize for filesystem)
        project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', request.niche.lower())
        
        # Register project in database
        memory.register_project(
            user_id=request.user_id,
            project_id=project_id,
            niche=request.name
        )
        
        logger.info(f"Created project: {project_id} for user {request.user_id}")
        
        # Automatically trigger onboarding agent in background
        async def trigger_onboarding():
            try:
                onboarding_input = AgentInput(
                    task="onboarding",
                    user_id=request.user_id,
                    params={
                        "niche": project_id,
                        "message": "",
                        "history": ""
                    }
                )
                await kernel.dispatch(onboarding_input)
                logger.info(f"Onboarding agent completed for project {project_id}")
            except Exception as e:
                logger.error(f"Onboarding agent error for project {project_id}: {e}", exc_info=True)
        
        background_tasks.add_task(trigger_onboarding)
        logger.info(f"Triggered onboarding agent for project {project_id}")
        
        return ProjectResponse(
            success=True,
            project_id=project_id,
            message="Project created and onboarding started"
        )
    except Exception as e:
        logger.error(f"Projects error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects")
async def get_projects(user_id: str):
    """Get all projects for a specific user."""
    try:
        projects = memory.get_projects(user_id=user_id)
        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Include voice router
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])

if __name__ == "__main__":
    # Dev Mode: Runs on localhost:8000
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)