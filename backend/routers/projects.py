import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.config import ConfigLoader
from backend.core.memory import memory
from backend.core.models import AgentInput
from backend.core.kernel import kernel

router = APIRouter(tags=["projects"])
logger = logging.getLogger("Apex.Router.Projects")


class ProjectInput(BaseModel):
    name: str
    niche: str


class ProjectResponse(BaseModel):
    success: bool
    project_id: str
    message: str = "Project created successfully"


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    request: ProjectInput,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    """Create a new project and trigger onboarding agent."""
    try:
        project_id = re.sub(r"[^a-zA-Z0-9_-]", "_", request.niche.lower())

        memory.register_project(
            user_id=user_id,
            project_id=project_id,
            niche=request.name,
        )

        logger.info(f"Created project: {project_id} for user {user_id}")

        async def trigger_onboarding():
            try:
                onboarding_input = AgentInput(
                    task="onboarding",
                    user_id=user_id,
                    params={
                        "niche": project_id,
                        "message": "",
                        "history": "",
                    },
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
            message="Project created and onboarding started",
        )
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
    name: str
    module: str  # "pseo" or "lead_gen"
    config: Dict[str, Any]


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
    """Create a new campaign for a project (direct config, no interview)."""
    try:
        if not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")
        if request.module not in ("pseo", "lead_gen"):
            raise HTTPException(status_code=400, detail="module must be 'pseo' or 'lead_gen'")

        campaign_id = memory.create_campaign(
            user_id=user_id,
            project_id=project_id,
            name=request.name,
            module=request.module,
            config=request.config,
        )
        try:
            config_loader = ConfigLoader()
            config_loader.save_campaign(project_id, campaign_id, request.config)
        except Exception as e:
            logger.warning(f"Failed to save campaign config to disk: {e}")
        logger.info(f"Created campaign {campaign_id} for project {project_id} by user {user_id}")
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
