# backend/modules/lead_gen/manager.py
import logging
import asyncio
import os
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class LeadGenManager(BaseAgent):
    def __init__(self):
        super().__init__(name="LeadGenManager")
        self.logger = logging.getLogger("Apex.LeadGenManager")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        The Orchestrator.
        Input params:
          - action: "hunt_sniper", "ignite_reactivation", "instant_call", "transcribe_call", "dashboard_stats"
          - lead_id: (Optional) Used for instant_call and transcribe_call
        """
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Get campaign_id from params or injected context
        campaign_id = input_data.params.get("campaign_id") or self.campaign_id
        
        if not campaign_id:
            return AgentOutput(
                status="error", 
                message="campaign_id is required. Please create a campaign first or provide campaign_id in params."
            )
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # Verify campaign ownership
        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found or access denied.")
        
        if campaign.get('module') != 'lead_gen':
            return AgentOutput(status="error", message=f"Campaign {campaign_id} is not a Lead Gen campaign.")
        
        action = input_data.params.get("action", "dashboard_stats")

        # 1. Use injected config (loaded by kernel - already merged DNA + campaign)
        config = self.config
        if not config.get('modules', {}).get('lead_gen', {}).get('enabled', False):
            return AgentOutput(status="error", message="Lead Gen module is not enabled in project DNA.")

        self.logger.info(f"💼 Manager executing action: {action} for {project_id}")

        try:
            # --- ACTION 1: THE HUNTER (Sniper) ---
            # Triggered by "HUNT NOW" button on Dashboard
            if action == "hunt_sniper":
                self.logger.info("🎯 Deploying Sniper Agent...")
                # Lazy import to avoid circular dependency during kernel initialization
                from backend.core.kernel import kernel
                # Dispatch to Sniper Agent
                # We use kernel.dispatch to keep agents decoupled
                try:
                    result = await asyncio.wait_for(
                        kernel.dispatch(
                            AgentInput(
                                task="sniper_agent",
                                user_id=user_id,
                                params={"mode": "aggressive", "project_id": project_id, "campaign_id": campaign_id} # Scrape everything
                            )
                        ),
                        timeout=300  # 5 minutes max per task
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Sniper Agent timed out after 5 minutes")
                    return AgentOutput(status="error", message="Sniper hunt timed out after 5 minutes.")
                
                # After sniper hunt, automatically score the new leads
                if result.status == "success":
                    self.logger.info("📊 Scoring new leads...")
                    try:
                        # Fetch recently created leads (within last 5 minutes would be ideal, but for simplicity, fetch all and score un-scored ones)
                        all_leads = memory.get_entities(
                            tenant_id=user_id,
                            entity_type="lead",
                            project_id=project_id,
                            limit=100
                        )
                        
                        # Filter leads by campaign_id and that don't have a score yet
                        unscored_leads = [
                            lead for lead in all_leads 
                            if lead.get('metadata', {}).get('campaign_id') == campaign_id
                            and lead.get('metadata', {}).get('score') is None
                        ]
                        
                        # Batch process (limit to 10 at a time to avoid timeout)
                        scored_count = 0
                        for lead in unscored_leads[:10]:
                            try:
                                score_result = await asyncio.wait_for(
                                    kernel.dispatch(
                                        AgentInput(
                                            task="lead_scorer",
                                            user_id=user_id,
                                            params={
                                                "lead_id": lead['id'],
                                                "project_id": project_id
                                            }
                                        )
                                    ),
                                    timeout=60  # 1 minute max per scoring
                                )
                                if score_result.status == "success":
                                    scored_count += 1
                            except asyncio.TimeoutError:
                                self.logger.warning(f"Scoring timed out for lead {lead.get('id')}")
                                continue
                            except Exception as e:
                                self.logger.warning(f"Failed to score lead {lead.get('id')}: {e}", exc_info=True)
                                continue
                        
                        self.logger.info(f"✅ Scored {scored_count} new leads")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Lead scoring failed: {e}", exc_info=True)
                        # Don't fail the whole operation if scoring fails
                
                return AgentOutput(status="success", data=result.data, message="Sniper hunt completed.")

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
            # Triggered by Webhooks (Google Ads) or "TEST CALL" button
            elif action == "instant_call":
                lead_id = input_data.params.get("lead_id")
                if not lead_id:
                    return AgentOutput(status="error", message="Missing lead_id for instant call.")
                
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