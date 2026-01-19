import os
import asyncio
import logging
from typing import Dict, Any, List
from twilio.rest import Client
from backend.core.memory import memory  # <--- The Critical Change: Unified DB Access
from backend.core.config import ConfigLoader # <--- To look up client phone numbers

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Apex.TwilioAgent")

class TwilioAgent:
    def __init__(self):
        # 1. Config Loader (To get the boss's phone number per project)
        self.config_loader = ConfigLoader()
        
        # 2. Connect to Twilio
        # Note: In a SaaS, these keys might eventually be per-client (in client_secrets).
        # For MVP, we use the Platform's keys.
        self.twilio_client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def run(self):
        """Main Loop: Background Service that polls for leads."""
        logger.info("Twilio Agent Service Started. Polling for leads...")
        
        while True:
            try:
                await self.process_new_leads()
            except Exception as e:
                logger.error(f"Critical Error in Twilio Loop: {e}")
            
            # Sleep for 10 seconds before next check
            await asyncio.sleep(10)

    async def process_new_leads(self):
        # 1. Fetch leads via Memory Manager (Abstracted DB)
        # We fetch for the default admin user. 
        # In the future, this could iterate through all active users.
        user_id = os.getenv("DEFAULT_USER_ID", "admin@admin.com")
        
        # Fetch ALL leads for this tenant
        leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
        
        # Filter: Leads that are NOT yet notified
        # We do this in Python because metadata JSON filtering varies by DB type
        new_leads = [
            l for l in leads 
            if not l.get("metadata", {}).get("notified", False)
        ]

        if not new_leads:
            return 

        logger.info(f"Found {len(new_leads)} unnotified leads.")

        for lead in new_leads:
            await self.dispatch_sms(lead)

    async def dispatch_sms(self, lead: Dict[str, Any]):
        try:
            # 1. Resolve Target Phone Number (Project Intelligence)
            # This ensures the Plumber gets the Plumber's leads, and Boss gets Boss's leads.
            target_phone = self._get_target_phone(lead)
            
            if not target_phone:
                logger.warning(f"Skipping Lead {lead['id']}: No target phone found.")
                return

            # 2. Format Message based on Source
            meta = lead.get("metadata", {})
            data = meta.get("data", {})
            source = meta.get("source", "Unknown")
            project_id = lead.get("project_id", "General")

            if source == "voice_call":
                # Voice Lead Format
                name = "Voice Caller"
                phone = meta.get("from_number", "Unknown")
                # Use the summary we generated earlier if available
                details = meta.get("summary", f"Recording: {meta.get('recording_url', 'N/A')}")
            else:
                # Web/Tool Lead Format
                name = data.get("fullName") or data.get("name") or "Web Visitor"
                phone = data.get("phoneNumber") or data.get("phone") or "N/A"
                tool_type = meta.get("tool_type", "Form")
                details = f"Action: Submitted {tool_type}"

            body = f"🔥 Apex Alert ({project_id})\nSource: {source}\nName: {name}\nPhone: {phone}\n{details}"
            
            # 3. Send via Twilio
            message = self.twilio_client.messages.create(
                body=body,
                from_=self.from_number,
                to=target_phone
            )
            
            logger.info(f"SMS Sent to {target_phone} (SID: {message.sid})")

            # 4. Update Database (via Memory Manager)
            # Mark as notified so we don't spam them
            new_meta = meta.copy()
            new_meta["notified"] = True
            
            # Memory manager handles the SQL update safely
            memory.update_entity(lead['id'], new_meta)

        except Exception as e:
            logger.error(f"Failed to send SMS for lead {lead['id']}: {e}")

    def _get_target_phone(self, lead: Dict[str, Any]) -> str:
        """
        Determines the correct phone number to text.
        Priority 1: The Client's Phone (from their Project DNA).
        Priority 2: The Fallback/Testing Phone (from .env).
        """
        project_id = lead.get("project_id")
        
        # Try to find the specific client's number first
        if project_id:
            try:
                config = self.config_loader.load(project_id)
                # Look in identity -> contact -> phone
                phone = config.get("identity", {}).get("contact", {}).get("phone")
                if phone and phone.startswith("+"):
                    return phone
            except Exception:
                logger.warning(f"Could not load config for project {project_id}, checking fallback.")

        # Fallback for testing (The "Brother Test")
        return os.getenv("TARGET_PHONE")

if __name__ == "__main__":
    agent = TwilioAgent()
    asyncio.run(agent.run())