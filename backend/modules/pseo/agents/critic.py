# backend/modules/pseo/agents/critic.py
import asyncio
import json
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway


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

        # 2. FETCH WORK ITEM (Find 'draft' drafts - Titanium status)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        to_review = [
            d for d in all_drafts
            if d.get("metadata", {}).get("campaign_id") == campaign_id
            and d.get("metadata", {}).get("status") == "draft"
        ]

        if not to_review:
            return AgentOutput(status="complete", message="No drafts waiting for review.")

        target_draft = to_review[0]
        draft_meta = target_draft.get("metadata", {})
        # Support both content and html_content for compatibility
        html_content = draft_meta.get("content") or draft_meta.get("html_content", "")
        keyword = draft_meta.get("keyword", "")

        self.logger.info(f"CRITIC: Reviewing draft for '{keyword}'")

        # 3. CONSTRUCT EVALUATION PROMPT
        prompt = f"""
        ACT AS: Senior Compliance Officer & Editor.
        TASK: Pass or Fail this web page draft.

        --- THE RULES (STRICT) ---
        1. **Brand Voice:** Must be "{brand_voice}".
        2. **Local Accuracy:** If an Anchor Location ({draft_meta.get('anchor_used', 'General City')}) was assigned, it MUST be mentioned in the text.
        3. **Forbidden Topics:** The text MUST NOT promise or discuss: {forbidden_topics}.
        4. **Structure:** Must contain an <h1> and placeholders like {{{{form_capture}}}}.

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
