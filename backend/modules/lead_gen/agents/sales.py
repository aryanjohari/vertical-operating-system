# backend/modules/lead_gen/agents/sales.py
import os
import logging
from twilio.rest import Client
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class SalesAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SalesAgent")
        self.logger = logging.getLogger("Apex.SalesAgent")
        
        # 1. Initialize Twilio
        # These keys come from your .env file
        self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        # 2. Define the URL for the TwiML logic
        # Priority: NGROK_URL (for testing) > NEXT_PUBLIC_API_URL (production) > localhost fallback
        self.api_base_url = (
            os.getenv("NGROK_URL") or 
            os.getenv("NEXT_PUBLIC_API_URL") or 
            "http://localhost:8000"
        )
        self.logger.info(f"Using API base URL: {self.api_base_url}")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Input params:
          - action: "instant_call", "notify_sms"
          - lead_id: The ID of the lead to process
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
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        action = input_data.params.get("action", "instant_call")
        lead_id = input_data.params.get("lead_id")
        
        if not lead_id:
            return AgentOutput(status="error", message="Missing lead_id parameter.")
        
        # 1. Fetch Lead Data (fix: get_entity doesn't exist, use get_entities and filter)
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
        
        # Verify lead belongs to this project
        if lead.get('metadata', {}).get('project_id') != project_id:
            self.logger.warning(f"Lead {lead_id} does not belong to project {project_id}")
            return AgentOutput(status="error", message="Lead not found or access denied.")

        customer_phone = lead.get('primary_contact')
        
        # 2. Use injected config (loaded by kernel)
        config = self.config
        lead_gen_config = config.get('modules', {}).get('lead_gen', {})
        
        # Get the Boss's private mobile
        boss_phone = lead_gen_config.get('sales_bridge', {}).get('destination_phone')
        
        if not boss_phone:
            return AgentOutput(status="error", message="No destination_phone configured in project DNA.")

        try:
            # --- ACTION A: THE SPEED BRIDGE (Call Boss -> Connect Customer) ---
            if action == "instant_call":
                self.logger.info(f"🚀 Bridging: Client ({boss_phone}) <-> Customer ({customer_phone})")
                
                # The Whisper Text (e.g., "New Lead. Press 1")
                whisper = lead_gen_config.get('sales_bridge', {}).get('whisper_text', "Apex Alert. Press 1 to connect.")
                
                # Construct the TwiML URL that handles the "Press 1" logic
                # We encode the target (customer) phone so the router knows who to dial next
                import urllib.parse
                safe_target = urllib.parse.quote(customer_phone)
                action_url = f"{self.api_base_url}/api/voice/connect?target={safe_target}"

                # Construct status callback URL with lead_id and project_id for tracking
                status_callback_url = f"{self.api_base_url}/api/voice/status?lead_id={lead_id}&project_id={project_id}"
                recording_status_callback_url = f"{self.api_base_url}/api/voice/recording-status"

                # Initiate the call to the BOSS with recording and status callbacks enabled
                try:
                    call = self.client.calls.create(
                        to=boss_phone,
                        from_=self.twilio_number,
                        twiml=f"""
                        <Response>
                            <Pause length="1"/>
                            <Say voice="alice">{whisper}</Say>
                            <Gather numDigits="1" action="{action_url}" timeout="10">
                            </Gather>
                            <Say>We did not receive input. Goodbye.</Say>
                        </Response>
                        """,
                        record=True,  # Enable recording
                        recording_status_callback=recording_status_callback_url,
                        recording_status_callback_method='POST',
                        status_callback=status_callback_url,
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],  # Only valid events
                        status_callback_method='POST'
                    )
                    self.logger.info(f"📞 Call initiated: {call.sid} to {boss_phone}")
                except Exception as call_error:
                    self.logger.error(f"❌ Failed to create Twilio call: {call_error}", exc_info=True)
                    raise
                
                # Update DB with call_sid stored for status callback lookup
                self._update_lead_status(lead_id, lead, "calling", call.sid)
                return AgentOutput(status="success", data={"call_sid": call.sid}, message="Bridge call started.")

            # --- ACTION B: SMS NOTIFICATION (Fallback) ---
            elif action == "notify_sms":
                template = lead_gen_config.get('sales_bridge', {}).get('sms_alert_template', "New Lead: [Name]")
                # Simple replacement of variables
                msg_body = template.replace("[Name]", lead['name']).replace("[Source]", lead['metadata'].get('source', 'Web'))
                
                msg = self.client.messages.create(
                    body=msg_body,
                    from_=self.twilio_number,
                    to=boss_phone
                )
                
                self._update_lead_status(lead_id, lead, "notified_sms", msg.sid)
                return AgentOutput(status="success", data={"msg_sid": msg.sid}, message="SMS sent.")

        except Exception as e:
            self.logger.error(f"❌ SalesAgent Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))

    def _update_lead_status(self, lead_id, lead_data, status, ref_id):
        """Update lead status and store call_sid for status callback lookup."""
        new_meta = lead_data['metadata'].copy()
        new_meta['status'] = status
        new_meta['last_action_ref'] = ref_id
        # Store call_sid in metadata for status callback to find this lead
        if ref_id and status == "calling":
            new_meta['call_sid'] = ref_id
            self.logger.debug(f"Stored call_sid {ref_id} in lead {lead_id} metadata")
        memory.update_entity(lead_id, new_meta, self.user_id)