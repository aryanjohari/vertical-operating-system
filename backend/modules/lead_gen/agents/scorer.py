# backend/modules/lead_gen/agents/scorer.py
import asyncio
import json
import logging
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway


class LeadScorerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="LeadScorerAgent")

    def _get_scoring_rules(self, config: dict) -> dict:
        """Resolve scoring rules from config (dual-path)."""
        return (
            config.get("lead_gen_integration", {}).get("scoring_rules", {})
            or config.get("modules", {}).get("lead_gen", {}).get("scoring_rules", {})
            or {}
        )

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Scores a lead using LLM Judge based on intent and urgency.
        Input params:
          - lead_id: The ID of the lead to score
        """
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")

        project_id = self.project_id
        user_id = self.user_id
        lead_id = input_data.params.get("lead_id")

        if not lead_id:
            return AgentOutput(status="error", message="Missing lead_id parameter.")

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        try:
            # 1. Fetch lead
            all_leads = memory.get_entities(
                tenant_id=user_id,
                entity_type="lead",
                project_id=project_id,
                limit=1000,
            )
            lead = next((l for l in all_leads if l.get("id") == lead_id), None)
            if not lead:
                return AgentOutput(status="error", message=f"Lead {lead_id} not found.")

            # 2. Build lead data for prompt
            metadata = lead.get("metadata", {})
            data = metadata.get("data", {})
            lead_data = {
                "name": lead.get("name", ""),
                "primary_contact": lead.get("primary_contact", ""),
                "description": metadata.get("description", ""),
                "source": metadata.get("source", ""),
                "phone": data.get("phone") or data.get("phoneNumber", ""),
                "email": data.get("email", ""),
                "message": data.get("message", ""),
            }

            # 3. Get scoring rules from config
            scoring_rules = self._get_scoring_rules(self.config)

            # 4. Build prompt and call LLM (non-blocking)
            user_prompt = f"""
Score this lead based on intent, urgency, and qualification.

LEAD DATA:
- Name: {lead_data['name']}
- Primary Contact: {lead_data['primary_contact']}
- Phone: {lead_data['phone']}
- Email: {lead_data['email']}
- Source: {lead_data['source']}
- Message/Description: {lead_data['message']}

SCORING RULES (if any): {json.dumps(scoring_rules)}

Return ONLY a JSON object with these exact keys:
- "score": integer 0-100 (higher = more qualified/urgent)
- "priority": one of "Low", "Medium", "High"
- "reasoning": brief explanation (1-2 sentences)
"""

            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt="You are a lead scoring judge. Return only valid JSON with keys: score (0-100), priority (Low/Medium/High), reasoning. No markdown, no extra text.",
                user_prompt=user_prompt,
                model="gemini-2.5-flash",
                temperature=0.3,
                max_retries=2,
            )

            # 5. Parse output (strip markdown fences)
            content_str = response_text.strip()
            if "```json" in content_str:
                content_str = content_str.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content_str:
                content_str = content_str.split("```", 1)[1].split("```", 1)[0].strip()
            result = json.loads(content_str)

            score = int(result.get("score", 50))
            priority = str(result.get("priority", "Medium"))
            if priority not in ("Low", "Medium", "High"):
                priority = "Medium"
            score = max(0, min(100, score))

            # 6. Update lead metadata
            new_meta = metadata.copy()
            new_meta["score"] = score
            new_meta["priority"] = priority
            new_meta["scoring_reasoning"] = result.get("reasoning", "")

            success = memory.update_entity(lead_id, new_meta, user_id)
            if not success:
                return AgentOutput(status="error", message="Failed to update lead score.")

            self.logger.info(f"Scored lead {lead_id}: {score}/100 ({priority})")
            return AgentOutput(
                status="success",
                data={
                    "lead_id": lead_id,
                    "score": score,
                    "priority": priority,
                },
                message=f"Lead scored: {score}/100 ({priority} priority)",
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"LLM returned invalid JSON: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to parse LLM response: {e}")
        except Exception as e:
            self.logger.error(f"LeadScorerAgent Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))
