# backend/core/context.py
import redis
import json
import os
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

logger = logging.getLogger("Apex.Context")

class AgentContext(BaseModel):
    """
    Short-term memory (RAM) for agent communication.
    Stored in Redis with TTL for automatic expiration.
    """
    context_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique context identifier")
    project_id: str = Field(..., description="Project identifier")
    user_id: str = Field(..., description="User identifier (tenant)")
    created_at: datetime = Field(default_factory=datetime.now, description="Context creation timestamp")
    expires_at: datetime = Field(..., description="Context expiration timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Flexible key-value store for agent data")
    
    def extend_ttl(self, seconds: int = 3600):
        """Extend expiration time."""
        self.expires_at = datetime.now() + timedelta(seconds=seconds)

class ContextManager:
    """
    Manages agent context in Redis (RAM).
    Falls back to in-memory dict if Redis is unavailable.
    
    Architecture Pattern: Follows MemoryManager and Kernel singleton pattern.
    """
    def __init__(self):
        self.logger = logging.getLogger("Apex.Context")
        
        # In-memory fallback storage
        self._in_memory_contexts: Dict[str, AgentContext] = {}
        
        # Try to connect to Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.default_ttl = int(os.getenv("REDIS_TTL_SECONDS", "3600"))
        
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
            self.enabled = True
            self.logger.info("✅ Redis Context Manager initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ Redis not available: {e}. Context will be disabled.")
            self.redis_client = None
            self.enabled = False
            self.logger.info("⚠️ Using in-memory context (not persistent)")
    
    def create_context(
        self, 
        project_id: str, 
        user_id: str, 
        initial_data: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> AgentContext:
        """
        Create a new context and store in Redis (or in-memory fallback).
        
        Args:
            project_id: Project identifier
            user_id: User identifier (tenant)
            initial_data: Optional initial data to store in context
            ttl_seconds: Time-to-live in seconds (defaults to REDIS_TTL_SECONDS or 3600)
            
        Returns:
            AgentContext with context_id that can be passed to agents
        """
        ttl = ttl_seconds or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        context = AgentContext(
            project_id=project_id,
            user_id=user_id,
            expires_at=expires_at,
            data=initial_data or {}
        )
        
        if self.enabled:
            # Store in Redis
            try:
                key = f"context:{context.context_id}"
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(context.dict(), default=str)
                )
                self.logger.debug(f"Created context {context.context_id} for project {project_id}")
            except Exception as e:
                self.logger.error(f"Failed to create context in Redis: {e}", exc_info=True)
                # Fall back to in-memory
                self._in_memory_contexts[context.context_id] = context
                self.logger.warning("⚠️ Falled back to in-memory context storage")
        else:
            # Store in-memory
            self._in_memory_contexts[context.context_id] = context
        
        return context
    
    def get_context(self, context_id: str) -> Optional[AgentContext]:
        """
        Retrieve context from Redis (or in-memory fallback).
        
        Args:
            context_id: Context identifier to retrieve
            
        Returns:
            AgentContext if found and not expired, None otherwise
        """
        if self.enabled:
            # Try Redis first
            try:
                key = f"context:{context_id}"
                data = self.redis_client.get(key)
                if not data:
                    return None
                
                context_dict = json.loads(data)
                # Convert datetime strings back to datetime objects
                context_dict['created_at'] = datetime.fromisoformat(context_dict['created_at'])
                context_dict['expires_at'] = datetime.fromisoformat(context_dict['expires_at'])
                
                context = AgentContext(**context_dict)
                
                # Check if expired
                if context.expires_at < datetime.now():
                    self.delete_context(context_id)
                    return None
                
                return context
            except Exception as e:
                self.logger.error(f"Failed to get context from Redis: {e}", exc_info=True)
                # Fall back to in-memory
                pass
        
        # In-memory fallback
        context = self._in_memory_contexts.get(context_id)
        if not context:
            return None
        
        # Check if expired
        if context.expires_at < datetime.now():
            del self._in_memory_contexts[context_id]
            return None
        
        return context
    
    def update_context(
        self, 
        context_id: str, 
        updates: Dict[str, Any],
        extend_ttl: bool = True
    ) -> bool:
        """
        Update context data and optionally extend TTL.
        
        Args:
            context_id: Context to update
            updates: Key-value pairs to merge into context.data
            extend_ttl: If True, extend TTL by default_ttl
            
        Returns:
            True on success, False on error or if context not found
        """
        context = self.get_context(context_id)
        if not context:
            return False
        
        # Merge updates
        context.data.update(updates)
        
        # Extend TTL if requested
        if extend_ttl:
            context.extend_ttl(self.default_ttl)
        
        # Save back
        if self.enabled:
            try:
                key = f"context:{context_id}"
                remaining_ttl = int((context.expires_at - datetime.now()).total_seconds())
                if remaining_ttl > 0:
                    self.redis_client.setex(
                        key,
                        remaining_ttl,
                        json.dumps(context.dict(), default=str)
                    )
                    return True
                return False
            except Exception as e:
                self.logger.error(f"Failed to update context in Redis: {e}", exc_info=True)
                # Fall back to in-memory
                self._in_memory_contexts[context_id] = context
                return True
        else:
            # Update in-memory
            self._in_memory_contexts[context_id] = context
            return True
    
    def delete_context(self, context_id: str) -> bool:
        """
        Delete context from Redis (or in-memory fallback).
        
        Args:
            context_id: Context to delete
            
        Returns:
            True on success, False on error
        """
        if self.enabled:
            try:
                key = f"context:{context_id}"
                self.redis_client.delete(key)
                return True
            except Exception as e:
                self.logger.error(f"Failed to delete context from Redis: {e}", exc_info=True)
                # Fall back to in-memory
                pass
        
        # In-memory fallback
        if context_id in self._in_memory_contexts:
            del self._in_memory_contexts[context_id]
            return True
        
        return False

# Singleton
context_manager = ContextManager()
