import os
import json
import re
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Critic")
        # Model selection for quality review (lightweight model for fast feedback)
        self.model = "gemini-2.5-flash-lite"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # 1. FETCH UNREVIEWED DRAFTS (Scoped to Project)
        drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        # Find drafts that have status 'draft' and no quality_score > 0
        to_review = [d for d in drafts if d['metadata'].get('status') == 'draft' and d['metadata'].get('quality_score', 0) == 0]
        
        if not to_review:
            return AgentOutput(status="complete", message="No drafts to review.")
        
        target = to_review[0]
        content = target['metadata'].get('content', '')
        
        # 2. KEYWORD PLACEMENT VALIDATION (Strict SEO Check)
        primary_keyword = target['metadata'].get('primary_keyword', '')
        context_keywords = target['metadata'].get('context_keywords', [])
        
        keyword_issues = []
        keyword_score = 100
        
        if primary_keyword:
            # Check primary keyword in H1
            h1_pattern = r'<h1[^>]*>(.*?)</h1>'
            h1_matches = re.findall(h1_pattern, content, re.IGNORECASE | re.DOTALL)
            if not h1_matches:
                keyword_issues.append("Missing H1 tag")
                keyword_score -= 30
            else:
                h1_text = h1_matches[0].strip()
                if primary_keyword.lower() not in h1_text.lower():
                    keyword_issues.append(f"Primary keyword '{primary_keyword}' not found in H1")
                    keyword_score -= 30
        
        if context_keywords:
            # Check context keywords in H2 tags and body
            h2_pattern = r'<h2[^>]*>(.*?)</h2>'
            h2_matches = re.findall(h2_pattern, content, re.IGNORECASE | re.DOTALL)
            
            context_found = 0
            for ctx_kw in context_keywords[:3]:  # Check first 3 context keywords
                ctx_lower = ctx_kw.lower()
                # Check in H2 tags
                for h2_text in h2_matches:
                    if ctx_lower in h2_text.lower():
                        context_found += 1
                        break
                # Also check in body content (not just H2)
                if ctx_lower in content.lower():
                    context_found += 0.5  # Partial credit for body presence
            
            if context_found < 2:
                keyword_issues.append(f"Only {context_found} context keywords found in H2/body (expected at least 2)")
                keyword_score -= 20
        
        keyword_validation = {
            "passed": len(keyword_issues) == 0,
            "issues": keyword_issues,
            "score": keyword_score
        }
        
        # 3. THE RUBRIC (Content Quality Check)
        prompt = f"""
        Act as a Strict Editor. Review this HTML content.
        Criteria:
        1. Is the phone number present?
        2. Are there H2/H3 tags?
        3. Does it sound robotic (words like 'delve', 'unleash', 'elevate')?
        4. Is the content natural and engaging?
        
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
            
            # 4. COMBINE SCORES (Keyword validation + Content quality)
            content_score = review['score']
            combined_score = (keyword_score * 0.4) + (content_score * 0.6)  # 40% keyword, 60% content
            combined_score = int(combined_score)
            
            # Both must pass
            keyword_pass = keyword_validation['passed']
            content_pass = review['pass']
            overall_pass = keyword_pass and content_pass and combined_score >= 80
            
            # 5. ACTION
            new_meta = target['metadata'].copy()
            new_meta['quality_score'] = combined_score
            new_meta['keyword_validation'] = keyword_validation
            new_meta['critic_notes'] = review['reason']
            
            if keyword_issues:
                new_meta['critic_notes'] += f" | Keyword Issues: {', '.join(keyword_issues)}"
            
            if overall_pass:
                new_meta['status'] = 'ready_for_media' # Passed! Next step.
                msg = f"✅ Passed {target['name']} (Score: {combined_score}, Keywords: {'✓' if keyword_pass else '✗'}, Content: {'✓' if content_pass else '✗'})"
            else:
                new_meta['status'] = 'rejected' # Needs rewrite
                msg = f"❌ Rejected {target['name']} (Score: {combined_score}, Keywords: {'✓' if keyword_pass else '✗'}, Content: {'✓' if content_pass else '✗'}): {review['reason']}"
            
            memory.update_entity(target['id'], new_meta)
            return AgentOutput(status="success", message=msg)
            
        except Exception as e:
            return AgentOutput(status="error", message=f"Critique Error: {e}")