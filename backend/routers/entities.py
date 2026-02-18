import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.memory import memory
from backend.core.models import Entity

router = APIRouter(tags=["entities"])
logger = logging.getLogger("Apex.Router.Entities")


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


class LeadInput(BaseModel):
    project_id: str
    source: str
    data: Dict[str, Any]


class LeadResponse(BaseModel):
    success: bool
    lead_id: Optional[str] = None
    message: str = "Lead captured successfully"


@router.get("/entities")
async def get_entities(
    entity_type: Optional[str] = None,
    project_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user_id: str = Depends(get_current_user),
):
    """Get entities from SQL database for a specific user (RLS enforced). Supports limit, offset, and campaign_id filter. When campaign_id is set, response includes total count."""
    try:
        if project_id and not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        entities = memory.get_entities(
            tenant_id=user_id,
            entity_type=entity_type,
            project_id=project_id,
            campaign_id=campaign_id,
            limit=min(limit, 500),
            offset=offset,
        )
        out = {"entities": entities}
        if campaign_id and project_id:
            total = memory.get_entities_count(
                tenant_id=user_id,
                entity_type=entity_type,
                project_id=project_id,
                campaign_id=campaign_id,
            )
            out["total"] = total
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entities error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch entities")


@router.post("/entities")
async def create_entity(
    request: EntityCreateInput,
    user_id: str = Depends(get_current_user),
):
    """Create a new entity."""
    try:
        if request.project_id and not memory.verify_project_ownership(user_id, request.project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        entity = Entity(
            tenant_id=user_id,
            entity_type=request.entity_type,
            name=request.name,
            primary_contact=request.primary_contact,
            metadata=request.metadata,
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


@router.put("/entities/{entity_id}")
async def update_entity_endpoint(
    entity_id: str,
    request: EntityUpdateInput,
    user_id: str = Depends(get_current_user),
):
    """Update an existing entity (RLS enforced)."""
    try:
        entity = memory.get_entity(entity_id, user_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found or access denied")

        if request.name is not None or request.primary_contact is not None:
            success = memory.update_entity_name_contact(
                entity_id, user_id, name=request.name, primary_contact=request.primary_contact
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update entity name/contact")

        if request.metadata:
            clean_metadata = {k: v for k, v in request.metadata.items() if not k.startswith("_")}
            if clean_metadata:
                success = memory.update_entity(entity_id, clean_metadata, user_id)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to update entity metadata")

        logger.info(f"Updated entity: {entity_id} for user {user_id}")
        return {"success": True, "message": "Entity updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{entity_id}")
async def delete_entity_endpoint(
    entity_id: str,
    user_id: str = Depends(get_current_user),
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


@router.post("/leads", response_model=LeadResponse)
async def create_lead(
    request: LeadInput,
    user_id: str = Depends(get_current_user),
):
    """Capture a lead from calculator/contact form and save to SQLite."""
    try:
        if not memory.verify_project_ownership(user_id, request.project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        lead_entity = Entity(
            tenant_id=user_id,
            entity_type="lead",
            name=request.source,
            metadata=request.data,
        )
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


@router.get("/leads")
async def get_leads(user_id: str = Depends(get_current_user)):
    """Get all leads for a specific user (RLS enforced)."""
    try:
        leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
        return {"leads": leads}
    except Exception as e:
        logger.error(f"Error fetching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch leads")
