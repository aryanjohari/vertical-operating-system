import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.auth import create_access_token, verify_user_credentials
from backend.core.memory import memory

router = APIRouter(tags=["auth"])
logger = logging.getLogger("Apex.Router.Auth")


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None


class AuthResponseWithToken(AuthResponse):
    """Extended response with JWT token."""
    token: Optional[str] = None


@router.post("/auth/verify", response_model=AuthResponseWithToken)
async def verify_auth(request: AuthRequest):
    """Verify user credentials and return JWT token."""
    try:
        email = request.email.strip()
        password = request.password.strip()

        if not email or not password:
            logger.warning("Auth failed: empty email or password")
            return AuthResponseWithToken(success=False, user_id=None, token=None)

        logger.info(f"Verifying user: {email}")
        user_id = verify_user_credentials(email, password)

        if user_id:
            token = create_access_token(user_id)
            logger.info(f"Auth success: {email}")
            return AuthResponseWithToken(success=True, user_id=user_id, token=token)

        logger.warning(f"Auth failed: credentials don't match for {email}")
        return AuthResponseWithToken(success=False, user_id=None, token=None)
    except Exception as e:
        logger.error(f"Auth error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed. Please try again.")


@router.post("/auth/register", response_model=AuthResponse)
async def register_user(request: AuthRequest):
    """Register a new user."""
    try:
        email = request.email.strip()
        password = request.password.strip()

        if not email or not password:
            logger.warning("Registration failed: empty email or password")
            return AuthResponse(success=False, user_id=None)

        logger.info(f"Registering user: {email}")
        success = memory.create_user(email, password)

        if success:
            logger.info(f"Registration success: {email}")
            return AuthResponse(success=True, user_id=email)
        else:
            logger.warning(f"Registration failed: user {email} already exists")
            return AuthResponse(success=False, user_id=None)
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
