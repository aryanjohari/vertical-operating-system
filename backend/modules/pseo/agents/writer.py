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
from backend.core.config import ConfigLoader

class SeoWriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SEOWriter")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'
        self.config_loader = ConfigLoader()

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. LOAD PROJECT & DNA (The Fix)
        # We find the active project for this user to get the correct phone/voice
        user_project = memory.get_user_project(user_id)
        if not user_project:
            return AgentOutput(status="error", message="No active project found for user.")
        
        project_id = user_project['project_id']
        config = self.config_loader.load(project_id)
        
        # Extract Dynamic Values from DNA
        contact_info = config.get('identity', {}).get('contact', {})
        content_dna = config.get('content_dna', {})
        
        phone = contact_info.get('phone', "")
        website = contact_info.get('website', "")
        voice_tone = content_dna.get('voice_tone', "Professional")
        
        # Synthesize USPs from Pain Points/Solutions if explicit list missing
        solution = content_dna.get('solution_hook', "Immediate Service")
        pain = content_dna.get('pain_point', "Urgent Help")
        usps = f"- {solution}\n- {pain}\n- 24/7 Availability"

        # 2. FETCH ASSETS & DEDUPLICATE (Project Scoped)
        # We pass project_id to ensure we don't mix up clients
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        
        seen_names = set()
        pending_kws = []
        for k in all_kws:
            # Check status and ensure uniqueness
            if k['metadata'].get('status') == 'pending' and k['name'] not in seen_names:
                pending_kws.append(k)
                seen_names.add(k['name'])
        
        if not pending_kws:
            return AgentOutput(status="complete", message="No pending keywords to write.")

        # Batch Size (Increase to 5 for speed)
        batch = pending_kws[:1] 
        written_count = 0
        
        self.logger.info(f"Writing {len(batch)} pages for project '{project_id}'...")

        # 3. SYSTEM INSTRUCTIONS (Injected with DNA Voice)
        system_instruction_text = f"""You are an Expert SEO Copywriter.
        Tone: {voice_tone}
        OBJECTIVE: Write a high-converting, 600-word HTML landing page.
        RULES:
        1. HTML ONLY: <div> body content only. NO <html> tags.
        2. NO MARKDOWN.
        3. STRUCTURE: H1, Intro, USPs (<ul>), Process (<ul>), Service Details, FAQs, CTA.
        4. MENTION: Target Entity & Address 3x.
        """

        for kw_entity in batch:
            try:
                # 4. CONTEXT & LINKS
                keyword = kw_entity['name']
                city = kw_entity['metadata'].get('city', 'Auckland')
                target_anchor_name = kw_entity['metadata'].get('target_anchor', 'Local Office')
                
                # Internal Linking (Same City, Same Project)
                nearby_links_html = ""
                siblings = [k for k in all_kws if k['metadata'].get('city') == city and k['id'] != kw_entity['id']]
                if siblings:
                    links = random.sample(siblings, min(5, len(siblings)))
                    list_items = "".join([f'<li><a href="/{k["id"]}">{k["name"]}</a></li>' for k in links])
                    nearby_links_html = f"<h3>Other Services in {city}</h3><ul>{list_items}</ul>"

                # 5. GENERATE CONTENT
                user_prompt = f"""
                Title: {keyword}
                Target: {target_anchor_name}, {city}
                Phone: {phone}
                Website: {website}
                Key Benefits: {usps}
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
                
                # 6. CLEAN & ASSEMBLE
                raw_html = response.text.strip().replace("```html", "").replace("```", "")
                clean_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', raw_html)
                
                schema = self._generate_schema(kw_entity, phone, project_id)
                full_html = clean_html + "\n" + nearby_links_html + "\n" + schema

                # 7. SAVE PAGE (With Project ID)
                page_id = f"page_{kw_entity['id']}"
                page_entity = Entity(
                    id=page_id,
                    tenant_id=user_id,
                    project_id=project_id, # Link to project
                    entity_type="page_draft",
                    name=keyword,
                    metadata={
                        "keyword_id": kw_entity['id'],
                        "content": full_html,
                        "status": "draft",
                        "city": city,
                        "project_id": project_id
                    },
                    created_at=datetime.now()
                )
                
                if memory.save_entity(page_entity):
                    # Update Keyword
                    updated_kw = Entity(
                        id=kw_entity['id'],
                        tenant_id=user_id,
                        project_id=project_id, # Ensure project link persists
                        entity_type="seo_keyword",
                        name=kw_entity['name'],
                        metadata={
                            **kw_entity['metadata'],
                            "status": "published"
                        },
                        created_at=datetime.now()
                    )
                    memory.save_entity(updated_kw)
                    
                    written_count += 1
                    self.logger.info(f"✅ Published: {keyword}")
                    
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"❌ Failed to write '{keyword}': {e}")
                continue

        return AgentOutput(
            status="success", 
            message=f"Drafted {written_count} pages for project {project_id}.",
            data={"count": written_count}
        )

    def _generate_schema(self, kw_entity, phone, project_id):
        """Generates LocalBusiness Schema JSON-LD"""
        city = kw_entity['metadata'].get('city', 'Auckland')
        anchor = kw_entity['metadata'].get('target_anchor', 'Local Office')
        
        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": f"Services near {anchor}", # Generic name, could be improved with DNA
            "telephone": phone,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": "New Zealand" 
            },
            "areaServed": city,
            "branchCode": project_id # Optional: helps track in data
        }
        return f'<script type="application/ld+json">{json.dumps(schema)}</script>'