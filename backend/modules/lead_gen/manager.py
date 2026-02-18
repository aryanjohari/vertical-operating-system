# backend/modules/lead_gen/manager.py
import logging
import asyncio
import os
from datetime import datetime, timedelta
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.business_hours import within_business_hours, business_hours_message
from backend.core.services.email import send_email

class LeadGenManager(BaseAgent):
    def __init__(self):
        super().__init__(name="LeadGenManager")
        self.logger = logging.getLogger("Apex.LeadGenManager")

    def _resolve_campaign_id(self, user_id: str, project_id: str, campaign_id_from_params: str = None) -> str:
        """Resolve campaign_id: use params, or first lead_gen campaign for project, or None."""
        if campaign_id_from_params:
            return campaign_id_from_params
        campaigns = memory.get_campaigns_by_project(user_id, project_id, module="lead_gen")
        if campaigns:
            return campaigns[0].get("id", "")
        return None

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        The Orchestrator (Inbound Conversion Engine).
        Input params:
          - action: "lead_received", "ignite_reactivation", "instant_call", "transcribe_call", "dashboard_stats"
          - lead_id: (Optional) Used for lead_received, instant_call, transcribe_call
        """
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")

        project_id = self.project_id
        user_id = self.user_id
        action = input_data.params.get("action", "dashboard_stats")
        campaign_id_param = input_data.params.get("campaign_id") or self.campaign_id

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        campaign_id = self._resolve_campaign_id(user_id, project_id, campaign_id_param)

        if campaign_id:
            campaign = memory.get_campaign(campaign_id, user_id)
            if not campaign:
                return AgentOutput(status="error", message="Campaign not found or access denied.")
            if campaign.get("module") != "lead_gen":
                return AgentOutput(status="error", message=f"Campaign {campaign_id} is not a Lead Gen campaign.")
        elif action not in ("lead_received", "dashboard_stats"):
            return AgentOutput(
                status="error",
                message="campaign_id is required for this action. Please create a campaign or provide campaign_id.",
            )

        config = self.config
        if not config.get("modules", {}).get("lead_gen", {}).get("enabled", False):
            return AgentOutput(status="error", message="Lead Gen module is not enabled in project DNA.")

        self.logger.info(f"Manager executing action: {action} for {project_id}")

        try:
            from backend.core.kernel import kernel

            # --- ACTION 1: LEAD RECEIVED (Inbound from Webhooks) ---
            if action == "lead_received":
                lead_id = input_data.params.get("lead_id")
                if not lead_id:
                    return AgentOutput(status="error", message="Missing lead_id for lead_received.")

                self.logger.info(f"Processing inbound lead: {lead_id}")

                score_result = await asyncio.wait_for(
                    kernel.dispatch(
                        AgentInput(
                            task="lead_scorer",
                            user_id=user_id,
                            params={
                                "lead_id": lead_id,
                                "project_id": project_id,
                                "campaign_id": campaign_id,
                            },
                        )
                    ),
                    timeout=60,
                )

                if score_result.status != "success":
                    self.logger.warning(f"Scorer failed for lead {lead_id}: {score_result.message}")
                    return score_result

                score = score_result.data.get("score", 0) if isinstance(score_result.data, dict) else 0
                sb = config.get("modules", {}).get("lead_gen", {}).get("sales_bridge", {})
                min_score_to_ring = int(sb.get("min_score_to_ring", 90))

                if score < min_score_to_ring:
                    self.logger.info(f"Lead {lead_id} score {score} < {min_score_to_ring}; not eligible for bridge.")
                    return AgentOutput(
                        status="success",
                        data={"lead_id": lead_id, "score": score_result.data},
                        message=f"Lead scored; not eligible for bridge (score < {min_score_to_ring}).",
                    )

                # Manual review: send email only; do not auto-bridge
                bridge_review_email = (sb.get("bridge_review_email") or "").strip()
                if not bridge_review_email:
                    self.logger.warning("bridge_review_email not configured; skipping bridge-review notification.")
                    return AgentOutput(
                        status="success",
                        data={"lead_id": lead_id, "score": score_result.data},
                        message="Lead scored; bridge review email not configured.",
                    )

                # Schedule auto-bridge after delay (e.g. 10 min); process_scheduled_bridges will run the call
                bridge_delay_minutes = int(sb.get("bridge_delay_minutes", 10))
                scheduled_at = (datetime.utcnow() + timedelta(minutes=bridge_delay_minutes)).isoformat() + "Z"
                all_leads = memory.get_entities(tenant_id=user_id, entity_type="lead", project_id=project_id, limit=1000)
                lead = next((l for l in all_leads if l.get("id") == lead_id), None)
                if lead:
                    meta = (lead.get("metadata") or {}).copy()
                    meta["scheduled_bridge_at"] = scheduled_at
                    meta["bridge_status"] = "scheduled"
                    memory.update_entity(lead_id, meta, tenant_id=user_id)

                # Build lead summary for email
                lead_name = lead.get("name", "—") if lead else "—"
                lead_contact = lead.get("primary_contact", "—") if lead else "—"
                lead_message = ""
                if lead:
                    lead_message = (lead.get("metadata") or {}).get("data") or {}
                    if isinstance(lead_message, dict):
                        lead_message = lead_message.get("message", "") or ""
                    else:
                        lead_message = str(lead_message)[:500]
                app_url = os.getenv("NEXT_PUBLIC_APP_URL") or os.getenv("APP_URL") or "https://app.apex.local"
                dashboard_link = f"{app_url.rstrip('/')}/projects/{project_id}"
                subject = f"High-value lead (score {score}) – bridge in {bridge_delay_minutes} min or connect now"
                body_plain = f"""High-value lead (score {score}/100)

Name: {lead_name}
Contact: {lead_contact}
Message: {lead_message}

Bridge will be attempted automatically in {bridge_delay_minutes} minutes (within business hours).
Or connect now: {dashboard_link}"""
                body_html = f"""<p>High-value lead (score <strong>{score}/100</strong>)</p>
<p><strong>Name:</strong> {lead_name}<br/><strong>Contact:</strong> {lead_contact}</p>
<p><strong>Message:</strong><br/>{lead_message or "—"}</p>
<p>Bridge in {bridge_delay_minutes} min (if within business hours), or <a href="{dashboard_link}">connect now</a>.</p>"""
                send_email(to=bridge_review_email, subject=subject, body_plain=body_plain, body_html=body_html)

                return AgentOutput(
                    status="success",
                    data={"lead_id": lead_id, "score": score_result.data, "scheduled_bridge_at": scheduled_at},
                    message=f"Lead scored; bridge scheduled in {bridge_delay_minutes} min.",
                )

            # --- ACTION 2: THE MINER (Reactivation) ---
            # Triggered by "BLAST LIST" button
            elif action == "ignite_reactivation":
                self.logger.info("🔥 Igniting Reactivation Campaign...")
                # Lazy import to avoid circular dependency during kernel initialization
                from backend.core.kernel import kernel
                try:
                    result = await asyncio.wait_for(
                        kernel.dispatch(
                            AgentInput(
                                task="reactivator_agent",
                                user_id=user_id,
                                params={"limit": 50, "project_id": project_id, "campaign_id": campaign_id} # Safety limit: 50 SMS at a time
                            )
                        ),
                        timeout=300  # 5 minutes max per task
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Reactivator Agent timed out after 5 minutes")
                    return AgentOutput(status="error", message="Reactivation campaign timed out after 5 minutes.")
                return AgentOutput(status="success", data=result.data, message="Reactivation blast finished.")

            # --- ACTION 3: THE BRIDGE (Sales/Speed-to-Lead) ---
            # Triggered by dashboard "Connect call" or approve-bridge link
            elif action == "instant_call":
                lead_id = input_data.params.get("lead_id")
                if not lead_id:
                    return AgentOutput(status="error", message="Missing lead_id for instant call.")

                if not within_business_hours(config):
                    msg = business_hours_message(config)
                    self.logger.info(f"Bridge refused for lead {lead_id}: outside business hours")
                    return AgentOutput(status="error", message=msg)

                self.logger.info(f"📞 Bridging Call for Lead: {lead_id}")
                # Lazy import to avoid circular dependency during kernel initialization
                from backend.core.kernel import kernel
                try:
                    result = await asyncio.wait_for(
                        kernel.dispatch(
                            AgentInput(
                                task="sales_agent",
                                user_id=user_id,
                                params={"action": "instant_call", "lead_id": lead_id, "project_id": project_id, "campaign_id": campaign_id}
                            )
                        ),
                        timeout=60  # 1 minute max for call setup
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Sales Agent timed out after 1 minute")
                    return AgentOutput(status="error", message="Bridge call setup timed out.")
                return AgentOutput(status="success", data=result.data, message="Bridge call initiated.")

            # --- ACTION 3b: PROCESS SCHEDULED BRIDGES (Cron / Poll) ---
            # Call periodically (e.g. every 1–2 min). Finds leads with scheduled_bridge_at <= now,
            # within business hours, and dispatches instant_call for each; marks bridge_attempted.
            elif action == "process_scheduled_bridges":
                from backend.core.kernel import kernel
                now_iso = datetime.utcnow().isoformat() + "Z"
                all_leads = memory.get_entities(
                    tenant_id=user_id,
                    entity_type="lead",
                    project_id=project_id,
                    limit=500,
                )
                to_bridge = []
                for lead in all_leads:
                    meta = lead.get("metadata") or {}
                    if meta.get("bridge_status") != "scheduled":
                        continue
                    at = meta.get("scheduled_bridge_at")
                    if not at or at > now_iso:
                        continue
                    to_bridge.append(lead)
                attempted = 0
                for lead in to_bridge:
                    lead_id = lead.get("id")
                    if not lead_id:
                        continue
                    if not within_business_hours(config):
                        self.logger.info("process_scheduled_bridges: outside business hours; stopping.")
                        break
                    try:
                        result = await asyncio.wait_for(
                            kernel.dispatch(
                                AgentInput(
                                    task="lead_gen_manager",
                                    user_id=user_id,
                                    params={
                                        "action": "instant_call",
                                        "lead_id": lead_id,
                                        "project_id": project_id,
                                        "campaign_id": campaign_id,
                                    },
                                )
                            ),
                            timeout=60,
                        )
                    except Exception as e:
                        self.logger.warning(f"Bridge attempt failed for lead {lead_id}: {e}")
                    memory.update_entity(lead_id, {"bridge_status": "bridge_attempted"}, tenant_id=user_id)
                    attempted += 1
                return AgentOutput(
                    status="success",
                    data={"attempted": attempted, "candidates": len(to_bridge)},
                    message=f"Processed scheduled bridges: {attempted} attempted.",
                )

            # --- ACTION 4: TRANSCRIBE CALL (Manual Transcription) ---
            # Triggered manually to transcribe an existing call recording
            elif action == "transcribe_call":
                lead_id = input_data.params.get("lead_id")
                if not lead_id:
                    return AgentOutput(status="error", message="Missing lead_id for transcription.")
                
                self.logger.info(f"🎤 Transcribing call for Lead: {lead_id}")
                
                # Find the lead
                all_leads = memory.get_entities(
                    tenant_id=user_id,
                    entity_type="lead",
                    project_id=project_id,
                    limit=1000
                )
                
                lead = None
                for l in all_leads:
                    if l.get('id') == lead_id:
                        lead = l
                        break
                
                if not lead:
                    return AgentOutput(status="error", message=f"Lead {lead_id} not found.")
                
                # Get call_sid from metadata
                call_sid = lead.get('metadata', {}).get('call_sid')
                if not call_sid:
                    return AgentOutput(status="error", message="No call_sid found. Lead hasn't been called yet.")
                
                # Get recording URL
                recording_url = lead.get('metadata', {}).get('recording_url')
                if not recording_url:
                    # Try to fetch from Twilio
                    try:
                        from twilio.rest import Client
                        twilio_client = Client(
                            os.getenv("TWILIO_ACCOUNT_SID"),
                            os.getenv("TWILIO_AUTH_TOKEN")
                        )
                        recordings = twilio_client.recordings.list(call_sid=call_sid)
                        if recordings:
                            recording = recordings[0]
                            recording_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                        else:
                            return AgentOutput(status="error", message="No recording found for this call.")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to fetch recording from Twilio: {e}", exc_info=True)
                        return AgentOutput(status="error", message=f"Failed to fetch recording: {str(e)}")
                
                # Transcribe using the transcription service
                try:
                    from backend.core.services.transcription import transcription_service
                    
                    transcription_text, error = transcription_service.transcribe_recording(
                        recording_url=recording_url,
                        call_sid=call_sid,
                        delete_after_transcription=True
                    )
                    
                    if transcription_text:
                        # Update lead metadata with transcription
                        updated_meta = lead['metadata'].copy()
                        updated_meta['call_transcription'] = transcription_text
                        self.logger.info(f"✅ Transcription saved: {len(transcription_text)} chars")
                        
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
                            self.logger.info(f"✅ Call analysis saved: {analysis_data.get('summary', '')[:50]}...")
                            
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to analyze transcription with Gemini: {e}", exc_info=True)
                        
                        memory.update_entity(lead_id, updated_meta, self.user_id)
                        return AgentOutput(
                            status="success",
                            data={
                                "transcription_length": len(transcription_text),
                                "has_analysis": 'call_analysis' in updated_meta
                            },
                            message="Call transcribed and analyzed successfully."
                        )
                    elif error:
                        return AgentOutput(status="error", message=f"Transcription failed: {error}")
                    else:
                        return AgentOutput(status="error", message="No transcription returned.")
                        
                except ImportError as e:
                    self.logger.error(f"❌ Failed to import transcription service: {e}")
                    return AgentOutput(status="error", message="Transcription service not available. Make sure GOOGLE_API_KEY is set in .env")
                except Exception as e:
                    self.logger.error(f"❌ Transcription failed: {e}", exc_info=True)
                    return AgentOutput(status="error", message=f"Transcription failed: {str(e)}")

            # --- ACTION 5: DASHBOARD STATS (Default) ---
            # Returns data for the Frontend Graphs
            else:
                stats = self._get_stats(project_id, user_id, campaign_id)
                return AgentOutput(status="success", data=stats, message="Stats retrieved.")

        except Exception as e:
            self.logger.error(f"❌ Manager Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))

    def _get_stats(self, project_id, user_id, campaign_id):
        """
        Helper to count leads for the dashboard with enhanced analytics.
        """
        # Fetch all leads for this project (use user_id, not hardcoded "admin")
        all_leads = memory.get_entities(tenant_id=user_id, entity_type="lead", project_id=project_id, limit=1000)
        # Filter by campaign_id
        leads = [l for l in all_leads if l.get('metadata', {}).get('campaign_id') == campaign_id]
        
        if not leads:
            return {
                "total_leads": 0,
                "avg_lead_score": 0,
                "total_pipeline_value": 0,
                "conversion_rate": 0,
                "sources": {
                    "sniper": 0,
                    "web": 0,
                    "voice": 0,
                    "google_ads": 0,
                    "wordpress_form": 0
                },
                "priorities": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                },
                "recent_leads": []
            }
        
        # Calculate average lead score
        scores = [l.get('metadata', {}).get('score', 0) for l in leads if l.get('metadata', {}).get('score') is not None]
        avg_lead_score = sum(scores) / len(scores) if scores else 0
        
        # Calculate total pipeline value (assumed $500 per lead)
        total_pipeline_value = len(leads) * 500
        
        # Calculate conversion rate (leads with status='won')
        won_leads = [l for l in leads if l.get('metadata', {}).get('status') == 'won']
        conversion_rate = len(won_leads) / len(leads) if leads else 0
        
        # Source breakdown
        sources = {
            "sniper": len([l for l in leads if l.get('metadata', {}).get('source') == 'sniper']),
            "web": len([l for l in leads if l.get('metadata', {}).get('source') in ['web_form', 'web']]),
            "voice": len([l for l in leads if l.get('metadata', {}).get('source') == 'voice_call']),
            "google_ads": len([l for l in leads if l.get('metadata', {}).get('source') == 'google_ads']),
            "wordpress_form": len([l for l in leads if l.get('metadata', {}).get('source') == 'wordpress_form'])
        }
        
        # Priority breakdown
        priorities = {
            "high": len([l for l in leads if l.get('metadata', {}).get('priority') == 'High']),
            "medium": len([l for l in leads if l.get('metadata', {}).get('priority') == 'Medium']),
            "low": len([l for l in leads if l.get('metadata', {}).get('priority') == 'Low'])
        }
        
        return {
            "total_leads": len(leads),
            "avg_lead_score": round(avg_lead_score, 2),
            "total_pipeline_value": total_pipeline_value,
            "conversion_rate": round(conversion_rate, 4),  # Return as decimal (0.25 = 25%)
            "sources": sources,
            "priorities": priorities,
            "recent_leads": [l.get('name', 'Unknown') for l in leads[:5]]
        }