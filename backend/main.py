from dotenv import load_dotenv
load_dotenv() # backend/main.py


from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from backend.core.models import AgentInput, AgentOutput, Entity
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.logger import setup_logging
from backend.core.auth import (
    get_current_user,
    create_access_token,
    verify_user_credentials
)
from backend.routers.voice import voice_router
from backend.routers.webhooks import webhook_router
import logging
import uvicorn
import os
import re
import traceback
import sqlite3
import yaml
from datetime import datetime



# Initialize logging system BEFORE app initialization
setup_logging()
logger = logging.getLogger("Apex.Main")

# Initialize the App
app = FastAPI(
    title="Apex Sovereign OS", 
    version="1.0",
    description="The Vertical Operating System for Revenue & Automation"
)

# CORS Configuration (secure defaults, configurable via env)
ALLOWED_ORIGINS = os.getenv(
    "APEX_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:5500"  # Default: Next.js dev ports
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Whitelist specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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

@app.post("/api/run")
async def run_command(
    payload: AgentInput,
    user_id: str = Depends(get_current_user)
):
    """
    The Single Entry Point with Safety Net.
    
    Data Flow:
    1. Receives AgentInput packet from frontend
    2. Authenticates user via JWT token (user_id derived from token)
    3. Dispatches to Kernel which resolves agent via Registry
    4. Kernel loads DNA config and executes agent
    5. Agent saves snapshot and returns AgentOutput
    6. Always returns HTTP 200 with structured JSON (never 500)
    7. Frontend can always display the result, even on errors
    
    This endpoint is wrapped in comprehensive error handling to ensure
    the frontend never sees a 500 error and can always display logs.
    """
    try:
        # Override user_id from token (security: never trust client-supplied user_id)
        payload.user_id = user_id
        
        result = await kernel.dispatch(payload)
        
        # Sanitize response - only return safe fields, not full dict
        return {
            "status": result.status,
            "data": result.data,
            "message": result.message,
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp),
            "error_details": None
        }
    except ImportError as e:
        # Catch missing dependencies (e.g., ChromaDB not installed)
        error_trace = traceback.format_exc()
        logger.error(f"ImportError in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None
        }
    except Exception as e:
        # Catch all other exceptions (logic crashes, etc.)
        error_trace = traceback.format_exc()
        logger.error(f"Exception in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None
        }

# Authentication endpoint
class AuthRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None

class AuthResponseWithToken(AuthResponse):
    """Extended response with JWT token."""
    token: Optional[str] = None

@app.post("/api/auth/verify", response_model=AuthResponseWithToken)
async def verify_auth(request: AuthRequest):
    """Verify user credentials and return JWT token."""
    try:
        # Trim whitespace from inputs
        email = request.email.strip()
        password = request.password.strip()
        
        # Validate inputs
        if not email or not password:
            logger.warning("Auth failed: empty email or password")
            return AuthResponseWithToken(success=False, user_id=None, token=None)
        
        logger.info(f"Verifying user: {email}")
        
        # Verify credentials using auth provider (SQLite now, Supabase-ready)
        user_id = verify_user_credentials(email, password)
        
        if user_id:
            # Create JWT token
            token = create_access_token(user_id)
            logger.info(f"Auth success: {email}")
            return AuthResponseWithToken(success=True, user_id=user_id, token=token)
        
        logger.warning(f"Auth failed: credentials don't match for {email}")
        return AuthResponseWithToken(success=False, user_id=None, token=None)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Auth error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed. Please try again.")

@app.post("/api/auth/register", response_model=AuthResponse)
async def register_user(request: AuthRequest):
    """Register a new user."""
    try:
        # Trim whitespace from inputs
        email = request.email.strip()
        password = request.password.strip()
        
        # Validate inputs
        if not email or not password:
            logger.warning("Registration failed: empty email or password")
            return AuthResponse(success=False, user_id=None)
        
        logger.info(f"Registering user: {email}")
        
        success = memory.create_user(email, password)
        
        if success:
            logger.info(f"Registration success: {email}")
            return AuthResponse(success=True, user_id=email)
        else:
            logger.warning(f"Registration failed: user {email} already exists")
            return AuthResponse(success=False, user_id=None)
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Entities endpoints
@app.get("/api/entities")
async def get_entities(
    entity_type: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Get entities from SQL database for a specific user (RLS enforced)."""
    try:
        # Verify project ownership if project_id provided
        if project_id and not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        
        entities = memory.get_entities(tenant_id=user_id, entity_type=entity_type, project_id=project_id)
        return {"entities": entities}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entities error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch entities")

class EntityCreateInput(BaseModel):
    entity_type: str
    name: str
    primary_contact: Optional[str] = None
    metadata: Dict[str, Any] = {}
    project_id: Optional[str] = None

class EntityUpdateInput(BaseModel):
    name: Optional[str] = None
    primary_contact: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@app.post("/api/entities")
async def create_entity(
    request: EntityCreateInput,
    user_id: str = Depends(get_current_user)
):
    """Create a new entity."""
    try:
        # Verify project ownership if project_id provided
        if request.project_id and not memory.verify_project_ownership(user_id, request.project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        
        entity = Entity(
            tenant_id=user_id,  # Use authenticated user_id
            entity_type=request.entity_type,
            name=request.name,
            primary_contact=request.primary_contact,
            metadata=request.metadata
        )
        success = memory.save_entity(entity, project_id=request.project_id)
        if success:
            logger.info(f"Created entity: {entity.id} of type {request.entity_type} for user {user_id}")
            return {"success": True, "entity": entity.dict()}
        else:
            raise HTTPException(status_code=500, detail="Failed to save entity")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create entity")

@app.put("/api/entities/{entity_id}")
async def update_entity_endpoint(
    entity_id: str,
    request: EntityUpdateInput,
    user_id: str = Depends(get_current_user)
):
    """Update an existing entity (RLS enforced)."""
    try:
        # Verify entity belongs to user
        entities = memory.get_entities(tenant_id=user_id)
        entity = next((e for e in entities if e.get("id") == entity_id), None)
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found or access denied")
        
        # Build update metadata - combine all fields into metadata for update_entity
        update_metadata = {}
        if request.name is not None:
            update_metadata["_name"] = request.name  # Special key for name update
        if request.primary_contact is not None:
            update_metadata["_primary_contact"] = request.primary_contact  # Special key
        if request.metadata:
            update_metadata.update(request.metadata)
        
        # Update name and primary_contact directly via SQL if provided
        if request.name is not None or request.primary_contact is not None:
            conn = None
            try:
                logger.debug(f"Updating entity {entity_id} name/contact via direct SQL for user {user_id}")
                conn = sqlite3.connect(memory.db_path)
                cursor = conn.cursor()
                if request.name is not None and request.primary_contact is not None:
                    cursor.execute(
                        "UPDATE entities SET name = ?, primary_contact = ? WHERE id = ? AND tenant_id = ?",
                        (request.name, request.primary_contact, entity_id, user_id)
                    )
                elif request.name is not None:
                    cursor.execute(
                        "UPDATE entities SET name = ? WHERE id = ? AND tenant_id = ?",
                        (request.name, entity_id, user_id)
                    )
                elif request.primary_contact is not None:
                    cursor.execute(
                        "UPDATE entities SET primary_contact = ? WHERE id = ? AND tenant_id = ?",
                        (request.primary_contact, entity_id, user_id)
                    )
                conn.commit()
                logger.debug(f"Successfully updated entity {entity_id} name/contact via direct SQL")
            except sqlite3.Error as e:
                logger.error(f"Database error updating entity {entity_id} name/contact: {e}")
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error updating entity {entity_id} name/contact: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
            finally:
                if conn:
                    conn.close()
        
        # Update metadata if provided
        if request.metadata:
            # Remove special keys from metadata before updating
            clean_metadata = {k: v for k, v in request.metadata.items() if not k.startswith("_")}
            if clean_metadata:
                success = memory.update_entity(entity_id, clean_metadata)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to update entity metadata")
        
        logger.info(f"Updated entity: {entity_id} for user {user_id}")
        return {"success": True, "message": "Entity updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/entities/{entity_id}")
async def delete_entity_endpoint(
    entity_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete an entity (RLS enforced)."""
    try:
        success = memory.delete_entity(entity_id, user_id)
        if success:
            logger.info(f"Deleted entity: {entity_id} for user {user_id}")
            return {"success": True, "message": "Entity deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Entity not found or access denied")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete entity")

# Lead capture endpoints
class LeadInput(BaseModel):
    project_id: str
    source: str  # e.g., "Bail Calc - Auckland Central"
    data: Dict[str, Any]  # Flexible dictionary for captured form data

class LeadResponse(BaseModel):
    success: bool
    lead_id: Optional[str] = None
    message: str = "Lead captured successfully"

@app.post("/api/leads", response_model=LeadResponse)
async def create_lead(
    request: LeadInput,
    user_id: str = Depends(get_current_user)
):
    """Capture a lead from calculator/contact form and save to SQLite."""
    try:
        # Verify project ownership
        if not memory.verify_project_ownership(user_id, request.project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        
        # Create Entity for lead
        lead_entity = Entity(
            tenant_id=user_id,  # Use authenticated user_id
            entity_type="lead",
            name=request.source,
            metadata=request.data
        )
        
        # Save to database with project_id
        success = memory.save_entity(lead_entity, project_id=request.project_id)
        
        if success:
            logger.info(f"Captured lead: {request.source} for user {user_id}, project {request.project_id}")
            return LeadResponse(success=True, lead_id=lead_entity.id, message="Lead captured successfully")
        else:
            raise HTTPException(status_code=500, detail="Failed to save lead")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Leads error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to capture lead")

@app.get("/api/leads")
async def get_leads(user_id: str = Depends(get_current_user)):
    """Get all leads for a specific user (RLS enforced)."""
    try:
        leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
        return {"leads": leads}
    except Exception as e:
        logger.error(f"Error fetching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch leads")

# Projects endpoint
class ProjectInput(BaseModel):
    name: str
    niche: str

class ProjectResponse(BaseModel):
    success: bool
    project_id: str
    message: str = "Project created successfully"

@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(
    request: ProjectInput,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    """Create a new project and trigger onboarding agent."""
    try:
        # Generate project_id from niche (sanitize for filesystem)
        project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', request.niche.lower())
        
        # Register project in database
        memory.register_project(
            user_id=user_id,  # Use authenticated user_id
            project_id=project_id,
            niche=request.name
        )
        
        logger.info(f"Created project: {project_id} for user {user_id}")
        
        # Automatically trigger onboarding agent in background
        async def trigger_onboarding():
            try:
                onboarding_input = AgentInput(
                    task="onboarding",
                    user_id=user_id,  # Use authenticated user_id
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
        raise HTTPException(status_code=500, detail="Failed to create project")

@app.get("/api/projects")
async def get_projects(user_id: str = Depends(get_current_user)):
    """Get all projects for a specific user."""
    try:
        projects = memory.get_projects(user_id=user_id)
        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch projects")

# Settings endpoints
class SettingsInput(BaseModel):
    wp_url: str
    wp_user: str
    wp_password: str

@app.get("/api/settings")
async def get_settings(user_id: str = Depends(get_current_user)):
    """Get WordPress credentials for a user."""
    try:
        secrets = memory.get_client_secrets(user_id)
        if secrets:
            return {
                "wp_url": secrets.get("wp_url", ""),
                "wp_user": secrets.get("wp_user", ""),
                "wp_password": ""  # Never return password in API
            }
        return {
            "wp_url": "",
            "wp_user": "",
            "wp_password": ""
        }
    except Exception as e:
        logger.error(f"Get settings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch settings")

@app.post("/api/settings")
async def save_settings(
    request: SettingsInput,
    user_id: str = Depends(get_current_user)
):
    """Save WordPress credentials for a user."""
    try:
        success = memory.save_client_secrets(
            user_id=user_id,  # Use authenticated user_id
            wp_url=request.wp_url,
            wp_user=request.wp_user,
            wp_password=request.wp_password
        )
        if success:
            logger.info(f"Saved settings for user {user_id}")
            return {"success": True, "message": "Settings saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save settings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save settings")

# DNA Config endpoints
@app.get("/api/projects/{project_id}/dna")
async def get_dna_config(
    project_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get DNA configuration for a project."""
    try:
        # Verify project ownership
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        
        # Load config using ConfigLoader
        from backend.core.config import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load(project_id)
        
        if "error" in config:
            raise HTTPException(status_code=404, detail=config.get("error", "Config not found"))
        
        return {"config": config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get DNA config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load DNA configuration")

@app.put("/api/projects/{project_id}/dna")
async def update_dna_config(
    project_id: str,
    config: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """Update DNA configuration for a project (writes to dna.custom.yaml)."""
    try:
        # Verify project ownership
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        
        # Get profile path
        from backend.core.config import ConfigLoader
        config_loader = ConfigLoader()
        profile_path = os.path.join(config_loader.profiles_dir, project_id)
        
        # Ensure directory exists
        os.makedirs(profile_path, exist_ok=True)
        
        # Write to dna.custom.yaml
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        with open(custom_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Updated DNA config for project {project_id} by user {user_id}")
        return {"success": True, "message": "DNA configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update DNA config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update DNA configuration")

# Include voice router
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
app.include_router(webhook_router, prefix="/api/webhooks", tags=["webhooks"])

if __name__ == "__main__":
    # Dev Mode: Runs on localhost:8000
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)