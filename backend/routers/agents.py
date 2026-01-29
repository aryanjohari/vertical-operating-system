import logging
import traceback
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import ValidationError

from backend.core.auth import get_current_user
from backend.core.context import context_manager
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.models import AgentInput, AgentOutput
from backend.core.schemas import TASK_SCHEMA_MAP

router = APIRouter(tags=["agents"])
logger = logging.getLogger("Apex.Router.Agents")


@router.get("/api/context/{context_id}")
async def get_context(context_id: str, user_id: str = Depends(get_current_user)):
    """
    Retrieve context status for async task polling.
    Returns context with task status and result (if completed).
    """
    try:
        context = context_manager.get_context(context_id)

        if not context:
            raise HTTPException(status_code=404, detail="Context not found or expired")

        if context.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "context_id": context.context_id,
            "project_id": context.project_id,
            "user_id": context.user_id,
            "created_at": context.created_at.isoformat(),
            "expires_at": context.expires_at.isoformat(),
            "data": context.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving context {context_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve context")


@router.post("/api/run")
async def run_command(
    payload: AgentInput,
    user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    The Single Entry Point with Safety Net.
    Receives AgentInput, validates, runs heavy tasks in background or light tasks synchronously.
    Always returns HTTP 200 with structured JSON.
    """
    try:
        payload.user_id = user_id

        agent_key = kernel._resolve_agent(payload.task)
        if agent_key:
            schema_class = TASK_SCHEMA_MAP.get(agent_key)
            if schema_class is not None:
                try:
                    schema_class.model_validate(payload.params or {})
                except ValidationError as e:
                    logger.warning(f"Params validation failed for task {payload.task}: {e}")
                    raise HTTPException(status_code=400, detail=e.errors())

        is_heavy = kernel.is_heavy(payload.task, payload.params)

        if is_heavy and background_tasks:
            project_id = payload.params.get("project_id") or payload.params.get("niche")
            if not project_id:
                try:
                    project = memory.get_user_project(user_id)
                    if project:
                        project_id = project.get("project_id")
                except Exception as e:
                    logger.debug(f"Could not get user project for context: {e}")

            context = None
            if project_id:
                try:
                    context = context_manager.create_context(
                        project_id=project_id,
                        user_id=user_id,
                        initial_data={"request_id": payload.request_id},
                        ttl_seconds=3600,
                    )
                    payload.params["context_id"] = context.context_id
                except Exception as e:
                    logger.warning(f"Failed to create context: {e}", exc_info=True)

            async def run_agent_background():
                context_id_to_update = context.context_id if context else None
                try:
                    result = await kernel.dispatch(payload)
                    logger.info(f"Background task {payload.task} completed: {result.status}")
                    if context_id_to_update:
                        try:
                            context_manager.update_context(
                                context_id_to_update,
                                {"status": "completed", "result": result.dict()},
                                extend_ttl=False,
                            )
                            logger.debug(f"Updated context {context_id_to_update} with result")
                        except Exception as e:
                            logger.error(f"Failed to update context with result: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Background task {payload.task} failed: {e}", exc_info=True)
                    if context_id_to_update:
                        try:
                            error_result = AgentOutput(
                                status="error",
                                message=f"Task failed: {str(e)}",
                            )
                            context_manager.update_context(
                                context_id_to_update,
                                {"status": "failed", "result": error_result.dict()},
                                extend_ttl=False,
                            )
                            logger.debug(f"Updated context {context_id_to_update} with error")
                        except Exception as update_error:
                            logger.error(f"Failed to update context with error: {update_error}", exc_info=True)

            background_tasks.add_task(run_agent_background)
            logger.info(f"Scheduled heavy task '{payload.task}' for background execution")

            return {
                "status": "processing",
                "data": {
                    "context_id": context.context_id if context else None,
                    "task": payload.task,
                },
                "message": f"Task '{payload.task}' is processing in background",
                "timestamp": datetime.now().isoformat(),
                "error_details": None,
            }

        result = await kernel.dispatch(payload)
        return {
            "status": result.status,
            "data": result.data,
            "message": result.message,
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, "isoformat") else str(result.timestamp),
            "error_details": None,
        }
    except ValidationError as e:
        logger.warning(f"Params validation failed in /api/run: {e}")
        raise HTTPException(status_code=400, detail=e.errors())
    except ImportError as e:
        error_trace = traceback.format_exc()
        logger.error(f"ImportError in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None,
        }
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Exception in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None,
        }
