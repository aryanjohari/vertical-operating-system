# backend/core/agent_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import traceback
import json
import os
from datetime import datetime
from backend.core.models import AgentInput, AgentOutput

class BaseAgent(ABC):
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.project_id: Optional[str] = None  # Injected by kernel
        self.user_id: Optional[str] = None  # Injected by kernel
        self.logger = logging.getLogger(f"Apex.{name}")
        
    def log(self, message: str):
        self.logger.info(message)

    def save_snapshot(self, step_name: str, input_data: AgentInput, output_data: Optional[AgentOutput] = None, error_traceback: Optional[str] = None):
        """
        Saves a snapshot of agent execution to logs/snapshots/ for debugging.
        
        Data Flow: This method captures the complete state of an agent execution,
        including inputs, outputs, and any errors. This allows debugging the "black box"
        by examining JSON files after execution.
        
        Args:
            step_name: "start" or "end" to indicate when the snapshot was taken
            input_data: The AgentInput packet received from Kernel
            output_data: The AgentOutput returned (None for "start" snapshots)
            error_traceback: Full traceback string if an error occurred
        """
        try:
            # Ensure logs/snapshots directory exists
            snapshot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "snapshots")
            os.makedirs(snapshot_dir, exist_ok=True)
            
            # Create timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            filename = f"{timestamp}_{self.name}_{step_name}.json"
            filepath = os.path.join(snapshot_dir, filename)
            
            # Build snapshot data
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "agent_name": self.name,
                "step": step_name,
                "input_context": {
                    "task": input_data.task,
                    "user_id": input_data.user_id,
                    "request_id": input_data.request_id,
                    "params": input_data.params
                },
                "output_result": output_data.dict() if output_data else None,
                "error_traceback": error_traceback
            }
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)
                
            self.logger.debug(f"Snapshot saved: {filename}")
        except Exception as e:
            # Don't let snapshot failures break the agent execution
            self.logger.warning(f"Failed to save snapshot: {e}")

    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        The entry point for all agents with automatic logging and snapshot recording.
        
        Data Flow:
        1. Receives AgentInput packet from Kernel (via /api/run endpoint)
        2. Saves "start" snapshot with input data
        3. Calls _execute() (agent-specific logic implemented by each agent)
        4. Saves "end" snapshot with input and output data
        5. Returns AgentOutput to Kernel, which returns it to the frontend
        
        This method wraps _execute() with logging, error handling, and snapshot recording.
        """
        self.logger.info(f"Agent Started: {self.name}")
        
        # Save snapshot at start of execution
        # TEMPORARILY DISABLED: Commented out until needed for debugging
        # self.save_snapshot("start", input_data, None)
        
        try:
            # Call the abstract method that each agent implements
            result = await self._execute(input_data)
            
            # Log successful completion
            self.logger.info(f"Agent Finished: {self.name} - Status: {result.status}")
            
            # Save snapshot at end of successful execution
            # TEMPORARILY DISABLED: Commented out until needed for debugging
            # self.save_snapshot("end", input_data, result, None)
            
            return result
            
        except Exception as e:
            # Log full traceback to file (logger.exception() includes stack trace)
            self.logger.exception(f"Agent Failed: {self.name} - {str(e)}")
            
            # Capture full traceback for snapshot
            error_trace = traceback.format_exc()
            
            # Return error output
            error_result = AgentOutput(
                status="error",
                message=f"Agent {self.name} failed: {str(e)}"
            )
            
            # Save snapshot at end of failed execution
            # TEMPORARILY DISABLED: Commented out until needed for debugging
            # self.save_snapshot("end", input_data, error_result, error_trace)
            
            return error_result

    @abstractmethod
    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Every agent must implement this function.
        It takes the Universal Packet (Input) and returns the Universal Receipt (Output).
        This is called by run() which provides logging and error handling.
        """
        pass