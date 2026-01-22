# backend/modules/system_ops/middleware.py
import os
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("Apex.SecurityMiddleware")

async def security_middleware(request: Request, call_next):
    """
    Security middleware for Twilio signature validation and admin authentication.
    
    Rules:
    - Public access to /health endpoint
    - /api/voice/* endpoints: Validate X-Twilio-Signature (production only)
    - /api/admin/* endpoints: Validate Authorization Bearer token
    """
    # Allow public access to /health endpoint
    if request.url.path == "/health" or request.url.path == "/":
        return await call_next(request)
    
    # Twilio signature validation for /api/voice/* endpoints (production only)
    if request.url.path.startswith("/api/voice/"):
        env = os.getenv("ENV") or os.getenv("ENVIRONMENT", "development")
        if env.lower() == "production":
            try:
                from twilio.request_validator import RequestValidator
                
                twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                if not twilio_auth_token:
                    logger.warning("TWILIO_AUTH_TOKEN not set, skipping signature validation")
                    return await call_next(request)
                
                validator = RequestValidator(twilio_auth_token)
                
                # Get the signature from header
                signature = request.headers.get("X-Twilio-Signature")
                if not signature:
                    logger.warning("Missing X-Twilio-Signature header")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Missing Twilio signature"
                    )
                
                # Get the full URL
                url = str(request.url)
                
                # Get form data for POST requests
                form_data = {}
                if request.method == "POST":
                    form_data = await request.form()
                    form_dict = dict(form_data)
                else:
                    form_dict = {}
                
                # Validate the signature
                is_valid = validator.validate(url, form_dict, signature)
                
                if not is_valid:
                    logger.warning(f"Invalid Twilio signature for {url}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid Twilio signature"
                    )
                
                logger.debug("Twilio signature validated successfully")
            except HTTPException:
                raise
            except ImportError:
                logger.warning("twilio.request_validator not available, skipping validation")
            except Exception as e:
                logger.error(f"Error validating Twilio signature: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Signature validation error"
                )
    
    # Admin authentication for /api/admin/* endpoints
    if request.url.path.startswith("/api/admin/"):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header for admin endpoint")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization token"
            )
        
        token = auth_header.replace("Bearer ", "").strip()
        admin_key = os.getenv("APEX_ADMIN_KEY")
        
        if not admin_key:
            logger.error("APEX_ADMIN_KEY not set in environment")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Admin authentication not configured"
            )
        
        if token != admin_key:
            logger.warning(f"Invalid admin token attempt for {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin token"
            )
        
        logger.debug("Admin authentication successful")
    
    # Continue to the next middleware/handler
    return await call_next(request)
