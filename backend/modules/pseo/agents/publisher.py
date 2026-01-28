# backend/modules/pseo/agents/publisher.py
import json
import base64
import requests
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


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

        wp_url = cms_config.get("url")
        wp_user = cms_config.get("username")
        try:
            secrets = memory.get_client_secrets(user_id)
            wp_password = secrets.get("wp_password") if secrets else None
            if not wp_password:
                return AgentOutput(status="error", message="WordPress password not found in secrets.")
        except Exception as e:
            self.logger.error(f"Failed to retrieve WordPress password: {e}", exc_info=True)
            return AgentOutput(status="error", message="Credential retrieval failed.")

        if not wp_url or not wp_user:
            return AgentOutput(status="error", message="Missing WordPress URL or username in Config.")

        # 2. FETCH READY PAGES (campaign-scoped)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        ready_pages = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "ready_to_publish"
        ]

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
                    slug = meta.get("slug") or (meta.get("keyword", "").lower().replace(" ", "-"))
                    meta["live_url"] = f"{wp_url.rstrip('/')}/{slug}"
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
        slug = meta.get("slug") or (meta.get("keyword", "").lower().replace(" ", "-"))

        if schema_raw:
            try:
                schema_json = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
                content = content + "\n\n" + f"<script type='application/ld+json'>{json.dumps(schema_json, ensure_ascii=False)}</script>"
            except Exception as e:
                self.logger.warning(f"Failed to inject schema: {e}")

        post_data = {
            "title": title,
            "content": content,
            "slug": slug,
            "status": "publish",
            "excerpt": meta_description,
            "categories": [1],
            "meta": {},
        }
        if meta_description:
            post_data["meta"]["_yoast_wpseo_metadesc"] = meta_description
            post_data["meta"]["rank_math_description"] = meta_description

        try:
            res = requests.post(endpoint, json=post_data, headers={"Authorization": f"Basic {creds}"}, timeout=10)
            if res.status_code in (200, 201):
                return True
            self.logger.error(f"WP Error {res.status_code}: {res.text}")
            return False
        except Exception as e:
            self.logger.error(f"WP Connection Failed: {e}")
            return False
