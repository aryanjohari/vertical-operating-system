# backend/core/agent_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import traceback
from backend.core.models import AgentInput, AgentOutput

class BaseAgent(ABC):
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"Apex.{name}")
        
    def log(self, message: str):
        self.logger.info(message)

    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        The entry point for all agents with automatic logging.
        This method wraps _execute() with logging and error handling.
        """
        self.logger.info(f"Agent Started: {self.name}")
        
        try:
            # Call the abstract method that each agent implements
            result = await self._execute(input_data)
            
            # Log successful completion
            self.logger.info(f"Agent Finished: {self.name} - Status: {result.status}")
            return result
            
        except Exception as e:
            # Log full traceback to file (logger.exception() includes stack trace)
            self.logger.exception(f"Agent Failed: {self.name} - {str(e)}")
            
            # Return error output
            return AgentOutput(
                status="error",
                message=f"Agent {self.name} failed: {str(e)}"
            )

    @abstractmethod
    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Every agent must implement this function.
        It takes the Universal Packet (Input) and returns the Universal Receipt (Output).
        This is called by run() which provides logging and error handling.
        """
        pass