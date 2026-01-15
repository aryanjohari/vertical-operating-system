# backend/core/kernel.py
import logging
import importlib
from typing import Dict, Optional
from backend.core.models import AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.config import ConfigLoader
from backend.core.agent_base import BaseAgent

class Kernel:
    def __init__(self):
        self.logger = logging.getLogger("ApexKernel")
        logging.basicConfig(level=logging.INFO)
        
        self.logger.info("⚡ Booting Apex Sovereign OS...")
        
        # 1. Initialize Subsystems
        self.memory = memory  # The Librarian (SQL + Vector)
        self.config_loader = ConfigLoader() # The DNA Reader
        self.agents: Dict[str, BaseAgent] = {} # The Roster
        
        # 2. Auto-Register Core Agents (We will build these next)
        # self.register_agent("scout", "backend.agents.scout", "ScoutAgent")
        
    def register_agent(self, key: str, module_path: str, class_name: str):
        """Dynamically loads agent code so we don't need huge imports."""
        try:
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            self.agents[key] = agent_class()
            self.logger.info(f"✅ Registered Agent: {key}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load agent {key}: {e}")

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        """
        The Main Event Loop.
        1. Logs the request.
        2. Loads the correct User Profile (RLS).
        3. Routes to the correct Agent.
        """
        self.logger.info(f"Command: {packet.task} | User: {packet.user_id}")
        
        # A. PERMISSION & CONTEXT CHECK
        # We assume the 'params' has a 'niche' or we default to 'personal'
        niche = packet.params.get("niche", "personal")
        user_config = self.config_loader.load(niche)
        
        if "error" in user_config:
            return AgentOutput(
                status="error", 
                message=f"Profile '{niche}' not found. Run Strategist first."
            )

        # B. ROUTING LOGIC (Simple Verb Matching)
        agent_key = None
        if "scrape" in packet.task or "find" in packet.task:
            agent_key = "scout"
        elif "write" in packet.task or "blog" in packet.task:
            agent_key = "writer"
        elif "strategy" in packet.task:
            agent_key = "strategist"

        # C. EXECUTION
        if agent_key and agent_key in self.agents:
            agent = self.agents[agent_key]
            # Inject the fresh config into the agent before running
            agent.config = user_config 
            return await agent.run(packet)
        else:
            return AgentOutput(
                status="error", 
                message=f"No agent found for task: {packet.task}"
            )

# Create the Singleton
kernel = Kernel()