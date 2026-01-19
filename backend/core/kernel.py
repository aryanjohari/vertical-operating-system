# backend/core/kernel.py
import logging
import importlib
from typing import Dict
from backend.core.models import AgentInput, AgentOutput
from backend.core.registry import AgentRegistry
from backend.core.memory import memory  # <--- NEW: Access to DB

class Kernel:
    def __init__(self):
        self.logger = logging.getLogger("ApexKernel")
        self.agents: Dict[str, any] = {}
        
        # Dynamic Registration from Registry
        self.logger.info("⚡ Booting Apex Sovereign OS...")
        for key, (module_path, class_name) in AgentRegistry.DIRECTORY.items():
            self.register_agent(key, module_path, class_name)

    def register_agent(self, key: str, module_path: str, class_name: str):
        try:
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            self.agents[key] = agent_class()
            self.logger.info(f"✅ Registered Agent: {key}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load agent {key}: {e}")

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        self.logger.info(f"📡 Dispatching: {packet.task}")

        # --- 1. BYPASS RULE: System Agents ---
        system_tasks = ["onboarding", "scrape_site", "manager"]
        if packet.task in system_tasks:
            # Simple mapping
            if packet.task == "manager": agent_key = "manager"
            elif packet.task == "onboarding": agent_key = "onboarding"
            else: agent_key = "scout"
            
            if agent_key in self.agents:
                return await self.agents[agent_key].run(packet)

        # --- 2. SMART CONTEXT LOADING (The Fix) ---
        # Try to get niche from params, OR fetch from DB using user_id
        niche = packet.params.get("niche")
        
        if not niche and packet.user_id:
            # 🧠 SMART LOOKUP: Ask DB for this user's project
            project = memory.get_user_project(packet.user_id)
            if project:
                niche = project['project_id']
                self.logger.info(f"🔍 Auto-detected Project: {niche}")

        # Fallback if still missing
        if not niche:
            niche = "personal"

        # Load the Profile
        from backend.core.config import ConfigLoader
        user_config = ConfigLoader().load(niche)
        
        if "error" in user_config:
            return AgentOutput(status="error", message=f"Profile '{niche}' not found. Please run Onboarding.")

        # --- 3. INTELLIGENT ROUTING ---
        agent_key = None
        
        # Route: Scout (Lead Gen)
        if "scout" in packet.task or "find" in packet.task: 
            agent_key = "scout"
        
        # Route: SEO Keyword Agent (Strategy) <--- NEW BLOCK
        elif "keyword" in packet.task:
            agent_key = "seo_keyword"

        # Route: SEO Writer Agent
        elif "write" in packet.task: # <--- CATCHES "write_pages"
            agent_key = "seo_writer"

        elif "enhance_media" in packet.task:
            agent_key = "media"
            
        elif "enhance_utility" in packet.task:
            agent_key = "utility"
            
        elif "publish" in packet.task:
            agent_key = "publisher"

        # Route: Manager (Boss)
        elif packet.task == "manager":
            agent_key = "manager"
        
        # EXECUTION
        if agent_key and agent_key in self.agents:
            agent = self.agents[agent_key]
            agent.config = user_config # Inject Config
            return await agent.run(packet)
            
        return AgentOutput(status="error", message=f"Task {packet.task} not recognized.")

kernel = Kernel()