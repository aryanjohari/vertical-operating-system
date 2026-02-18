# backend/core/exceptions.py
"""Custom exceptions for Apex Sovereign OS. Handled globally so frontend never receives raw stack traces."""
from typing import Optional


class ApexBaseException(Exception):
    """Base for all Apex API exceptions. Logged fully; only message/request_id returned to client."""
    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        request_id: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        super().__init__(message)


class ProjectAccessDenied(ApexBaseException):
    """Raised when the user does not own the project or project not found."""
    def __init__(self, message: str = "Project not found or access denied", request_id: Optional[str] = None):
        super().__init__(message=message, status_code=403, request_id=request_id)


class AgentExecutionError(ApexBaseException):
    """Raised when an agent execution fails."""
    def __init__(self, message: str = "Agent execution failed", request_id: Optional[str] = None):
        super().__init__(message=message, status_code=500, request_id=request_id)
