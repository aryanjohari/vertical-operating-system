"""Schema API: expose YAML-derived form schemas for dynamic forms."""
import logging
from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import get_current_user
from backend.core.schema_loader import load_yaml_template, yaml_to_form_schema

router = APIRouter(tags=["schemas"])
logger = logging.getLogger("Apex.Router.Schemas")


@router.get("/schemas/profile")
async def get_profile_schema(_user_id: str = Depends(get_current_user)):
    """Get form schema for profile (profile_template.yaml)."""
    try:
        template = load_yaml_template("profile_template")
        schema = yaml_to_form_schema(template)
        return {"schema": schema, "defaults": template}
    except FileNotFoundError as e:
        logger.error(f"Profile schema error: {e}")
        raise HTTPException(status_code=500, detail="Profile template not found")
    except Exception as e:
        logger.error(f"Profile schema error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemas/campaign/pseo")
async def get_pseo_schema(_user_id: str = Depends(get_current_user)):
    """Get form schema for pSEO campaign (pseo_default.yaml)."""
    try:
        template = load_yaml_template("pseo_default")
        schema = yaml_to_form_schema(template)
        return {"schema": schema, "defaults": template}
    except FileNotFoundError as e:
        logger.error(f"pSEO schema error: {e}")
        raise HTTPException(status_code=500, detail="pSEO template not found")
    except Exception as e:
        logger.error(f"pSEO schema error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemas/campaign/lead_gen")
async def get_lead_gen_schema(_user_id: str = Depends(get_current_user)):
    """Get form schema for Lead Gen campaign (lead_gen_default.yaml)."""
    try:
        template = load_yaml_template("lead_gen_default")
        schema = yaml_to_form_schema(template)
        return {"schema": schema, "defaults": template}
    except FileNotFoundError as e:
        logger.error(f"Lead Gen schema error: {e}")
        raise HTTPException(status_code=500, detail="Lead Gen template not found")
    except Exception as e:
        logger.error(f"Lead Gen schema error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
