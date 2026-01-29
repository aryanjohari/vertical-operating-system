# backend/modules/lead_gen/agents/scorer.py
import logging
import re
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class LeadScorerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="LeadScorerAgent")
        self.logger = logging.getLogger("Apex.LeadScorer")
        
        # Urgency keywords that indicate high-priority leads
        self.urgency_keywords = [
            "emergency", "now", "urgent", "asap", "leak", "arrested", 
            "burst", "broken", "immediate", "critical", "help needed"
        ]
        
        # Phone number pattern (basic validation)
        self.phone_pattern = re.compile(r'[\+]?[0-9]{8,15}')

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Scores a lead based on urgency, source, and contact information.
        Input params:
          - lead_id: The ID of the lead to score
        """
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        lead_id = input_data.params.get("lead_id")
        
        if not lead_id:
            return AgentOutput(status="error", message="Missing lead_id parameter.")
        
        try:
            # Fetch lead - get_entity doesn't exist, so we fetch and filter
            # For efficiency, we'll fetch a small limit and filter by ID
            all_leads = memory.get_entities(
                tenant_id=user_id,
                entity_type="lead",
                project_id=project_id,
                limit=1000
            )
            
            lead = None
            for l in all_leads:
                if l.get('id') == lead_id:
                    lead = l
                    break
            
            if not lead:
                return AgentOutput(status="error", message=f"Lead {lead_id} not found.")
            
            # Calculate score
            score = self._calculate_score(lead)
            
            # Determine priority
            if score >= 80:
                priority = "High"
            elif score >= 50:
                priority = "Medium"
            else:
                priority = "Low"
            
            # Update lead metadata
            metadata = lead.get('metadata', {}).copy()
            metadata['score'] = score
            metadata['priority'] = priority
            
            # Save updated metadata
            success = memory.update_entity(lead_id, metadata, self.user_id)
            
            if not success:
                return AgentOutput(status="error", message="Failed to update lead score.")
            
            self.logger.info(f"✅ Scored lead {lead_id}: {score}/100 ({priority})")
            
            return AgentOutput(
                status="success",
                data={
                    "lead_id": lead_id,
                    "score": score,
                    "priority": priority
                },
                message=f"Lead scored: {score}/100 ({priority} priority)"
            )
            
        except Exception as e:
            self.logger.error(f"❌ LeadScorerAgent Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))

    def _calculate_score(self, lead: dict) -> int:
        """
        Calculates lead score based on multiple factors.
        Returns score between 0-100.
        """
        score = 0
        metadata = lead.get('metadata', {})
        name = lead.get('name', '').lower()
        description = metadata.get('description', '').lower()
        source = metadata.get('source', '').lower()
        primary_contact = lead.get('primary_contact', '')
        
        # Combine text fields for urgency keyword search
        text_content = f"{name} {description}".lower()
        
        # +50 points: Urgency keywords found
        for keyword in self.urgency_keywords:
            if keyword in text_content:
                score += 50
                self.logger.debug(f"Urgency keyword '{keyword}' found: +50")
                break  # Only count once
        
        # +30 points: Phone number present
        if primary_contact and self.phone_pattern.search(primary_contact):
            score += 30
            self.logger.debug("Phone number detected: +30")
        elif metadata.get('data', {}).get('phone') or metadata.get('data', {}).get('phoneNumber'):
            # Check metadata.data for phone
            phone = metadata.get('data', {}).get('phone') or metadata.get('data', {}).get('phoneNumber', '')
            if self.phone_pattern.search(str(phone)):
                score += 30
                self.logger.debug("Phone number in metadata detected: +30")
        
        # +20 points: High-intent sources
        if source in ['web_form', 'voice_call', 'google_ads', 'wordpress_form']:
            score += 20
            self.logger.debug(f"High-intent source '{source}': +20")
        
        # -20 points: Cold sources (Sniper leads are less qualified)
        if source == 'sniper':
            score -= 20
            self.logger.debug("Cold source (sniper): -20")
        
        # Ensure score is within 0-100 range
        score = max(0, min(100, score))
        
        return score
