# backend/core/auth.py
"""
Authentication abstraction layer.

Current implementation: JWT with SQLite user store
Future: Can be swapped to Supabase Auth with minimal changes to API

This abstraction allows switching from SQLite to Supabase without changing
the FastAPI endpoints - only the AuthProvider implementation changes.
"""
import os
import jwt
import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.memory import memory

logger = logging.getLogger("Apex.Auth")

# Security scheme
security = HTTPBearer()

# JWT Configuration (can be moved to env/config later)
_jwt_secret = os.getenv("APEX_JWT_SECRET") or os.getenv("JWT_SECRET")
if not _jwt_secret:
    raise ValueError("APEX_JWT_SECRET or JWT_SECRET environment variable must be set. Cannot start without a secure JWT secret.")
JWT_SECRET = _jwt_secret
JWT_ALGORITHM = os.getenv("APEX_JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("APEX_JWT_EXPIRATION_HOURS", "24"))


class AuthProvider:
    """
    Abstract authentication provider interface.
    
    Current: SQLiteAuthProvider (uses memory.py)
    Future: SupabaseAuthProvider (uses Supabase Auth)
    """
    
    def verify_credentials(self, email: str, password: str) -> Optional[str]:
        """
        Verify user credentials and return user_id if valid.
        
        Returns:
            user_id (str) if valid, None otherwise
        """
        raise NotImplementedError
    
    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Extract and verify user_id from JWT token.
        
        Returns:
            user_id (str) if valid, None otherwise
        """
        raise NotImplementedError
    
    def create_token(self, user_id: str) -> str:
        """
        Create JWT token for user.
        
        Args:
            user_id: The user identifier
            
        Returns:
            JWT token string
        """
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class SQLiteAuthProvider(AuthProvider):
    """
    Current implementation: SQLite-backed authentication.
    Uses memory.py for user storage and verification.
    
    To migrate to Supabase:
    1. Create SupabaseAuthProvider class
    2. Implement verify_credentials() using Supabase Auth API
    3. Implement get_user_id_from_token() using Supabase JWT verification
    4. Swap provider instance in get_auth_provider()
    """
    
    def verify_credentials(self, email: str, password: str) -> Optional[str]:
        """Verify against SQLite user store."""
        if memory.verify_user(email, password):
            return email  # user_id is email in SQLite implementation
        return None
    
    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Verify JWT and extract user_id.
        
        Future: When using Supabase, this would:
        1. Verify token signature with Supabase JWT secret
        2. Extract user_id from Supabase claims
        3. Optionally verify token hasn't been revoked in Supabase
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            
            # Verify user still exists (SQLite check)
            # Future: Supabase would verify against Supabase Auth user pool
            if user_id and memory._user_exists(user_id):
                return user_id
            return None
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}", exc_info=True)
            return None


# Singleton provider instance (swapable for Supabase migration)
_auth_provider: Optional[AuthProvider] = None


def get_auth_provider() -> AuthProvider:
    """
    Get the current authentication provider.
    
    Current: SQLiteAuthProvider
    Future: Swap to SupabaseAuthProvider by changing this function:
        
        def get_auth_provider() -> AuthProvider:
            return SupabaseAuthProvider()
    """
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = SQLiteAuthProvider()
    return _auth_provider


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    FastAPI dependency to extract authenticated user_id from JWT token.
    
    Usage in endpoints:
        @app.get("/api/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            # user_id is guaranteed to be valid
    """
    token = credentials.credentials
    provider = get_auth_provider()
    
    user_id = provider.get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )
    
    return user_id


def create_access_token(user_id: str) -> str:
    """Create JWT access token for user."""
    provider = get_auth_provider()
    return provider.create_token(user_id)


def verify_user_credentials(email: str, password: str) -> Optional[str]:
    """
    Verify user credentials and return user_id if valid.
    
    Used by login endpoint.
    """
    provider = get_auth_provider()
    return provider.verify_credentials(email, password)
