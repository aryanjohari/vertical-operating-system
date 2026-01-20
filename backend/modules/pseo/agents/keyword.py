import json
import os
import time
from google import genai
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity

class SeoKeywordAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SEOKeyword")
        self._api_key = os.getenv("GOOGLE_API_KEY")
        self._client = None  # Lazy initialization
        self.model_id = 'gemini-2.5-flash'
    
    @property
    def client(self):
        """Lazy initialization of GenAI client to avoid async httpx errors."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # Get project context
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
        project_id = project['project_id']
        
        # 1. FETCH ANCHORS (scoped to project)
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        if not anchors:
            print("❌ No Anchors found in DB!")
            return AgentOutput(status="error", message="No locations found. Run Scout first.")

        services = self.config.get('content_dna', {}).get('services', ["Bail Support", "Legal Aid"])
        
        # 2. GENERATE ACTUAL KEYWORDS FOR EACH ANCHOR
        generated_count = 0
        print(f"🔄 Processing {len(anchors)} locations...")
        
        for anchor in anchors:
            try:
                anchor_name = anchor['name']
                # Safe City Extraction
                address = anchor['metadata'].get('address', 'Auckland')
                city = address.split(',')[-1].strip() if address else "Auckland"
                
                # Generate actual keywords for this specific anchor
                prompt = f"""
                I am a local SEO expert. Services: {', '.join(services)}.
                
                Generate 5 high-intent SEO keywords for the location: "{anchor_name}" in {city}.
                
                Requirements:
                - Keywords should be specific, searchable phrases (e.g., "Bail Support near {anchor_name}")
                - Include location context naturally
                - Focus on high-intent, conversion-focused phrases
                - Each keyword should be a complete, ready-to-use search term
                
                Return ONLY a JSON array of strings (actual keywords, not templates).
                Example format: ["Bail Support near {anchor_name}", "Emergency Bail Services {city}", ...]
                """
                
                print(f"🧠 Generating keywords for: {anchor_name}...")
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt
                )
                cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
                keywords = json.loads(cleaned_text)
                
                if not isinstance(keywords, list):
                    self.log(f"⚠️ Invalid response format for {anchor_name}, skipping...")
                    continue
                
                print(f"✅ Generated {len(keywords)} keywords for {anchor_name}")
                
                # Save each keyword as an entity
                for kw in keywords:
                    if not kw or not isinstance(kw, str):
                        continue
                    
                    # Generate unique ID
                    safe_id = str(anchor['id'])
                    kw_id = f"kw_{hash(kw + safe_id)}"
                    
                    # Create Entity
                    kw_entity = Entity(
                        id=kw_id,
                        tenant_id=user_id,
                        project_id=project_id,
                        entity_type="seo_keyword",
                        name=kw.strip(),
                        metadata={
                            "target_anchor": anchor_name,
                            "target_id": safe_id,
                            "city": city,
                            "status": "pending"
                        },
                        created_at=datetime.now()
                    )
                    
                    # Explicitly pass project_id for clarity and reliability
                    if memory.save_entity(kw_entity, project_id=project_id):
                        generated_count += 1
                        
            except Exception as e:
                # 🛑 PRINT THE ERROR SO WE SEE IT
                self.log(f"❌ FAILED on {anchor.get('name', 'Unknown')}: {e}")
                print(f"❌ FAILED on {anchor.get('name', 'Unknown')}: {e}")
                continue

        print(f"🏁 Finished. Saved: {generated_count}")
        
        return AgentOutput(
            status="success", 
            message=f"Strategy Executed. Generated {generated_count} keywords.",
            data={"count": generated_count}
        )