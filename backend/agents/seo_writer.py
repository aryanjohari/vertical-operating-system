import os
import json
import re
import time
import random
from datetime import datetime
from google import genai
from google.genai import types
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity

class SeoWriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SEOWriter")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. FETCH ASSETS & DEDUPLICATE
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword")
        
        # Filter: Pending AND Unique Names only
        seen_names = set()
        pending_kws = []
        for k in all_kws:
            if k['metadata'].get('status') == 'pending' and k['name'] not in seen_names:
                pending_kws.append(k)
                seen_names.add(k['name'])
        
        if not pending_kws:
            return AgentOutput(status="complete", message="No pending keywords to write.")

        # PROD MODE: Change to [:5] or [:10] to write more at once
        batch = pending_kws[:1] 
        written_count = 0
        
        print(f"✍️ Writing {len(batch)} unique page(s)...")

        # 2. SYSTEM INSTRUCTIONS
        system_instruction_text = """You are an Expert SEO Copywriter.
        OBJECTIVE: Write a high-converting, 600-word HTML landing page.
        RULES:
        1. HTML ONLY: <div> body content only. NO <html> tags.
        2. NO MARKDOWN.
        3. STRUCTURE: H1, Intro, USPs (<ul>), Process (<ul>), Service Details, FAQs, CTA.
        4. MENTION: Target Entity & Address 3x.
        """

        for kw_entity in batch:
            try:
                # 3. CONTEXT & LINKS
                keyword = kw_entity['name']
                city = kw_entity['metadata'].get('city', 'Auckland')
                target_anchor_name = kw_entity['metadata'].get('target_anchor', 'Local Office')
                
                # DNA (Hardcoded for MVP)
                phone = "0800-LEG-AID"
                usps = "- 24/7 Availability\n- No Win No Fee\n- Local Experts"
                
                # --- MINI-LIBRARIAN: FIND NEARBY LINKS ---
                nearby_links_html = ""
                # Find siblings in the same city
                siblings = [k for k in all_kws if k['metadata'].get('city') == city and k['id'] != kw_entity['id']]
                if siblings:
                    # Pick 5 random neighbors to link to
                    links = random.sample(siblings, min(5, len(siblings)))
                    list_items = "".join([f'<li><a href="/{k["id"]}">{k["name"]}</a></li>' for k in links])
                    nearby_links_html = f"<h3>Other Services in {city}</h3><ul>{list_items}</ul>"
                # ------------------------------------------

                # 4. GENERATE CONTENT
                user_prompt = f"""
                Title: {keyword}
                Target: {target_anchor_name}, {city}
                Phone: {phone}
                USPs: {usps}
                Instruction: Write the HTML body.
                """
                
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]),
                    config=types.GenerateContentConfig(
                        system_instruction=[types.Part.from_text(text=system_instruction_text)],
                        temperature=0.7
                    )
                )
                
                # 5. CLEAN & ASSEMBLE
                raw_html = response.text.strip().replace("```html", "").replace("```", "")
                clean_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', raw_html)
                
                # Inject Schema & Links
                schema = self._generate_schema(kw_entity, phone)
                full_html = clean_html + "\n" + nearby_links_html + "\n" + schema

                # 6. SAVE PAGE
                page_id = f"page_{kw_entity['id']}"
                page_entity = Entity(
                    id=page_id,
                    tenant_id=user_id,
                    entity_type="page_draft",
                    name=keyword,
                    metadata={
                        "keyword_id": kw_entity['id'],
                        "content": full_html,
                        "status": "draft",
                        "city": city
                    },
                    created_at=datetime.now()
                )
                
                if memory.save_entity(page_entity):
                    # --- 7. UPDATE KEYWORD STATUS ---
                    # We must recreate the Entity object to save it back
                    updated_kw = Entity(
                        id=kw_entity['id'],
                        tenant_id=user_id,
                        entity_type="seo_keyword",
                        name=kw_entity['name'],
                        metadata={
                            **kw_entity['metadata'], # Keep existing metadata
                            "status": "published"    # Update status
                        },
                        created_at=datetime.now() # Update timestamp or keep original if avail
                    )
                    memory.save_entity(updated_kw)
                    
                    written_count += 1
                    print(f"✅ Published & Linked: {keyword}")
                    
                time.sleep(1) # Respect limits
                
            except Exception as e:
                print(f"❌ Failed to write '{keyword}': {e}")
                continue

        return AgentOutput(
            status="success", 
            message=f"Drafted {written_count} pages with internal links.",
            data={"count": written_count}
        )

    def _generate_schema(self, kw_entity, phone):
        """Generates LocalBusiness Schema JSON-LD"""
        city = kw_entity['metadata'].get('city', 'Auckland')
        anchor = kw_entity['metadata'].get('target_anchor', 'Local Office')
        
        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": f"Legal Services near {anchor}",
            "telephone": phone,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": "New Zealand" 
            },
            "areaServed": city
        }
        return f'<script type="application/ld+json">{json.dumps(schema)}</script>'