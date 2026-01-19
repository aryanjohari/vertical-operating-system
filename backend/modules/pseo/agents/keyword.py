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
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. FETCH ANCHORS
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location")
        if not anchors:
            print("❌ No Anchors found in DB!")
            return AgentOutput(status="error", message="No locations found. Run Scout first.")

        services = self.config.get('content_dna', {}).get('services', ["Bail Support", "Legal Aid"])
        
        # 2. GENERATE TEMPLATES
        prompt = f"""
        I am a local SEO expert. Services: {', '.join(services)}.
        Generate 5 high-intent "Keyword Templates" with python placeholders {{name}} and {{city}}.
        Return ONLY a JSON array of strings.
        """
        
        templates = []
        try:
            print("🧠 Generating Keyword Formulas...")
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
            templates = json.loads(cleaned_text)
            print(f"✅ Formulas Acquired: {templates}")
        except Exception as e:
            return AgentOutput(status="error", message=f"AI Template Gen Failed: {e}")

        # 3. APPLY FORMULAS LOCALLY
        generated_count = 0
        print(f"🔄 Processing {len(anchors)} locations...") # DEBUG LOG

        for anchor in anchors:
            try:
                name = anchor['name']
                # Safe City Extraction
                address = anchor['metadata'].get('address', 'Auckland')
                city = address.split(',')[-1].strip() if address else "Auckland"
                
                for temp in templates:
                    # Fill the blanks
                    kw = temp.format(name=name, city=city)
                    
                    # SAFER ID GENERATION (Convert to string first)
                    safe_id = str(anchor['id'])
                    kw_id = f"kw_{hash(kw + safe_id)}"
                    
                    # Create Entity
                    kw_entity = Entity(
                        id=kw_id,
                        tenant_id=user_id,
                        entity_type="seo_keyword",
                        name=kw,
                        metadata={
                            "target_anchor": anchor['name'],
                            "target_id": safe_id,
                            "city": city,
                            "status": "pending"
                        },
                        created_at=datetime.now()
                    )
                    
                    if memory.save_entity(kw_entity):
                        generated_count += 1
                        
            except Exception as e:
                # 🛑 PRINT THE ERROR SO WE SEE IT
                print(f"❌ FAILED on {anchor.get('name', 'Unknown')}: {e}")
                continue

        print(f"🏁 Finished. Saved: {generated_count}")
        
        return AgentOutput(
            status="success", 
            message=f"Strategy Executed. Generated {generated_count} keywords.",
            data={"count": generated_count}
        )