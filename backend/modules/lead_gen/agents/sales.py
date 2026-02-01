# backend/modules/lead_gen/agents/sales.py
import asyncio
import os
import urllib.parse
import logging
from twilio.rest import Client
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory


class SalesAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SalesAgent")

        self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.api_base_url = (
            os.getenv("NGROK_URL")
            or os.getenv("NEXT_PUBLIC_API_URL")
            or "http://localhost:8000"
        )
        self.logger.info(f"Using API base URL: {self.api_base_url}")

    def _get_lead_gen_config(self):
        """Resolve lead gen config (dual-path: lead_gen_integration or modules.lead_gen)."""
        config = self.config or {}
        lg = config.get("modules", {}).get("lead_gen", {})
        bridge = lg.get("sales_bridge", {})
        integration = config.get("lead_gen_integration", {})
        return {
            "destination_phone": integration.get("destination_phone") or bridge.get("destination_phone"),
            "whisper_text": bridge.get("whisper_text", "Apex Alert. Press 1 to connect."),
            "sms_alert_template": bridge.get("sms_alert_template", "New Lead: [Name]"),
        }

    def _update_lead_status(self, lead_id, lead_data, status, ref_id):
        """Update lead status and store call_sid for status callback lookup."""
        new_meta = lead_data["metadata"].copy()
        new_meta["status"] = status
        new_meta["last_action_ref"] = ref_id
        if ref_id and status == "calling":
            new_meta["call_sid"] = ref_id
            self.logger.debug(f"Stored call_sid {ref_id} in lead {lead_id} metadata")
        memory.update_entity(lead_id, new_meta, self.user_id)

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Input params:
          - action: "instant_call", "notify_sms"
          - lead_id: The ID of the lead to process
        """
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")

        project_id = self.project_id
        user_id = self.user_id
        action = input_data.params.get("action", "instant_call")
        lead_id = input_data.params.get("lead_id")

        if not lead_id:
            return AgentOutput(status="error", message="Missing lead_id parameter.")

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        all_leads = memory.get_entities(
            tenant_id=user_id,
            entity_type="lead",
            project_id=project_id,
            limit=1000,
        )
        lead = next((l for l in all_leads if l.get("id") == lead_id), None)
        if not lead:
            return AgentOutput(status="error", message=f"Lead {lead_id} not found.")

        if lead.get("metadata", {}).get("project_id") != project_id:
            self.logger.warning(f"Lead {lead_id} does not belong to project {project_id}")
            return AgentOutput(status="error", message="Lead not found or access denied.")

        customer_phone = lead.get("primary_contact", "")
        lg_config = self._get_lead_gen_config()
        boss_phone = lg_config["destination_phone"]

        if not boss_phone or boss_phone == "REQUIRED":
            return AgentOutput(status="error", message="No destination_phone configured in project DNA.")

        try:
            if action == "instant_call":
                self.logger.info(f"Bridging: Client ({boss_phone}) <-> Customer ({customer_phone})")
                whisper = lg_config["whisper_text"]
                safe_target = urllib.parse.quote(customer_phone)
                action_url = f"{self.api_base_url}/api/voice/connect?target={safe_target}"
                status_callback_url = f"{self.api_base_url}/api/voice/status?lead_id={lead_id}&project_id={project_id}"
                recording_status_callback_url = f"{self.api_base_url}/api/voice/recording-status"

                twiml = f"""
                <Response>
                    <Pause length="1"/>
                    <Say voice="alice">{whisper}</Say>
                    <Gather numDigits="1" action="{action_url}" timeout="10">
                    </Gather>
                    <Say>We did not receive input. Goodbye.</Say>
                </Response>
                """

                call = await asyncio.to_thread(
                    self.client.calls.create,
                    to=boss_phone,
                    from_=self.twilio_number,
                    twiml=twiml,
                    record=True,
                    recording_status_callback=recording_status_callback_url,
                    recording_status_callback_method="POST",
                    status_callback=status_callback_url,
                    status_callback_event=["initiated", "ringing", "answered", "completed"],
                    status_callback_method="POST",
                )
                self.logger.info(f"Call initiated: {call.sid} to {boss_phone}")

                self._update_lead_status(lead_id, lead, "calling", call.sid)
                return AgentOutput(status="success", data={"call_sid": call.sid}, message="Bridge call started.")

            elif action == "notify_sms":
                template = lg_config["sms_alert_template"]
                msg_body = template.replace("[Name]", lead.get("name", "")).replace(
                    "[Source]", lead.get("metadata", {}).get("source", "Web")
                )

                msg = await asyncio.to_thread(
                    self.client.messages.create,
                    body=msg_body,
                    from_=self.twilio_number,
                    to=boss_phone,
                )

                self._update_lead_status(lead_id, lead, "notified_sms", msg.sid)
                return AgentOutput(status="success", data={"msg_sid": msg.sid}, message="SMS sent.")

            else:
                return AgentOutput(status="error", message=f"Unknown action: {action}")

        except Exception as e:
            self.logger.error(f"SalesAgent Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))
