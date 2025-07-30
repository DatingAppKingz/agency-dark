"""WebSocket connection manager and utilities."""

from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status
from datetime import datetime
import json
import asyncio
import logging
from collections import defaultdict

from core.redis import redis_manager
from api.v1.endpoints.auth_simple import decode_access_token
from models.user import User
from core.database import AsyncSessionLocal
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time features."""
    
    def __init__(self):
        # Store active connections by user_id
        self._connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        # Store connection metadata
        self._connection_meta: Dict[WebSocket, Dict[str, Any]] = {}
        # Store room memberships (e.g., chat rooms, agency rooms)
        self._rooms: Dict[str, Set[int]] = defaultdict(set)
        # Store user to rooms mapping
        self._user_rooms: Dict[int, Set[str]] = defaultdict(set)
        
    async def connect(self, websocket: WebSocket, user_id: int, metadata: Optional[Dict[str, Any]] = None):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        # Add to connections
        self._connections[user_id].add(websocket)
        
        # Store metadata
        self._connection_meta[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Notify about connection
        await self._notify_connection_status(user_id, "connected")
        
        logger.info(f"User {user_id} connected via WebSocket")
        
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        # Get user_id from metadata
        meta = self._connection_meta.get(websocket)
        if not meta:
            return
            
        user_id = meta["user_id"]
        
        # Remove from connections
        self._connections[user_id].discard(websocket)
        
        # If no more connections for this user, clean up
        if not self._connections[user_id]:
            del self._connections[user_id]
            
            # Leave all rooms
            for room_id in list(self._user_rooms[user_id]):
                await self.leave_room(user_id, room_id)
            
            # Notify about disconnection
            await self._notify_connection_status(user_id, "disconnected")
        
        # Remove metadata
        del self._connection_meta[websocket]
        
        logger.info(f"User {user_id} disconnected from WebSocket")
        
    async def join_room(self, user_id: int, room_id: str):
        """Add a user to a room."""
        self._rooms[room_id].add(user_id)
        self._user_rooms[user_id].add(room_id)
        
        # Notify room members
        await self.send_to_room(room_id, {
            "type": "room_join",
            "room_id": room_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user=user_id)
        
    async def leave_room(self, user_id: int, room_id: str):
        """Remove a user from a room."""
        self._rooms[room_id].discard(user_id)
        self._user_rooms[user_id].discard(room_id)
        
        # If room is empty, clean up
        if not self._rooms[room_id]:
            del self._rooms[room_id]
        
        # Notify room members
        await self.send_to_room(room_id, {
            "type": "room_leave",
            "room_id": room_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    async def send_personal_message(self, user_id: int, message: Dict[str, Any]):
        """Send a message to a specific user."""
        if user_id not in self._connections:
            # User not connected, could queue message in Redis
            await self._queue_offline_message(user_id, message)
            return
        
        # Send to all user's connections
        disconnected = []
        for websocket in self._connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            await self.disconnect(ws)
            
    async def send_to_room(self, room_id: str, message: Dict[str, Any], exclude_user: Optional[int] = None):
        """Send a message to all users in a room."""
        user_ids = self._rooms.get(room_id, set())
        
        for user_id in user_ids:
            if user_id != exclude_user:
                await self.send_personal_message(user_id, message)
                
    async def broadcast(self, message: Dict[str, Any], user_ids: Optional[Set[int]] = None):
        """Broadcast a message to multiple users or all connected users."""
        if user_ids is None:
            user_ids = set(self._connections.keys())
            
        tasks = []
        for user_id in user_ids:
            tasks.append(self.send_personal_message(user_id, message))
            
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def send_to_agency(self, agency_id: int, message: Dict[str, Any]):
        """Send a message to all users in an agency."""
        room_id = f"agency_{agency_id}"
        await self.send_to_room(room_id, message)
        
    async def _notify_connection_status(self, user_id: int, status: str):
        """Notify about user connection status changes."""
        # Could implement presence tracking here
        await redis_manager.set(
            f"user_presence:{user_id}",
            json.dumps({
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }),
            expire=300  # 5 minutes
        )
        
    async def _queue_offline_message(self, user_id: int, message: Dict[str, Any]):
        """Queue a message for offline users."""
        key = f"offline_messages:{user_id}"
        await redis_manager.client.lpush(key, json.dumps(message))
        await redis_manager.client.expire(key, 86400)  # 24 hours
        
    async def get_offline_messages(self, user_id: int) -> list[Dict[str, Any]]:
        """Retrieve queued messages for a user."""
        key = f"offline_messages:{user_id}"
        messages = await redis_manager.client.lrange(key, 0, -1)
        
        # Clear the messages
        await redis_manager.client.delete(key)
        
        return [json.loads(msg) for msg in messages]
        
    def get_user_connections(self, user_id: int) -> int:
        """Get the number of active connections for a user."""
        return len(self._connections.get(user_id, set()))
        
    def get_room_users(self, room_id: str) -> Set[int]:
        """Get all users in a room."""
        return self._rooms.get(room_id, set()).copy()
        
    def is_user_online(self, user_id: int) -> bool:
        """Check if a user is online."""
        return user_id in self._connections


# Global connection manager instance
manager = ConnectionManager()


async def get_current_user_websocket(websocket: WebSocket, token: str) -> User:
    """Authenticate WebSocket connection."""
    try:
        # Decode token
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user from database
        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.id == int(user_id))
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                raise HTTPException(status_code=401, detail="User not found or inactive")
                
            return user
            
    except Exception as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(status_code=401, detail="Authentication failed")


class WebSocketHandler:
    """Base class for WebSocket handlers."""
    
    def __init__(self, websocket: WebSocket, user: User):
        self.websocket = websocket
        self.user = user
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def handle(self):
        """Main handler loop."""
        try:
            # Connect to manager
            await manager.connect(self.websocket, self.user.id)
            
            # Send any offline messages
            offline_messages = await manager.get_offline_messages(self.user.id)
            for msg in offline_messages:
                await self.websocket.send_json(msg)
            
            # Handle incoming messages
            while True:
                data = await self.websocket.receive_json()
                await self.process_message(data)
                
        except WebSocketDisconnect:
            await manager.disconnect(self.websocket)
        except Exception as e:
            self.logger.error(f"WebSocket error for user {self.user.id}: {e}")
            await manager.disconnect(self.websocket)
            
    async def process_message(self, data: Dict[str, Any]):
        """Process incoming WebSocket message."""
        message_type = data.get("type")
        
        if message_type == "ping":
            await self.websocket.send_json({"type": "pong"})
        elif message_type == "join_room":
            await self.handle_join_room(data)
        elif message_type == "leave_room":
            await self.handle_leave_room(data)
        else:
            # Subclasses should implement specific message handling
            await self.handle_custom_message(data)
            
    async def handle_join_room(self, data: Dict[str, Any]):
        """Handle room join request."""
        room_id = data.get("room_id")
        if room_id:
            await manager.join_room(self.user.id, room_id)
            await self.websocket.send_json({
                "type": "room_joined",
                "room_id": room_id
            })
            
    async def handle_leave_room(self, data: Dict[str, Any]):
        """Handle room leave request."""
        room_id = data.get("room_id")
        if room_id:
            await manager.leave_room(self.user.id, room_id)
            await self.websocket.send_json({
                "type": "room_left",
                "room_id": room_id
            })
            
    async def handle_custom_message(self, data: Dict[str, Any]):
        """Handle custom message types. Override in subclasses."""
        pass