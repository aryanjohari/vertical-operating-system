# backend/modules/pseo/agents/publisher.py
import json
import re
import base64
import requests
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


def _slugify(text: str) -> str:
    """Lowercase, replace spaces with hyphens, remove non-alphanumeric."""
    if not text:
        return "post"
    s = text.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "post"


class PublisherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Publisher")

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

        # Load Campaign Config (CMS Credentials)
        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        campaign_config = campaign.get("config", {})
        # Support both cms_settings (new) and publisher_settings from DNA (old)
        cms_config = campaign_config.get("cms_settings") or self.config.get("modules", {}).get("local_seo", {}).get("publisher_settings", {})

        try:
            secrets = memory.get_client_secrets(user_id)
        except Exception as e:
            self.logger.error(f"Failed to retrieve WordPress credentials: {e}", exc_info=True)
            return AgentOutput(status="error", message="Credential retrieval failed.")

        wp_url = (cms_config.get("url") or "").strip() or (secrets or {}).get("wp_url") or ""
        wp_user = (cms_config.get("username") or "").strip() or (secrets or {}).get("wp_user") or ""
        wp_password = secrets.get("wp_password") if secrets else None

        if not wp_password:
            return AgentOutput(status="error", message="WordPress password not found. Save it in Settings → WordPress / CMS.")
        if not wp_url or not wp_user:
            return AgentOutput(status="error", message="Missing WordPress URL or username. Set them in Settings → WordPress / CMS (or in campaign cms_settings).")

        # 2. FETCH READY PAGES (campaign-scoped; optional draft_id for row control)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        ready_pages = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "ready_to_publish"
        ]
        draft_id_param = input_data.params.get("draft_id")
        if draft_id_param:
            ready_pages = [d for d in ready_pages if d.get("id") == draft_id_param]
        if not ready_pages:
            return AgentOutput(status="complete", message="No pages ready to publish.")

        limit = input_data.params.get("limit", 2)
        batch = ready_pages[:limit]
        self.logger.info(f"Publishing {len(batch)} pages to {wp_url}...")

        published_count = 0
        errors = []
        for page in batch:
            try:
                success = self._publish_to_wordpress(page, wp_url, wp_user, wp_password)
                if success:
                    meta = page["metadata"].copy()
                    meta["status"] = "published"
                    meta["published_at"] = datetime.now().isoformat()
                    meta["live_url"] = f"{wp_url.rstrip('/')}/{meta.get('slug') or _slugify(meta.get('keyword', ''))}"
                    memory.save_entity(Entity(**{**page, "metadata": meta}), project_id=project_id)
                    published_count += 1
                    self.logger.info(f"Published '{page.get('name')}'")
                else:
                    errors.append(f"Failed {page.get('name')}")
            except Exception as e:
                self.logger.error(f"Publisher fail on '{page.get('name')}': {e}")
                errors.append(f"Failed {page.get('name')}: {e}")

        return AgentOutput(
            status="success" if not errors else "partial",
            message=f"Published {published_count} pages.",
            data={"published": published_count, "errors": errors, "count": published_count},
        )

    def _publish_to_wordpress(self, page: dict, wp_url: str, wp_user: str, wp_password: str) -> bool:
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        creds = base64.b64encode(f"{wp_user}:{wp_password}".encode()).decode()
        meta = page.get("metadata", {})
        title = meta.get("meta_title") or meta.get("title", page.get("name", ""))
        content = meta.get("content", "")
        meta_description = meta.get("meta_description", "")
        schema_raw = meta.get("json_ld_schema")
        keyword = (meta.get("keyword") or meta.get("h1_title") or page.get("name", "") or "").strip()
        slug = meta.get("slug") or _slugify(keyword)

        # Ensure JSON-LD schema is in content (Utility may already have injected it; append if missing)
        if schema_raw:
            try:
                schema_json = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
                schema_block = f"<script type='application/ld+json'>{json.dumps(schema_json, ensure_ascii=False)}</script>"
                if "application/ld+json" not in content:
                    content = content + "\n\n" + schema_block
            except Exception as e:
                self.logger.warning(f"Failed to inject schema: {e}")

        # Rank Math & Yoast meta for SEO (focus keyword = primary keyword for the post)
        focus_keyword = keyword or title[:60]

        post_data = {
            "title": title,
            "content": content,
            "slug": slug,
            "status": "publish",
            "excerpt": meta_description,
            "categories": [1],
            "meta": {
                "_yoast_wpseo_metadesc": meta_description or "",
                "_yoast_wpseo_title": title[:60] if title else "",
                "_yoast_wpseo_focuskw": focus_keyword[:60] if focus_keyword else "",
                "rank_math_description": meta_description or "",
                "rank_math_title": title[:60] if title else "",
                "rank_math_focus_keyword": focus_keyword[:60] if focus_keyword else "",
            },
        }

        try:
            res = requests.post(endpoint, json=post_data, headers={"Authorization": f"Basic {creds}"}, timeout=10)
            if res.status_code in (200, 201):
                return True
            self.logger.error(f"WP Error {res.status_code}: {res.text}")
            return False
        except Exception as e:
            self.logger.error(f"WP Connection Failed: {e}")
            return False
