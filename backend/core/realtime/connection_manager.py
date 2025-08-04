from typing import Dict, Set, Optional, Any, List
from datetime import datetime, timedelta
import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

@dataclass
class ConnectionInfo:
    user_id: int
    connection_id: str
    connected_at: datetime
    last_activity: datetime
    rooms: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: ConnectionState = ConnectionState.CONNECTED
    heartbeat_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "connection_id": self.connection_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "rooms": list(self.rooms),
            "metadata": self.metadata,
            "state": self.state.value,
            "heartbeat_count": self.heartbeat_count,
        }

class EnhancedConnectionManager:
    def __init__(self):
        # Connection tracking
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[int, Set[str]] = {}
        self.room_members: Dict[str, Set[str]] = {}
        
        # Heartbeat monitoring
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_timeout = 90  # seconds
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        # Message queue for offline delivery
        self.message_queue: Dict[int, List[Dict[str, Any]]] = {}
        self.max_queue_size = 100
        
        # Presence tracking
        self.user_presence: Dict[int, Dict[str, Any]] = {}
        
    async def register_connection(
        self, 
        connection_id: str, 
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConnectionInfo:
        """Register a new connection."""
        now = datetime.utcnow()
        
        # Create connection info
        conn_info = ConnectionInfo(
            user_id=user_id,
            connection_id=connection_id,
            connected_at=now,
            last_activity=now,
            metadata=metadata or {}
        )
        
        # Store connection
        self.connections[connection_id] = conn_info
        
        # Track user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # Update presence
        await self.update_presence(user_id, "online", metadata)
        
        # Start heartbeat monitoring
        self.heartbeat_tasks[connection_id] = asyncio.create_task(
            self._monitor_heartbeat(connection_id)
        )
        
        # Deliver queued messages
        await self.deliver_queued_messages(user_id)
        
        logger.info(f"Connection registered: {connection_id} for user {user_id}")
        return conn_info
    
    async def unregister_connection(self, connection_id: str) -> None:
        """Unregister a connection."""
        conn_info = self.connections.get(connection_id)
        if not conn_info:
            return
        
        # Cancel heartbeat monitoring
        if connection_id in self.heartbeat_tasks:
            self.heartbeat_tasks[connection_id].cancel()
            del self.heartbeat_tasks[connection_id]
        
        # Remove from rooms
        for room in list(conn_info.rooms):
            await self.leave_room(connection_id, room)
        
        # Remove from user connections
        if conn_info.user_id in self.user_connections:
            self.user_connections[conn_info.user_id].discard(connection_id)
            if not self.user_connections[conn_info.user_id]:
                del self.user_connections[conn_info.user_id]
                # Update presence if no more connections
                await self.update_presence(conn_info.user_id, "offline")
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"Connection unregistered: {connection_id}")
    
    async def join_room(self, connection_id: str, room: str) -> bool:
        """Join a room."""
        conn_info = self.connections.get(connection_id)
        if not conn_info:
            return False
        
        # Add to room
        if room not in self.room_members:
            self.room_members[room] = set()
        self.room_members[room].add(connection_id)
        
        # Update connection info
        conn_info.rooms.add(room)
        conn_info.last_activity = datetime.utcnow()
        
        logger.debug(f"Connection {connection_id} joined room {room}")
        return True
    
    async def leave_room(self, connection_id: str, room: str) -> bool:
        """Leave a room."""
        conn_info = self.connections.get(connection_id)
        if not conn_info:
            return False
        
        # Remove from room
        if room in self.room_members:
            self.room_members[room].discard(connection_id)
            if not self.room_members[room]:
                del self.room_members[room]
        
        # Update connection info
        conn_info.rooms.discard(room)
        conn_info.last_activity = datetime.utcnow()
        
        logger.debug(f"Connection {connection_id} left room {room}")
        return True
    
    async def update_presence(
        self, 
        user_id: int, 
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update user presence."""
        self.user_presence[user_id] = {
            "user_id": user_id,
            "status": status,
            "last_seen": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        # Broadcast presence update to relevant connections
        await self.broadcast_presence_update(user_id)
    
    async def broadcast_presence_update(self, user_id: int) -> None:
        """Broadcast presence update to relevant users."""
        presence_data = self.user_presence.get(user_id)
        if not presence_data:
            return
        
        # Get all connections that should receive this update
        # (This is simplified - in production, you'd check friendships, etc.)
        for conn_id, conn_info in self.connections.items():
            if conn_info.user_id != user_id:  # Don't send to self
                # Send presence update
                # (This would integrate with your WebSocket send mechanism)
                pass
    
    async def heartbeat(self, connection_id: str) -> None:
        """Handle heartbeat from connection."""
        conn_info = self.connections.get(connection_id)
        if conn_info:
            conn_info.last_activity = datetime.utcnow()
            conn_info.heartbeat_count += 1
            logger.debug(f"Heartbeat received from {connection_id}")
    
    async def _monitor_heartbeat(self, connection_id: str) -> None:
        """Monitor connection heartbeat."""
        while connection_id in self.connections:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                conn_info = self.connections.get(connection_id)
                if not conn_info:
                    break
                
                # Check last activity
                time_since_activity = (
                    datetime.utcnow() - conn_info.last_activity
                ).total_seconds()
                
                if time_since_activity > self.heartbeat_timeout:
                    logger.warning(
                        f"Connection {connection_id} timed out "
                        f"(no activity for {time_since_activity}s)"
                    )
                    # Mark connection as dead
                    await self.mark_connection_dead(connection_id)
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    async def mark_connection_dead(self, connection_id: str) -> None:
        """Mark a connection as dead (for reconnection handling)."""
        conn_info = self.connections.get(connection_id)
        if conn_info:
            conn_info.state = ConnectionState.DISCONNECTED
            # Don't immediately remove - allow time for reconnection
            asyncio.create_task(self._delayed_cleanup(connection_id))
    
    async def _delayed_cleanup(self, connection_id: str, delay: int = 300) -> None:
        """Clean up connection after delay if not reconnected."""
        await asyncio.sleep(delay)
        conn_info = self.connections.get(connection_id)
        if conn_info and conn_info.state == ConnectionState.DISCONNECTED:
            await self.unregister_connection(connection_id)
    
    async def queue_message(
        self, 
        user_id: int, 
        message: Dict[str, Any]
    ) -> None:
        """Queue message for offline delivery."""
        if user_id not in self.message_queue:
            self.message_queue[user_id] = []
        
        # Add timestamp
        message["queued_at"] = datetime.utcnow().isoformat()
        
        # Limit queue size
        if len(self.message_queue[user_id]) >= self.max_queue_size:
            self.message_queue[user_id].pop(0)
        
        self.message_queue[user_id].append(message)
        logger.debug(f"Message queued for user {user_id}")
    
    async def deliver_queued_messages(self, user_id: int) -> List[Dict[str, Any]]:
        """Deliver queued messages to user."""
        if user_id not in self.message_queue:
            return []
        
        messages = self.message_queue[user_id]
        del self.message_queue[user_id]
        
        logger.info(f"Delivering {len(messages)} queued messages to user {user_id}")
        return messages
    
    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get connection information."""
        return self.connections.get(connection_id)
    
    def get_user_connections(self, user_id: int) -> List[ConnectionInfo]:
        """Get all connections for a user."""
        conn_ids = self.user_connections.get(user_id, set())
        return [
            self.connections[conn_id] 
            for conn_id in conn_ids 
            if conn_id in self.connections
        ]
    
    def get_room_members(self, room: str) -> List[ConnectionInfo]:
        """Get all members in a room."""
        conn_ids = self.room_members.get(room, set())
        return [
            self.connections[conn_id] 
            for conn_id in conn_ids 
            if conn_id in self.connections
        ]
    
    def get_presence(self, user_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get presence information for users."""
        if user_ids:
            return [
                {**self.user_presence[uid], "last_seen": self.user_presence[uid]["last_seen"].isoformat()}
                for uid in user_ids 
                if uid in self.user_presence
            ]
        else:
            return [
                {**presence, "last_seen": presence["last_seen"].isoformat()}
                for presence in self.user_presence.values()
            ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "unique_users": len(self.user_connections),
            "total_rooms": len(self.room_members),
            "queued_messages": sum(
                len(messages) for messages in self.message_queue.values()
            ),
            "online_users": len([
                p for p in self.user_presence.values() 
                if p["status"] == "online"
            ]),
        }

# Global instance
connection_manager = EnhancedConnectionManager()