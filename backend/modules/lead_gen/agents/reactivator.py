import os
import csv
import logging
import asyncio
from twilio.rest import Client
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class ReactivatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ReactivatorAgent")
        self.logger = logging.getLogger("Apex.Reactivator")
        self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Action: Reads contacts.csv and blasts SMS.
        Params: limit (int) - Max messages to send this run.
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
        
        limit = input_data.params.get("limit", 20) # Safety batch size

        # 1. Use injected config (loaded by kernel)
        config = self.config
        reactivator_config = config.get('modules', {}).get('lead_gen', {}).get('reactivation', {})
        
        if not reactivator_config.get('enabled', False):
            return AgentOutput(status="skipped", message="Reactivation disabled in DNA.")

        offer_text = reactivator_config.get('offer_text')
        if not offer_text:
            return AgentOutput(status="error", message="No offer_text defined in DNA.")

        # 2. Load CSV File
        # Assumes you uploaded a file named 'contacts.csv' to the project folder
        csv_path = f"backend/data/{project_id}/uploads/contacts.csv"
        if not os.path.exists(csv_path):
            return AgentOutput(status="error", message=f"No CSV found at {csv_path}")

        sent_count = 0
        errors = 0

        # 3. Process the List
        try:
            # Read all rows
            rows = []
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Iterate and Send
            updated_rows = []
            for row in rows:
                # Stop if we hit the batch limit
                if sent_count >= limit:
                    updated_rows.append(row) # Keep remaining rows as is
                    continue

                # Check if already contacted
                if row.get('status') == 'sent':
                    updated_rows.append(row)
                    continue

                name = row.get('Name', 'Valued Customer')
                phone = row.get('Phone', '')
                
                if not phone or len(phone) < 8:
                    updated_rows.append(row)
                    continue

                try:
                    # Personalize the message
                    body = offer_text.replace("[Name]", name).replace("[Business Name]", config['identity']['business_name'])
                    
                    # SEND SMS
                    self.client.messages.create(
                        body=body,
                        from_=self.twilio_number,
                        to=phone
                    )
                    
                    row['status'] = 'sent' # Mark as done
                    sent_count += 1
                    self.logger.info(f"📤 Reactivated: {name} ({phone})")
                    
                    # Sleep to prevent rate limiting (1 sec)
                    await asyncio.sleep(1)

                except Exception as e:
                    self.logger.error(f"Failed to text {phone}: {e}", exc_info=True)
                    row['status'] = 'error'
                    errors += 1
                
                updated_rows.append(row)

            # 4. Save Progress (Rewrite CSV)
            # In a real app, use a Database. For MVP, updating CSV is fine.
            keys = rows[0].keys()
            with open(csv_path, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, keys)
                dict_writer.writeheader()
                dict_writer.writerows(updated_rows)

            return AgentOutput(
                status="success", 
                message=f"Campaign Run: Sent {sent_count} messages. Errors: {errors}.",
                data={"sent": sent_count}
            )

        except Exception as e:
            self.logger.error(f"❌ ReactivatorAgent Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))