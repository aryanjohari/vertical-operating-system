# backend/modules/pseo/agents/media.py
import asyncio
import json
import os
import httpx
import html
from urllib.parse import urlparse
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "YOUR_KEY_HERE")
FALLBACK_IMG = "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b"


class MediaAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Media")
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # 1. Titanium Standard: Validate injected context
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        project_id = self.project_id
        user_id = self.user_id
        campaign_id = input_data.params.get("campaign_id") or self.campaign_id

        if not campaign_id:
            return AgentOutput(status="error", message="Campaign ID required")

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        # 2. FETCH WORK ITEM ('ready_for_media')
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        media_ready_drafts = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "ready_for_media"
        ]

        if not media_ready_drafts:
            return AgentOutput(status="complete", message="No drafts waiting for images.")

        target_draft = media_ready_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content (Titanium: content)
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"MEDIA: Finding visuals for '{keyword}'")

        # 3. GENERATE VISUAL SEARCH TERMS (LLM "Director") via llm_gateway
        prompt = f"""
        Act as a Visual Director.
        Topic: "{keyword}"
        Goal: Find a safe, professional, abstract stock photo from Unsplash.

        Rules:
        1. NO text, people's faces, or scary items (like handcuffs/jails).
        2. Focus on: Architecture, Keys, Office settings, Paperwork, Calming interiors.
        3. Return ONLY a JSON list of 3 search queries.

        Example for 'Plumber': ["modern bathroom faucet", "clean copper pipes", "tools on table"]
        """
        search_terms = [keyword]
        try:
            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt="You are a visual director. Return only a JSON array of 3 search query strings.",
                user_prompt=prompt,
                model="gemini-2.5-flash",
                temperature=0.5,
                max_retries=2,
            )
            content = response_text.strip().replace("```json", "").replace("```", "").strip()
            search_terms = json.loads(content)
            if not isinstance(search_terms, list):
                search_terms = [keyword]
        except Exception as e:
            self.logger.warning(f"LLM visual generation failed, using keyword: {e}")

        # 4. SEARCH UNSPLASH (async; non-blocking)
        image_url = None
        credit_text = ""
        for term in search_terms:
            found = await self._search_unsplash(term)
            if found:
                image_url = found["url"]
                credit_text = f"Photo by {found['photographer']} on Unsplash"
                self.logger.info(f"Found image for '{term}'")
                break
        if not image_url:
            self.logger.warning("Specific images failed, trying generic fallback.")
            fallback = await self._search_unsplash("modern office architecture")
            if fallback:
                image_url = fallback["url"]
        if not image_url:
            image_url = FALLBACK_IMG
            credit_text = "Unsplash"
        if not self._validate_url(image_url):
            image_url = FALLBACK_IMG
            credit_text = "Unsplash"

        # 5. INJECT INTO HTML (SEO Optimized)
        img_tag = f"""
            <figure class="main-image">
                <img src="{html.escape(image_url)}" alt="{html.escape(keyword)} - Professional Service" title="{html.escape(keyword)}" loading="lazy" width="800" height="500">
                <figcaption><small>{html.escape(credit_text)}</small></figcaption>
            </figure>
            """
        if "{{image_main}}" in html_content:
            html_content = html_content.replace("{{image_main}}", img_tag)
        else:
            html_content = html_content.replace("</h1>", f"</h1>\n{img_tag}")

        # 6. SAVE & ADVANCE (use "content" per Titanium/DB pattern)
        target_draft["metadata"]["content"] = html_content
        target_draft["metadata"]["status"] = "ready_for_utility"
        target_draft["metadata"]["image_added"] = bool(image_url and image_url != FALLBACK_IMG)
        memory.save_entity(Entity(**target_draft), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Added image to '{keyword}'",
            data={
                "draft_id": target_draft["id"],
                "search_terms_used": search_terms,
                "next_step": "Ready for Utility",
            },
        )

    async def _search_unsplash(self, query: str):
        try:
            key = self.unsplash_key or UNSPLASH_ACCESS_KEY
            if not key or key == "YOUR_KEY_HERE":
                return None
            url = f"https://api.unsplash.com/search/photos?query={query}&orientation=landscape&per_page=1"
            headers = {"Authorization": f"Client-ID {key}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()
                if data.get("results"):
                    photo = data["results"][0]
                    return {"url": photo["urls"]["regular"], "photographer": photo["user"]["name"]}
        except Exception:
            pass
        return None

    def _validate_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return result.scheme in ("http", "https") and bool(result.netloc)
        except Exception:
            return False
