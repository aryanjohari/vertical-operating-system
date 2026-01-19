import os
import asyncio
import logging
from typing import List, Dict, Any
from twilio.rest import Client
from supabase import create_client, Client as SupabaseClient

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Apex.TwilioAgent")

class TwilioAgent:
    def __init__(self):
        # 1. Connect to Supabase
        self.supabase: SupabaseClient = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
        
        # 2. Connect to Twilio
        self.twilio_client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def run(self):
        """Main Loop: Wakes up, checks for leads, sleeps."""
        logger.info("Twilio Agent Started. Polling for leads...")
        
        while True:
            try:
                await self.process_new_leads()
            except Exception as e:
                logger.error(f"Critical Error in Twilio Loop: {e}")
            
            # Sleep for 10 seconds before next check
            await asyncio.sleep(10)

    async def process_new_leads(self):
        # 1. Fetch unnotified leads (Status: 'new' or notified: false)
        # Note: We filter by 'notified' column in metadata or a top-level column if you added one.
        # This query assumes 'metadata->>notified' is 'false' or null.
        response = self.supabase.table("entities") \
            .select("*") \
            .eq("entity_type", "lead") \
            .execute()
            
        leads = [l for l in response.data if not l.get("metadata", {}).get("notified", False)]

        if not leads:
            return # Silence is golden

        logger.info(f"Found {len(leads)} new leads.")

        for lead in leads:
            await self.dispatch_sms(lead)

    async def dispatch_sms(self, lead: Dict[str, Any]):
        try:
            # 1. Identify Target Phone
            # Priority A: Check client_secrets table for this tenant
            # Priority B: Fallback to .env (The "Brother Test")
            target_phone = os.getenv("TARGET_PHONE") 
            
            # (Future: Fetch from DB)
            # secrets = self.supabase.table("client_secrets").select("target_phone").eq("user_id", lead['tenant_id']).execute()
            # if secrets.data: target_phone = secrets.data[0]['target_phone']

            if not target_phone:
                logger.warning(f"No target phone found for lead {lead['id']}")
                return

            # 2. Format Message
            lead_data = lead.get("metadata", {}).get("data", {})
            name = lead_data.get("fullName", "Unknown")
            phone = lead_data.get("phoneNumber", "Unknown")
            source = lead.get("metadata", {}).get("source", "Unknown")
            
            body = f"🔥 Apex Lead Alert!\nSource: {source}\nName: {name}\nPhone: {phone}"
            
            # 3. Send via Twilio
            message = self.twilio_client.messages.create(
                body=body,
                from_=self.from_number,
                to=target_phone
            )
            
            logger.info(f"SMS Sent: {message.sid}")

            # 4. Update Database (Mark as Notified)
            current_metadata = lead.get("metadata", {})
            current_metadata["notified"] = True
            
            self.supabase.table("entities") \
                .update({"metadata": current_metadata}) \
                .eq("id", lead["id"]) \
                .execute()

        except Exception as e:
            logger.error(f"Failed to send SMS for lead {lead['id']}: {e}")

# To run standalone:
if __name__ == "__main__":
    agent = TwilioAgent()
    asyncio.run(agent.run())