# backend/modules/pseo/agents/librarian.py
import re
import random
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


class LibrarianAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Librarian")

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

        # 2. FETCH WORK ITEM (Find 'validated' drafts ready for linking)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        validated_drafts = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "validated"
        ]

        if not validated_drafts:
            return AgentOutput(status="complete", message="No validated drafts waiting for linking.")

        target_draft = validated_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content (Titanium: content)
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"LIBRARIAN: Linking page for '{keyword}'")

        # 3. LOAD LINKING ASSETS
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        campaign_kws = [
            k for k in all_kws
            if k.get("metadata", {}).get("campaign_id") == campaign_id
            and k.get("name") != keyword
        ]

        all_intel = memory.get_entities(tenant_id=user_id, entity_type="knowledge_fragment", project_id=project_id)
        campaign_intel = [i for i in all_intel if i.get("metadata", {}).get("campaign_id") == campaign_id]

        # 4. EXECUTE LINKING STRATEGY (Regex Injection)
        linked_html = html_content
        links_added = 0

        random.shuffle(campaign_kws)
        internal_count = 0
        for kw_entity in campaign_kws:
            if internal_count >= 3:
                break
            target_term = kw_entity.get("name")
            slug = target_term.lower().replace(" ", "-")
            pattern = re.compile(re.escape(target_term), re.IGNORECASE)
            if pattern.search(linked_html):
                replacement = f'<a href="/{slug}" title="{target_term}" class="internal-link">{target_term}</a>'
                linked_html = pattern.sub(replacement, linked_html, count=1)
                internal_count += 1
                links_added += 1

        if campaign_intel:
            sources = random.sample(campaign_intel, min(len(campaign_intel), 2))
            source_html = '<div class="sources-section"><h4>References & Official Rules:</h4><ul>'
            for source in sources:
                url = source.get("metadata", {}).get("url", "")
                title = source.get("name", "")
                source_html += f'<li><a href="{url}" target="_blank" rel="nofollow noreferrer">{title}</a></li>'
            source_html += "</ul></div>"
            linked_html += f"\n{source_html}"
            links_added += 1

        # 5. SAVE & ADVANCE (use "content" per Titanium/DB pattern)
        target_draft["metadata"]["content"] = linked_html
        target_draft["metadata"]["status"] = "ready_for_media"
        target_draft["metadata"]["links_added_count"] = links_added
        memory.save_entity(Entity(**target_draft), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Added {links_added} links to '{keyword}'",
            data={
                "draft_id": target_draft["id"],
                "links_added": links_added,
                "next_step": "Ready for Media",
            },
        )
