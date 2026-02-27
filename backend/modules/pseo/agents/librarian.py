# backend/modules/pseo/agents/librarian.py
import re
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory

_VALID_LINK_TARGET_STATUSES = {"validated", "ready_for_media", "ready_for_utility", "ready_to_publish", "published"}
_PENDING_STATUSES = {"pending_writer", "draft", "rejected"}


class LibrarianAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Librarian")

    def _get_librarian_config(self) -> Dict[str, Any]:
        """Read librarian config from DNA or campaign (modules.pseo.librarian)."""
        return (
            (self.config or {}).get("librarian")
            or (self.config or {}).get("modules", {}).get("pseo", {}).get("librarian")
            or {}
        )

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

        librarian_config = self._get_librarian_config()
        run_only_when_all_validated = librarian_config.get("run_only_when_all_validated", True)
        max_internal_links = int(librarian_config.get("max_internal_links", 3))
        max_intel_sources = int(librarian_config.get("max_intel_sources", 2))

        # 2. FETCH WORK ITEM and gate: run only when all cluster pages are validated
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        campaign_drafts = [d for d in all_drafts if d.get("metadata", {}).get("campaign_id") == campaign_id]

        if run_only_when_all_validated and campaign_drafts:
            any_pending = any(
                (d.get("metadata", {}).get("status") or "") in _PENDING_STATUSES
                for d in campaign_drafts
            )
            if any_pending:
                return AgentOutput(
                    status="complete",
                    message="Waiting for all pages to be validated before linking.",
                )

        validated_drafts = [
            d for d in campaign_drafts
            if (d.get("metadata", {}).get("status") or "") == "validated"
        ]
        draft_id_param = input_data.params.get("draft_id")
        if draft_id_param:
            validated_drafts = [d for d in validated_drafts if d.get("id") == draft_id_param]
        if not validated_drafts:
            return AgentOutput(status="complete", message="No validated drafts waiting for linking.")

        target_draft = validated_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content (Titanium: content)
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword") or draft_meta.get("h1_title") or (target_draft.get("name") or "").replace("Page: ", "").strip()

        self.logger.info(f"LIBRARIAN: Linking page for '{keyword}'")

        # 3. LOAD LINKING ASSETS (keywords or other drafts that are validated or later)
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        campaign_kws = [
            k for k in all_kws
            if k.get("metadata", {}).get("campaign_id") == campaign_id
            and (k.get("name") or "").strip() != keyword
        ]

        link_targets: List[Dict[str, str]] = []
        if campaign_kws:
            link_targets = [{"term": k.get("name", "").strip(), "slug": (k.get("name") or "").lower().replace(" ", "-")} for k in campaign_kws if k.get("name")]
        else:
            other_drafts = [
                d for d in campaign_drafts
                if d.get("id") != target_draft.get("id")
                and (d.get("metadata", {}).get("status") or "") in _VALID_LINK_TARGET_STATUSES
            ]
            for d in other_drafts:
                term = (d.get("metadata", {}).get("h1_title") or d.get("name") or "").replace("Page: ", "").strip()
                if term:
                    link_targets.append({"term": term, "slug": term.lower().replace(" ", "-")})

        # Deterministic order: sort by term then take first max_internal_links
        link_targets = sorted(link_targets, key=lambda x: (x.get("term") or "", x.get("slug") or ""))[: max_internal_links * 2]
        internal_count = 0

        all_intel = memory.get_entities(tenant_id=user_id, entity_type="knowledge_fragment", project_id=project_id)
        campaign_intel = [i for i in all_intel if i.get("metadata", {}).get("campaign_id") == campaign_id]
        # Deterministic: sort by name/url and take first max_intel_sources
        campaign_intel_sorted = sorted(campaign_intel, key=lambda i: (i.get("name") or "", i.get("metadata", {}).get("url") or ""))

        # 4. EXECUTE LINKING STRATEGY (Safe regex: only match term in text, not inside HTML tags)
        linked_html = html_content
        links_added = 0

        def _replace_first_term_outside_tags(html: str, term: str, replacement: str) -> str:
            """Replace first occurrence of term only in text content (not inside <...>)."""
            if not term:
                return html
            parts = re.split(r"(<[^>]+>)", html)
            for i, part in enumerate(parts):
                if part.startswith("<"):
                    continue
                if re.search(re.escape(term), part, re.IGNORECASE):
                    new_part = re.sub(
                        re.compile(re.escape(term), re.IGNORECASE),
                        lambda m: replacement,
                        part,
                        count=1,
                    )
                    parts[i] = new_part
                    return "".join(parts)
            return html

        for item in link_targets:
            if internal_count >= max_internal_links:
                break
            target_term = item.get("term", "")
            slug = item.get("slug", target_term.lower().replace(" ", "-"))
            if not target_term:
                continue
            replacement = f'<a href="/{slug}" title="{target_term}" class="internal-link">{target_term}</a>'
            new_html = _replace_first_term_outside_tags(linked_html, target_term, replacement)
            if new_html != linked_html:
                linked_html = new_html
                internal_count += 1
                links_added += 1

        if campaign_intel_sorted:
            sources = campaign_intel_sorted[:max_intel_sources]
            source_html = '<div class="sources-section"><h4>References & Official Rules:</h4><ul>'
            for source in sources:
                url = source.get("metadata", {}).get("url", "")
                title = source.get("name", "")
                source_html += f'<li><a href="{url}" target="_blank" rel="nofollow noreferrer">{title}</a></li>'
            source_html += "</ul></div>"
            if "</article>" in linked_html:
                linked_html = linked_html.replace("</article>", source_html + "\n</article>", 1)
            else:
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
