# backend/modules/lead_gen/agents/utility.py
import html as html_module
import json
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


DEFAULT_FORM_FIELDS = [
    {"name": "name", "type": "text", "label": "Name", "required": True},
    {"name": "phone", "type": "tel", "label": "Phone", "required": True},
    {"name": "email", "type": "email", "label": "Email", "required": False},
]


class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")

    def _get_form_fields(self, config: dict) -> List[Dict[str, Any]]:
        """Resolve form fields from config (dual-path for backward compatibility)."""
        fields = (
            config.get("lead_gen_integration", {}).get("form_settings", {}).get("fields")
            or config.get("modules", {}).get("lead_gen", {}).get("form_settings", {}).get("fields")
        )
        return fields if fields else DEFAULT_FORM_FIELDS

    def _get_destination_phone(self, config: dict) -> str:
        """Resolve destination_phone from config (dual-path)."""
        return (
            config.get("lead_gen_integration", {}).get("destination_phone")
            or config.get("modules", {}).get("lead_gen", {}).get("sales_bridge", {}).get("destination_phone")
            or ""
        )

    def _build_dynamic_form(self, fields: List[Dict[str, Any]]) -> str:
        """Build HTML form from field config (text, tel, email, select)."""
        parts = ['<form class="lead-gen-form" method="post" action="/api/webhooks/lead">']
        for field in fields:
            name = field.get("name", "field")
            field_type = field.get("type", "text")
            label = field.get("label", name.title())
            required = field.get("required", False)
            req_attr = ' required' if required else ''
            label_html = f'<label for="{html_module.escape(name)}">{html_module.escape(label)}</label>'
            if field_type == "select":
                options = field.get("options", [])
                if not isinstance(options, list):
                    options = []
                opts_html = ""
                for opt in options:
                    if isinstance(opt, dict):
                        val = str(opt.get("value", opt.get("label", "")))
                        lbl = str(opt.get("label", val))
                    else:
                        val = str(opt)
                        lbl = str(opt)
                    opts_html += f'<option value="{html_module.escape(val)}">{html_module.escape(lbl)}</option>'
                parts.append(f'{label_html}<select name="{html_module.escape(name)}" id="{html_module.escape(name)}"{req_attr}>{opts_html}</select>')
            else:
                input_type = field_type if field_type in ("text", "tel", "email") else "text"
                parts.append(f'{label_html}<input type="{input_type}" name="{html_module.escape(name)}" id="{html_module.escape(name)}"{req_attr} />')
        parts.append('<button type="submit" class="btn btn-primary">Get Immediate Help</button>')
        parts.append("</form>")
        return "\n".join(parts)

    def _build_schema(self, draft: dict, config: dict, user_id: str) -> dict:
        """Build LocalBusiness/Service JSON-LD schema (E-E-A-T signals)."""
        service_name = config.get("service_focus", "Service")
        brand_name = config.get("brand_name", config.get("identity", {}).get("business_name", "Our Agency"))
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

        # Load Campaign Config (merged DNA + campaign)
        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        config = campaign.get("config", {})

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
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"UTILITY: Building technical assets for '{keyword}'")

        # 3. BUILD JSON-LD SCHEMA (Always Run - E-E-A-T signals)
        schema_json = self._build_schema(target_draft, config, user_id)
        schema_script = f'<script type="application/ld+json">{json.dumps(schema_json)}</script>'

        # 4. DYNAMIC FORM from config
        fields = self._get_form_fields(config)
        form_html = self._build_dynamic_form(fields)

        keyword_safe = (draft_meta.get("keyword") or "").strip() or "Support"
        anchor_used = (draft_meta.get("anchor_used") or "").strip()
        if anchor_used:
            headline = f"Immediate {html_module.escape(keyword_safe)} Support near {html_module.escape(anchor_used)}"
        else:
            headline = f"Immediate {html_module.escape(keyword_safe)} Support in Your Area"

        conversion_block = (
            '<div class="conversion-block">'
            f'<h3 class="conversion-headline">{headline}</h3>'
            f'<div class="conversion-inner">{form_html}</div>'
            "</div>"
        )

        final_html = html_content
        form_injected = False
        if "{{form_capture}}" in final_html:
            final_html = final_html.replace("{{form_capture}}", conversion_block)
            form_injected = True
        else:
            final_html += f"\n<div class='conversion-section'>{conversion_block}</div>"
            form_injected = True

        if "{{table_here}}" in final_html:
            final_html = final_html.replace("{{table_here}}", "")

        # 5. ALWAYS inject schema (E-E-A-T)
        if "</body>" in final_html:
            final_html = final_html.replace("</body>", f"{schema_script}</body>")
        else:
            final_html += f"\n{schema_script}"

        # 6. STICKY CALL BUTTON if destination_phone exists
        destination_phone = self._get_destination_phone(config)
        if destination_phone and destination_phone != "REQUIRED":
            phone_clean = "".join(c for c in destination_phone if c.isdigit() or c in "+")
            sticky_css = (
                '<style>.sticky-footer{position:fixed;bottom:0;left:0;right:0;'
                'background:#1a73e8;color:#fff;padding:12px;text-align:center;'
                'text-decoration:none;font-weight:bold;z-index:9999;}</style>'
            )
            sticky_btn = f'<a href="tel:{html_module.escape(phone_clean)}" class="sticky-footer">Call Now</a>'
            if "</body>" in final_html:
                final_html = final_html.replace("</body>", f"{sticky_css}{sticky_btn}</body>")
            else:
                final_html += f"\n{sticky_css}{sticky_btn}"

        # 7. SAVE & FINISH (Titanium/DB pattern)
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
