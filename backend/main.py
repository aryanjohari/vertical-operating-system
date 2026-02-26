from dotenv import load_dotenv

load_dotenv()

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.exceptions import ApexBaseException
from backend.core.db import get_db_factory
from backend.core.kernel import kernel
from backend.core.logger import setup_logging
from backend.core.memory import memory
from backend.modules.system_ops.middleware import security_middleware
from backend.routers import system
from backend.routers import auth
from backend.routers import projects
from backend.routers import schemas
from backend.routers import entities
from backend.routers import agents
from backend.routers.voice import voice_router
from backend.routers.webhooks import webhook_router

setup_logging()
logger = logging.getLogger("Apex.Main")

scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global scheduler

    logger.info("Starting Apex Sovereign OS...")

    try:
        memory.create_usage_table_if_not_exists()
        logger.info("Usage ledger table initialized")
    except Exception as e:
        logger.error(f"Failed to initialize usage ledger table: {e}", exc_info=True)

    try:
        get_db_factory(memory.db_path)
        logger.info("Database factory (and pool if PostgreSQL) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize DB factory: {e}", exc_info=True)

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler()

        async def run_health_check():
            try:
                logger.debug("Running scheduled health check...")
                from backend.core.models import AgentInput
                result = await kernel.dispatch(
                    AgentInput(task="health_check", user_id="system", params={})
                )
                if result.status == "error":
                    logger.warning(f"Health check failed: {result.message}")
                else:
                    logger.debug(f"Health check completed: {result.data.get('status', 'unknown')}")
            except Exception as e:
                logger.error(f"Error in scheduled health check: {e}", exc_info=True)

        async def run_cleanup():
            try:
                logger.info("Running scheduled cleanup...")
                from backend.core.models import AgentInput
                result = await kernel.dispatch(
                    AgentInput(task="cleanup", user_id="system", params={})
                )
                if result.status == "error":
                    logger.warning(f"Cleanup failed: {result.message}")
                else:
                    logger.info(f"Cleanup completed: {result.message}")
            except Exception as e:
                logger.error(f"Error in scheduled cleanup: {e}", exc_info=True)

        scheduler.add_job(
            run_health_check,
            trigger=IntervalTrigger(minutes=1440),
            id="health_check",
            replace_existing=True,
        )
        scheduler.add_job(
            run_cleanup,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started (health check: interval, cleanup: daily at 3 AM)")
    except ImportError:
        logger.warning("APScheduler not available, scheduled jobs disabled")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)

    yield

    logger.info("Shutting down Apex Sovereign OS...")
    if scheduler:
        try:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)

    try:
        factory = get_db_factory()
        if hasattr(factory, "close_pool"):
            factory.close_pool()
            logger.info("Database pool closed")
    except Exception as e:
        logger.warning(f"Error closing DB pool: {e}")


app = FastAPI(
    title="Apex Sovereign OS",
    version="1.0",
    description="The Vertical Operating System for Revenue & Automation",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.getenv(
    "APEX_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:5500",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)
app.middleware("http")(security_middleware)


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = await call_next(request)
    return response


@app.exception_handler(ApexBaseException)
async def apex_exception_handler(request: Request, exc: ApexBaseException):
    request_id = _request_id(request)
    logger.error(
        f"ApexBaseException: {exc.message} (request_id={request_id or exc.request_id})",
        exc_info=True,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "request_id": exc.request_id or request_id,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = _request_id(request)
    logger.exception(f"Unhandled exception (request_id={request_id}): {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error. Please try again later.",
            "request_id": request_id,
        },
    )

app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(schemas.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(agents.router)
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
app.include_router(webhook_router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/")
def health_check():
    """Ping this to check if the OS is alive."""
    return {
        "status": "online",
        "system": "Apex Kernel",
        "version": "1.0",
        "loaded_agents": list(kernel.agents.keys()),
    }


@app.get("/health")
def health_check_endpoint():
    """Ping this to check if the OS is alive."""
    return {
        "status": "online",
        "system": "Apex Kernel",
        "version": "1.0",
        "loaded_agents": list(kernel.agents.keys()),
    }


class SettingsInput(BaseModel):
    wp_url: str = ""
    wp_user: str = ""
    wp_password: Optional[str] = ""  # Optional: only update password when non-empty


@app.get("/api/settings")
async def get_settings(user_id: str = Depends(get_current_user)):
    """Get WordPress credentials for a user (password never returned)."""
    try:
        secrets = memory.get_client_secrets(user_id)
        if secrets:
            return {
                "wp_url": secrets.get("wp_url", ""),
                "wp_user": secrets.get("wp_user", ""),
                "wp_password": "",
            }
        return {"wp_url": "", "wp_user": "", "wp_password": ""}
    except Exception as e:
        logger.error(f"Get settings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@app.post("/api/settings")
async def save_settings(
    request: SettingsInput,
    user_id: str = Depends(get_current_user),
):
    """Save WordPress credentials. If wp_password is empty, only URL and username are updated."""
    try:
        if request.wp_password and request.wp_password.strip():
            success = memory.save_client_secrets(
                user_id=user_id,
                wp_url=request.wp_url or "",
                wp_user=request.wp_user or "",
                wp_password=request.wp_password,
            )
        else:
            success = memory.save_client_secrets_partial(
                user_id=user_id,
                wp_url=request.wp_url or "",
                wp_user=request.wp_user or "",
            )
        if success:
            logger.info(f"Saved settings for user {user_id}")
            return {"success": True, "message": "Settings saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save settings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save settings")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
