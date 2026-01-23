# backend/routers/webhooks.py
import os
import re
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from backend.core.memory import memory
from backend.core.models import Entity
from backend.core.kernel import kernel
from backend.core.agent_base import AgentInput
from backend.core.context import context_manager

# Initialize Logger
logger = logging.getLogger("Apex.Webhooks")
webhook_router = APIRouter()

# Maximum payload size (10MB)
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024

def _normalize_lead_data(payload: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalizes different webhook payload formats into a standard structure.
    Handles Google Ads, WordPress forms, and other common formats.
    """
    # Try to extract common fields from various payload structures
    name = (
        payload.get('name') or 
        payload.get('fullName') or 
        payload.get('full_name') or
        payload.get('contact_name') or
        payload.get('first_name', '') + ' ' + payload.get('last_name', '')
    ).strip() or f"{source.title()} Lead"
    
    phone = (
        payload.get('phone') or 
        payload.get('phoneNumber') or 
        payload.get('phone_number') or
        payload.get('mobile') or
        payload.get('tel')
    )
    
    email = (
        payload.get('email') or 
        payload.get('emailAddress') or 
        payload.get('email_address')
    )
    
    message = (
        payload.get('message') or 
        payload.get('description') or 
        payload.get('comments') or
        payload.get('notes') or
        payload.get('details')
    )
    
    # Primary contact: prefer phone, fallback to email
    primary_contact = phone or email or ""
    
    return {
        'name': name,
        'phone': phone,
        'email': email,
        'message': message,
        'primary_contact': primary_contact,
        'raw_data': payload  # Keep original for reference
    }

def _validate_project_id(project_id: str) -> bool:
    """
    Validates project_id format to prevent path traversal attacks.
    """
    if not isinstance(project_id, str) or not project_id:
        return False
    # Only allow alphanumeric, underscores, and hyphens (same as kernel validation)
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', project_id))

def _get_user_id_from_project(project_id: str) -> Optional[str]:
    """
    Gets the user_id (owner) of a project.
    For webhooks, we need to find the project owner to set tenant_id correctly.
    Now uses memory abstraction instead of direct DB access.
    """
    if not project_id:
        return None
    return memory.get_project_owner(project_id)

async def _create_and_trigger_lead(
    normalized_data: Dict[str, Any], 
    source: str, 
    project_id: str, 
    user_id: str = None,
    background_tasks: Optional[BackgroundTasks] = None
) -> Dict[str, Any]:
    """
    Creates a lead entity and triggers SalesAgent for instant call.
    
    If background_tasks is provided, executes SalesAgent in background (non-blocking).
    Otherwise, executes synchronously (backward compatible).
    """
    # Validate project_id format (security: prevent path traversal)
    if not _validate_project_id(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id format. Only alphanumeric characters, underscores, and hyphens allowed.")
    
    # Get the actual project owner if user_id not provided
    if not user_id:
        user_id = _get_user_id_from_project(project_id)
        if not user_id:
            # Project doesn't exist - fail early for security
            logger.warning(f"Project {project_id} not found in database")
            raise HTTPException(status_code=404, detail="Project not found")
        logger.info(f"Using tenant_id: {user_id} for project {project_id}")
    
    # Verify project ownership (security: ensure project exists and belongs to user_id)
    if not memory.verify_project_ownership(user_id, project_id):
        logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
        raise HTTPException(status_code=403, detail="Project access denied")
    
    # Create Entity
    lead_entity = Entity(
        tenant_id=user_id,
        entity_type="lead",
        name=normalized_data['name'],
        primary_contact=normalized_data['primary_contact'],
        metadata={
            "source": source,
            "status": "new",
            "project_id": project_id,
            "data": {
                "name": normalized_data['name'],
                "phone": normalized_data.get('phone'),
                "email": normalized_data.get('email'),
                "message": normalized_data.get('message')
            },
            "raw_payload": normalized_data.get('raw_data', {})
        },
        created_at=datetime.now()
    )
    
    # Save to database
    success = memory.save_entity(lead_entity, project_id=project_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save lead to database")
    
    logger.info(f"💾 Saved lead {lead_entity.id} from {source} for project {project_id}")
    
    # If background_tasks is available, execute in background (non-blocking)
    if background_tasks:
        # Create context for this workflow
        context = context_manager.create_context(
            project_id=project_id,
            user_id=user_id,
            initial_data={
                "lead_id": lead_entity.id,
                "source": source,
                "normalized_data": normalized_data
            },
            ttl_seconds=3600  # 1 hour
        )
        
        # Define background task wrapper
        async def trigger_sales_agent():
            try:
                await kernel.dispatch(AgentInput(
                    task="sales_agent",
                    user_id=user_id,
                    params={
                        "action": "instant_call",
                        "lead_id": lead_entity.id,
                        "project_id": project_id,
                        "context_id": context.context_id  # Pass context to agent
                    }
                ))
                logger.info(f"📞 Background SalesAgent completed for lead {lead_entity.id}")
            except Exception as e:
                logger.error(f"❌ Background SalesAgent failed for lead {lead_entity.id}: {e}", exc_info=True)
        
        # Schedule background task
        background_tasks.add_task(trigger_sales_agent)
        logger.info(f"📞 Scheduled SalesAgent for lead {lead_entity.id} (background)")
        
        # Return immediately with context_id
        return {
            "success": True,
            "lead_id": lead_entity.id,
            "context_id": context.context_id,
            "status": "processing",
            "message": "Lead captured and bridge call initiated (processing in background)"
        }
    else:
        # Backward compatibility: Execute synchronously
        try:
            await kernel.dispatch(AgentInput(
                task="sales_agent",
                user_id=user_id,
                params={
                    "action": "instant_call",
                    "lead_id": lead_entity.id,
                    "project_id": project_id
                }
            ))
            logger.info(f"📞 Triggered SalesAgent for lead {lead_entity.id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to trigger SalesAgent for lead {lead_entity.id}: {e}", exc_info=True)
            # Don't fail the webhook if SalesAgent fails - lead is still saved
        
        return {
            "success": True,
            "lead_id": lead_entity.id,
            "message": "Lead captured and bridge call initiated"
        }

# --- 0. CORS PREFLIGHT HANDLERS ---
@webhook_router.options("/google-ads")
async def handle_google_ads_webhook_options(request: Request):
    """Handle CORS preflight for Google Ads webhook."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )

@webhook_router.options("/wordpress")
async def handle_wordpress_webhook_options(request: Request):
    """Handle CORS preflight for WordPress webhook."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )

# --- 1. GOOGLE ADS WEBHOOK ---
@webhook_router.post("/google-ads")
async def handle_google_ads_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives leads from Google Ads conversion tracking.
    Expected payload: JSON with name, phone, email, message, etc.
    """
    try:
        # Get project_id from query params (required)
        project_id = request.query_params.get("project_id")
        if not project_id:
            logger.error("Missing project_id in Google Ads webhook")
            raise HTTPException(status_code=400, detail="project_id query parameter is required")
        
        # Validate project_id format (security: prevent path traversal)
        if not _validate_project_id(project_id):
            logger.error(f"Invalid project_id format in Google Ads webhook: {project_id}")
            raise HTTPException(status_code=400, detail="Invalid project_id format. Only alphanumeric characters, underscores, and hyphens allowed.")
        
        # Check payload size (security: prevent DoS)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_SIZE:
            logger.error(f"Payload too large in Google Ads webhook: {content_length} bytes")
            raise HTTPException(status_code=413, detail="Payload too large. Maximum size is 10MB.")
        
        # Parse JSON payload
        try:
            payload = await request.json()
            # Additional size check after parsing
            import sys
            payload_size = sys.getsizeof(str(payload))
            if payload_size > MAX_PAYLOAD_SIZE:
                logger.error(f"Parsed payload too large: {payload_size} bytes")
                raise HTTPException(status_code=413, detail="Payload too large.")
        except HTTPException:
            raise
        except Exception:
            # Try form data as fallback
            form_data = await request.form()
            payload = dict(form_data)
        
        logger.info(f"📥 Google Ads webhook received for project {project_id}")
        
        # Get project owner for tenant_id
        project_owner = _get_user_id_from_project(project_id)
        if not project_owner:
            logger.warning(f"Project {project_id} not found in database")
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Normalize payload
        normalized_data = _normalize_lead_data(payload, "google_ads")
        
        # Create lead and trigger SalesAgent
        result = await _create_and_trigger_lead(
            normalized_data, 
            "google_ads", 
            project_id, 
            user_id=project_owner,
            background_tasks=background_tasks
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Google Ads webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

# --- 2. WORDPRESS FORMS WEBHOOK ---
@webhook_router.post("/wordpress")
async def handle_wordpress_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives leads from WordPress forms (Gravity Forms, Contact Form 7, etc.).
    Accepts both JSON and form-encoded data.
    """
    try:
        # Get project_id from query params (required)
        project_id = request.query_params.get("project_id")
        if not project_id:
            logger.error("Missing project_id in WordPress webhook")
            raise HTTPException(status_code=400, detail="project_id query parameter is required")
        
        # Validate project_id format (security: prevent path traversal)
        if not _validate_project_id(project_id):
            logger.error(f"Invalid project_id format in WordPress webhook: {project_id}")
            raise HTTPException(status_code=400, detail="Invalid project_id format. Only alphanumeric characters, underscores, and hyphens allowed.")
        
        # Check payload size (security: prevent DoS)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_SIZE:
            logger.error(f"Payload too large in WordPress webhook: {content_length} bytes")
            raise HTTPException(status_code=413, detail="Payload too large. Maximum size is 10MB.")
        
        # Try to parse as JSON first
        payload = {}
        content_type = request.headers.get("content-type", "").lower()
        
        if "application/json" in content_type:
            try:
                payload = await request.json()
                # Additional size check after parsing
                import sys
                payload_size = sys.getsizeof(str(payload))
                if payload_size > MAX_PAYLOAD_SIZE:
                    logger.error(f"Parsed payload too large: {payload_size} bytes")
                    raise HTTPException(status_code=413, detail="Payload too large.")
            except HTTPException:
                raise
            except Exception:
                logger.warning("Failed to parse JSON, trying form data", exc_info=True)
                form_data = await request.form()
                payload = dict(form_data)
        else:
            # Assume form data
            form_data = await request.form()
            payload = dict(form_data)
        
        logger.info(f"📥 WordPress webhook received for project {project_id}")
        
        # Get project owner for tenant_id
        project_owner = _get_user_id_from_project(project_id)
        if not project_owner:
            logger.warning(f"Project {project_id} not found in database")
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Normalize payload
        normalized_data = _normalize_lead_data(payload, "wordpress_form")
        
        # Create lead and trigger SalesAgent
        result = await _create_and_trigger_lead(
            normalized_data, 
            "wordpress_form", 
            project_id, 
            user_id=project_owner,
            background_tasks=background_tasks
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ WordPress webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")
