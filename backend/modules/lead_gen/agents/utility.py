# backend/modules/lead_gen/agents/utility.py
import html as html_module
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from jinja2 import Environment, BaseLoader
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory

DEFAULT_FORM_FIELDS = [
    {"name": "name", "type": "text", "label": "Name", "required": True},
    {"name": "phone", "type": "tel", "label": "Phone", "required": True},
    {"name": "email", "type": "email", "label": "Email", "required": False},
]

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "core", "templates")
_DEFAULT_FORM_TEMPLATE_PATH = os.path.join(_TEMPLATE_DIR, "lead_gen_form.html")
_DEFAULT_SCHEMA_TEMPLATE = '''{
  "@context": "https://schema.org",
  "@type": "Service",
  "serviceType": "{{ service_name }}",
  "provider": { "@type": "LocalBusiness", "name": "{{ brand_name }}" },
  "areaServed": {{ area_served_json }},
  "offers": { "@type": "Offer", "priceCurrency": "{{ price_currency }}", "availability": "https://schema.org/InStock" }
}'''
_DEFAULT_CALL_BUTTON = '<a href="{{ tel_link }}" class="sticky-footer">Call Now</a>'


def _lead_gen_section(campaign: Dict[str, Any], campaign_config: Dict[str, Any], merged_config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve lead_gen config: campaign config (if lead_gen) or merged DNA modules.lead_gen."""
    if campaign.get("module") == "lead_gen":
        return campaign_config
    return (merged_config or {}).get("modules", {}).get("lead_gen", {})


def _load_form_template(lead_gen_cfg: Optional[Dict] = None) -> str:
    """Load form Jinja2 template from campaign/DNA (form_template) or default file."""
    if lead_gen_cfg:
        t = lead_gen_cfg.get("form_template")
        if t and isinstance(t, str) and t.strip():
            return t.strip()
    if os.path.exists(_DEFAULT_FORM_TEMPLATE_PATH):
        with open(_DEFAULT_FORM_TEMPLATE_PATH, "r") as f:
            return f.read()
    return """<form class="lead-gen-form" method="post" action="{{ form_action_url }}">
{% for field in fields %}<label for="{{ field.name }}">{{ field.label }}</label>
{% if field.type == "select" %}<select name="{{ field.name }}" id="{{ field.name }}"{% if field.required %} required{% endif %}>{% for opt in field.options or [] %}<option value="{{ opt.value or opt.label or opt }}">{{ opt.label or opt.value or opt }}</option>{% endfor %}</select>
{% else %}<input type="{{ field.type if field.type in ('text','tel','email') else 'text' }}" name="{{ field.name }}" id="{{ field.name }}"{% if field.required %} required{% endif %} />{% endif %}
{% endfor %}<button type="submit" class="btn btn-primary">Get Immediate Help</button>
</form>"""


def _load_schema_template(lead_gen_cfg: Optional[Dict] = None) -> str:
    """Load schema Jinja2 template from campaign/DNA (schema_template) or default."""
    if lead_gen_cfg:
        t = lead_gen_cfg.get("schema_template")
        if t and isinstance(t, str) and t.strip():
            return t.strip()
    schema_path = os.path.join(_TEMPLATE_DIR, "lead_gen_schema.json")
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            return f.read()
    return _DEFAULT_SCHEMA_TEMPLATE


def _load_call_button_template(lead_gen_cfg: Optional[Dict] = None) -> str:
    """Load call button Jinja2 template; vars: tel_link, phone. Empty = use default sticky."""
    if lead_gen_cfg:
        t = lead_gen_cfg.get("call_button_template")
        if t and isinstance(t, str) and t.strip():
            return t.strip()
    return _DEFAULT_CALL_BUTTON


def _validate_final_lead_gen_assets(
    html_content: str,
    config: Dict[str, Any],
    expected_webhook_path: str = "/api/webhooks/lead",
) -> Tuple[bool, str]:
    """
    Post-Utility deterministic check: form action, tel link (if destination_phone set), JSON-LD.
    Returns (passed, failure_reason).
    """
    content_lower = html_content.lower()
    # Form must exist and post to webhook
    if "<form" not in content_lower or "action=" not in content_lower:
        return False, "Missing form or form action."
    if expected_webhook_path not in html_content:
        return False, f"Form action must point to webhook (expected path containing '{expected_webhook_path}')."
    # Tel link if destination_phone is set
    destination_phone = (
        (config.get("modules") or {}).get("lead_gen", {}).get("sales_bridge", {}).get("destination_phone")
        or (config.get("lead_gen_integration") or {}).get("destination_phone")
        or config.get("destination_phone")
        or ""
    )
    if destination_phone and str(destination_phone).strip() != "REQUIRED":
        if "tel:" not in html_content:
            return False, "Missing tel: link for destination_phone (call button)."
    # JSON-LD script present and valid
    ld_match = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([^<]+)</script>',
        html_content,
        re.DOTALL | re.IGNORECASE,
    )
    if not ld_match:
        return False, "Missing JSON-LD script block."
    try:
        json.loads(ld_match.group(1).strip())
    except (json.JSONDecodeError, ValueError):
        return False, "Invalid JSON in application/ld+json script."
    return True, ""


class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")

    def _get_form_fields(self, lead_gen_cfg: dict) -> List[Dict[str, Any]]:
        fields = (lead_gen_cfg or {}).get("form_settings", {}).get("fields")
        return fields if fields else DEFAULT_FORM_FIELDS

    def _get_destination_phone(self, lead_gen_cfg: dict) -> str:
        return (lead_gen_cfg or {}).get("sales_bridge", {}).get("destination_phone") or ""

    def _get_schema_data(self, draft: dict, config: dict) -> Dict[str, Any]:
        """Build schema data dict from config + draft (deterministic, no LLM)."""
        service_name = config.get("service_focus", "Service")
        brand_name = config.get("brand_name") or config.get("identity", {}).get("business_name", "Our Agency")
        cities = config.get("targeting", {}).get("geo_targets", {}).get("cities", [])
        if not isinstance(cities, list):
            cities = [cities] if cities else []
        anchor_name = draft.get("metadata", {}).get("anchor_used")
        area_served = []
        if anchor_name:
            locality = cities[0] if cities else "New Zealand"
            area_served.append({
                "@type": "Place",
                "name": f"Area near {anchor_name}",
                "address": {"@type": "PostalAddress", "addressLocality": locality},
            })
        else:
            for city in cities:
                area_served.append({"@type": "City", "name": city})
        return {
            "service_name": service_name,
            "brand_name": brand_name,
            "area_served_json": json.dumps(area_served),
            "price_currency": "NZD",
        }

    def _get_form_action_url(self, lead_gen_cfg: Optional[Dict] = None) -> str:
        """Full URL for form action so WordPress-hosted pages POST to deployed backend (e.g. Railway)."""
        base = (lead_gen_cfg or {}).get("webhook_base_url") or os.getenv("WEBHOOK_BASE_URL") or os.getenv("API_URL") or ""
        path = (lead_gen_cfg or {}).get("form_webhook_path") or "/api/webhooks/lead"
        if base:
            return f"{base.rstrip('/')}{path}"
        return path

    def _render_form_html(self, fields: List[Dict[str, Any]], lead_gen_cfg: Optional[Dict] = None) -> str:
        """Render form HTML via Jinja2 template (campaign-specific or default)."""
        template_str = _load_form_template(lead_gen_cfg)
        env = Environment(loader=BaseLoader(), autoescape=True)
        template = env.from_string(template_str)
        form_action_url = self._get_form_action_url(lead_gen_cfg)
        return template.render(fields=fields, form_action_url=form_action_url)

    def _render_schema_script(self, draft: dict, full_config: dict, lead_gen_cfg: Optional[Dict] = None) -> str:
        """Render JSON-LD schema via Jinja2 template (campaign-specific or default)."""
        data = self._get_schema_data(draft, full_config)
        template_str = _load_schema_template(lead_gen_cfg)
        env = Environment(loader=BaseLoader())
        template = env.from_string(template_str)
        out = template.render(**data)
        return f'<script type="application/ld+json">{out}</script>'

    def _render_call_button(self, tel_link: str, phone_display: str, lead_gen_cfg: Optional[Dict] = None) -> str:
        """Render call button HTML via Jinja2 template (vars: tel_link, phone)."""
        template_str = _load_call_button_template(lead_gen_cfg)
        env = Environment(loader=BaseLoader(), autoescape=True)
        template = env.from_string(template_str)
        return template.render(tel_link=tel_link, phone=phone_display)

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

        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        config = campaign.get("config", {})

        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        utility_ready_drafts = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") in ["ready_for_utility", "ready_for_media", "utility_validation_failed"]
        ]
        draft_id_param = input_data.params.get("draft_id")
        if draft_id_param:
            utility_ready_drafts = [d for d in utility_ready_drafts if d.get("id") == draft_id_param]
        if not utility_ready_drafts:
            return AgentOutput(status="complete", message="No drafts waiting for utility processing.")

        target_draft = utility_ready_drafts[0]
        draft_meta = target_draft.get("metadata", {})
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"UTILITY: Building technical assets for '{keyword}' (Jinja2)")

        lead_gen_cfg = _lead_gen_section(campaign, config, self.config or {})
        full_config = self.config or {}

        schema_script = self._render_schema_script(target_draft, full_config, lead_gen_cfg)
        schema_json = self._get_schema_data(target_draft, full_config)
        schema_json["area_served_json"] = json.loads(schema_json["area_served_json"])
        full_schema = {
            "@context": "https://schema.org",
            "@type": "Service",
            "serviceType": schema_json["service_name"],
            "provider": {"@type": "LocalBusiness", "name": schema_json["brand_name"]},
            "areaServed": schema_json["area_served_json"],
            "offers": {"@type": "Offer", "priceCurrency": schema_json["price_currency"], "availability": "https://schema.org/InStock"},
        }

        fields = self._get_form_fields(lead_gen_cfg)
        form_html = self._render_form_html(fields, lead_gen_cfg)

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

        if "</body>" in final_html:
            final_html = final_html.replace("</body>", f"{schema_script}</body>")
        else:
            final_html += f"\n{schema_script}"

        destination_phone = self._get_destination_phone(lead_gen_cfg)
        if destination_phone and destination_phone != "REQUIRED":
            phone_clean = "".join(c for c in destination_phone if c.isdigit() or c in "+")
            tel_link = f"tel:{html_module.escape(phone_clean)}"
            phone_display = html_module.escape(destination_phone.strip())
            call_html = self._render_call_button(tel_link, phone_display, lead_gen_cfg)
            sticky_css = (
                '<style>.sticky-footer{position:fixed;bottom:0;left:0;right:0;'
                'background:#1a73e8;color:#fff;padding:12px;text-align:center;'
                'text-decoration:none;font-weight:bold;z-index:9999;}</style>'
            )
            if "</body>" in final_html:
                final_html = final_html.replace("</body>", f"{sticky_css}{call_html}</body>")
            else:
                final_html += f"\n{sticky_css}{call_html}"

        # Post-Utility validator: form webhook, tel link, JSON-LD
        expected_webhook = (lead_gen_cfg or {}).get("form_webhook_path") or "/api/webhooks/lead"
        valid, reason = _validate_final_lead_gen_assets(final_html, full_config, expected_webhook)
        if not valid:
            target_draft["metadata"]["content"] = final_html
            target_draft["metadata"]["json_ld_schema"] = json.dumps(full_schema)
            target_draft["metadata"]["status"] = "utility_validation_failed"
            target_draft["metadata"]["utility_validation_reason"] = reason
            memory.save_entity(Entity(**target_draft), project_id=project_id)
            self.logger.warning(f"UTILITY: Post-validation failed for '{keyword}': {reason}")
            return AgentOutput(
                status="error",
                message=f"Lead gen validation failed: {reason}",
                data={"draft_id": target_draft["id"], "validation_reason": reason},
            )

        target_draft["metadata"]["content"] = final_html
        target_draft["metadata"]["json_ld_schema"] = json.dumps(full_schema)
        target_draft["metadata"]["status"] = "ready_to_publish"
        if "utility_validation_reason" in target_draft["metadata"]:
            del target_draft["metadata"]["utility_validation_reason"]
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
