# backend/modules/system_ops/manager.py
import logging
import asyncio
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class SystemOpsManager(BaseAgent):
    def __init__(self):
        super().__init__(name="SystemOpsManager")
        self.logger = logging.getLogger("Apex.SystemOpsManager")
        
        # Valid actions for this manager
        self.VALID_ACTIONS = ["run_diagnostics"]

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        The Orchestrator for System Operations.
        
        Input params:
          - action: "run_diagnostics" (triggers health check)
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
        
        # Validate config (if available)
        if self.config:
            if not self.config.get('modules', {}).get('system_ops', {}).get('enabled', True):
                return AgentOutput(status="error", message="System Ops module is disabled in DNA.")
        
        # Get and validate action parameter
        action = input_data.params.get("action", "run_diagnostics")
        
        # Validate action is in allowed list
        if action not in self.VALID_ACTIONS:
            self.logger.warning(f"Invalid action requested: {action}")
            return AgentOutput(
                status="error",
                message=f"Unknown action: {action}. Supported actions: {', '.join(self.VALID_ACTIONS)}"
            )
        
        self.logger.info(f"💼 SystemOpsManager executing action: {action} for {project_id}")
        
        try:
            # Action: Run Diagnostics (Health Check)
            if action == "run_diagnostics":
                self.logger.info("🔍 Deploying Sentinel Agent for health check...")
                
                # Lazy import to avoid circular dependency
                from backend.core.kernel import kernel
                
                try:
                    result = await asyncio.wait_for(
                        kernel.dispatch(
                            AgentInput(
                                task="health_check",
                                user_id=user_id,
                                params={"project_id": project_id}
                            )
                        ),
                        timeout=30  # 30 seconds max for health check
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Health check timed out after 30 seconds")
                    return AgentOutput(status="error", message="Health check timed out.")
                except Exception as e:
                    self.logger.error(f"❌ Health check failed: {e}", exc_info=True)
                    return AgentOutput(status="error", message=f"Health check failed: {str(e)}")
                
                return AgentOutput(
                    status="success",
                    data=result.data,
                    message="Health check completed."
                )
            
            # Unknown action (should not reach here due to validation above, but kept for safety)
            else:
                return AgentOutput(
                    status="error",
                    message=f"Unknown action: {action}. Supported actions: {', '.join(self.VALID_ACTIONS)}"
                )
        
        except Exception as e:
            self.logger.error(f"❌ SystemOpsManager Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))
