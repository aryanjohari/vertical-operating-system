# backend/modules/pseo/agents/critic.py
import asyncio
import json
import re
from typing import List, Dict, Any, Tuple
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway


def _run_deterministic_structure_checks(
    html_content: str,
    draft_meta: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[bool, str]:
    """Run deterministic checks (placeholders, h1, form, tel, metadata). Returns (passed, failure_reason). Schema/JSON-LD is injected later by Utility."""
    critic_cfg = config.get("critic") or config.get("modules", {}).get("pseo", {}).get("critic") or {}
    required_placeholders = critic_cfg.get("required_placeholders") or ["form_capture", "image_main"]
    check_form_webhook = critic_cfg.get("check_form_webhook", False)
    expected_webhook = critic_cfg.get("form_webhook_path") or "/api/webhooks/lead"
    content_lower = html_content.lower()

    if "<h1>" not in content_lower and "<h1 " not in content_lower:
        return False, "Missing required <h1> tag."

    if "form_capture" in required_placeholders:
        has_form_placeholder = "{{form_capture}}" in html_content
        has_form_injected = "<form" in content_lower or "conversion-block" in content_lower
        if not has_form_placeholder and not has_form_injected:
            return False, "Missing required placeholder {{form_capture}} or form block."
        if check_form_webhook and (has_form_injected or "action=" in content_lower):
            if expected_webhook not in html_content and "action=" in content_lower:
                if "/api/webhooks" not in html_content:
                    return False, f"Form action should point to webhook (e.g. {expected_webhook})."

    if "image_main" in required_placeholders:
        has_image_placeholder = "{{image_main}}" in html_content
        has_image_injected = "<img" in content_lower and "src=" in content_lower
        if not has_image_placeholder and not has_image_injected:
            return False, "Missing required placeholder {{image_main}} or image tag."

    if critic_cfg.get("check_tel_link"):
        destination_phone = (
            (config.get("modules") or {}).get("lead_gen", {}).get("sales_bridge", {}).get("destination_phone")
            or (config.get("lead_gen_integration") or {}).get("destination_phone")
            or ""
        )
        if destination_phone and destination_phone != "REQUIRED" and "tel:" not in html_content:
            return False, "Missing tel: link for destination_phone."

    if critic_cfg.get("check_metadata", True):
        if not (draft_meta.get("meta_title") or "").strip():
            return False, "Missing meta_title."
        if not (draft_meta.get("meta_description") or "").strip():
            return False, "Missing meta_description."

    return True, ""


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Critic")
        self.model = "gemini-2.5-flash-lite"

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

        # Load Configuration (identity from injected config)
        brand_brain = self.config.get("brand_brain", {})
        forbidden_topics = brand_brain.get("forbidden_topics", [])
        brand_voice = brand_brain.get("voice_tone", "Professional")

        # 2. FETCH WORK ITEM (Find 'draft' or 'rejected' drafts; optional draft_id for row control)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        to_review = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") in ("draft", "rejected")
        ]
        draft_id_param = input_data.params.get("draft_id")
        if draft_id_param:
            to_review = [d for d in to_review if d.get("id") == draft_id_param]
        if not to_review:
            return AgentOutput(status="complete", message="No drafts waiting for review.")

        target_draft = to_review[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content for compatibility
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"CRITIC: Reviewing draft for '{keyword}'")

        # 2b. Deterministic structure checks (before LLM)
        config = self.config or {}
        struct_ok, struct_reason = _run_deterministic_structure_checks(html_content, draft_meta, config)
        if not struct_ok:
            target_draft["metadata"]["status"] = "rejected"
            target_draft["metadata"]["qa_score"] = 0
            target_draft["metadata"]["qa_notes"] = f"Structure check failed: {struct_reason}"
            memory.save_entity(Entity(**target_draft), project_id=project_id)
            self.logger.warning(f"FAILED (structure): {keyword} - {struct_reason}")
            return AgentOutput(
                status="success",
                message=f"Draft rejected for '{keyword}': {struct_reason}",
                data={"draft_id": target_draft["id"], "score": 0, "failure_reason": struct_reason},
            )

        critic_cfg = config.get("critic") or config.get("modules", {}).get("pseo", {}).get("critic") or {}
        run_llm_after_checks = critic_cfg.get("run_llm_after_checks", True)
        if not run_llm_after_checks:
            target_draft["metadata"]["status"] = "validated"
            target_draft["metadata"]["qa_score"] = 10
            target_draft["metadata"]["qa_notes"] = "Deterministic checks passed (LLM skipped)."
            memory.save_entity(Entity(**target_draft), project_id=project_id)
            return AgentOutput(
                status="success",
                message=f"Draft validated for '{keyword}' (structure only)",
                data={"draft_id": target_draft["id"], "score": 10, "next_step": "Ready for Librarian"},
            )

        # 3. CONSTRUCT EVALUATION PROMPT
        prompt = f"""
        ACT AS: Senior Compliance Officer & Editor.
        TASK: Pass or Fail this web page draft.

        --- THE RULES (STRICT) ---
        1. **Brand Voice:** Must be "{brand_voice}".
        2. **Local Accuracy:** If an Anchor Location ({draft_meta.get('anchor_used', 'General City')}) was assigned, it must be naturally mentioned in the text (referenced in a natural way, not necessarily the exact config string).
        3. **Forbidden Topics:** The text MUST NOT promise or discuss: {forbidden_topics}. If you fail the draft for a Forbidden Topic, you MUST quote the exact sentence from the draft in your reason. Do not fail unless there is an explicit mention.
        4. **Structure:** Must contain an <h1> and placeholders like {{{{form_capture}}}}.
        5. **Formatting:** Fail the draft if there are massive walls of text. Paragraphs over 100 words should be penalized.

        --- THE DRAFT CONTENT ---
        {html_content[:3000]} ... (truncated)

        --- EVALUATION FORMAT ---
        Return ONLY a JSON object:
        {{
            "status": "PASS" | "FAIL",
            "score": <0-10>,
            "reason": "Short explanation of failure or success",
            "fix_suggestions": "If fail, what needs fixing?"
        }}
        """

        # 4. RUN AUDIT (use llm_gateway via asyncio.to_thread)
        try:
            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt="You are a strict content editor. Return only valid JSON with status, score, reason, fix_suggestions.",
                user_prompt=prompt,
                model=self.model,
                temperature=0.3,
                max_retries=3,
            )
            content = response_text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            content = content.strip()
            result = json.loads(content)
        except Exception as e:
            self.logger.error(f"Critic LLM Failed: {e}")
            return AgentOutput(status="error", message=f"Critic failed to parse result: {e}")

        # 5. EXECUTE JUDGMENT
        status = result.get("status", "FAIL").upper()
        score = result.get("score", 0)
        reason = result.get("reason", "")

        if status == "PASS" and score >= 7:
            target_draft["metadata"]["status"] = "validated"
            target_draft["metadata"]["qa_score"] = score
            target_draft["metadata"]["qa_notes"] = reason
            memory.save_entity(Entity(**target_draft), project_id=project_id)
            self.logger.info(f"PASSED: {keyword} (Score: {score})")
            return AgentOutput(
                status="success",
                message=f"Draft validated for '{keyword}'",
                data={"draft_id": target_draft["id"], "score": score, "next_step": "Ready for Librarian"},
            )
        else:
            target_draft["metadata"]["status"] = "rejected"
            target_draft["metadata"]["qa_score"] = score
            target_draft["metadata"]["qa_notes"] = f"FAILED: {reason}"
            memory.save_entity(Entity(**target_draft), project_id=project_id)
            self.logger.warning(f"FAILED: {keyword} - {reason}")
            return AgentOutput(
                status="success",
                message=f"Draft rejected for '{keyword}': {reason}",
                data={"draft_id": target_draft["id"], "score": score, "failure_reason": reason},
            )
