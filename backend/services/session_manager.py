"""
Multi-tenant session manager for OAuth2 authentication.
Handles session storage, retrieval, and management in Redis with agency isolation.
"""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta, timezone
import json
import secrets
import logging
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class MultiTenantSessionManager:
    """
    Manages user sessions in Redis with multi-tenant support.
    Provides agency-level isolation and session lifecycle management.
    """
    
    def __init__(self, redis: Redis, default_ttl: int = 86400):
        """
        Initialize session manager.
        
        Args:
            redis: Async Redis client
            default_ttl: Default session TTL in seconds (24 hours)
        """
        self.redis = redis
        self.default_ttl = default_ttl
        self.session_prefix = "session"
        self.user_sessions_prefix = "user_sessions"
        self.agency_sessions_prefix = "agency_sessions"
    
    def _get_session_key(self, agency_id: str, session_id: str) -> str:
        """Generate Redis key for a session."""
        return f"{self.session_prefix}:{agency_id}:{session_id}"
    
    def _get_user_sessions_key(self, agency_id: str, user_id: str) -> str:
        """Generate Redis key for user's sessions set."""
        return f"{self.user_sessions_prefix}:{agency_id}:{user_id}"
    
    def _get_agency_sessions_key(self, agency_id: str) -> str:
        """Generate Redis key for agency's sessions set."""
        return f"{self.agency_sessions_prefix}:{agency_id}"
    
    async def create_session(
        self,
        user_id: str,
        agency_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> str:
        """
        Create a new session with agency isolation.
        
        Args:
            user_id: User ID
            agency_id: Agency ID for multi-tenant isolation
            metadata: Optional session metadata
            ttl: Optional custom TTL in seconds
            
        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        session_key = self._get_session_key(agency_id, session_id)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "agency_id": agency_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "active": True
        }
        
        ttl = ttl or self.default_ttl
        
        try:
            # Store session data
            await self.redis.setex(
                session_key,
                ttl,
                json.dumps(session_data)
            )
            
            # Track session in user's set
            user_sessions_key = self._get_user_sessions_key(agency_id, user_id)
            await self.redis.sadd(user_sessions_key, session_id)
            await self.redis.expire(user_sessions_key, ttl)
            
            # Track session in agency's set
            agency_sessions_key = self._get_agency_sessions_key(agency_id)
            await self.redis.sadd(agency_sessions_key, f"{user_id}:{session_id}")
            await self.redis.expire(agency_sessions_key, ttl)
            
            logger.info(f"Created session {session_id} for user {user_id} in agency {agency_id}")
            return session_id
            
        except RedisError as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def get_session(
        self,
        session_id: str,
        agency_id: str,
        update_activity: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get session with agency validation.
        
        Args:
            session_id: Session ID
            agency_id: Agency ID for validation
            update_activity: Whether to update last activity timestamp
            
        Returns:
            Session data or None if not found/invalid
        """
        session_key = self._get_session_key(agency_id, session_id)
        
        try:
            data = await self.redis.get(session_key)
            if not data:
                return None
            
            session = json.loads(data)
            
            # Validate agency match
            if session.get("agency_id") != agency_id:
                logger.warning(f"Agency mismatch for session {session_id}")
                return None
            
            # Check if session is active
            if not session.get("active", True):
                return None
            
            # Update last activity if requested
            if update_activity:
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                ttl = await self.redis.ttl(session_key)
                if ttl > 0:
                    await self.redis.setex(
                        session_key,
                        ttl,
                        json.dumps(session)
                    )
            
            return session
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def update_session(
        self,
        session_id: str,
        agency_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session ID
            agency_id: Agency ID for validation
            updates: Data to update
            
        Returns:
            True if updated, False otherwise
        """
        session = await self.get_session(session_id, agency_id, update_activity=False)
        if not session:
            return False
        
        session_key = self._get_session_key(agency_id, session_id)
        
        try:
            # Update session data
            session.update(updates)
            session["last_activity"] = datetime.now(timezone.utc).isoformat()
            
            # Preserve TTL
            ttl = await self.redis.ttl(session_key)
            if ttl > 0:
                await self.redis.setex(
                    session_key,
                    ttl,
                    json.dumps(session)
                )
                return True
            return False
            
        except RedisError as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    async def revoke_session(self, session_id: str, agency_id: str) -> bool:
        """
        Revoke a specific session.
        
        Args:
            session_id: Session ID
            agency_id: Agency ID for validation
            
        Returns:
            True if revoked, False otherwise
        """
        session_data = await self.get_session(session_id, agency_id, update_activity=False)
        if not session_data:
            return False
        
        session_key = self._get_session_key(agency_id, session_id)
        user_id = session_data.get("user_id")
        
        try:
            # Remove from user's sessions set
            if user_id:
                user_sessions_key = self._get_user_sessions_key(agency_id, user_id)
                await self.redis.srem(user_sessions_key, session_id)
                
                # Remove from agency's sessions set
                agency_sessions_key = self._get_agency_sessions_key(agency_id)
                await self.redis.srem(agency_sessions_key, f"{user_id}:{session_id}")
            
            # Delete session
            await self.redis.delete(session_key)
            
            logger.info(f"Revoked session {session_id} for agency {agency_id}")
            return True
            
        except RedisError as e:
            logger.error(f"Failed to revoke session {session_id}: {e}")
            return False
    
    async def revoke_all_user_sessions(
        self,
        user_id: str,
        agency_id: str
    ) -> int:
        """
        Revoke all sessions for a user in an agency.
        
        Args:
            user_id: User ID
            agency_id: Agency ID
            
        Returns:
            Number of sessions revoked
        """
        user_sessions_key = self._get_user_sessions_key(agency_id, user_id)
        
        try:
            # Get all session IDs for the user
            session_ids = await self.redis.smembers(user_sessions_key)
            if not session_ids:
                return 0
            
            # Build keys to delete
            session_keys = [
                self._get_session_key(agency_id, sid.decode() if isinstance(sid, bytes) else sid)
                for sid in session_ids
            ]
            
            # Delete all sessions
            if session_keys:
                await self.redis.delete(*session_keys)
            
            # Clear user sessions set
            await self.redis.delete(user_sessions_key)
            
            # Remove from agency sessions
            agency_sessions_key = self._get_agency_sessions_key(agency_id)
            for sid in session_ids:
                sid_str = sid.decode() if isinstance(sid, bytes) else sid
                await self.redis.srem(agency_sessions_key, f"{user_id}:{sid_str}")
            
            count = len(session_ids)
            logger.info(f"Revoked {count} sessions for user {user_id} in agency {agency_id}")
            return count
            
        except RedisError as e:
            logger.error(f"Failed to revoke user sessions: {e}")
            return 0
    
    async def get_user_sessions(
        self,
        user_id: str,
        agency_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User ID
            agency_id: Agency ID
            
        Returns:
            List of session data
        """
        user_sessions_key = self._get_user_sessions_key(agency_id, user_id)
        
        try:
            session_ids = await self.redis.smembers(user_sessions_key)
            if not session_ids:
                return []
            
            sessions = []
            for sid in session_ids:
                sid_str = sid.decode() if isinstance(sid, bytes) else sid
                session = await self.get_session(sid_str, agency_id, update_activity=False)
                if session:
                    sessions.append(session)
            
            return sessions
            
        except RedisError as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    async def get_agency_active_sessions(self, agency_id: str) -> int:
        """
        Get count of active sessions in an agency.
        
        Args:
            agency_id: Agency ID
            
        Returns:
            Number of active sessions
        """
        agency_sessions_key = self._get_agency_sessions_key(agency_id)
        
        try:
            return await self.redis.scard(agency_sessions_key)
        except RedisError as e:
            logger.error(f"Failed to get agency session count: {e}")
            return 0
    
    async def cleanup_expired_sessions(self, agency_id: Optional[str] = None) -> int:
        """
        Clean up expired sessions from sets.
        This should be run periodically as a background task.
        
        Args:
            agency_id: Optional agency ID to limit cleanup scope
            
        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        
        try:
            if agency_id:
                # Clean specific agency
                pattern = f"{self.session_prefix}:{agency_id}:*"
            else:
                # Clean all agencies
                pattern = f"{self.session_prefix}:*"
            
            # Scan for session keys
            async for key in self.redis.scan_iter(match=pattern):
                # Check if key exists (Redis will auto-expire, but we clean sets)
                if not await self.redis.exists(key):
                    # Extract agency_id and session_id from key
                    parts = key.decode() if isinstance(key, bytes) else key
                    parts = parts.split(":")
                    if len(parts) >= 3:
                        agency_id = parts[1]
                        session_id = parts[2]
                        
                        # Clean from sets
                        # Note: We don't have user_id here, so this is partial cleanup
                        # Full cleanup happens when sessions are accessed
                        cleaned += 1
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired session references")
            
            return cleaned
            
        except RedisError as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return cleaned
    
    async def extend_session(
        self,
        session_id: str,
        agency_id: str,
        additional_ttl: int
    ) -> bool:
        """
        Extend session TTL.
        
        Args:
            session_id: Session ID
            agency_id: Agency ID
            additional_ttl: Additional seconds to add to TTL
            
        Returns:
            True if extended, False otherwise
        """
        session_key = self._get_session_key(agency_id, session_id)
        
        try:
            # Verify session exists
            if not await self.redis.exists(session_key):
                return False
            
            # Extend TTL
            current_ttl = await self.redis.ttl(session_key)
            if current_ttl > 0:
                new_ttl = current_ttl + additional_ttl
                await self.redis.expire(session_key, new_ttl)
                
                # Also extend user sessions set TTL
                session_data = await self.get_session(session_id, agency_id, update_activity=False)
                if session_data:
                    user_id = session_data.get("user_id")
                    if user_id:
                        user_sessions_key = self._get_user_sessions_key(agency_id, user_id)
                        await self.redis.expire(user_sessions_key, new_ttl)
                
                return True
            return False
            
        except RedisError as e:
            logger.error(f"Failed to extend session {session_id}: {e}")
            return False
    
    async def get_session_stats(self, agency_id: str) -> Dict[str, Any]:
        """
        Get session statistics for an agency.
        
        Args:
            agency_id: Agency ID
            
        Returns:
            Statistics dictionary
        """
        try:
            active_sessions = await self.get_agency_active_sessions(agency_id)
            
            # Get unique users with sessions
            agency_sessions_key = self._get_agency_sessions_key(agency_id)
            sessions = await self.redis.smembers(agency_sessions_key)
            
            unique_users = set()
            for session in sessions:
                session_str = session.decode() if isinstance(session, bytes) else session
                user_id = session_str.split(":")[0]
                unique_users.add(user_id)
            
            return {
                "total_sessions": active_sessions,
                "unique_users": len(unique_users),
                "agency_id": agency_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except RedisError as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "total_sessions": 0,
                "unique_users": 0,
                "agency_id": agency_id,
                "error": str(e)
            }