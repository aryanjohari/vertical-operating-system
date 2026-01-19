# backend/core/kernel.py
import logging
import importlib
from typing import Dict
from backend.core.models import AgentInput, AgentOutput
from backend.core.registry import AgentRegistry
from backend.core.memory import memory

class Kernel:
    def __init__(self):
        self.logger = logging.getLogger("ApexKernel")
        self.agents: Dict[str, any] = {}
        
        # Dynamic Registration
        self.logger.info("⚡ Booting Apex Sovereign OS...")
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

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        self.logger.info(f"📡 Dispatching: {packet.task}")

        # --- 1. BYPASS RULE: System Agents ---
        system_tasks = ["onboarding", "scrape_site", "manager"]
        if packet.task in system_tasks:
            agent_key = "scout" if packet.task == "scrape_site" else packet.task
            if agent_key in self.agents:
                return await self.agents[agent_key].run(packet)

        # --- 2. SMART CONTEXT LOADING ---
        niche = packet.params.get("niche")
        
        if not niche and packet.user_id:
            # Smart Lookup via Memory
            project = memory.get_user_project(packet.user_id)
            if project:
                niche = project['project_id']
                self.logger.info(f"🔍 Auto-detected Project: {niche}")

        if not niche:
            # Fallback for dev/testing
            niche = "personal" 

        # Load Profile (DNA)
        from backend.core.config import ConfigLoader
        user_config = ConfigLoader().load(niche)
        
        if "error" in user_config:
            self.logger.warning(f"⚠️ Profile '{niche}' not found. Using defaults.")

        # --- 3. INTELLIGENT ROUTING ---
        agent_key = None
        
        # Module: pSEO
        if "scout" in packet.task or "find" in packet.task: 
            agent_key = "scout"
        elif "keyword" in packet.task:
            agent_key = "seo_keyword"
        elif "write" in packet.task: 
            agent_key = "seo_writer"
        elif "enhance_media" in packet.task:
            agent_key = "media"
        elif "publish" in packet.task:
            agent_key = "publisher"
        elif packet.task == "manager":
            agent_key = "manager"
            
        # Module: Lead Gen
        elif "enhance_utility" in packet.task:
            agent_key = "utility"
        elif "twilio" in packet.task or "sms" in packet.task:
            agent_key = "twilio"

        # EXECUTION
        if agent_key and agent_key in self.agents:
            agent = self.agents[agent_key]
            # Inject Config (Context Injection)
            agent.config = user_config 
            return await agent.run(packet)
            
        return AgentOutput(status="error", message=f"Task '{packet.task}' not recognized or agent missing.")

# Singleton Kernel
kernel = Kernel()