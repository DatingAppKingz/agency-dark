"""WebSocket endpoints for real-time features."""

from fastapi import APIRouter, WebSocket, Depends, Query
from typing import Dict, Any, Optional
import json
import logging

from core.websocket import WebSocketHandler, manager, get_current_user_websocket
from models.user import User, UserRole
from models.chat import Conversation, Message, MessageType, MessageStatus
from core.database import AsyncSessionLocal
from sqlalchemy import select, and_
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatWebSocketHandler(WebSocketHandler):
    """Handler for chat-related WebSocket connections."""
    
    async def handle_custom_message(self, data: Dict[str, Any]):
        """Handle chat-specific messages."""
        message_type = data.get("type")
        
        if message_type == "chat_message":
            await self.handle_chat_message(data)
        elif message_type == "typing_start":
            await self.handle_typing_indicator(data, True)
        elif message_type == "typing_stop":
            await self.handle_typing_indicator(data, False)
        elif message_type == "mark_read":
            await self.handle_mark_read(data)
        elif message_type == "join_chat":
            await self.handle_join_chat(data)
            
    async def handle_chat_message(self, data: Dict[str, Any]):
        """Handle incoming chat message."""
        chat_id = data.get("chat_id")
        content = data.get("content")
        message_type = data.get("message_type", "text")
        
        if not chat_id or not content:
            await self.websocket.send_json({
                "type": "error",
                "message": "Missing chat_id or content"
            })
            return
            
        async with AsyncSessionLocal() as db:
            # Verify user has access to this chat
            # For now, just check if the conversation exists
            # In production, you'd check if the user is part of the conversation
            stmt = select(Conversation).where(Conversation.id == chat_id)
            result = await db.execute(stmt)
            chat = result.scalar_one_or_none()
            
            if not chat:
                await self.websocket.send_json({
                    "type": "error",
                    "message": "Chat not found or access denied"
                })
                return
                
            # Create message
            message = Message(
                conversation_id=chat_id,
                sender_id=self.user.id,
                content=content,
                type=MessageType(message_type),
                status=MessageStatus.SENT
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)
            
            # Prepare message data
            message_data = {
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "sender_id": message.sender_id,
                    "sender_name": self.user.username,
                    "content": message.content,
                    "type": message.type.value,
                    "status": message.status.value,
                    "created_at": message.created_at.isoformat()
                }
            }
            
            # Send to all chat participants
            room_id = f"chat_{chat_id}"
            await manager.send_to_room(room_id, message_data)
            
            # Send delivery confirmation to sender
            await self.websocket.send_json({
                "type": "message_sent",
                "message_id": message.id,
                "chat_id": chat_id
            })
            
    async def handle_typing_indicator(self, data: Dict[str, Any], is_typing: bool):
        """Handle typing indicators."""
        chat_id = data.get("chat_id")
        
        if not chat_id:
            return
            
        # Notify other participants
        room_id = f"chat_{chat_id}"
        await manager.send_to_room(room_id, {
            "type": "typing_indicator",
            "chat_id": chat_id,
            "user_id": self.user.id,
            "username": self.user.username,
            "is_typing": is_typing
        }, exclude_user=self.user.id)
        
    async def handle_mark_read(self, data: Dict[str, Any]):
        """Mark messages as read."""
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")
        
        if not chat_id:
            return
            
        async with AsyncSessionLocal() as db:
            # Update message status
            if message_id:
                stmt = select(Message).where(
                    and_(
                        Message.id == message_id,
                        Message.conversation_id == chat_id
                    )
                )
                result = await db.execute(stmt)
                message = result.scalar_one_or_none()
                
                if message and message.sender_id != self.user.id:
                    message.status = MessageStatus.READ
                    message.read_at = datetime.utcnow()
                    await db.commit()
                    
                    # Notify sender
                    await manager.send_personal_message(message.sender_id, {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "read_by": self.user.id
                    })
                    
    async def handle_join_chat(self, data: Dict[str, Any]):
        """Join a chat room."""
        chat_id = data.get("chat_id")
        
        if not chat_id:
            return
            
        # Join the chat room
        room_id = f"chat_{chat_id}"
        await manager.join_room(self.user.id, room_id)
        
        # Get recent messages
        async with AsyncSessionLocal() as db:
            stmt = select(Message).where(
                Message.conversation_id == chat_id
            ).order_by(Message.created_at.desc()).limit(50)
            
            result = await db.execute(stmt)
            messages = result.scalars().all()
            
            # Send recent messages
            await self.websocket.send_json({
                "type": "chat_history",
                "chat_id": chat_id,
                "messages": [
                    {
                        "id": msg.id,
                        "sender_id": msg.sender_id,
                        "content": msg.content,
                        "type": msg.type.value,
                        "status": msg.status.value,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in reversed(messages)
                ]
            })


class NotificationWebSocketHandler(WebSocketHandler):
    """Handler for notification WebSocket connections."""
    
    async def handle(self):
        """Override to auto-join agency room."""
        # Join agency room if user belongs to one
        if self.user.agency_id:
            await manager.join_room(self.user.id, f"agency_{self.user.agency_id}")
            
        # Join role-specific rooms
        if self.user.role == UserRole.MODEL:
            await manager.join_room(self.user.id, f"model_{self.user.id}")
        elif self.user.role == UserRole.CHATTER:
            await manager.join_room(self.user.id, "chatters")
            
        await super().handle()
        
    async def handle_custom_message(self, data: Dict[str, Any]):
        """Handle notification-specific messages."""
        message_type = data.get("type")
        
        if message_type == "mark_notification_read":
            await self.handle_mark_notification_read(data)
            
    async def handle_mark_notification_read(self, data: Dict[str, Any]):
        """Mark notification as read."""
        notification_id = data.get("notification_id")
        
        if notification_id:
            # Would update notification status in database
            await self.websocket.send_json({
                "type": "notification_marked_read",
                "notification_id": notification_id
            })


@router.websocket("/chat")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time chat."""
    try:
        user = await get_current_user_websocket(websocket, token)
        handler = ChatWebSocketHandler(websocket, user)
        await handler.handle()
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        

@router.websocket("/notifications")
async def websocket_notifications_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time notifications."""
    try:
        user = await get_current_user_websocket(websocket, token)
        handler = NotificationWebSocketHandler(websocket, user)
        await handler.handle()
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")


# Utility functions for sending notifications from other parts of the app

async def send_notification(user_id: int, notification: Dict[str, Any]):
    """Send a notification to a user."""
    await manager.send_personal_message(user_id, {
        "type": "notification",
        "notification": notification
    })


async def send_agency_notification(agency_id: int, notification: Dict[str, Any]):
    """Send a notification to all users in an agency."""
    await manager.send_to_agency(agency_id, {
        "type": "agency_notification",
        "notification": notification
    })


async def broadcast_system_notification(notification: Dict[str, Any], role: Optional[UserRole] = None):
    """Broadcast a system notification."""
    if role:
        # Would filter users by role
        pass
    else:
        await manager.broadcast({
            "type": "system_notification",
            "notification": notification
        })