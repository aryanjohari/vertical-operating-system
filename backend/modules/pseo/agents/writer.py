# backend/modules/pseo/agents/writer.py
import asyncio
import html
import json
import hashlib
import os
from typing import List, Dict, Any, Optional
from jinja2 import Environment, BaseLoader
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway
from backend.modules.pseo.agents.utility import get_local_blurb

# Default page body template (Jinja2); can be overridden from config
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "core", "templates")
_DEFAULT_TEMPLATE_PATH = os.path.join(_TEMPLATE_DIR, "page_draft_body.html")


def _is_informational_intent(draft_meta: Dict[str, Any]) -> bool:
    """True if intent is guide/how-to; otherwise transactional."""
    intent_role = (draft_meta.get("intent_role") or "").strip()
    cluster_id = (draft_meta.get("cluster_id") or draft_meta.get("intent") or "").strip().lower()
    if "informational" in intent_role.lower():
        return True
    if "guide" in cluster_id or "how-to" in cluster_id or "howto" in cluster_id:
        return True
    return False


def _load_page_template(config: Optional[Dict] = None) -> str:
    """Load page body template from config (pseo.page_template) or default file."""
    if config:
        t = config.get("modules", {}).get("local_seo", {}).get("page_template")
        if t and isinstance(t, str):
            return t
    if os.path.exists(_DEFAULT_TEMPLATE_PATH):
        with open(_DEFAULT_TEMPLATE_PATH, "r") as f:
            return f.read()
    return """<h1>{{ keyword }}</h1>
{{ image_main_placeholder }}
<p>{{ hook_paragraph }}</p>
{% if local_blurb %}<p>{{ local_blurb }}</p>
{% endif %}<p>{{ local_paragraph }}</p>
<p>{{ regulatory_paragraph }}</p>
{% if fact_box and fact_box|length > 0 %}
<div class="fact-box"><table>{% for row in fact_box %}<tr><th>{{ row.label }}</th><td>{{ row.value }}</td></tr>{% endfor %}</table></div>
{% endif %}
{% if feature_list_title or feature_list_body %}<h2>{{ feature_list_title }}</h2>
{{ feature_list_body }}
{% endif %}
{% if faq_body %}{{ faq_body }}
{% endif %}
{{ form_capture_placeholder }}
"""


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Writer")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
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

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found.")
        config = campaign.get("config", {})
        targeting = config.get("targeting", {})
        service_focus = targeting.get("service_focus", config.get("service_focus", "Service"))

        brand_voice = self.config.get("brand_brain", {}).get("voice_tone", "Professional, Empathetic")

        # Prefer intent-cluster page_draft; fallback to seo_keyword (legacy).
        # When invoked with draft_id (e.g. from Manager run_next_for_draft), allow rewrites of rejected drafts.
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        draft_id_param = input_data.params.get("draft_id")

        target_draft = None
        use_draft_path = False
        is_informational = False

        if draft_id_param:
            # Explicit rewrite path: target this draft even if status is 'rejected' or 'draft'
            matching = [
                d
                for d in all_drafts
                if d.get("id") == draft_id_param
                and d.get("metadata", {}).get("campaign_id") == campaign_id
                and d.get("metadata", {}).get("status") in ("pending_writer", "draft", "rejected")
            ]
            if matching:
                target_draft = matching[0]
        else:
            # Batch path: only pick drafts marked pending_writer
            pending_drafts = [
                d for d in all_drafts
                if d.get("metadata", {}).get("campaign_id") == campaign_id
                and d.get("metadata", {}).get("status") == "pending_writer"
            ]
            if pending_drafts:
                target_draft = pending_drafts[0]

        if target_draft:
            # Intent-cluster path: write into existing page_draft
            draft_meta = target_draft.get("metadata", {})
            kw_text = draft_meta.get("h1_title") or target_draft.get("name", "").replace("Page: ", "")
            anchor_ref_id = draft_meta.get("anchor_id")
            kw_meta = {
                "intent": draft_meta.get("cluster_id"),
                "anchor_reference": anchor_ref_id,
                "intent_role": draft_meta.get("intent_role"),
                "cluster_id": draft_meta.get("cluster_id"),
            }
            use_draft_path = True
            is_informational = _is_informational_intent(draft_meta)
        else:
            # Legacy path: seo_keyword pending
            keyword_id_param = input_data.params.get("keyword_id")
            all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
            pending_kws = [
                k for k in all_kws
                if k.get("metadata", {}).get("campaign_id") == campaign_id
                and k.get("metadata", {}).get("status") == "pending"
                and not k.get("metadata", {}).get("excluded")
            ]
            if keyword_id_param is not None:
                pending_kws = [k for k in pending_kws if k.get("id") == keyword_id_param]
            if not pending_kws:
                return AgentOutput(status="complete", message="No pending keywords or drafts to write.")
            target_kw = pending_kws[0]
            kw_text = target_kw.get("name")
            kw_meta = target_kw.get("metadata", {})
            anchor_ref_id = kw_meta.get("anchor_reference")
            target_draft = None
            use_draft_path = False
            is_informational = False

        self.logger.info(f"WRITER: Drafting page for '{kw_text}' (data-only + Jinja2)")

        anchor_data = None
        if anchor_ref_id:
            anchor_entity = memory.get_entity(anchor_ref_id, user_id)
            if anchor_entity:
                anchor_data = {
                    "name": anchor_entity.get("name"),
                    "address": anchor_entity.get("metadata", {}).get("address"),
                    "phone": anchor_entity.get("metadata", {}).get("primary_contact"),
                }

        vector_fragments = memory.query_context(
            tenant_id=user_id,
            query=kw_text,
            n_results=5,
            project_id=project_id,
            campaign_id=campaign_id,
            return_metadata=True,
        )
        all_intel = memory.get_entities(tenant_id=user_id, entity_type="knowledge_fragment", project_id=project_id)
        campaign_intel = [i for i in all_intel if i.get("metadata", {}).get("campaign_id") == campaign_id]
        intel_list = []
        for frag in vector_fragments:
            frag_meta = frag.get("metadata", {})
            intel_list.append({
                "name": frag_meta.get("title", ""),
                "url": frag_meta.get("url", ""),
                "snippet": frag.get("text", ""),
                "type": frag_meta.get("fragment_type", "fact"),
            })
        sql_added = 0
        for sql_frag in campaign_intel:
            if sql_added >= max(0, 4 - len(intel_list)):
                break
            sql_url = sql_frag.get("metadata", {}).get("url", "")
            if not any(f.get("url") == sql_url for f in intel_list):
                intel_list.append({
                    "name": sql_frag.get("name", ""),
                    "url": sql_url,
                    "snippet": sql_frag.get("metadata", {}).get("snippet", ""),
                    "type": sql_frag.get("metadata", {}).get("type", "fact"),
                })
                sql_added += 1
        selected_intel = intel_list[:4]
        intel_context = "\n".join([
            f"- {frag.get('type', 'fact').upper()}: {frag.get('name', 'Unknown')} (Source: {frag.get('url', 'N/A')})\n  {frag.get('snippet', '')[:200]}"
            for frag in selected_intel
        ])
        if not intel_context:
            intel_context = "No specific knowledge fragments available. Use general best practices."
            self.logger.warning(f"No knowledge fragments found for keyword '{kw_text}' in campaign {campaign_id}")

        if is_informational:
            intent_task = """
- "expert_insight": string, one paragraph of expert insight or understanding specific to the keyword (guide/how-to).
- "step_by_step_guide": array of exactly 4 objects, each {"step_title": "...", "step_description": "..."}, clear steps for the user.
Do NOT include "service_overview" or "service_features"."""
        else:
            intent_task = """
- "service_overview": string, 1-2 paragraphs describing the service offering and how it addresses the keyword.
- "service_features": array of exactly 4 objects, each {"feature": "...", "benefit": "..."}, key features and benefits.
Do NOT include "expert_insight" or "step_by_step_guide"."""

        # Data-only prompt: LLM returns structured JSON, no HTML. No JSON-LD (schema is added deterministically later).
        prompt = f"""
ACT AS: Senior Content Writer & SEO Specialist for '{service_focus}' services.
TONE: {brand_voice}.

INPUT DATA (USE THIS, DO NOT INVENT):
KEYWORD: "{kw_text}"
INTENT: {kw_meta.get('intent')}
LOCAL ANCHOR: {f"User is near: {anchor_data['name']} at {anchor_data['address']}." if anchor_data else "User is searching city-wide."}

KNOWLEDGE BANK (cite only; never invent):
{intel_context}

TASK: Return ONLY a JSON object with these keys (plain text content, no HTML).
Common keys (always include):
- "meta_title": string, max 60 chars, includes keyword
- "meta_description": string, max 160 chars, includes keyword
- "hook_paragraph": string, 1-3 sentences answering the pain point
- "local_paragraph": string, 1-2 sentences about being minutes away from anchor or central
- "regulatory_paragraph": string, 1-3 sentences using KNOWLEDGE BANK for rules/costs (no invention)
- "fact_box": array of {{"label": "...", "value": "..."}} ONLY for facts explicitly in KNOWLEDGE BANK (costs, fees, processing times, documents, hours). If none, use [].
- "feature_list": object with "title" (string) and "items" (array of exactly 5 strings, bullet points specific to the keyword/niche).
- "faq_section": array of exactly 3 objects, each {{"question": "...", "answer": "..."}}, relevant to the keyword for SEO rich snippets.
Intent-specific (include only these for this intent):
{intent_task}

Never invent costs, fees, or figures. If no hard facts in KNOWLEDGE BANK, fact_box must be [].
"""

        try:
            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt="You are a content writer. Return only valid JSON. Keys include: meta_title, meta_description, hook_paragraph, local_paragraph, regulatory_paragraph, fact_box, feature_list (title, items), faq_section; for informational intent also expert_insight and step_by_step_guide; for transactional intent also service_overview and service_features. No HTML, no markdown, no JSON-LD.",
                user_prompt=prompt,
                model="gemini-2.5-flash",
                temperature=0.5,
                max_retries=2,
            )
            content_str = response_text.strip()
            if "```json" in content_str:
                content_str = content_str.split("```json")[1].split("```")[0]
            elif "```" in content_str:
                content_str = content_str.split("```")[1]
            content_str = content_str.strip()
            result = json.loads(content_str)
        except Exception as e:
            self.logger.error(f"Writer LLM/parse failed: {e}")
            return AgentOutput(status="error", message=f"Failed to generate valid JSON content: {e}")

        meta_title = result.get("meta_title", kw_text)
        meta_description = result.get("meta_description", "")
        hook_paragraph = result.get("hook_paragraph", "")
        local_paragraph = result.get("local_paragraph", "")
        regulatory_paragraph = result.get("regulatory_paragraph", "")
        fact_box = result.get("fact_box")
        if not isinstance(fact_box, list):
            fact_box = []

        # feature_list: { "title": "...", "items": [5 strings] }
        feature_list = result.get("feature_list") or {}
        if not isinstance(feature_list, dict):
            feature_list = {}
        fl_items = feature_list.get("items")
        if not isinstance(fl_items, list):
            fl_items = []
        fl_items = [str(x).strip() for x in fl_items[:5] if x]
        feature_list_title = (feature_list.get("title") or "").strip()
        feature_list_body = ""
        if fl_items:
            feature_list_body = "<ul>\n" + "\n".join(f"<li>{html.escape(i)}</li>" for i in fl_items) + "\n</ul>"

        # faq_section: [ { "question": "...", "answer": "..." }, ... ] -> <details><summary>...</summary>...</details>
        faq_section = result.get("faq_section")
        if not isinstance(faq_section, list):
            faq_section = []
        faq_section = faq_section[:3]
        faq_body = ""
        for item in faq_section:
            if not isinstance(item, dict):
                continue
            q = (item.get("question") or "").strip()
            a = (item.get("answer") or "").strip()
            if q or a:
                faq_body += f'<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>\n'

        expert_insight = (result.get("expert_insight") or "").strip() if is_informational else ""
        step_by_step_guide = result.get("step_by_step_guide")
        if not isinstance(step_by_step_guide, list):
            step_by_step_guide = []
        step_by_step_guide = [
            {"step_title": str(s.get("step_title", "")).strip(), "step_description": str(s.get("step_description", "")).strip()}
            for s in step_by_step_guide[:4] if isinstance(s, dict)
        ]

        service_overview = (result.get("service_overview") or "").strip() if not is_informational else ""
        service_features = result.get("service_features")
        if not isinstance(service_features, list):
            service_features = []
        service_features = [
            {"feature": str(s.get("feature", "")).strip(), "benefit": str(s.get("benefit", "")).strip()}
            for s in service_features[:4] if isinstance(s, dict)
        ]

        # destination_phone: from lead_gen config, digits and + only
        merged_config = self.config or {}
        lead_gen_cfg = (merged_config.get("modules") or {}).get("lead_gen", {}) or merged_config.get("lead_gen_integration") or {}
        dest_phone_raw = (lead_gen_cfg.get("sales_bridge") or {}).get("destination_phone") or lead_gen_cfg.get("destination_phone") or ""
        destination_phone = "".join(c for c in str(dest_phone_raw) if c.isdigit() or c == "+") if dest_phone_raw else ""

        # Local blurb (Python-generated sentence)
        geo = targeting.get("geo_targets", {}) or {}
        cities = geo.get("cities", []) if isinstance(geo.get("cities"), list) else []
        city = (cities[0] or "").strip() if cities else ""
        distance = (
            targeting.get("default_distance")
            or (self.config.get("modules", {}) or {}).get("local_seo", {}).get("default_distance")
            or "minutes"
        )
        anchor = (anchor_data.get("name", "") or "").strip() if anchor_data else ""
        local_blurb = get_local_blurb(city, distance, anchor)

        # Render Jinja2 template with data
        template_str = _load_page_template(self.config)
        env = Environment(loader=BaseLoader())
        template = env.from_string(template_str)
        html_content = template.render(
            keyword=kw_text,
            hook_paragraph=hook_paragraph,
            local_paragraph=local_paragraph,
            local_blurb=local_blurb,
            regulatory_paragraph=regulatory_paragraph,
            fact_box=fact_box,
            feature_list_title=feature_list_title,
            feature_list_body=feature_list_body,
            faq_body=faq_body,
            expert_insight=expert_insight,
            step_by_step_guide=step_by_step_guide,
            service_overview=service_overview,
            service_features=service_features,
            destination_phone=destination_phone,
            anchor_used=anchor_data.get("name") if anchor_data else None,
            image_main_placeholder="{{image_main}}",
            form_capture_placeholder="{{form_capture}}",
        )

        if use_draft_path and target_draft:
            # Update existing page_draft in place (intent-cluster flow)
            existing_meta = target_draft.get("metadata", {}) or {}
            new_meta = {
                **existing_meta,
                "status": "draft",
                "content": html_content,
                "html_content": html_content,
                "meta_title": meta_title,
                "meta_description": meta_description,
                "anchor_used": anchor_data.get("name") if anchor_data else None,
                "version": existing_meta.get("version", 1) + 1,
            }
            memory.update_entity(target_draft["id"], new_meta, tenant_id=user_id)
            page_id = target_draft["id"]
        else:
            # Legacy: create new page_draft and mark keyword as drafted
            page_id = hashlib.md5(kw_text.encode()).hexdigest()[:16]
            draft = Entity(
                id=f"page_{page_id}",
                tenant_id=user_id,
                entity_type="page_draft",
                name=f"Page: {kw_text}",
                primary_contact=None,
                metadata={
                    "campaign_id": campaign_id,
                    "keyword_id": target_kw.get("id"),
                    "keyword": kw_text,
                    "status": "draft",
                    "content": html_content,
                    "meta_title": meta_title,
                    "meta_description": meta_description,
                    "anchor_used": anchor_data.get("name") if anchor_data else None,
                    "version": 1,
                },
            )
            memory.save_entity(draft, project_id=project_id)
            meta = target_kw.get("metadata") or {}
            meta = dict(meta)
            meta["status"] = "drafted"
            target_kw["metadata"] = meta
            memory.save_entity(Entity(**target_kw), project_id=project_id)

        return AgentOutput(
            status="success",
            message=f"Drafted page '{kw_text}' with SEO metadata",
            data={
                "page_id": page_id if isinstance(page_id, str) else f"page_{page_id}",
                "keyword": kw_text,
                "meta_title": meta_title,
                "next_step": "Ready for Critic",
            },
        )
