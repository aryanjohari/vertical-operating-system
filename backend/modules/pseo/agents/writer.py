# backend/modules/pseo/agents/writer.py
import asyncio
import json
import random
import hashlib
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Writer")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # 1. Titanium Standard: Validate injected context
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")

        project_id = self.project_id
        user_id = self.user_id
        campaign_id = input_data.params.get("campaign_id") or self.campaign_id

        if not campaign_id:
            return AgentOutput(status="error", message="Campaign ID required")

        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        # Load Campaign Config
        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        config = campaign.get("config", {})
        service_focus = config.get("service_focus", "Service")

        # Load Identity / Brand from injected config (DNA)
        brand_voice = self.config.get("brand_brain", {}).get("voice_tone", "Professional, Empathetic")

        # 2. FETCH WORK ITEM (Find a 'pending' keyword)
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        pending_kws = [
            k
            for k in all_kws
            if k.get("metadata", {}).get("campaign_id") == campaign_id
            and k.get("metadata", {}).get("status") == "pending"
            and not k.get("metadata", {}).get("status") == "excluded"
        ]

        if not pending_kws:
            return AgentOutput(status="complete", message="No pending keywords to write.")

        target_kw = pending_kws[0]
        kw_text = target_kw.get("name")
        kw_meta = target_kw.get("metadata", {})
        self.logger.info(f"WRITER: Drafting page for '{kw_text}'")

        # 3. GATHER INTELLIGENCE (Anti-Hallucination Data)
        anchor_data = None
        anchor_ref_id = kw_meta.get("anchor_reference")
        if anchor_ref_id:
            anchor_entity = memory.get_entity(anchor_ref_id, user_id)
            if anchor_entity:
                anchor_data = {
                    "name": anchor_entity.name,
                    "address": anchor_entity.metadata.get("address"),
                    "phone": anchor_entity.metadata.get("primary_contact"),
                }

        # Query ChromaDB for semantically relevant knowledge fragments (RAG)
        # This finds fragments most relevant to the keyword being written
        vector_fragments = memory.query_context(
            tenant_id=user_id,
            query=kw_text,  # Use keyword as semantic search query
            n_results=5,  # Get top 5 most relevant fragments
            project_id=project_id,
            campaign_id=campaign_id,
            return_metadata=True  # Get metadata with text
        )
        
        # Also get from SQL DB as fallback/backup
        all_intel = memory.get_entities(tenant_id=user_id, entity_type="knowledge_fragment", project_id=project_id)
        campaign_intel = [i for i in all_intel if i.get("metadata", {}).get("campaign_id") == campaign_id]
        
        # Combine vector results with SQL results, prioritizing vector (semantic) matches
        intel_list = []
        
        # Add vector DB results first (most relevant)
        for frag in vector_fragments:
            frag_meta = frag.get("metadata", {})
            intel_list.append({
                "name": frag_meta.get("title", ""),
                "url": frag_meta.get("url", ""),
                "snippet": frag.get("text", ""),  # Use full text from vector DB
                "type": frag_meta.get("fragment_type", "fact")
            })
        
        # Add SQL DB results if we need more (up to 4 total)
        sql_added = 0
        for sql_frag in campaign_intel:
            if sql_added >= max(0, 4 - len(intel_list)):
                break
            # Skip if already in vector results (by URL)
            sql_url = sql_frag.get("metadata", {}).get("url", "")
            if not any(f.get("url") == sql_url for f in intel_list):
                intel_list.append({
                    "name": sql_frag.get("name", ""),
                    "url": sql_url,
                    "snippet": sql_frag.get("metadata", {}).get("snippet", ""),
                    "type": sql_frag.get("metadata", {}).get("type", "fact")
                })
                sql_added += 1
        
        # Limit to 4 fragments total
        selected_intel = intel_list[:4]
        
        # Build context string for prompt
        intel_context = "\n".join([
            f"- {frag.get('type', 'fact').upper()}: {frag.get('name', 'Unknown')} (Source: {frag.get('url', 'N/A')})\n  {frag.get('snippet', '')[:200]}"
            for frag in selected_intel
        ])
        
        if not intel_context:
            intel_context = "No specific knowledge fragments available. Use general best practices."
            self.logger.warning(f"No knowledge fragments found for keyword '{kw_text}' in campaign {campaign_id}")

        # 4. CONSTRUCT THE PROMPT
        prompt = f"""
        ACT AS: Senior Content Writer & SEO Specialist for '{service_focus}' services.
        TONE: {brand_voice}.
        GOAL: Write a high-converting, local service page + SEO Metadata.

        --- INPUT DATA (USE THIS, DO NOT INVENT) ---
        KEYWORD: "{kw_text}"
        INTENT: {kw_meta.get('intent')}

        LOCAL ANCHOR CONTEXT (Crucial):
        {f"User is near: {anchor_data['name']} at {anchor_data['address']}." if anchor_data else "User is searching city-wide."}

        KNOWLEDGE BANK (CITE THESE):
        {intel_context}

        --- STRUCTURE & REQUIREMENTS ---
        1. **HTML Content:** - H1 tag must include the Keyword.
           - Direct hook answering the pain point.
           - *Local Paragraph:* Explain we are "minutes away from {anchor_data['name'] if anchor_data else 'central locations'}".
           - *Regulatory Reality:* Use KNOWLEDGE BANK to explain rules/costs.
           - Placeholders: Insert {{{{image_main}}}} after H1, {{{{form_capture}}}} at end.
           - FORMAT: Pure HTML body tags (<p>, <h2>, <ul>). NO <html> or <body> tags.

        2. **HARD FACTS (Anti-Hallucination — CRITICAL):**
           Search the KNOWLEDGE BANK snippets ONLY for these "Hard Facts":
           - **Costs/Fees:** dollar amounts, filing fees, callout fees, price ranges (e.g. "$150", "from $X").
           - **Processing Times:** durations, deadlines (e.g. "5–7 days", "within 24 hours").
           - **Required Documents:** lists of forms, IDs, certificates (e.g. "proof of address, ID").
           - **Opening Hours:** business/court hours (e.g. "Mon–Fri 9–5", "24/7").
           **IF you find one or more such facts** (explicitly stated in the snippets):
           - You MUST add a structured HTML block *inside* the body (e.g. after the regulatory paragraph).
           - Use either <div class="fact-box"> with an inner <table>, or <table class="fact-box">.
           - Include one row per fact (e.g. "Filing fee" | "$X", "Processing" | "Y days", "Documents required" | "A, B, C").
           - Add a brief caption/source if the snippet mentions it (e.g. "Source: [name]").
           **IF you find NO such facts** in the KNOWLEDGE BANK:
           - Do NOT add any fact-box or table. Do NOT guess, estimate, or invent prices or figures.
           - Omit the block entirely. Never hallucinate data.

        3. **Meta Data:**
           - Meta Title: Catchy, includes keyword, max 60 chars.
           - Meta Description: Persuasive ad copy, includes keyword, max 160 chars.

        --- OUTPUT FORMAT (STRICT JSON) ---
        Return ONLY a JSON object with these keys:
        {{
            "html_content": "...",
            "meta_title": "...",
            "meta_description": "..."
        }}
        """

        # 5. GENERATE & PARSE (use llm_gateway via asyncio.to_thread)
        try:
            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt="You are a content writer. Return only valid JSON with keys html_content, meta_title, meta_description. Never invent costs, fees, processing times, documents, or opening hours—only use facts explicitly present in the provided KNOWLEDGE BANK; if none exist, omit any fact-box/table.",
                user_prompt=prompt,
                model="gemini-2.5-flash",
                temperature=0.7,
                max_retries=2,
            )
            content_str = response_text.strip()
            if "```json" in content_str:
                content_str = content_str.split("```json")[1].split("```")[0]
            elif "```" in content_str:
                content_str = content_str.split("```")[1]
            content_str = content_str.strip()

            result = json.loads(content_str)
            html_content = result.get("html_content", "")
            meta_title = result.get("meta_title", "")
            meta_description = result.get("meta_description", "")
        except Exception as e:
            self.logger.error(f"Writer Generation Failed: {e}")
            return AgentOutput(status="error", message=f"Failed to generate valid JSON content: {e}")

        # 6. SAVE DRAFT (use "content" and "draft" per Titanium/DB pattern)
        page_id = hashlib.md5(kw_text.encode()).hexdigest()[:16]
        draft = Entity(
            id=f"page_{page_id}",
            tenant_id=user_id,
            project_id=project_id,
            entity_type="page_draft",
            name=f"Page: {kw_text}",
            metadata={
                "campaign_id": campaign_id,
                "keyword_id": target_kw.get("id"),
                "keyword": kw_text,
                "status": "draft",
                "content": html_content,
                "meta_title": meta_title,
                "meta_description": meta_description,
                "anchor_used": anchor_data["name"] if anchor_data else None,
                "version": 1,
            },
        )
        memory.save_entity(draft, project_id=project_id)

        # 7. UPDATE KEYWORD STATUS
        target_kw["metadata"]["status"] = "drafted"
        memory.save_entity(Entity(**target_kw), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Drafted page '{kw_text}' with SEO metadata",
            data={
                "page_id": f"page_{page_id}",
                "keyword": kw_text,
                "meta_title": meta_title,
                "next_step": "Ready for Critic",
            },
        )
