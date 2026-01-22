# backend/routers/voice.py
import os
import logging
import sqlite3
import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial
from twilio.rest import Client
from backend.core.config import ConfigLoader
from backend.core.models import Entity
from backend.core.memory import memory

# Initialize Logger
logger = logging.getLogger("Apex.Voice")
voice_router = APIRouter()

def _get_user_id_from_project(project_id: str):
    """
    Gets the user_id (owner) of a project.
    Used to find the correct tenant_id for lead lookup.
    """
    try:
        conn = sqlite3.connect(memory.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            user_id = row[0]
            logger.debug(f"Found project owner: {user_id} for project {project_id}")
            return user_id
        else:
            logger.warning(f"Project {project_id} not found in database")
            return None
    except Exception as e:
        logger.error(f"Error finding project owner: {e}", exc_info=True)
        return None

# --- 1. THE BRIDGE CONNECTOR (SPEED-TO-LEAD) ---
# Triggered when the Boss presses "1" on the "Whisper Call".
# It connects the Boss's active line to the Customer's phone number.
@voice_router.post("/connect")
async def connect_bridge(request: Request):
    """
    Action: Connects the Boss to the Customer.
    """
    try:
        # Get the customer's phone number passed from SalesAgent
        target_phone = request.query_params.get("target")
        
        response = VoiceResponse()
        
        if not target_phone:
            logger.error("❌ No target phone number provided in /connect")
            response.say("Error. No target number found.")
            response.hangup()
            return Response(content=str(response), media_type="application/xml")

        # Decode URL-encoded phone number
        target_phone = urllib.parse.unquote(target_phone)
        
        # Validate and normalize phone number format (ensure E.164)
        original_phone = target_phone
        if not target_phone.startswith('+'):
            # Try to add country code if missing (assume NZ for now)
            if target_phone.startswith('0'):
                target_phone = '+64' + target_phone[1:]  # Replace leading 0 with +64
            elif not target_phone.startswith('64'):
                target_phone = '+64' + target_phone.lstrip('0')
        
        logger.info(f"📞 Connecting to customer: {original_phone} -> {target_phone}")

        # The Audio Bridge
        response.say("Connecting you now. Good luck.")
        
        # Dial the Customer with recording enabled
        # caller_id is set to your Twilio Number so the customer sees the Business Number, 
        # NOT the Boss's private mobile number.
        api_base_url = os.getenv("NGROK_URL") or os.getenv("NEXT_PUBLIC_API_URL") or "http://localhost:8000"
        
        dial = Dial(
            caller_id=os.getenv("TWILIO_PHONE_NUMBER"),
            record="record-from-ringing-dual",  # Record both sides (we'll transcribe with Whisper)
            recording_status_callback=f"{api_base_url}/api/voice/recording-status",
            recording_status_callback_method='POST',
            # Note: We use OpenAI Whisper for transcription (better quality, lower cost)
            # No need for Twilio's transcribe=True
            action=f"{api_base_url}/api/voice/dial-status",  # Handle Dial completion
            timeout=30,  # Wait 30 seconds for answer
            hangup_on_star=False,
            time_limit=3600  # Max call duration: 1 hour
        )
        dial.number(target_phone)
        response.append(dial)
        
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"❌ Bridge Connect Failed: {e}", exc_info=True)
        resp = VoiceResponse()
        resp.say("Connection failed. Please check logs.")
        resp.hangup()
        return Response(content=str(resp), media_type="application/xml")


# --- 1B. DIAL STATUS HANDLER ---
# Triggered when Dial completes (answered, busy, no-answer, failed).
@voice_router.post("/dial-status")
async def handle_dial_status(request: Request):
    """
    Handles Dial completion status (answered, busy, no-answer, failed).
    """
    try:
        form_data = await request.form()
        dial_call_status = form_data.get("DialCallStatus", "")  # completed, busy, no-answer, failed, canceled
        dial_call_duration = form_data.get("DialCallDuration", "0")
        dial_call_sid = form_data.get("DialCallSid", "")
        
        logger.info(f"📞 Dial Status: {dial_call_status} | Duration: {dial_call_duration}s | Call SID: {dial_call_sid}")
        
        response = VoiceResponse()
        
        if dial_call_status == "completed":
            response.say("Call completed. Goodbye.")
            logger.info(f"✅ Call completed successfully. Duration: {dial_call_duration}s")
        elif dial_call_status in ["busy", "no-answer"]:
            response.say("The customer did not answer. Goodbye.")
            logger.warning(f"⚠️ Customer did not answer. Status: {dial_call_status}")
        elif dial_call_status == "failed":
            response.say("Call failed. Please try again later.")
            logger.error(f"❌ Call failed. Status: {dial_call_status}")
        else:
            response.say("Call ended. Goodbye.")
            logger.info(f"📞 Call ended. Status: {dial_call_status}")
        
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Error handling dial status: {e}", exc_info=True)
        response = VoiceResponse()
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


# --- 2. INBOUND HANDLER (PASSIVE) ---
# Triggered when a customer calls the public Twilio number directly.
# Forwards the call to the Boss's private mobile.
@voice_router.post("/incoming")
async def handle_incoming_call(request: Request):
    """
    Action: Forwards customer calls to the Boss's real mobile.
    """
    try:
        # 1. Identify Project (Logic to map phone # to project)
        # For MVP, we default to the env var or query param
        project_id = request.query_params.get("project_id") or os.getenv("DEFAULT_PROJECT_ID")
        
        # 2. Load Config to find where to forward
        config_loader = ConfigLoader()
        config = config_loader.load(project_id)
        
        # Get the "Batphone" (Destination)
        forwarding_number = config.get("modules", {}).get("lead_gen", {}).get("sales_bridge", {}).get("destination_phone")
        
        if not forwarding_number:
            # Fallback to env if DNA is missing
            forwarding_number = os.getenv("TARGET_PHONE")

        response = VoiceResponse()
        
        if not forwarding_number:
            logger.error(f"❌ No forwarding number found for Project {project_id}")
            response.say("Error. Forwarding number not configured.")
            return Response(content=str(response), media_type="application/xml")

        # 3. Connect the call
        # We record it so we can transcribe it later ("record-from-ringing-dual")
        # When call ends, Twilio hits /status to save the recording
        dial = Dial(record="record-from-ringing-dual", action="/api/voice/status") 
        dial.number(forwarding_number)
        response.append(dial)
        
        logger.info(f"📞 Inbound Call Forwarding to {forwarding_number} (Project: {project_id})")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An error occurred. Please try again later.")
        return Response(content=str(response), media_type="application/xml")


# --- 3. STATUS & SAFETY NET (NURTURE) ---
# Triggered when any call ends (Inbound OR Outbound).
# Saves the recording, transcribes, and updates lead entity.
@voice_router.post("/status")
async def handle_call_status(request: Request):
    """
    Action: Saves call recording, transcribes, and updates lead entity.
    """
    try:
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        call_status = form_data.get("CallStatus", "")  # completed, busy, no-answer, failed
        call_duration = form_data.get("CallDuration", "0")  # Duration in seconds
        
        # Get lead_id and project_id from query params (set by SalesAgent)
        lead_id = request.query_params.get("lead_id")
        project_id = request.query_params.get("project_id") or os.getenv("DEFAULT_PROJECT_ID")

        logger.info(f"📞 Call Status: {call_sid} | Status: {call_status} | Lead: {lead_id} | Project: {project_id}")

        # A. FIND ORIGINAL LEAD (process all completed calls, search by lead_id or call_sid)
        if call_status == "completed":
            try:
                # Get project owner's tenant_id to search in the right place
                project_owner_id = None
                if project_id:
                    project_owner_id = _get_user_id_from_project(project_id)
                
                # Build list of tenant_ids to search (prioritize project owner)
                tenant_ids_to_try = []
                if project_owner_id:
                    tenant_ids_to_try.append(project_owner_id)
                tenant_ids_to_try.extend(["system", "admin"])
                # Remove duplicates while preserving order
                tenant_ids_to_try = list(dict.fromkeys(tenant_ids_to_try))
                
                logger.info(f"🔍 Searching for lead with call_sid={call_sid}, lead_id={lead_id}, project={project_id} in tenant_ids: {tenant_ids_to_try}")
                
                lead = None
                
                # First, try to find by lead_id if provided
                if lead_id:
                    for tenant_id in tenant_ids_to_try:
                        all_leads = memory.get_entities(
                            tenant_id=tenant_id,
                            entity_type="lead",
                            project_id=project_id,
                            limit=1000
                        )
                        for l in all_leads:
                            if l.get('id') == lead_id:
                                lead = l
                                logger.info(f"✅ Found lead by lead_id: {lead_id} in tenant_id: {tenant_id}")
                                break
                        if lead:
                            break
                
                # If not found by lead_id, try to find by call_sid in metadata
                if not lead:
                    logger.info(f"🔍 Searching by call_sid: {call_sid}")
                    for tenant_id in tenant_ids_to_try:
                        all_leads = memory.get_entities(
                            tenant_id=tenant_id,
                            entity_type="lead",
                            project_id=project_id,
                            limit=1000
                        )
                        for l in all_leads:
                            if l.get('metadata', {}).get('call_sid') == call_sid:
                                lead = l
                                lead_id = l.get('id')  # Update lead_id for later use
                                logger.info(f"✅ Found lead by call_sid: {call_sid} -> lead_id: {lead_id} in tenant_id: {tenant_id}")
                                break
                        if lead:
                            break
                
                if lead:
                    logger.info(f"✅ Found lead {lead_id} for call {call_sid}")
                    
                    # B. FETCH RECORDING FROM TWILIO
                    recording_url = None
                    transcription_text = None
                    
                    try:
                        twilio_client = Client(
                            os.getenv("TWILIO_ACCOUNT_SID"),
                            os.getenv("TWILIO_AUTH_TOKEN")
                        )
                        
                        # Get recordings for this call
                        recordings = twilio_client.recordings.list(call_sid=call_sid)
                        if recordings:
                            recording = recordings[0]
                            recording_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                            logger.info(f"📼 Found recording: {recording_url}")
                            
                            # C. TRANSCRIBE WITH GOOGLE GEMINI (better quality, lower cost)
                            try:
                                from backend.core.services.transcription import transcription_service
                                
                                logger.info("🎤 Transcribing with Google Gemini...")
                                transcription_text, error = transcription_service.transcribe_recording(
                                    recording_url=recording_url,
                                    call_sid=call_sid,
                                    delete_after_transcription=True  # Delete to minimize Twilio storage costs
                                )
                                
                                if transcription_text:
                                    logger.info(f"✅ Transcription complete: {len(transcription_text)} characters")
                                elif error:
                                    logger.warning(f"⚠️ Transcription failed: {error}")
                                else:
                                    logger.warning("⚠️ No transcription returned")
                                    
                            except ImportError as e:
                                logger.error(f"❌ Failed to import transcription service: {e}")
                                logger.error("   Make sure GOOGLE_API_KEY is set in .env")
                            except Exception as transcribe_error:
                                logger.warning(f"⚠️ Failed to transcribe with Gemini: {transcribe_error}", exc_info=True)
                        else:
                            logger.warning(f"⚠️ No recordings found for call {call_sid}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to fetch recording/transcription: {e}", exc_info=True)
                    
                    # D. UPDATE LEAD ENTITY WITH CALL DATA
                    updated_meta = lead['metadata'].copy()
                    updated_meta['status'] = 'called'
                    updated_meta['call_sid'] = call_sid
                    updated_meta['call_status'] = call_status
                    updated_meta['call_duration'] = int(call_duration) if call_duration.isdigit() else 0
                    updated_meta['called_at'] = datetime.now().isoformat()
                    
                    if recording_url:
                        updated_meta['recording_url'] = recording_url
                        logger.info(f"💾 Recording URL saved: {recording_url}")
                    
                    if transcription_text:
                        updated_meta['call_transcription'] = transcription_text
                        logger.info(f"✅ Transcription saved for lead {lead_id} ({len(transcription_text)} chars)")
                        
                        # Analyze transcription with Gemini to extract structured data
                        try:
                            from backend.core.services.llm_gateway import llm_gateway
                            import json
                            
                            analysis_prompt = f"""Analyze this phone call transcription and extract structured information.

Call Transcription:
{transcription_text}

Extract and return a JSON object with:
- summary: Brief 2-3 sentence summary of the call
- key_points: Array of main topics discussed
- customer_intent: What the customer wants/needs
- next_steps: Recommended follow-up actions
- sentiment: positive/neutral/negative
- urgency: high/medium/low

Return only valid JSON, no markdown formatting."""
                            
                            analysis = llm_gateway.generate_content(
                                system_prompt="You are a call analysis assistant. Extract structured data from call transcriptions. Always return valid JSON only.",
                                user_prompt=analysis_prompt,
                                temperature=0.3
                            )
                            
                            # Parse JSON response (remove markdown if present)
                            analysis_clean = analysis.strip()
                            if analysis_clean.startswith('```json'):
                                analysis_clean = analysis_clean.replace('```json', '').replace('```', '').strip()
                            elif analysis_clean.startswith('```'):
                                analysis_clean = analysis_clean.replace('```', '').strip()
                            
                            analysis_data = json.loads(analysis_clean)
                            
                            updated_meta['call_analysis'] = analysis_data
                            logger.info(f"✅ Call analysis saved for lead {lead_id}: {analysis_data.get('summary', '')[:50]}...")
                            
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to analyze transcription with Gemini: {e}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ No transcription available for call {call_sid}")
                    
                    success = memory.update_entity(lead_id, updated_meta)
                    if success:
                        logger.info(f"💾 Updated lead {lead_id} with call data (status: called, duration: {call_duration}s, recording: {'yes' if recording_url else 'no'}, transcription: {'yes' if transcription_text else 'no'})")
                    else:
                        logger.error(f"❌ Failed to update lead {lead_id}")
                else:
                    logger.warning(f"⚠️ Lead not found for call {call_sid} (searched lead_id={lead_id}, call_sid={call_sid}, project={project_id}, tenant_ids={tenant_ids_to_try})")
            except Exception as e:
                logger.error(f"❌ Error processing call status for call {call_sid} (lead_id={lead_id}): {e}", exc_info=True)
                    
        # E. HANDLE INBOUND CALLS (existing logic - no lead_id)
        elif not lead_id:
            recording_url = form_data.get("RecordingUrl", "")
        if recording_url:
            lead_entity = Entity(
                tenant_id="admin",
                entity_type="lead",
                name="Inbound Call",
                primary_contact=from_number,
                metadata={
                    "source": "voice_call",
                    "recording_url": recording_url,
                    "call_sid": call_sid,
                    "call_status": call_status,
                    "project_id": project_id,
                    "status": "new"
                }
            )
            memory.save_entity(lead_entity, project_id=project_id)
            logger.info(f"💾 Saved Inbound Call Recording for Call {call_sid}")

        # F. NURTURE LOGIC (existing - for missed calls)
        if call_status in ["busy", "no-answer", "failed"]:
            config_loader = ConfigLoader()
            config = config_loader.load(project_id)
            nurture_config = config.get('modules', {}).get('lead_gen', {}).get('nurturing', {})
            
            if nurture_config.get('enabled', False):
                nurture_text = nurture_config.get('missed_call_sms')
                
                if nurture_text:
                    customer_phone = from_number 
                    from backend.core.kernel import kernel
                    from backend.core.agent_base import AgentInput
                    
                    logger.info(f"🚑 Triggering Nurture SMS to {customer_phone}")
                    
                    try:
                        await kernel.dispatch(AgentInput(
                            task="sales_agent",
                        user_id="admin",
                        project_id=project_id,
                        params={
                                "action": "notify_sms",
                                "lead_id": "DIRECT_SMS",
                            "direct_phone": customer_phone,
                            "custom_message": nurture_text
                        }
                    ))
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to send nurture SMS: {e}", exc_info=True)

        return Response(content="", status_code=200)
        
    except Exception as e:
        logger.error(f"❌ Error handling call status: {e}", exc_info=True)
        return Response(content="", status_code=200)


# --- 4. RECORDING STATUS CALLBACK ---
# Triggered when recording is complete.
@voice_router.post("/recording-status")
async def handle_recording_status(request: Request):
    """
    Triggered when recording is complete.
    Fetches transcription if available.
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        recording_sid = form_data.get("RecordingSid")
        recording_url = form_data.get("RecordingUrl", "")
        recording_status = form_data.get("RecordingStatus", "")
        
        logger.info(f"📼 Recording Status: {recording_status} for Call {call_sid} (Recording: {recording_sid})")
        
        # If recording is complete, try to get transcription
        if recording_status == "completed" and recording_url:
            try:
                twilio_client = Client(
                    os.getenv("TWILIO_ACCOUNT_SID"),
                    os.getenv("TWILIO_AUTH_TOKEN")
                )
                
                # Fix: Use call object to get transcriptions
                try:
                    call = twilio_client.calls.get(call_sid)
                    transcriptions = call.transcriptions.list()
                    if transcriptions:
                        transcription_text = transcriptions[0].transcription_text
                        logger.info(f"📝 Transcription available for {call_sid}: {transcription_text[:100]}...")
                    else:
                        logger.info(f"📝 No transcription found for {call_sid}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to fetch transcription: {e}", exc_info=True)
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Twilio client for transcription: {e}", exc_info=True)
        
        return Response(content="", status_code=200)
    except Exception as e:
        logger.error(f"❌ Error handling recording status: {e}", exc_info=True)
        return Response(content="", status_code=200)


# --- 5. TRANSCRIPTION CALLBACK ---
# Triggered when transcription is complete.
@voice_router.post("/transcription")
async def handle_transcription(request: Request):
    """
    Triggered when transcription is complete.
    Updates lead entity with transcription.
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        transcription_text = form_data.get("TranscriptionText", "")
        transcription_status = form_data.get("TranscriptionStatus", "")
        
        logger.info(f"📝 Transcription Status: {transcription_status} for Call {call_sid}")
        
        if transcription_status == "completed" and transcription_text:
            # Find lead by call_sid
            try:
                # Search all projects for lead with this call_sid
                project_id = request.query_params.get("project_id") or os.getenv("DEFAULT_PROJECT_ID")
                
                all_leads = memory.get_entities(
                    tenant_id="system",
                    entity_type="lead",
                    project_id=project_id,
                    limit=1000
                )
                
                lead = None
                for l in all_leads:
                    if l.get('metadata', {}).get('call_sid') == call_sid:
                        lead = l
                        break
                
                if lead:
                    updated_meta = lead['metadata'].copy()
                    updated_meta['call_transcription'] = transcription_text
                    memory.update_entity(lead['id'], updated_meta)
                    logger.info(f"✅ Updated lead {lead['id']} with transcription")
                else:
                    logger.warning(f"⚠️ Lead not found for call_sid {call_sid}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to update lead with transcription: {e}", exc_info=True)
        
        return Response(content="", status_code=200)
    except Exception as e:
        logger.error(f"❌ Error handling transcription: {e}", exc_info=True)
        return Response(content="", status_code=200)