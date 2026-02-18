import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.config import ConfigLoader
from backend.core.memory import memory
from backend.core.models import AgentInput
from backend.core.kernel import kernel

router = APIRouter(tags=["projects"])
logger = logging.getLogger("Apex.Router.Projects")


class ProjectInput(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    success: bool
    project_id: str
    message: str = "Project created successfully"


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    request: ProjectInput,
    user_id: str = Depends(get_current_user),
):
    """Create a new project. If profile is provided, runs form-based genesis to save DNA."""
    try:
        if request.profile:
            # Full profile form: genesis handles register_project + save_dna + RAG
            identity = request.profile.get("identity") or {}
            project_id_raw = (identity.get("project_id") or "").strip()
            project_id = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id_raw.lower())
            if not project_id:
                raise HTTPException(status_code=400, detail="Project ID (slug) is required in profile.identity")
            if not (identity.get("business_name") or "").strip():
                raise HTTPException(status_code=400, detail="Business name is required")
            if not (identity.get("niche") or "").strip():
                raise HTTPException(status_code=400, detail="Niche is required")

            result = await kernel.dispatch(
                AgentInput(
                    task="onboarding",
                    user_id=user_id,
                    params={"action": "compile_profile", "profile": request.profile},
                )
            )
            if result.status == "error":
                raise HTTPException(status_code=400, detail=result.message or "Failed to create profile")

            return ProjectResponse(
                success=True,
                project_id=project_id,
                message="Project created successfully",
            )

        # Simple create (name + niche)
        if not request.name or not request.niche:
            raise HTTPException(status_code=400, detail="name and niche are required when profile is not provided")

        project_id = re.sub(r"[^a-zA-Z0-9_-]", "_", request.niche.lower())
        memory.register_project(user_id=user_id, project_id=project_id, niche=request.name)
        logger.info(f"Created project: {project_id} for user {user_id}")
        return ProjectResponse(success=True, project_id=project_id, message="Project created successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Projects error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.get("/projects")
async def get_projects(user_id: str = Depends(get_current_user)):
    """Get all projects for a specific user."""
    try:
        projects = memory.get_projects(user_id=user_id)
        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.get("/projects/{project_id}/dna")
async def get_dna_config(
    project_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get DNA configuration for a project."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

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


@router.put("/projects/{project_id}/dna")
async def update_dna_config(
    project_id: str,
    config: Dict[str, Any],
    user_id: str = Depends(get_current_user),
):
    """Update DNA configuration for a project (writes to dna.custom.yaml)."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        config_loader = ConfigLoader()
        config_loader.save_dna_custom(project_id, config)

        logger.info(f"Updated DNA config for project {project_id} by user {user_id}")
        return {"success": True, "message": "DNA configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update DNA config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update DNA configuration")


class CampaignCreateInput(BaseModel):
    name: str = ""
    module: str  # "pseo" or "lead_gen"
    form_data: Optional[Dict[str, Any]] = None  # Form data (1:1 mapping to template)


class CampaignCreateResponse(BaseModel):
    success: bool
    campaign_id: str
    message: str = "Campaign created successfully"


@router.post("/projects/{project_id}/campaigns", response_model=CampaignCreateResponse)
async def create_campaign(
    project_id: str,
    request: CampaignCreateInput,
    user_id: str = Depends(get_current_user),
):
    """Create a new campaign via kernel (form-based, no LLM)."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        if request.module not in ("pseo", "lead_gen"):
            raise HTTPException(status_code=400, detail="module must be 'pseo' or 'lead_gen'")
        if not request.form_data:
            raise HTTPException(status_code=400, detail="form_data is required")

        result = await kernel.dispatch(
            AgentInput(
                task="onboarding",
                user_id=user_id,
                params={
                    "action": "create_campaign",
                    "project_id": project_id,
                    "module": request.module,
                    "name": request.name or "",
                    "form_data": request.form_data,
                },
            )
        )
        if result.status == "error":
            raise HTTPException(status_code=400, detail=result.message or "Failed to create campaign")

        campaign_id = (result.data or {}).get("campaign_id")
        if not campaign_id:
            raise HTTPException(status_code=500, detail="Campaign created but no ID returned")

        return CampaignCreateResponse(
            success=True,
            campaign_id=campaign_id,
            message="Campaign created successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create campaign")


@router.get("/projects/{project_id}/campaigns")
async def get_campaigns(
    project_id: str,
    module: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    """Get campaigns for a project, optionally filtered by module."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        campaigns = memory.get_campaigns_by_project(user_id, project_id, module=module)
        return {"campaigns": campaigns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch campaigns")


@router.get("/projects/{project_id}/campaigns/{campaign_id}")
async def get_campaign(
    project_id: str,
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a single campaign by ID with full config."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="Campaign not found in this project")

        return {"campaign": campaign}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch campaign")


class CampaignConfigUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None  # Full config replace
    config_partial: Optional[Dict[str, Any]] = None  # Shallow merge into existing


@router.patch("/projects/{project_id}/campaigns/{campaign_id}")
async def patch_campaign(
    project_id: str,
    campaign_id: str,
    body: CampaignConfigUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update campaign config. Send config for full replace, or config_partial for shallow merge."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="Campaign not found in this project")

        existing = campaign.get("config") or {}
        if body.config is not None:
            new_config = body.config
        elif body.config_partial is not None:
            new_config = {**existing, **body.config_partial}
        else:
            raise HTTPException(status_code=400, detail="Provide config or config_partial")

        if not memory.update_campaign_config(campaign_id=campaign_id, user_id=user_id, new_config=new_config):
            raise HTTPException(status_code=500, detail="Failed to update campaign config")

        updated = memory.get_campaign(campaign_id, user_id)
        return {"campaign": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.post("/projects/{project_id}/lead-gen/process-scheduled-bridges")
async def process_scheduled_bridges(
    project_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Process scheduled voice bridges: find leads with scheduled_bridge_at <= now,
    within business hours, and dispatch instant_call for each. Call periodically (e.g. cron every 1–2 min).
    """
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        result = await kernel.dispatch(
            AgentInput(
                task="lead_gen_manager",
                user_id=user_id,
                params={
                    "action": "process_scheduled_bridges",
                    "project_id": project_id,
                },
            )
        )
        if result.status == "error":
            raise HTTPException(status_code=400, detail=result.message or "Process scheduled bridges failed")
        return {"success": True, "data": result.data, "message": result.message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process scheduled bridges error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process scheduled bridges")
