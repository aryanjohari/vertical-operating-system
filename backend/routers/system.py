import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import get_current_user
from backend.core.context import context_manager
from backend.core.db import get_db_factory
from backend.core.kernel import kernel
from backend.core.memory import memory

router = APIRouter(tags=["system"])
logger = logging.getLogger("Apex.Router.System")

# Project root (parent of backend/) for log file path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@router.get("/health")
def health_check():
    """Enhanced health check with component status (Redis, DB, Twilio)."""
    health_status = {
        "status": "online",
        "system": "Apex Kernel",
        "version": "1.0",
        "loaded_agents": list(kernel.agents.keys()),
        "redis_ok": False,
        "database_ok": False,
        "twilio_ok": False,
    }

    try:
        if context_manager.enabled and context_manager.redis_client:
            context_manager.redis_client.ping()
            health_status["redis_ok"] = True
    except Exception as e:
        logger.debug(f"Redis check failed: {e}")

    try:
        db_factory = get_db_factory(db_path=memory.db_path)
        with db_factory.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status["database_ok"] = True
    except Exception as e:
        logger.debug(f"Database check failed: {e}")

    try:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        health_status["twilio_ok"] = bool(twilio_sid and twilio_token)
    except Exception as e:
        logger.debug(f"Twilio check failed: {e}")

    return health_status


@router.get("/logs")
async def get_logs(
    lines: int = 50,
    user_id: str = Depends(get_current_user),
):
    """Get the last N lines from the system log file."""
    try:
        log_file_path = os.path.join(BASE_DIR, "logs", "apex.log")

        if not os.path.exists(log_file_path):
            return {
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found",
            }

        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        cleaned_lines = [line.rstrip("\n\r") for line in last_lines]

        return {
            "logs": cleaned_lines,
            "total_lines": len(cleaned_lines),
        }
    except Exception as e:
        logger.error(f"Error reading logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read logs")


@router.get("/usage")
async def get_usage(
    project_id: Optional[str] = None,
    limit: int = 100,
    user_id: str = Depends(get_current_user),
):
    """Get usage records from the usage_ledger table."""
    try:
        if project_id and not memory.verify_project_ownership(user_id, project_id):
            raise HTTPException(status_code=403, detail="Project not found or access denied")

        usage_records = memory.get_usage_ledger(user_id, project_id=project_id, limit=limit)
        return {"usage": usage_records, "total": len(usage_records)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching usage records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch usage records")
