"""
Session management with Redis backend.
Handles user sessions, concurrent session limits, and sliding windows.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import json
import secrets
import redis.asyncio as redis
from redis.exceptions import RedisError

from ..config import security_config

class SessionManager:
    """Manages user sessions with Redis backend."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize session manager.
        
        Args:
            redis_client: Optional Redis client instance
        """
        self.redis_client = redis_client
        self.timeout_minutes = security_config.SESSION_TIMEOUT_MINUTES
        self.sliding_window = security_config.SESSION_SLIDING_WINDOW
        self.max_concurrent = security_config.SESSION_MAX_CONCURRENT
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
    
    async def create_session(
        self, 
        user_id: int, 
        session_data: Dict[str, Any],
        device_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new session for a user.
        
        Args:
            user_id: User ID
            session_data: Data to store in session
            device_info: Optional device/browser information
            
        Returns:
            Session ID
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        # Generate session ID
        session_id = secrets.token_urlsafe(32)
        
        # Prepare session data
        session = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "data": session_data,
            "device_info": device_info or {}
        }
        
        # Check concurrent session limit
        await self._enforce_session_limit(user_id)
        
        # Store session
        session_key = f"{self.session_prefix}{session_id}"
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        
        try:
            # Store session data
            await self.redis_client.setex(
                session_key,
                timedelta(minutes=self.timeout_minutes),
                json.dumps(session)
            )
            
            # Add to user's session list
            await self.redis_client.sadd(user_sessions_key, session_id)
            
            # Set expiration on user sessions set
            await self.redis_client.expire(
                user_sessions_key,
                timedelta(minutes=self.timeout_minutes)
            )
            
            return session_id
            
        except RedisError as e:
            raise RuntimeError(f"Failed to create session: {e}")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session data or None if not found/expired
        """
        if not self.redis_client:
            return None
        
        session_key = f"{self.session_prefix}{session_id}"
        
        try:
            session_data = await self.redis_client.get(session_key)
            
            if not session_data:
                return None
            
            session = json.loads(session_data)
            
            # Update last activity if sliding window enabled
            if self.sliding_window:
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                await self.redis_client.setex(
                    session_key,
                    timedelta(minutes=self.timeout_minutes),
                    json.dumps(session)
                )
            
            return session
            
        except (RedisError, json.JSONDecodeError):
            return None
    
    async def update_session(
        self, 
        session_id: str, 
        data: Dict[str, Any]
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session ID to update
            data: New data to merge with existing session
            
        Returns:
            True if updated successfully
        """
        session = await self.get_session(session_id)
        
        if not session:
            return False
        
        # Merge new data
        session["data"].update(data)
        session["last_activity"] = datetime.now(timezone.utc).isoformat()
        
        session_key = f"{self.session_prefix}{session_id}"
        
        try:
            await self.redis_client.setex(
                session_key,
                timedelta(minutes=self.timeout_minutes),
                json.dumps(session)
            )
            return True
            
        except RedisError:
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted successfully
        """
        if not self.redis_client:
            return False
        
        session_key = f"{self.session_prefix}{session_id}"
        
        # Get session to find user ID
        session = await self.get_session(session_id)
        
        if session:
            user_id = session.get("user_id")
            if user_id:
                # Remove from user's session list
                user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                await self.redis_client.srem(user_sessions_key, session_id)
        
        # Delete session
        try:
            result = await self.redis_client.delete(session_key)
            return result > 0
        except RedisError:
            return False
    
    async def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of session data
        """
        if not self.redis_client:
            return []
        
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        
        try:
            session_ids = await self.redis_client.smembers(user_sessions_key)
            sessions = []
            
            for session_id in session_ids:
                session = await self.get_session(session_id)
                if session:
                    sessions.append({
                        "session_id": session_id,
                        **session
                    })
            
            return sessions
            
        except RedisError:
            return []
    
    async def delete_user_sessions(self, user_id: int) -> int:
        """
        Delete all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions deleted
        """
        sessions = await self.get_user_sessions(user_id)
        deleted = 0
        
        for session in sessions:
            if await self.delete_session(session["session_id"]):
                deleted += 1
        
        return deleted
    
    async def _enforce_session_limit(self, user_id: int) -> None:
        """
        Enforce maximum concurrent session limit.
        
        Args:
            user_id: User ID to check
        """
        if self.max_concurrent <= 0:
            return  # No limit
        
        sessions = await self.get_user_sessions(user_id)
        
        if len(sessions) >= self.max_concurrent:
            # Sort by last activity (oldest first)
            sessions.sort(
                key=lambda s: s.get("last_activity", ""),
                reverse=False
            )
            
            # Delete oldest sessions to make room
            sessions_to_delete = len(sessions) - self.max_concurrent + 1
            for session in sessions[:sessions_to_delete]:
                await self.delete_session(session["session_id"])
    
    async def is_session_valid(self, session_id: str) -> bool:
        """
        Check if a session is valid and not expired.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            True if session is valid
        """
        session = await self.get_session(session_id)
        return session is not None
    
    async def extend_session(self, session_id: str, minutes: int = None) -> bool:
        """
        Extend a session's expiration time.
        
        Args:
            session_id: Session ID to extend
            minutes: Minutes to extend (uses default if not specified)
            
        Returns:
            True if extended successfully
        """
        if not self.redis_client:
            return False
        
        session_key = f"{self.session_prefix}{session_id}"
        minutes = minutes or self.timeout_minutes
        
        try:
            result = await self.redis_client.expire(
                session_key,
                timedelta(minutes=minutes)
            )
            return bool(result)
        except RedisError:
            return False

# Session manager will be initialized with Redis client when available
session_manager = None

def init_session_manager(redis_client: redis.Redis) -> SessionManager:
    """
    Initialize the session manager with Redis client.
    
    Args:
        redis_client: Redis client instance
        
    Returns:
        Initialized SessionManager
    """
    global session_manager
    session_manager = SessionManager(redis_client)
    return session_manager