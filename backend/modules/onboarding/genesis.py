# backend/modules/onboarding/genesis.py
import os
import json
import yaml
from dotenv import load_dotenv
from google import genai
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.universal import UniversalScraper

load_dotenv()

class OnboardingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Onboarding")
        self.template_path = "backend/core/profile_template.yaml"
        self._client = None  # Lazy initialization
        self.model = "gemini-2.5-flash"
    
    @property
    def client(self):
        """Lazy initialization of GenAI client to avoid async httpx errors."""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        State Machine Routing:
        Step 1: 'analyze' -> Scrape URL & Extract Identity
        Step 2: 'interview_start' -> Generate Questions based on Modules
        Step 3: 'interview_loop' -> Chat until Wisdom is extracted
        """
        step = input_data.params.get("step", "analyze")
        
        if step == "analyze":
            return await self._phase_1_analyze(input_data)
        elif step == "interview_start":
            return await self._phase_2_start(input_data)
        elif step == "interview_loop":
            return await self._phase_3_loop(input_data)
        else:
            return AgentOutput(status="error", message=f"Unknown step: {step}")

    # --- PHASE 1: THE COLD READ ---
    async def _phase_1_analyze(self, packet):
        url = packet.params.get("url")
        if not url:
            return AgentOutput(status="error", message="URL required for analysis.")

        # 1. Scrape the Site
        self.log(f"Scraping {url}...")
        scraper = UniversalScraper()
        raw_data = await scraper.scrape(url) # You need to implement/use your service here
        
        # 2. AI Extraction
        prompt = f"""
        Analyze this raw website text. Extract the Core Identity.
        JSON Output ONLY.
        Keys: business_name, niche (2-3 words), phone, email, address, key_services (list).
        
        TEXT:
        {raw_data.get('content', '')[:10000]}
        """
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        try:
            # Clean generic markdown
            json_str = response.text.replace("```json", "").replace("```", "").strip()
            identity_data = json.loads(json_str)
            identity_data['website'] = url
            
            return AgentOutput(
                status="success",
                message="Analysis Complete",
                data={"identity": identity_data} # Send back to UI for User Confirmation
            )
        except:
            return AgentOutput(status="error", message="Failed to extract identity.")

    # --- PHASE 2: THE STRATEGY SELECTOR ---
    async def _phase_2_start(self, packet):
        """
        Input: Confirmed Identity + Selected Modules List
        Output: The "First Question" to start the Deep Dive.
        """
        identity = packet.params.get("identity", {})
        modules = packet.params.get("modules", []) # e.g. ['local_seo', 'lead_gen']
        
        # Build the "Wisdom Agenda"
        agenda = []
        if "local_seo" in modules:
            agenda.append("I need to know your 'Anchor Locations' (e.g. Courts, Suppliers).")
            agenda.append("What is a common mistake your customers make that you fix?")
        if "lead_gen" in modules:
            agenda.append("Do you have a specific phone number for forwarding calls?")
            
        start_msg = (
            f"Great. I've set up the project for **{identity.get('business_name')}**.\n\n"
            f"To activate the **{', '.join(modules)}** modules, I need to extract some expert knowledge.\n\n"
            f"First: {agenda[0] if agenda else 'Tell me about your business.'}"
        )
        
        return AgentOutput(
            status="continue",
            message="Starting Interview",
            data={"reply": start_msg, "context": {"modules": modules, "identity": identity}}
        )

    # --- PHASE 3: THE DEEP DIVE (Chat Loop) ---
    async def _phase_3_loop(self, packet):
        history = packet.params.get("history", [])
        user_msg = packet.params.get("message", "")
        context = packet.params.get("context", {}) # Passed back and forth
        
        # Load Template
        with open(self.template_path, 'r') as f:
            template = f.read()

        prompt = f"""
        ROLE: You are Genesis, the Apex Consultant.
        GOAL: Fill the YAML Template based on the User's inputs.
        
        CONTEXT:
        - Business: {context.get('identity')}
        - Modules Active: {context.get('modules')}
        
        TEMPLATE TO FILL:
        {template}
        
        INSTRUCTIONS:
        1. Check if we have enough info to fill the 'identity', 'brand_brain', and ACTIVE 'modules'.
        2. IF MISSING INFO: Ask the next logical question. Focus on "Expert Nuggets" (insider tips, specific guarantees).
        3. IF COMPLETE: Output the full VALID YAML inside ```yaml``` tags.
        
        CHAT HISTORY:
        {history}
        """
        
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        reply = response.text
        
        if "```yaml" in reply:
            # We are done. Save and Register.
            yaml_content = reply.split("```yaml")[1].split("```")[0].strip()
            project_id = context.get('identity', {}).get('project_id', 'new_project')
            self._save_profile(project_id, yaml_content, packet.user_id)
            
            return AgentOutput(
                status="complete",
                message="Profile Generated",
                data={"reply": "Configuration saved. System ready.", "path": f"data/profiles/{project_id}"}
            )
        else:
            return AgentOutput(
                status="continue",
                message="Interviewing",
                data={"reply": reply, "context": context}
            )

    def _save_profile(self, project_id, content, user_id):
        # 1. Save File to Disk (as before)
        path = f"data/profiles/{project_id}"
        os.makedirs(path, exist_ok=True)
        with open(f"{path}/dna.generated.yaml", "w") as f:
            f.write(content)
        
        # 2. Register in SQLite (as before)
        parsed = yaml.safe_load(content)
        niche = parsed.get('identity', {}).get('niche', 'General')
        memory.register_project(user_id, project_id, niche)

        # --- 3. THE MISSING RAG INJECTION ---
        # We must feed the "Brand Brain" into ChromaDB so the Writer can find it.
        brand_brain = parsed.get('brand_brain', {})
        
        # A. Index Knowledge Nuggets
        nuggets = brand_brain.get('knowledge_nuggets', [])
        for nugget in nuggets:
            memory.save_context(
                tenant_id=user_id,
                text=nugget,
                metadata={"type": "wisdom", "source": "onboarding"},
                project_id=project_id
            )

        # B. Index Insider Tips
        tips = brand_brain.get('insider_tips', [])
        for tip in tips:
            memory.save_context(
                tenant_id=user_id,
                text=f"Insider Tip: {tip}",
                metadata={"type": "tip", "source": "onboarding"},
                project_id=project_id
            )
            
        self.log(f"🧠 Injected {len(nuggets) + len(tips)} wisdom nuggets into RAG Memory.")