#!/usr/bin/env python3
"""
Manual script to update lead status for existing calls.
Usage: python scripts/test_status_update.py <lead_id>
"""
# Load environment
from dotenv import load_dotenv
load_dotenv()
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from twilio.rest import Client
from backend.core.memory import memory
from datetime import datetime



def update_lead_status(lead_id: str):
    """Manually update lead status by fetching call status from Twilio."""
    
    # 1. Find the lead
    print(f"🔍 Looking for lead: {lead_id}")
    
    # Search across common tenant_ids
    lead = None
    for tenant_id in ["system", "admin", "admin@admin.com"]:
        all_leads = memory.get_entities(
            tenant_id=tenant_id,
            entity_type="lead",
            limit=1000
        )
        for l in all_leads:
            if l.get('id') == lead_id:
                lead = l
                print(f"✅ Found lead in tenant_id: {tenant_id}")
                break
        if lead:
            break
    
    if not lead:
        print(f"❌ Lead {lead_id} not found")
        return
    
    # 2. Get call_sid from metadata
    call_sid = lead.get('metadata', {}).get('call_sid')
    if not call_sid:
        print(f"❌ No call_sid found in lead metadata. Lead hasn't been called yet.")
        return
    
    print(f"📞 Found call_sid: {call_sid}")
    
    # 3. Fetch call status from Twilio
    twilio_client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )
    
    try:
        # Fetch call resource for status and duration
        call_resource = twilio_client.calls(call_sid).fetch()
        call_status = call_resource.status
        call_duration = str(call_resource.duration) if call_resource.duration else "0"
        
        print(f"📊 Call Status: {call_status}, Duration: {call_duration}s")
        
        if call_status != "completed":
            print(f"⚠️ Call status is '{call_status}', not 'completed'. Updating anyway...")
        
        # 4. Fetch recording
        recording_url = None
        recordings = twilio_client.recordings.list(call_sid=call_sid)
        if recordings:
            recording = recordings[0]
            recording_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
            print(f"📼 Found recording: {recording_url}")
        
        # 5. Transcribe recording using Google Gemini (better quality, lower cost)
        transcription_text = None
        if recording_url:
            try:
                from backend.core.services.transcription import transcription_service
                
                print("🎤 Transcribing with Google Gemini...")
                transcription_text, error = transcription_service.transcribe_recording(
                    recording_url=recording_url,
                    call_sid=call_sid,
                    delete_after_transcription=True  # Delete to minimize Twilio storage costs
                )
                
                if transcription_text:
                    print(f"✅ Transcription complete: {len(transcription_text)} characters")
                elif error:
                    print(f"❌ Transcription failed: {error}")
                else:
                    print("⚠️ No transcription returned")
                    
            except ImportError as e:
                print(f"❌ Failed to import transcription service: {e}")
                print("   Make sure OPENAI_API_KEY is set in .env")
            except Exception as e:
                print(f"❌ Failed to transcribe recording: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️ No recording URL available for transcription")
        
        # 6. Update lead metadata
        updated_meta = lead['metadata'].copy()
        updated_meta['status'] = 'called'
        updated_meta['call_sid'] = call_sid
        updated_meta['call_status'] = call_status
        updated_meta['call_duration'] = int(call_duration) if call_duration.isdigit() else 0
        updated_meta['called_at'] = datetime.now().isoformat()
        
        if recording_url:
            updated_meta['recording_url'] = recording_url
        
        if transcription_text:
            updated_meta['call_transcription'] = transcription_text
            print(f"📝 Transcription saved: {len(transcription_text)} chars")
            
            # Analyze transcription with Gemini to extract structured data
            try:
                from backend.core.services.llm_gateway import llm_gateway
                import json
                
                print("🤖 Analyzing transcription with Gemini...")
                
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
                print(f"✅ Call analysis saved: {analysis_data.get('summary', '')[:50]}...")
                
            except Exception as e:
                print(f"⚠️ Failed to analyze transcription with Gemini: {e}")
                import traceback
                traceback.print_exc()
        
        success = memory.update_entity(lead_id, updated_meta)
        
        if success:
            print(f"✅ Successfully updated lead {lead_id}")
            print(f"   Status: called")
            print(f"   Recording: {'yes' if recording_url else 'no'}")
            print(f"   Transcription: {'yes' if transcription_text else 'no'}")
            print(f"   Analysis: {'yes' if updated_meta.get('call_analysis') else 'no'}")
        else:
            print(f"❌ Failed to update lead {lead_id}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_status_update.py <lead_id>")
        sys.exit(1)
    
    lead_id = sys.argv[1]
    update_lead_status(lead_id)