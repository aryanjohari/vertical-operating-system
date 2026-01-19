# backend/routers/voice.py
import os
import logging
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Dial
from backend.core.config import ConfigLoader
from backend.core.models import Entity
from backend.core.memory import memory

logger = logging.getLogger("Apex.Voice")

voice_router = APIRouter()

@voice_router.post("/incoming")
async def handle_incoming_call(request: Request):
    """
    Twilio webhook handler for incoming calls.
    Returns TwiML to dial the TARGET_PHONE from project config.
    """
    try:
        # Get form data from Twilio webhook
        form_data = await request.form()
        
        # Get project_id from query params or form data
        project_id = request.query_params.get("project_id") or form_data.get("project_id")
        
        if not project_id:
            # Try to infer from caller number or use default
            # For MVP, we can use a default project or get from env
            project_id = os.getenv("DEFAULT_PROJECT_ID")
            if not project_id:
                logger.error("No project_id provided in voice webhook")
                # Return error TwiML
                response = VoiceResponse()
                response.say("Error: Project not configured.")
                return Response(content=str(response), media_type="application/xml")
        
        # Load project config to get forwarding_number
        config_loader = ConfigLoader()
        config = config_loader.load(project_id)
        
        if "error" in config:
            logger.error(f"Project config not found: {project_id}")
            response = VoiceResponse()
            response.say("Error: Project configuration not found.")
            return Response(content=str(response), media_type="application/xml")
        
        # Get forwarding_number from config
        forwarding_number = config.get("operations", {}).get("voice_agent", {}).get("forwarding_number")
        
        if not forwarding_number:
            # Fallback to environment variable
            forwarding_number = os.getenv("TARGET_PHONE")
        
        if not forwarding_number:
            logger.error(f"No forwarding_number found for project {project_id}")
            response = VoiceResponse()
            response.say("Error: Forwarding number not configured.")
            return Response(content=str(response), media_type="application/xml")
        
        # Create TwiML response to dial the target phone
        response = VoiceResponse()
        dial = Dial(caller_id=os.getenv("TWILIO_PHONE_NUMBER"))
        dial.number(forwarding_number)
        response.append(dial)
        
        logger.info(f"Incoming call routed to {forwarding_number} for project {project_id}")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An error occurred. Please try again later.")
        return Response(content=str(response), media_type="application/xml")

@voice_router.post("/status")
async def handle_call_status(request: Request):
    """
    Twilio status callback handler.
    Saves call recording as a lead entity.
    """
    try:
        # Get form data from Twilio callback
        form_data = await request.form()
        
        # Extract call information
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        call_status = form_data.get("CallStatus", "")
        recording_url = form_data.get("RecordingUrl", "")
        recording_duration = form_data.get("RecordingDuration", "0")
        
        # Get project_id from query params or form data
        project_id = request.query_params.get("project_id") or form_data.get("project_id")
        
        if not project_id:
            project_id = os.getenv("DEFAULT_PROJECT_ID")
        
        # Only save as lead if call was completed and has recording
        if call_status == "completed" and recording_url:
            # Get user_id from project
            user_id = os.getenv("DEFAULT_USER_ID", "admin")
            
            if project_id:
                # Get project to find user_id
                import sqlite3
                conn = sqlite3.connect(memory.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT user_id FROM projects WHERE project_id = ?", (project_id,))
                row = cursor.fetchone()
                if row:
                    user_id = row["user_id"]
                conn.close()
            
            # Create lead entity from call recording
            lead_entity = Entity(
                tenant_id=user_id,
                entity_type="lead",
                name="Voice Call",
                primary_contact=from_number,
                metadata={
                    "source": "voice_call",
                    "recording_url": recording_url,
                    "recording_duration": recording_duration,
                    "call_sid": call_sid,
                    "from_number": from_number,
                    "to_number": to_number,
                    "call_status": call_status,
                    "project_id": project_id
                }
            )
            
            # Save to database
            success = memory.save_entity(lead_entity, project_id=project_id)
            
            if success:
                logger.info(f"Saved voice call as lead: {call_sid} for project {project_id}")
            else:
                logger.error(f"Failed to save voice call as lead: {call_sid}")
        
        # Return empty 200 response (Twilio expects this)
        return Response(content="", status_code=200)
        
    except Exception as e:
        logger.error(f"Error handling call status: {e}", exc_info=True)
        # Still return 200 to avoid Twilio retries
        return Response(content="", status_code=200)
