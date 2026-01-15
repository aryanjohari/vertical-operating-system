# backend/core/agent_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
from backend.core.models import AgentInput, AgentOutput

class BaseAgent(ABC):
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"Apex.{name}")
        
    def log(self, message: str):
        self.logger.info(message)

    @abstractmethod
    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        Every agent must implement this function.
        It takes the Universal Packet (Input) and returns the Universal Receipt (Output).
        """
        pass