# backend/modules/pseo/agents/publisher.py
import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict

from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity, PageExportTrainingPayload
from backend.core.s3 import upload_bytes

_SLUG_STOP_WORDS = frozenset(
    {"near", "the", "for", "a", "an", "and", "or", "in", "on", "at", "to", "of"}
)

CRITIC_SYSTEM_PROMPT = (
    "You are a strict content editor. Return only valid JSON with status, score, reason, fix_suggestions."
)


def _slugify(text: str, max_length: int = 70) -> str:
    """Lowercase, strip stop words, replace spaces with hyphens, remove non-alphanumeric, cap length."""
    if not text:
        return "post"
    s = text.strip().lower()
    words = re.split(r"[^a-z0-9]+", s)
    words = [w for w in words if w and w not in _SLUG_STOP_WORDS]
    s = "-".join(words)
    s = re.sub(r"-+", "-", s).strip("-")
    if len(s) > max_length:
        truncated = s[: max_length + 1].rsplit("-", 1)
        s = truncated[0] if len(truncated) > 1 else s[:max_length]
    return s or "post"


def _build_csv_row(page: Dict[str, Any]) -> str:
    """Build a single-row CSV for WP import: Title, Content, Slug, Meta_Description, Focus_Keyword."""
    meta = page.get("metadata") or {}
    title = meta.get("meta_title") or meta.get("title") or page.get("name", "")
    content = meta.get("content", "")
    slug = meta.get("slug") or _slugify(
        (meta.get("keyword") or meta.get("h1_title") or page.get("name", "") or "").strip()
    )
    meta_desc = meta.get("meta_description", "")
    focus_kw = (meta.get("keyword") or meta.get("h1_title") or page.get("name", "") or "").strip()[:60]
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Title", "Content", "Slug", "Meta_Description", "Focus_Keyword"])
    writer.writerow([title, content, slug, meta_desc, focus_kw])
    return out.getvalue()


def _build_critic_user_prompt(draft_meta: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Reconstruct the critic user prompt for the training payload."""
    brand_voice = (config.get("brand_brain") or {}).get("voice_tone", "Professional")
    forbidden_topics = (config.get("brand_brain") or {}).get("forbidden_topics", [])
    if not isinstance(forbidden_topics, list):
        forbidden_topics = []
    anchor_used = draft_meta.get("anchor_used", "General City")
    html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
    snippet = (html_content[:3000] + " ... (truncated)") if len(html_content) > 3000 else html_content
    return f"""
        ACT AS: Senior Compliance Officer & Editor.
        TASK: Pass or Fail this web page draft.

        --- THE RULES (STRICT) ---
        1. **Brand Voice:** Must be "{brand_voice}".
        2. **Local Accuracy:** If an Anchor Location ({anchor_used}) was assigned, it must be naturally mentioned in the text (referenced in a natural way, not necessarily the exact config string).
        3. **Forbidden Topics:** The text MUST NOT promise or discuss: {forbidden_topics}. If you fail the draft for a Forbidden Topic, you MUST quote the exact sentence from the draft in your reason. Do not fail unless there is an explicit mention.
        4. **Structure:** Must contain an <h1> and placeholders like {{{{form_capture}}}}.
        5. **Formatting:** Fail the draft if there are massive walls of text. Paragraphs over 100 words should be penalized.

        --- THE DRAFT CONTENT ---
        {snippet}

        --- EVALUATION FORMAT ---
        Return ONLY a JSON object:
        {{
            "status": "PASS" | "FAIL",
            "score": <0-10>,
            "reason": "Short explanation of failure or success",
            "fix_suggestions": "If fail, what needs fixing?"
        }}
        """


def _build_training_payload(
    page: Dict[str, Any],
    campaign: Dict[str, Any],
    config: Dict[str, Any],
    slug: str,
    project_id: str,
) -> Dict[str, Any]:
    """Build the LoRA training JSON payload (schema_version, inputs, config_snapshot, prompts, outputs, pipeline_metadata, gsc_performance)."""
    meta = page.get("metadata") or {}
    campaign_id = campaign.get("id", "")
    draft_id = page.get("id", "")
    now = datetime.utcnow().isoformat() + "Z"

    targeting = config.get("targeting") or {}
    brand_brain = config.get("brand_brain") or {}
    identity = config.get("identity") or {}

    # inputs
    keyword = (meta.get("keyword") or meta.get("h1_title") or page.get("name") or "").strip()
    inputs = {
        "keyword": keyword,
        "h1_title": meta.get("h1_title"),
        "anchor_id": meta.get("anchor_id"),
        "anchor_name": meta.get("anchor_name"),
        "anchor_used": meta.get("anchor_used"),
        "cluster_id": meta.get("cluster_id"),
        "intent_role": meta.get("intent_role"),
        "secondary_keywords": meta.get("secondary_keywords") or [],
        "validation_score": meta.get("validation_score"),
        "campaign_id": campaign_id,
        "service_focus": targeting.get("service_focus") or config.get("service_focus"),
        "geo_targets": targeting.get("geo_targets"),
        "default_distance": targeting.get("default_distance"),
        "brand_voice": brand_brain.get("voice_tone"),
    }
    inputs = {k: v for k, v in inputs.items() if v is not None}

    # config_snapshot
    config_snapshot = {
        "targeting": targeting,
        "intent_clusters": config.get("intent_clusters"),
        "brand_brain": brand_brain,
        "identity": identity,
        "critic": config.get("critic") or ((config.get("modules") or {}).get("pseo") or {}).get("critic"),
        "modules": {"local_seo": (config.get("modules") or {}).get("local_seo")},
    }
    config_snapshot = {k: v for k, v in config_snapshot.items() if v is not None}

    # prompts (writer from metadata; critic reconstructed)
    writer_system = meta.get("writer_system") or ""
    writer_user = meta.get("writer_user") or ""
    critic_user = _build_critic_user_prompt(meta, config)
    prompts = {
        "writer_system": writer_system,
        "writer_user": writer_user,
        "critic_system": CRITIC_SYSTEM_PROMPT,
        "critic_user": critic_user,
    }

    # outputs
    schema_raw = meta.get("json_ld_schema")
    schema_obj = None
    if schema_raw:
        try:
            schema_obj = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
        except (json.JSONDecodeError, TypeError):
            pass
    outputs = {
        "meta_title": meta.get("meta_title"),
        "meta_description": meta.get("meta_description"),
        "content": meta.get("content"),
        "json_ld_schema": schema_obj,
        "writer_output_json": meta.get("writer_output_json"),
    }
    outputs = {k: v for k, v in outputs.items() if v is not None}

    # pipeline_metadata
    pipeline_metadata = {
        "qa_score": meta.get("qa_score"),
        "qa_notes": meta.get("qa_notes"),
        "links_added_count": meta.get("links_added_count"),
        "image_added": meta.get("image_added"),
        "version": meta.get("version"),
    }
    pipeline_metadata = {k: v for k, v in pipeline_metadata.items() if v is not None}

    return {
        "schema_version": "1.0",
        "exported_at": now,
        "draft_id": draft_id,
        "slug": slug,
        "campaign_id": campaign_id,
        "project_id": project_id,
        "inputs": inputs,
        "config_snapshot": config_snapshot,
        "prompts": prompts,
        "outputs": outputs,
        "pipeline_metadata": pipeline_metadata,
        "gsc_performance": {
            "clicks": None,
            "impressions": None,
            "ctr": None,
            "position": None,
            "date_range": None,
        },
    }


class PublisherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Publisher")

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

        bucket = os.getenv("S3_BUCKET", "").strip()
        if not bucket:
            return AgentOutput(
                status="error",
                message="S3_BUCKET environment variable is required for export.",
            )

        prefix = (os.getenv("S3_PREFIX", "") or "").strip()
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        config = self.config or {}

        # Fetch ready pages
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
        self.logger.info(f"Exporting {len(batch)} pages to S3 (bucket=%s)...", bucket)

        published_count = 0
        errors = []
        for page in batch:
            try:
                meta = page.get("metadata") or {}
                slug = meta.get("slug") or _slugify(
                    (meta.get("keyword") or meta.get("h1_title") or page.get("name") or "").strip()
                )
                csv_content = _build_csv_row(page)
                json_payload = _build_training_payload(page, campaign, config, slug, project_id)
                PageExportTrainingPayload.model_validate(json_payload)

                csv_key = f"{prefix}{slug}.csv"
                json_key = f"{prefix}{slug}.json"

                csv_url = upload_bytes(bucket, csv_key, csv_content.encode("utf-8"), "text/csv")
                json_url = upload_bytes(
                    bucket,
                    json_key,
                    json.dumps(json_payload, ensure_ascii=False).encode("utf-8"),
                    "application/json",
                )

                # Update entity: status published, live_url = S3 URL (for analytics/frontend), s3 keys for audit
                new_meta = {**meta}
                new_meta["status"] = "published"
                new_meta["published_at"] = datetime.utcnow().isoformat() + "Z"
                new_meta["live_url"] = json_url
                new_meta["s3_csv_key"] = csv_key
                new_meta["s3_json_key"] = json_key
                new_meta["exported_at"] = new_meta["published_at"]

                memory.save_entity(Entity(**{**page, "metadata": new_meta}), project_id=project_id)
                published_count += 1
                self.logger.info(f"Exported '{page.get('name')}' -> s3://%s/%s", bucket, json_key)
            except Exception as e:
                self.logger.error(f"Publisher fail on '{page.get('name')}': {e}", exc_info=True)
                errors.append(f"Failed {page.get('name')}: {e}")

        return AgentOutput(
            status="success" if not errors else "partial",
            message=f"Exported {published_count} pages to S3.",
            data={"published": published_count, "errors": errors, "count": published_count},
        )
