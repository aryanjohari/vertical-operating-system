# backend/modules/pseo/agents/writer.py
import os
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
        self._api_key = os.getenv("GOOGLE_API_KEY")
        self._client = None
        self.config_loader = ConfigLoader()

    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        project = memory.get_user_project(user_id)
        if not project: return AgentOutput(status="error", message="No project.")
        
        # Load Config
        config = self.config_loader.load(project['project_id'])
        contact = config['identity']['contact']
        phone_number = contact.get('phone', '')
        
        # 1. FETCH PENDING KEYWORDS
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project['project_id'])
        # Sort by cluster so we write related topics in batches (helps caching)
        pending = sorted(
            [k for k in all_kws if k['metadata'].get('status') == 'pending'],
            key=lambda x: x['metadata'].get('cluster', '')
        )
        
        if not pending: return AgentOutput(status="complete", message="No pending keywords.")
        
        target_kw = pending[0]
        
        # Retrieve map_embed_url from anchor_location metadata
        anchor_name = target_kw['metadata'].get('target_anchor', '')
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project['project_id'])
        matching_anchor = [a for a in anchors if a['name'] == anchor_name]
        map_embed_url = matching_anchor[0]['metadata'].get('map_embed_url', '') if matching_anchor else ''
        
        # 2. RAG RETRIEVAL (The Brain)
        # We query the vector DB for specific wisdom related to this keyword
        rag_hits = memory.query_context(tenant_id=user_id, query=target_kw['name'], project_id=project['project_id'])
        client_wisdom = rag_hits if rag_hits else "Focus on trust, speed, and reliability."

        # 3. GENERATE SLUG (SEO Friendly)
        # "Bail Support near Mt Eden Prison" -> "bail-support-mt-eden-prison"
        slug = target_kw['name'].lower().replace(' ', '-').replace('near', '').replace('--', '-')
        
        # 4. WRITE CONTENT
        # We removed the 'Internal Linking' block. The Librarian Agent does that later.
        system_prompt = f"""
        Role: Expert Copywriter for {config['identity']['business_name']}.
        Voice: {config['brand_brain'].get('voice_tone', 'Professional')}
        
        Context (Client Wisdom):
        {client_wisdom}
        
        Forbidden Topics: {config['brand_brain'].get('forbidden_topics', [])}
        
        Task: Write a 600-word HTML Article (Body Only).
        Structure:
        1. <h1>Title containing the Keyword</h1>
        2. <strong>Introduction:</strong> Empathize with the urgency.
        3. <strong>The Problem:</strong> Why specific local factors (near {target_kw['metadata']['target_anchor']}) matter.
        4. <strong>The Solution:</strong> How we help.
        5. <strong>FAQ Section:</strong> 3 relevant questions.
        6. <strong>CTA:</strong> Call {phone_number} immediately.
        
        Important: Include the phone number {phone_number} in the CTA section.
        If map_embed_url is provided ({map_embed_url}), you may reference the location map.
        
        Format: HTML only. No Markdown blocks. Use <h2> and <h3> tags.
        """
        
        user_prompt = f"""
        Target Keyword: {target_kw['name']}
        Location Context: {target_kw['metadata']['city']}
        Target Anchor: {target_kw['metadata']['target_anchor']}
        """

        # 4. GENERATE CONTENT WITH VALIDATION AND RETRY
        max_retries = 3
        min_content_length = 500  # Minimum characters for valid content
        content = None
        
        for attempt in range(max_retries):
            try:
                self.log(f"Generating content (attempt {attempt + 1}/{max_retries}) for: {target_kw['name']}")
                
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash-lite',
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.7
                    )
                )
                content = response.text.replace("```html", "").replace("```", "").strip()
                
                # Validate content
                if not content:
                    self.log(f"❌ Empty content on attempt {attempt + 1}")
                    continue
                
                # Check minimum length (rough word count estimate)
                if len(content) < min_content_length:
                    self.log(f"❌ Content too short ({len(content)} chars) on attempt {attempt + 1}, minimum: {min_content_length}")
                    continue
                
                # Check for HTML structure (should have h1 or h2 tags)
                if '<h1' not in content.lower() and '<h2' not in content.lower():
                    self.log(f"❌ Missing HTML structure (no h1/h2 tags) on attempt {attempt + 1}")
                    continue
                
                # Content is valid
                self.log(f"✅ Generated valid content ({len(content)} chars)")
                break
                
            except Exception as e:
                self.log(f"❌ Generation error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return AgentOutput(
                        status="error", 
                        message=f"Writing Failed after {max_retries} attempts: {str(e)}"
                    )
                continue
        
        # Final validation check
        if not content or len(content) < min_content_length:
            return AgentOutput(
                status="error",
                message=f"Generated content is too short or empty (length: {len(content) if content else 0}, minimum: {min_content_length}). Failed after {max_retries} attempts."
            )
        
        # 5. SAVE DRAFT
        page_id = f"page_{target_kw['id']}" # Stable ID linking back to keyword
        
        page = Entity(
            id=page_id,
            tenant_id=user_id,
            project_id=project['project_id'],
            entity_type="page_draft",
            name=target_kw['name'],
            metadata={
                "content": content,
                "slug": slug,          # Save the slug for the Librarian/Publisher
                "status": "draft",     # Hand off to Critic
                "city": target_kw['metadata']['city'],
                "cluster": target_kw['metadata'].get('cluster'), # Keep cluster for Librarian
                "keyword_id": target_kw['id'],
                "quality_score": 0
            },
            created_at=datetime.now()
        )
        # Explicitly pass project_id for clarity and reliability
        memory.save_entity(page, project_id=project['project_id'])
        
        # Update Keyword to 'drafted'
        memory.update_entity(target_kw['id'], {"status": "drafted"})
        
        return AgentOutput(status="success", message=f"Drafted: {target_kw['name']}")