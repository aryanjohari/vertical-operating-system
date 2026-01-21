import os
import json
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Critic")
        # Model selection for quality review (lightweight model for fast feedback)
        self.model = "gemini-2.5-flash-lite"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # Get project context
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
        project_id = project['project_id']
        
        # 1. FETCH UNREVIEWED DRAFTS (Scoped to Project)
        drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        # Find drafts that have status 'draft' and no quality_score > 0
        to_review = [d for d in drafts if d['metadata'].get('status') == 'draft' and d['metadata'].get('quality_score', 0) == 0]
        
        if not to_review:
            return AgentOutput(status="complete", message="No drafts to review.")
        
        target = to_review[0]
        content = target['metadata'].get('content', '')
        
        # 2. THE RUBRIC
        prompt = f"""
        Act as a Strict Editor. Review this HTML content.
        Criteria:
        1. Is the phone number present?
        2. Are there H2/H3 tags?
        3. Does it sound robotic (words like 'delve', 'unleash', 'elevate')?
        
        Output JSON: {{ "score": 0-100, "reason": "...", "pass": boolean }}
        Fail if score < 80.
        
        CONTENT:
        {content[:10000]} 
        """
        
        try:
            response_text = llm_gateway.generate_content(
                system_prompt="You are a strict content editor. Always return valid JSON with 'score', 'reason', and 'pass' fields.",
                user_prompt=prompt,
                model=self.model,
                temperature=0.3,  # Lower temperature for consistent scoring
                max_retries=3
            )
            review = json.loads(response_text.replace('```json','').replace('```',''))
            
            # 3. ACTION
            new_meta = target['metadata'].copy()
            new_meta['quality_score'] = review['score']
            new_meta['critic_notes'] = review['reason']
            
            if review['pass']:
                new_meta['status'] = 'ready_for_media' # Passed! Next step.
                msg = f"✅ Passed {target['name']} ({review['score']})"
            else:
                new_meta['status'] = 'rejected' # Needs rewrite
                msg = f"❌ Rejected {target['name']} ({review['score']}): {review['reason']}"
            
            memory.update_entity(target['id'], new_meta)
            return AgentOutput(status="success", message=msg)
            
        except Exception as e:
            return AgentOutput(status="error", message=f"Critique Error: {e}")