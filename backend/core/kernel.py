# backend/core/kernel.py
import logging
import importlib
from typing import Dict, Optional
from backend.core.models import AgentInput, AgentOutput
from backend.core.registry import AgentRegistry
from backend.core.memory import memory

class Kernel:
    def __init__(self):
        self.logger = logging.getLogger("ApexKernel")
        self.agents: Dict[str, any] = {}
        
        # Dynamic Registration from Registry
        self.logger.info("⚡ Booting Apex Sovereign OS...")
        self._boot_agents()

    def _boot_agents(self):
        """Dynamically loads all agents defined in the Registry."""
        for key, (module_path, class_name) in AgentRegistry.DIRECTORY.items():
            self.register_agent(key, module_path, class_name)

    def register_agent(self, key: str, module_path: str, class_name: str):
        """
        Register an agent with validation and error handling.
        
        Validates:
        - Module path is whitelisted (backend.modules.*)
        - Class exists and inherits from BaseAgent
        - Agent can be instantiated
        """
        try:
            # Validate module path for security
            if not isinstance(module_path, str) or not module_path:
                raise ValueError(f"Invalid module_path for agent {key}: must be non-empty string")
            
            # Whitelist module paths (security: prevent importing dangerous modules)
            if not module_path.startswith("backend.modules."):
                raise ValueError(f"Module path must start with 'backend.modules.': {module_path}")
            
            # Validate key format
            if not isinstance(key, str) or not key:
                raise ValueError(f"Invalid agent key: must be non-empty string")
            if not key.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid agent key format (alphanumeric, _, - only): {key}")
            
            # Validate class name
            if not isinstance(class_name, str) or not class_name:
                raise ValueError(f"Invalid class_name for agent {key}: must be non-empty string")
            
            # Import module
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                self.logger.error(f"❌ Module NOT FOUND for {key} at {module_path}: {e}")
                return  # Skip this agent, continue booting
            except ImportError as e:
                self.logger.error(f"❌ Import error for {key} at {module_path}: {e}")
                return  # Skip this agent
            
            # Get agent class
            try:
                agent_class = getattr(module, class_name)
            except AttributeError as e:
                self.logger.error(f"❌ Class {class_name} NOT FOUND in {module_path}: {e}")
                return  # Skip this agent
            
            # Validate agent class inherits from BaseAgent
            from backend.core.agent_base import BaseAgent
            if not issubclass(agent_class, BaseAgent):
                self.logger.error(f"❌ Class {class_name} must inherit from BaseAgent")
                return  # Skip this agent
            
            # Validate agent has required _execute method
            if not hasattr(agent_class, '_execute'):
                self.logger.error(f"❌ Class {class_name} missing required _execute method")
                return  # Skip this agent
            
            # Instantiate agent
            try:
                agent_instance = agent_class()
                self.agents[key] = agent_instance
                self.logger.info(f"✅ Registered Agent: {key} ({module_path}.{class_name})")
            except Exception as e:
                self.logger.error(f"❌ Failed to instantiate agent {key}: {e}", exc_info=True)
                return  # Skip this agent
                
        except ValueError as e:
            self.logger.error(f"❌ Validation error for agent {key}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Unexpected error loading agent {key}: {e}", exc_info=True)

    def _resolve_agent(self, task: str) -> Optional[str]:
        """
        Smart Routing: Maps a task name to a registered agent key.
        Priority 1: Exact Match (e.g. task='onboarding' -> agent='onboarding')
        Priority 2: Prefix Match (e.g. task='onboarding_start' -> agent='onboarding')
        
        Uses strict prefix matching to avoid collisions.
        """
        if not task or not isinstance(task, str):
            self.logger.warning(f"Invalid task name: {task}")
            return None
        
        # Validate task format (security: prevent injection)
        if len(task) > 100:  # Reasonable length limit
            self.logger.warning(f"Task name too long: {len(task)} chars")
            return None
        
        self.logger.debug(f"Resolving agent for task: {task}")
        
        # 1. Exact Match (highest priority)
        if task in self.agents:
            self.logger.debug(f"Exact match found: {task}")
            return task
        
        # 2. Prefix Match (strict: task must start with agent_key + "_")
        # This prevents collisions like "write" matching "rewrite_pages"
        for agent_key in sorted(self.agents.keys(), key=len, reverse=True):  # Longest first
            if task.startswith(agent_key + "_"):
                self.logger.debug(f"Prefix match found: {agent_key} for task {task}")
                return agent_key
        
        self.logger.debug(f"No agent match found for task: {task}")
        return None

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        """
        The Kernel's dispatch method - the central routing hub.
        
        Data Flow:
        1. Receives AgentInput packet from /api/run endpoint (main.py)
        2. Validates task and resolves agent via Registry
        3. Checks if system agent (bypasses DNA loading)
        4. For regular agents: Loads DNA config and verifies project ownership
        5. Injects config into agent instance
        6. Executes agent.run() which calls agent._execute()
        7. Returns AgentOutput back to /api/run endpoint
        
        This is the "brain" that connects the frontend request to the correct agent.
        """
        try:
            # Validate input packet
            if not packet or not hasattr(packet, 'task'):
                self.logger.error("Invalid AgentInput packet received")
                return AgentOutput(
                    status="error",
                    message="Invalid request packet."
                )
            
            # Validate task name
            if not packet.task or not isinstance(packet.task, str):
                self.logger.error(f"Invalid task name: {packet.task}")
                return AgentOutput(
                    status="error",
                    message="Invalid task name provided."
                )
            
            # Validate user_id
            if not packet.user_id or not isinstance(packet.user_id, str):
                self.logger.error(f"Invalid user_id: {packet.user_id}")
                return AgentOutput(
                    status="error",
                    message="Invalid user identifier."
                )
            
            self.logger.info(f"📡 Dispatching Task: {packet.task} | User: {packet.user_id}")

            # --- 1. RESOLVE AGENT ---
            agent_key = self._resolve_agent(packet.task)
            
            if not agent_key:
                self.logger.error(f"⛔ No agent found for task: {packet.task}")
                return AgentOutput(
                    status="error", 
                    message=f"System could not resolve an agent for task '{packet.task}'. Check Registry."
                )
            
            # Validate agent exists in registry (double-check)
            if agent_key not in self.agents:
                self.logger.error(f"⛔ Agent {agent_key} not found in loaded agents (registration may have failed)")
                return AgentOutput(
                    status="error",
                    message=f"Agent '{agent_key}' is not available. Registration may have failed."
                )

            # --- 2. BYPASS RULE: System Agents (No DNA Needed) ---
            # System agents bypass config loading because they don't need project context.
            # - onboarding: Creates the DNA config
            # - health_check: System-wide health monitoring (no project needed)
            # - cleanup: System-wide maintenance (no project needed)
            # - log_usage: System-wide usage tracking (uses hardcoded pricing, no config needed, but needs project_id/user_id)
            system_agents = ["onboarding", "health_check", "cleanup", "log_usage"]
            # System agents that need context injection (project_id/user_id) but not DNA config
            system_agents_with_context = ["log_usage"]
            
            if agent_key in system_agents:
                self.logger.debug(f"System agent detected: {agent_key} - bypassing DNA loading")
                
                # Some system agents still need project_id/user_id injected (but not DNA config)
                if agent_key in system_agents_with_context:
                    # Extract project_id from params
                    niche = None
                    if packet.params:
                        niche = packet.params.get("niche") or packet.params.get("project_id")
                    
                    if not niche:
                        self.logger.error(f"No project_id specified for system agent {agent_key}")
                        return AgentOutput(
                            status="error",
                            message="No project_id specified. Please provide a valid project_id in params."
                        )
                    
                    # Validate project_id format
                    if not isinstance(niche, str) or not niche:
                        self.logger.error(f"Invalid project_id format: {niche}")
                        return AgentOutput(
                            status="error",
                            message="Invalid project identifier format."
                        )
                    
                    import re
                    if not re.match(r'^[a-zA-Z0-9_-]+$', niche):
                        self.logger.error(f"Project_id contains invalid characters: {niche}")
                        return AgentOutput(
                            status="error",
                            message="Invalid project identifier format. Only alphanumeric characters, underscores, and hyphens allowed."
                        )
                    
                    # Verify project ownership
                    try:
                        if not memory.verify_project_ownership(packet.user_id, niche):
                            self.logger.error(f"Project ownership verification failed: user={packet.user_id}, project={niche}")
                            return AgentOutput(
                                status="error",
                                message=f"Project '{niche}' not found or access denied."
                            )
                    except Exception as e:
                        self.logger.error(f"Project ownership verification error: {e}", exc_info=True)
                        return AgentOutput(
                            status="error",
                            message="Failed to verify project ownership."
                        )
                    
                    # Inject context (but not config - system agents don't need DNA)
                    agent = self.agents[agent_key]
                    agent.project_id = niche
                    agent.user_id = packet.user_id
                    agent.config = {}  # Empty config for system agents
                    self.logger.debug(f"Injected context for system agent {agent_key}: project={niche}, user={packet.user_id}")
                
                try:
                    return await self.agents[agent_key].run(packet)
                except Exception as e:
                    self.logger.error(f"System agent {agent_key} execution failed: {e}", exc_info=True)
                    return AgentOutput(
                        status="error",
                        message=f"System agent '{agent_key}' execution failed: {str(e)}"
                    )

            # --- 3. SMART CONTEXT LOADING (DNA) ---
            # Regular agents need project context (DNA config)
            # Detect Project ID from Params OR Memory
            niche = None
            if packet.params:
                niche = packet.params.get("niche") or packet.params.get("project_id")
            
            if not niche and packet.user_id:
                # Auto-lookup active project
                try:
                    project = memory.get_user_project(packet.user_id)
                    if project:
                        niche = project.get('project_id')
                        if niche:
                            self.logger.info(f"🔍 Context Loaded from memory: {niche}")
                except Exception as e:
                    self.logger.error(f"Failed to load user project for {packet.user_id}: {e}", exc_info=True)
                    return AgentOutput(
                        status="error",
                        message=f"Failed to load user project: {str(e)}"
                    )

            if not niche:
                # Fail explicitly - no project_id and no auto-lookup
                self.logger.error(f"No niche/project_id specified for user {packet.user_id}")
                return AgentOutput(
                    status="error",
                    message="No project_id specified. Please provide a valid project_id in params or create a project first."
                )

            # Validate project_id format (security: prevent path traversal)
            if not isinstance(niche, str) or not niche:
                self.logger.error(f"Invalid project_id format: {niche}")
                return AgentOutput(
                    status="error",
                    message="Invalid project identifier format."
                )
            
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', niche):
                self.logger.error(f"Project_id contains invalid characters: {niche}")
                return AgentOutput(
                    status="error",
                    message="Invalid project identifier format. Only alphanumeric characters, underscores, and hyphens allowed."
                )

            # CRITICAL: Verify project ownership before loading config
            try:
                if not memory.verify_project_ownership(packet.user_id, niche):
                    self.logger.error(f"Project ownership verification failed: user={packet.user_id}, project={niche}")
                    return AgentOutput(
                        status="error",
                        message=f"Project '{niche}' not found or access denied."
                    )
            except Exception as e:
                self.logger.error(f"Project ownership verification error: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message="Failed to verify project ownership."
                )

            # Extract campaign_id from params if present
            campaign_id = packet.params.get("campaign_id")
            
            # Load DNA Profile (and campaign config if campaign_id provided)
            from backend.core.config import ConfigLoader
            try:
                config_loader = ConfigLoader()
                user_config = config_loader.load(niche, campaign_id=campaign_id)
                
                # Check for config errors
                if not isinstance(user_config, dict):
                    self.logger.error(f"Config loader returned non-dict for {niche}")
                    return AgentOutput(
                        status="error",
                        message=f"Invalid configuration format for project '{niche}'."
                    )
                
                if "error" in user_config:
                    error_msg = user_config.get("error", "Unknown config error")
                    self.logger.error(f"Config loading failed for {niche}: {error_msg}")
                    return AgentOutput(
                        status="error",
                        message=f"Configuration error for project '{niche}': {error_msg}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to load config for {niche}: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message=f"Failed to load configuration for project '{niche}': {str(e)}"
                )
            
            # Inject Context into Agent (Titanium Standard)
            agent = self.agents[agent_key]
            agent.config = user_config
            agent.project_id = niche
            agent.user_id = packet.user_id
            agent.campaign_id = campaign_id  # Inject campaign_id if present
            
            # Validate injected context
            if not agent.config or not isinstance(agent.config, dict):
                self.logger.error(f"Failed to inject valid config for agent {agent_key}")
                return AgentOutput(
                    status="error",
                    message="Configuration injection failed."
                )
            
            self.logger.debug(f"Injected context for {agent_key}: project={niche}, user={packet.user_id}")
            
            # --- 4. EXECUTE ---
            try:
                return await agent.run(packet)
            except Exception as e:
                self.logger.error(f"Agent {agent_key} execution failed: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message=f"Agent '{agent_key}' execution failed: {str(e)}"
                )
                
        except Exception as e:
            self.logger.error(f"Unexpected error in kernel dispatch: {e}", exc_info=True)
            return AgentOutput(
                status="error",
                message="Internal system error during dispatch. Please try again."
            )

# Singleton Kernel
kernel = Kernel()