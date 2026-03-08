# backend/modules/pseo/agents/media.py
import os
import random
import re
import httpx
import html
from urllib.parse import urlparse
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "YOUR_KEY_HERE")
FALLBACK_IMG = "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b"


def _normalize_query(keyword: str) -> str:
    """Normalize keyword for Unsplash: lowercase, strip, collapse spaces."""
    if not keyword or not isinstance(keyword, str):
        return "professional service"
    s = keyword.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s or "professional service"


def _build_search_queries(
    keyword: str,
    config_template: str = None,
    brand_or_article_hints: list = None,
) -> list:
    """
    Build Unsplash search queries. If config_template is set (non-empty), use it as the first query as-is.
    Otherwise use keyword-based queries with fallbacks.
    """
    queries = []
    template_str = (config_template or "").strip()
    if template_str:
        queries.append(template_str)
    normalized = _normalize_query(keyword)
    if not template_str:
        queries.append(f"{normalized} professional service")
    if brand_or_article_hints:
        hints = [h for h in brand_or_article_hints if isinstance(h, str) and h.strip()]
        if hints:
            combined = f"{normalized} {hints[0].strip().lower()}"
            if combined not in queries:
                queries.append(combined)
    first_word = normalized.split()[0] if normalized else "professional"
    if first_word != "professional":
        fallback = f"{first_word} service"
        if fallback not in queries:
            queries.append(fallback)
    if "professional service" not in queries:
        queries.append("professional service")
    return queries


class MediaAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Media")
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
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

        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        media_ready_drafts = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "ready_for_media"
        ]
        draft_id_param = input_data.params.get("draft_id")
        if draft_id_param:
            media_ready_drafts = [d for d in media_ready_drafts if d.get("id") == draft_id_param]
        if not media_ready_drafts:
            return AgentOutput(status="complete", message="No drafts waiting for images.")

        target_draft = media_ready_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = (
            draft_meta.get("keyword")
            or draft_meta.get("h1_title")
            or (target_draft.get("name") or "").replace("Page: ", "").strip()
        ) or ""

        self.logger.info(f"MEDIA: Finding visuals for '{keyword}' (deterministic Unsplash)")

        # Config-driven query template and optional brand/article hints, fallback URL
        config = self.config or {}
        media_config = config.get("modules", {}).get("local_seo", {}).get("media") or {}
        query_template = media_config.get("unsplash_query_template")
        brand_hints = media_config.get("brand_image_keywords") or media_config.get("article_image_hints") or []
        if isinstance(brand_hints, str):
            brand_hints = [brand_hints] if brand_hints.strip() else []
        fallback_url = (media_config.get("fallback_image_url") or "").strip() or None

        search_queries = _build_search_queries(keyword, query_template, brand_hints)

        image_url = None
        credit_text = ""
        used_query = None
        for q in search_queries:
            # Unsplash API expects + for spaces in URL
            api_query = q.replace(" ", "+")
            found = await self._search_unsplash(api_query)
            if found:
                image_url = found["url"]
                credit_text = f"Photo by {found['photographer']} on Unsplash"
                used_query = q
                self.logger.info(f"Found image for query: {q}")
                break

        if not image_url:
            self.logger.warning("All Unsplash queries returned no result; using fallback image.")
            image_url = fallback_url if fallback_url and self._validate_url(fallback_url) else FALLBACK_IMG
            credit_text = "Unsplash"

        if not self._validate_url(image_url):
            self.logger.warning("Image URL invalid; using fallback.")
            image_url = fallback_url if fallback_url and self._validate_url(fallback_url) else FALLBACK_IMG
            credit_text = "Unsplash"

        img_tag = f"""
            <figure class="main-image">
                <img src="{html.escape(image_url)}" alt="{html.escape(keyword)} - Professional Service" title="{html.escape(keyword)}" loading="lazy" width="800" height="500">
                <figcaption><small>{html.escape(credit_text)}</small></figcaption>
            </figure>
            """
        if "{{image_main_placeholder}}" in html_content:
            html_content = html_content.replace("{{image_main_placeholder}}", img_tag)
        elif "{{image_main}}" in html_content:
            html_content = html_content.replace("{{image_main}}", img_tag)
        else:
            if "</header>" in html_content:
                html_content = html_content.replace("</header>", f"</header>\n{img_tag}", 1)
            else:
                html_content = html_content.replace("</h1>", f"</h1>\n{img_tag}", 1)

        target_draft["metadata"]["content"] = html_content
        target_draft["metadata"]["status"] = "ready_for_utility"
        target_draft["metadata"]["image_added"] = bool(image_url and image_url != FALLBACK_IMG)
        memory.save_entity(Entity(**target_draft), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Added image to '{keyword}'",
            data={
                "draft_id": target_draft["id"],
                "search_queries_used": search_queries,
                "used_query": used_query,
                "next_step": "Ready for Utility",
            },
        )

    async def _search_unsplash(self, query: str):
        try:
            key = self.unsplash_key or UNSPLASH_ACCESS_KEY
            if not key or key == "YOUR_KEY_HERE":
                return None
            url = f"https://api.unsplash.com/search/photos?query={query}&orientation=landscape&per_page=10"
            headers = {"Authorization": f"Client-ID {key}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()
                results = data.get("results") or []
                if results:
                    photo = random.choice(results)
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
