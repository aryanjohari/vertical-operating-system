# backend/modules/lead_gen/agents/utility.py
import html
import json
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")

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

        # Load Campaign Config
        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        config = campaign.get("config", {})
        lead_gen_enabled = config.get("modules", {}).get("lead_gen", {}).get("enabled", True)

        # 2. FETCH WORK ITEM ('ready_for_utility' or 'ready_for_media')
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        utility_ready_drafts = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") in ["ready_for_utility", "ready_for_media"]
        ]

        if not utility_ready_drafts:
            return AgentOutput(status="complete", message="No drafts waiting for utility processing.")

        target_draft = utility_ready_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content (Titanium: content)
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"UTILITY: Building technical assets for '{keyword}'")

        # 3. BUILD JSON-LD SCHEMA (Always Run)
        schema_json = self._build_schema(target_draft, config, user_id)

        # 4. INJECT CONVERSION ASSETS (If Lead Gen Enabled)
        final_html = html_content
        form_injected = False
        keyword_safe = (draft_meta.get("keyword") or "").strip() or "Support"
        anchor_used = (draft_meta.get("anchor_used") or "").strip()

        if lead_gen_enabled:
            conversion_code = config.get("conversion_asset", {}).get("html_code")
            if not conversion_code:
                conversion_code = '<a href="/contact" class="btn btn-primary">Get Immediate Help</a>'
            # Dynamic headline: "Immediate {keyword} Support near {anchor_used}" or "Immediate {keyword} Support" when no anchor
            if anchor_used:
                headline = f"Immediate {html.escape(keyword_safe)} Support near {html.escape(anchor_used)}"
            else:
                headline = f"Immediate {html.escape(keyword_safe)} Support in Your Area"
            conversion_block = (
                f'<div class="conversion-block">'
                f'<h3 class="conversion-headline">{headline}</h3>'
                f'<div class="conversion-inner">{conversion_code}</div>'
                f'</div>'
            )
            if "{{form_capture}}" in final_html:
                final_html = final_html.replace("{{form_capture}}", conversion_block)
                form_injected = True
            else:
                final_html += f"\n<div class='conversion-section'>{conversion_block}</div>"
                form_injected = True
        else:
            final_html = final_html.replace("{{form_capture}}", "")

        if "{{table_here}}" in final_html:
            final_html = final_html.replace("{{table_here}}", "")

        # 5. SAVE & FINISH (use "content" per Titanium/DB pattern)
        target_draft["metadata"]["content"] = final_html
        target_draft["metadata"]["json_ld_schema"] = json.dumps(schema_json)
        target_draft["metadata"]["status"] = "ready_to_publish"
        memory.save_entity(Entity(**target_draft), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Utility complete for '{keyword}'",
            data={
                "draft_id": target_draft["id"],
                "schema_built": True,
                "form_injected": form_injected,
                "next_step": "Ready for Publisher",
            },
        )

    def _build_schema(self, draft: dict, config: dict, user_id: str) -> dict:
        service_name = config.get("service_focus", "Service")
        brand_name = config.get("brand_name", "Our Agency")
        schema = {
            "@context": "https://schema.org",
            "@type": "Service",
            "serviceType": service_name,
            "provider": {"@type": "LocalBusiness", "name": brand_name},
            "areaServed": [],
        }
        anchor_name = draft.get("metadata", {}).get("anchor_used")
        if anchor_name:
            schema["areaServed"].append({
                "@type": "Place",
                "name": f"Area near {anchor_name}",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": config.get("targeting", {}).get("geo_targets", {}).get("cities", ["New Zealand"])[0],
                },
            })
        else:
            cities = config.get("targeting", {}).get("geo_targets", {}).get("cities", [])
            for city in cities:
                schema["areaServed"].append({"@type": "City", "name": city})
        schema["offers"] = {
            "@type": "Offer",
            "priceCurrency": "NZD",
            "availability": "https://schema.org/InStock",
        }
        return schema
