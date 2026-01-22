# backend/modules/system_ops/agents/accountant.py
import logging
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class AccountantAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="AccountantAgent")
        self.logger = logging.getLogger("Apex.Accountant")
        
        # Hardcoded price list (in USD)
        self.PRICE_LIST = {
            "twilio_voice": 0.05,  # $0.05 per minute
            "gemini_token": 0.001,  # $0.001 per 1k tokens
        }
        
        # Default project limit (in USD)
        self.DEFAULT_PROJECT_LIMIT = 50.0

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Logs resource usage and checks if project has exceeded spending limit.
        
        Input params:
          - project_id: Project identifier
          - resource: Resource type (e.g., "twilio_voice", "gemini_token")
          - quantity: Quantity used (e.g., minutes, tokens)
        """
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
        
        # Get params
        resource_type = input_data.params.get("resource")
        quantity = input_data.params.get("quantity")
        
        if not resource_type:
            return AgentOutput(status="error", message="Missing 'resource' parameter.")
        
        # Validate resource_type is a string
        if not isinstance(resource_type, str):
            return AgentOutput(status="error", message="Invalid 'resource' parameter. Must be a string.")
        
        # Validate resource_type against whitelist (security: prevent injection)
        if resource_type not in self.PRICE_LIST:
            self.logger.warning(f"Unknown resource type: {resource_type}, rejecting request")
            return AgentOutput(
                status="error", 
                message=f"Invalid resource type: {resource_type}. Supported types: {', '.join(self.PRICE_LIST.keys())}"
            )
        
        if quantity is None:
            return AgentOutput(status="error", message="Missing 'quantity' parameter.")
        
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            return AgentOutput(status="error", message="Invalid 'quantity' parameter. Must be a number.")
        
        # Validate quantity is non-negative
        if quantity < 0:
            self.logger.warning(f"Negative quantity rejected: {quantity}")
            return AgentOutput(status="error", message="Invalid 'quantity' parameter. Must be non-negative.")
        
        # Calculate cost
        unit_price = self.PRICE_LIST.get(resource_type)
        
        # For gemini_token, quantity is in tokens, so divide by 1000
        if resource_type == "gemini_token":
            cost_usd = (quantity / 1000.0) * unit_price
        else:
            cost_usd = quantity * unit_price
        
        self.logger.info(f"💰 Logging usage: {resource_type} x {quantity} = ${cost_usd:.4f} for project {project_id}")
        
        # Ensure usage table exists
        try:
            memory.create_usage_table_if_not_exists()
        except Exception as e:
            self.logger.error(f"Failed to create usage table: {e}")
            return AgentOutput(status="error", message="Failed to initialize usage tracking.")
        
        # Log usage
        try:
            success = memory.log_usage(
                project_id=project_id,
                resource_type=resource_type,
                quantity=quantity,
                cost_usd=cost_usd
            )
            
            if not success:
                return AgentOutput(status="error", message="Failed to log usage.")
        except Exception as e:
            self.logger.error(f"Error logging usage: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Error logging usage: {str(e)}")
        
        # Get monthly spend
        try:
            monthly_spend = memory.get_monthly_spend(project_id)
        except Exception as e:
            self.logger.error(f"Error getting monthly spend: {e}", exc_info=True)
            monthly_spend = 0.0
        
        # Get project limit (could be from config, but using default for now)
        project_limit = self.DEFAULT_PROJECT_LIMIT
        
        # Check if limit exceeded
        if monthly_spend > project_limit:
            self.logger.warning(f"🚨 Project {project_id} exceeded spending limit: ${monthly_spend:.2f} > ${project_limit:.2f}")
            return AgentOutput(
                status="success",
                data={
                    "status": "PAUSED",
                    "monthly_spend": monthly_spend,
                    "project_limit": project_limit,
                    "cost_logged": cost_usd
                },
                message=f"Usage logged. Project paused due to spending limit exceeded (${monthly_spend:.2f} > ${project_limit:.2f})"
            )
        
        return AgentOutput(
            status="success",
            data={
                "status": "ACTIVE",
                "monthly_spend": monthly_spend,
                "project_limit": project_limit,
                "cost_logged": cost_usd
            },
            message=f"Usage logged successfully. Monthly spend: ${monthly_spend:.2f} / ${project_limit:.2f}"
        )
