"""
WebSocket presence management with agency and role-based isolation.
"""
import logging
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timedelta
import asyncio

from core.redis import redis_manager
from core.filters.websocket_filter import websocket_presence_filter
from core.logger import get_logger
from models.user import UserRole

logger = get_logger(__name__)


class PresenceManager:
    """Manage user presence with role-based visibility."""
    
    def __init__(self):
        self.presence_data: Dict[str, Dict[str, Any]] = {}  # user_id -> presence info
        self.last_ping: Dict[str, datetime] = {}  # user_id -> last ping time
        self.presence_timeout = 30  # seconds
        self.cleanup_interval = 10  # seconds
        self._cleanup_task = None
    
    async def start(self):
        """Start the presence manager."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Presence manager started")
    
    async def stop(self):
        """Stop the presence manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Presence manager stopped")
    
    async def update_presence(
        self, 
        user_context: Dict[str, Any], 
        status: str = "online",
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update user presence with visibility filtering.
        
        Args:
            user_context: User context from authentication
            status: Presence status (online, away, busy, offline)
            custom_data: Optional custom presence data
            
        Returns:
            Presence update that will be broadcast
        """
        user_id = user_context.get("user_id")
        
        # Create presence data
        presence = {
            "user_id": user_id,
            "email": user_context.get("email"),
            "full_name": user_context.get("full_name"),
            "role": user_context.get("role"),
            "agency_id": user_context.get("agency_id"),
            "status": status,
            "last_seen": datetime.utcnow().isoformat(),
            "custom_data": custom_data or {}
        }
        
        # Store in memory
        self.presence_data[user_id] = presence
        self.last_ping[user_id] = datetime.utcnow()
        
        # Store in Redis for distributed systems
        await self._store_presence_redis(user_id, presence)
        
        # Filter presence data based on role
        filtered_presence = self._filter_presence_for_broadcast(presence)
        
        return filtered_presence
    
    async def get_online_users(
        self, 
        requester_context: Dict[str, Any],
        agency_id: Optional[str] = None,
        role_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get online users visible to the requester.
        
        Args:
            requester_context: Context of user requesting the list
            agency_id: Optional agency filter
            role_filter: Optional role filter
            
        Returns:
            Filtered list of online users
        """
        # Get all online users
        all_online = []
        
        # Get from memory first
        for user_id, presence in self.presence_data.items():
            if presence.get("status") != "offline":
                all_online.append(presence)
        
        # Also check Redis for distributed presence
        redis_presence = await self._get_redis_presence()
        for presence in redis_presence:
            user_id = presence.get("user_id")
            if user_id not in self.presence_data:
                all_online.append(presence)
        
        # Apply filters
        if agency_id and not requester_context.get("is_super_admin"):
            all_online = [p for p in all_online if p.get("agency_id") == agency_id]
        
        if role_filter:
            all_online = [p for p in all_online if p.get("role") in role_filter]
        
        # Apply visibility filter
        filtered = websocket_presence_filter.filter_online_users(
            all_online, requester_context
        )
        
        # Additional filtering based on specific relationships
        filtered = await self._apply_relationship_filters(filtered, requester_context)
        
        return filtered
    
    async def get_user_presence(
        self, 
        user_id: str, 
        requester_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get presence for a specific user if visible to requester."""
        # Check if requester can see this user's presence
        if not await self._can_see_presence(requester_context, user_id):
            return None
        
        # Get from memory
        presence = self.presence_data.get(user_id)
        
        # Check Redis if not in memory
        if not presence:
            presence = await self._get_redis_presence_for_user(user_id)
        
        if presence:
            # Filter sensitive data based on requester's role
            return self._filter_presence_data(presence, requester_context)
        
        return None
    
    async def set_user_offline(self, user_id: str):
        """Mark a user as offline."""
        if user_id in self.presence_data:
            self.presence_data[user_id]["status"] = "offline"
            self.presence_data[user_id]["last_seen"] = datetime.utcnow().isoformat()
            
            # Update Redis
            await self._store_presence_redis(user_id, self.presence_data[user_id])
        
        # Remove from last ping
        self.last_ping.pop(user_id, None)
    
    async def handle_ping(self, user_id: str):
        """Handle presence ping from user."""
        self.last_ping[user_id] = datetime.utcnow()
        
        # Update last seen if user exists
        if user_id in self.presence_data:
            self.presence_data[user_id]["last_seen"] = datetime.utcnow().isoformat()
    
    def get_presence_rooms(self, user_context: Dict[str, Any]) -> List[str]:
        """Get presence rooms a user should join based on their role."""
        rooms = []
        user_id = user_context.get("user_id")
        role = user_context.get("role")
        agency_id = user_context.get("agency_id")
        
        # Personal presence room
        rooms.append(f"presence:user:{user_id}")
        
        # Agency presence room
        if agency_id:
            rooms.append(f"presence:agency:{agency_id}")
        
        # Role-specific presence rooms
        if role == UserRole.SUPER_ADMIN:
            rooms.append("presence:super_admins")
        elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            rooms.append(f"presence:agency_admins:{agency_id}")
        elif role == UserRole.MODEL:
            rooms.append(f"presence:models:{agency_id}")
        elif role == UserRole.CHATTER:
            rooms.append(f"presence:chatters:{agency_id}")
        
        return rooms
    
    # Private helper methods
    
    async def _cleanup_loop(self):
        """Periodically clean up stale presence data."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_stale_presence()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in presence cleanup: {e}")
    
    async def _cleanup_stale_presence(self):
        """Remove stale presence entries."""
        now = datetime.utcnow()
        timeout_threshold = now - timedelta(seconds=self.presence_timeout)
        
        stale_users = []
        
        for user_id, last_ping_time in self.last_ping.items():
            if last_ping_time < timeout_threshold:
                stale_users.append(user_id)
        
        for user_id in stale_users:
            logger.debug(f"Marking user {user_id} as offline due to timeout")
            await self.set_user_offline(user_id)
    
    async def _store_presence_redis(self, user_id: str, presence: Dict[str, Any]):
        """Store presence in Redis for distributed systems."""
        if not redis_manager:
            return
        
        key = f"presence:{user_id}"
        
        # Store with TTL
        import json
        await redis_manager.set(
            key,
            json.dumps(presence),
            expire=self.presence_timeout * 2  # Double the timeout for Redis
        )
        
        # Also add to sorted set for efficient queries
        await redis_manager.client.zadd(
            f"presence:online:{presence.get('agency_id', 'none')}",
            {user_id: datetime.utcnow().timestamp()}
        )
    
    async def _get_redis_presence(self) -> List[Dict[str, Any]]:
        """Get all presence data from Redis."""
        if not redis_manager:
            return []
        
        presence_list = []
        
        # Get all presence keys
        keys = await redis_manager.client.keys("presence:*")
        
        for key in keys:
            if key.decode().count(":") == 1:  # Skip special keys
                data = await redis_manager.get(key.decode())
                if data:
                    import json
                    presence_list.append(json.loads(data))
        
        return presence_list
    
    async def _get_redis_presence_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get presence for specific user from Redis."""
        if not redis_manager:
            return None
        
        key = f"presence:{user_id}"
        data = await redis_manager.get(key)
        
        if data:
            import json
            return json.loads(data)
        
        return None
    
    async def _can_see_presence(self, requester_context: Dict[str, Any], target_user_id: str) -> bool:
        """Check if requester can see target user's presence."""
        requester_role = requester_context.get("role")
        requester_agency = requester_context.get("agency_id")
        
        # Super admins see all
        if requester_context.get("is_super_admin"):
            return True
        
        # Get target user's presence to check agency
        target_presence = self.presence_data.get(target_user_id)
        if not target_presence:
            target_presence = await self._get_redis_presence_for_user(target_user_id)
        
        if not target_presence:
            return False
        
        target_agency = target_presence.get("agency_id")
        target_role = target_presence.get("role")
        
        # Different agency - no access (except super admins)
        if target_agency != requester_agency:
            return False
        
        # Role-based visibility within same agency
        if requester_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return True  # See all in agency
        
        elif requester_role == UserRole.MODEL:
            # Models see admins and assigned chatters
            if target_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                return True
            # TODO: Check chatter assignment
            
        elif requester_role == UserRole.CHATTER:
            # Chatters see admins and assigned models
            if target_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                return True
            # TODO: Check model assignment
        
        return False
    
    def _filter_presence_for_broadcast(self, presence: Dict[str, Any]) -> Dict[str, Any]:
        """Filter presence data for broadcasting."""
        # Remove sensitive fields for broadcast
        filtered = presence.copy()
        
        # Remove internal fields
        filtered.pop("custom_data", None)
        
        return filtered
    
    def _filter_presence_data(
        self, 
        presence: Dict[str, Any], 
        requester_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter presence data based on requester's permissions."""
        filtered = presence.copy()
        
        # Non-admins don't see certain fields
        if requester_context.get("role") not in [
            UserRole.SUPER_ADMIN, 
            UserRole.AGENCY_OWNER, 
            UserRole.AGENCY_ADMIN
        ]:
            filtered.pop("custom_data", None)
            filtered.pop("last_seen", None)
        
        return filtered
    
    async def _apply_relationship_filters(
        self, 
        users: List[Dict[str, Any]], 
        requester_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply additional filters based on user relationships."""
        requester_role = requester_context.get("role")
        requester_id = requester_context.get("user_id")
        
        if requester_role == UserRole.MODEL:
            # Filter to show only assigned chatters
            # TODO: Implement with actual assignment check
            pass
        
        elif requester_role == UserRole.CHATTER:
            # Filter to show only assigned models
            # TODO: Implement with actual assignment check
            pass
        
        return users


# Global presence manager
presence_manager = PresenceManager()


class TypingIndicatorManager:
    """Manage typing indicators with visibility rules."""
    
    def __init__(self):
        self.typing_users: Dict[str, Dict[str, Any]] = {}  # conversation_id -> {user_id: data}
        self.typing_timeout = 5  # seconds
    
    async def start_typing(
        self, 
        user_context: Dict[str, Any], 
        conversation_id: str
    ) -> Dict[str, Any]:
        """Start typing indicator for a user in a conversation."""
        user_id = user_context.get("user_id")
        
        # Create typing data
        typing_data = {
            "user_id": user_id,
            "user_name": user_context.get("full_name") or user_context.get("email"),
            "role": user_context.get("role"),
            "started_at": datetime.utcnow().isoformat(),
            "conversation_id": conversation_id
        }
        
        # Store typing state
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id] = {}
        
        self.typing_users[conversation_id][user_id] = typing_data
        
        # Schedule cleanup
        asyncio.create_task(self._cleanup_typing(conversation_id, user_id))
        
        return typing_data
    
    async def stop_typing(self, user_id: str, conversation_id: str):
        """Stop typing indicator for a user."""
        if conversation_id in self.typing_users:
            self.typing_users[conversation_id].pop(user_id, None)
            
            # Clean up empty conversations
            if not self.typing_users[conversation_id]:
                del self.typing_users[conversation_id]
    
    def get_typing_users(
        self, 
        conversation_id: str, 
        requester_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get users currently typing in a conversation."""
        if conversation_id not in self.typing_users:
            return []
        
        typing_list = []
        requester_id = requester_context.get("user_id")
        
        for user_id, data in self.typing_users[conversation_id].items():
            # Don't show own typing indicator
            if user_id != requester_id:
                typing_list.append({
                    "user_id": user_id,
                    "user_name": data["user_name"],
                    "role": data["role"]
                })
        
        return typing_list
    
    async def _cleanup_typing(self, conversation_id: str, user_id: str):
        """Clean up typing indicator after timeout."""
        await asyncio.sleep(self.typing_timeout)
        await self.stop_typing(user_id, conversation_id)


# Global typing indicator manager
typing_manager = TypingIndicatorManager()