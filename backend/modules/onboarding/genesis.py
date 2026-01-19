import os
import json
import yaml
from dotenv import load_dotenv
from google import genai
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.registry import ModuleManifest
from backend.core.memory import memory  # <--- NEW: Database Connection

load_dotenv()

class OnboardingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Onboarding")
        self.template_path = "backend/core/profile_template.yaml"
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash" # Keeping your requested model

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_message = input_data.params.get("message", "")
        chat_history = input_data.params.get("history", "") 
        niche_id = input_data.params.get("niche", "new_project")
        
        # 1. CAPTURE USER ID (Critical for RLS)
        current_user = input_data.user_id

        # --- CONTEXT DECODING ---
        if "INIT_PHASE_3" in chat_history:
            try:
                pass 
            except Exception:
                pass

        # Load Template
        try:
            with open(self.template_path, 'r') as f:
                template_str = f.read()
        except FileNotFoundError:
            return AgentOutput(status="error", message="Template file missing.", data=None)

        # --- DYNAMIC PROMPT ---
        registry_rules = """
        SYSTEM CONTEXT (APP STORE):
        The user has selected specific modules (visible in the chat history JSON).
        
        1. IF 'local_seo' IS SELECTED:
           - You MUST ensure 'anchor_entities' (Courts, Schools, etc.) are defined.
           - You MUST ensure 'cms_settings' (WordPress URL/User) are filled.
           
        2. IF 'voice_assistant' IS SELECTED:
           - You MUST ensure 'forwarding_number' is filled.
           
        3. IGNORE fields for modules NOT selected. 
        """

        system_prompt = f"""
        You are Genesis, the Apex OS Consultant.
        Your goal: Finalize the YAML Configuration for a new client.
        
        MASTER TEMPLATE:
        ```yaml
        {template_str}
        ```
        
        {registry_rules}
        
        INSTRUCTIONS:
        1. Analyze the CHAT HISTORY. It contains a [JSON SYSTEM EVENT] with Scraped Data and Selected Modules.
        2. AUTO-FILL: Use the scraped data JSON to fill Phone, Email, Name, and Keywords immediately.
        3. STRATEGY CHECK: Look at the selected modules. Ask *only* the specific configuration questions required for those modules.
        4. OUTPUT: Once the critical fields for the selected modules are known, output the YAML.
        
        CHAT HISTORY:
        {chat_history}
        
        USER INPUT:
        {user_message}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=system_prompt
            )
            ai_reply = response.text.strip()
            
        except Exception as e:
            return AgentOutput(status="error", message=f"Gemini API Error: {str(e)}", data=None)

        # 4. PROCESS RESPONSE (Save File & Register DB)
        if "```yaml" in ai_reply:
            try:
                yaml_content = ai_reply.split("```yaml")[1].split("```")[0].strip()
                
                # Save to Disk
                profile_dir = f"data/profiles/{niche_id}"
                os.makedirs(profile_dir, exist_ok=True)
                file_path = os.path.join(profile_dir, "dna.generated.yaml")
                
                with open(file_path, 'w') as f:
                    f.write(yaml_content)
                
                # --- NEW: DB REGISTRATION (The Handshake) ---
                if current_user:
                    try:
                        # Extract niche name for the dashboard label
                        parsed = yaml.safe_load(yaml_content)
                        niche_name = parsed.get('identity', {}).get('business_name', niche_id)
                    except:
                        niche_name = niche_id

                    # Link Project to User
                    memory.register_project(
                        user_id=current_user,
                        project_id=niche_id,
                        niche=niche_name
                    )
                # ---------------------------------------------
                
                return AgentOutput(
                    status="complete", 
                    message="Configuration generated.", 
                    data={"reply": "Configuration saved. System ready.", "path": file_path}
                )
            except Exception as e:
                 return AgentOutput(status="error", message=f"Save Error: {str(e)}", data={"reply": ai_reply})
        else:
            return AgentOutput(
                status="continue", 
                message="Interviewing...", 
                data={"reply": ai_reply}
            )