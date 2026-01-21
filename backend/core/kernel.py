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
        try:
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            self.agents[key] = agent_class()
            self.logger.info(f"✅ Registered Agent: {key}")
        except ModuleNotFoundError as e:
            self.logger.error(f"❌ Module NOT FOUND for {key} at {module_path}: {e}")
        except AttributeError as e:
            self.logger.error(f"❌ Class {class_name} NOT FOUND in {module_path}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load agent {key}: {e}")

    def _resolve_agent(self, task: str) -> Optional[str]:
        """
        Smart Routing: Maps a task name to a registered agent key.
        Priority 1: Exact Match (e.g. task='manager' -> agent='manager')
        Priority 2: Prefix Match (e.g. task='scout_anchors' -> agent='scout')
        """
        self.logger.debug(f"Resolving agent for task: {task}")
        
        # 1. Exact Match
        if task in self.agents:
            self.logger.debug(f"Exact match found: {task}")
            return task
        
        # 2. Prefix/Fuzzy Match (Dynamic)
        # We loop through registered agents to see if the task starts with their key
        # e.g. "seo_writer" matches "write_pages"?? No, that relies on naming convention.
        # Let's rely on the Registry keys being the prefix or substring.
        for agent_key in self.agents:
            if agent_key in task:
                self.logger.debug(f"Prefix match found: {agent_key} for task {task}")
                return agent_key
        
        self.logger.debug(f"No agent match found for task: {task}")
        return None

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        """
        The Kernel's dispatch method - the central routing hub.
        
        Data Flow:
        1. Receives AgentInput packet from /api/run endpoint (main.py)
        2. Resolves agent via Registry (maps task name to agent class)
        3. Loads DNA config (project-specific configuration) if needed
        4. Injects config into agent instance
        5. Executes agent.run() which:
           - Saves "start" snapshot
           - Calls agent._execute() (agent-specific logic)
           - Saves "end" snapshot
           - Returns AgentOutput
        6. Returns AgentOutput back to /api/run endpoint
        7. Endpoint wraps it in safety net JSON and returns to frontend
        
        This is the "brain" that connects the frontend request to the correct agent.
        """
        self.logger.info(f"📡 Dispatching Task: {packet.task} | User: {packet.user_id}")

        # --- 1. RESOLVE AGENT ---
        agent_key = self._resolve_agent(packet.task)
        
        if not agent_key:
            self.logger.error(f"⛔ No agent found for task: {packet.task}")
            return AgentOutput(
                status="error", 
                message=f"System could not resolve an agent for task '{packet.task}'. Check Registry."
            )

        # --- 2. BYPASS RULE: System Agents (No DNA Needed) ---
        system_agents = ["onboarding", "scout", "manager"]
        if agent_key in system_agents and packet.task in ["scrape_site", "onboarding", "manager"]:
             return await self.agents[agent_key].run(packet)

        # --- 3. SMART CONTEXT LOADING (DNA) ---
        # Detect Project ID from Params OR Memory
        niche = packet.params.get("niche") or packet.params.get("project_id")
        
        if not niche and packet.user_id:
            # Auto-lookup active project
            try:
                project = memory.get_user_project(packet.user_id)
                if project:
                    niche = project['project_id']
                    self.logger.info(f"🔍 Context Loaded: {niche}")
                else:
                    # No project found - fail explicitly instead of fallback
                    self.logger.error(f"No project found for user {packet.user_id}")
                    return AgentOutput(
                        status="error",
                        message=f"No active project found for user. Please create a project first."
                    )
            except Exception as e:
                self.logger.error(f"Failed to load user project for {packet.user_id}: {e}")
                return AgentOutput(
                    status="error",
                    message=f"Failed to load user project: {str(e)}"
                )

        if not niche:
            # Fail explicitly - no project_id and no auto-lookup
            self.logger.error(f"No niche/project_id specified for user {packet.user_id}")
            return AgentOutput(
                status="error",
                message="No project_id specified. Please provide a valid project_id in params."
            )

        # CRITICAL: Verify project ownership before loading config
        if not memory.verify_project_ownership(packet.user_id, niche):
            self.logger.error(f"Project ownership verification failed: user={packet.user_id}, project={niche}")
            return AgentOutput(
                status="error",
                message=f"Project '{niche}' not found or access denied."
            )

        # Load DNA Profile
        from backend.core.config import ConfigLoader
        try:
            user_config = ConfigLoader().load(niche)
            
            # Check for config errors
            if isinstance(user_config, dict) and "error" in user_config:
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
        
        # Inject Context into Agent
        agent = self.agents[agent_key]
        agent.config = user_config
        
        # --- 4. EXECUTE ---
        return await agent.run(packet)

# Singleton Kernel
kernel = Kernel()