"""
Socket.IO namespace for the new chat system.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from socketio import AsyncNamespace
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_token
from core.errors import AuthenticationError, AuthorizationError, NotFoundError
from core.logger import get_logger
from models.user import User, UserRole
from models.model import Model
from models.chat import (
    Conversation, ConversationStatus,
    Message, MessageType, MessageStatus
)

logger = get_logger(__name__)


class ChatNamespaceV2(AsyncNamespace):
    """Socket.IO namespace for real-time chat functionality."""
    
    def __init__(self, namespace='/chat/v2'):
        super().__init__(namespace)
        self.active_users: Dict[str, Dict[str, Any]] = {}  # sid -> user info
        self.user_sids: Dict[str, List[str]] = {}  # user_id -> list of sids
    
    async def on_connect(self, sid: str, environ: dict, auth: dict):
        """Handle client connection to chat namespace."""
        try:
            # Authenticate the user
            if not auth or 'token' not in auth:
                logger.warning(f"No auth token provided for {sid}")
                return False
            
            # Decode the token to get user info
            user_data = decode_token(auth['token'])
            if not user_data:
                logger.warning(f"Invalid token for {sid}")
                return False
            
            user_id = user_data.get('user_id')
            
            # Get user from database
            async for db in get_db():
                user = await db.get(User, user_id)
                if not user or not user.is_active:
                    logger.warning(f"User {user_id} not found or inactive")
                    return False
                
                # Store user info
                user_info = {
                    'user_id': str(user.id),
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role.value,
                    'agency_id': user.agency_id
                }
                
                self.active_users[sid] = user_info
                
                # Track multiple connections per user
                if user_id not in self.user_sids:
                    self.user_sids[user_id] = []
                self.user_sids[user_id].append(sid)
                
                # Join user-specific room
                await self.enter_room(sid, f"user:{user_id}")
                
                # Join agency room
                if user.agency_id:
                    await self.enter_room(sid, f"agency:{user.agency_id}")
                
                # Join role room
                await self.enter_room(sid, f"role:{user.role.value}")
                
                logger.info(f"User {user.email} connected to chat (sid: {sid})")
                
                # Send connection confirmation
                await self.emit('connected', {
                    'status': 'connected',
                    'user': user_info,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=sid)
                
                return True
                
        except Exception as e:
            logger.error(f"Connection error for {sid}: {e}")
            return False
    
    async def on_disconnect(self, sid: str):
        """Handle client disconnection."""
        user_info = self.active_users.get(sid)
        if user_info:
            user_id = user_info['user_id']
            
            # Remove from active users
            del self.active_users[sid]
            
            # Remove from user sids
            if user_id in self.user_sids:
                self.user_sids[user_id].remove(sid)
                if not self.user_sids[user_id]:
                    del self.user_sids[user_id]
            
            logger.info(f"User {user_info['email']} disconnected (sid: {sid})")
    
    async def on_join_conversation(self, sid: str, data: Dict[str, Any]):
        """Join a conversation room for real-time updates."""
        user_info = self.active_users.get(sid)
        if not user_info:
            await self.emit('error', {'message': 'Not authenticated'}, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.emit('error', {'message': 'Conversation ID required'}, room=sid)
            return
        
        async for db in get_db():
            # Check if user has access to the conversation
            conversation = await self._get_conversation_for_user(
                db, conversation_id, user_info
            )
            
            if not conversation:
                await self.emit('error', {'message': 'Conversation not found or access denied'}, room=sid)
                return
            
            # Join conversation room
            room_name = f"conversation:{conversation_id}"
            await self.enter_room(sid, room_name)
            
            # Send confirmation
            await self.emit('joined_conversation', {
                'conversation_id': conversation_id,
                'status': 'joined'
            }, room=sid)
            
            # Mark messages as read if user is model or chatter
            if user_info['role'] in ['model', 'chatter']:
                await self._mark_messages_read(db, conversation_id, user_info['user_id'])
            
            logger.info(f"User {user_info['email']} joined conversation {conversation_id}")
    
    async def on_leave_conversation(self, sid: str, data: Dict[str, Any]):
        """Leave a conversation room."""
        user_info = self.active_users.get(sid)
        if not user_info:
            return
        
        conversation_id = data.get('conversation_id')
        if conversation_id:
            room_name = f"conversation:{conversation_id}"
            await self.leave_room(sid, room_name)
            
            await self.emit('left_conversation', {
                'conversation_id': conversation_id,
                'status': 'left'
            }, room=sid)
    
    async def on_send_message(self, sid: str, data: Dict[str, Any]):
        """Handle sending a new message."""
        user_info = self.active_users.get(sid)
        if not user_info:
            await self.emit('error', {'message': 'Not authenticated'}, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        content = data.get('content')
        message_type = data.get('type', 'text')
        media_url = data.get('media_url')
        amount = data.get('amount')
        
        if not conversation_id or not content:
            await self.emit('error', {'message': 'Conversation ID and content required'}, room=sid)
            return
        
        async for db in get_db():
            # Verify access to conversation
            conversation = await self._get_conversation_for_user(
                db, conversation_id, user_info
            )
            
            if not conversation:
                await self.emit('error', {'message': 'Conversation not found or access denied'}, room=sid)
                return
            
            # Determine sender type
            sender_type = self._get_sender_type(user_info['role'])
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                sender_id=int(user_info['user_id']),
                sender_type=sender_type,
                type=message_type,
                content=content,
                media_url=media_url,
                amount=amount,
                agency_id=conversation.agency_id,
                status=MessageStatus.SENT
            )
            
            db.add(message)
            
            # Update conversation
            conversation.last_message_at = datetime.utcnow().isoformat()
            if sender_type == 'fan':
                conversation.last_fan_message_at = conversation.last_message_at
                conversation.unread_count += 1
            
            await db.commit()
            await db.refresh(message)
            
            # Prepare message data for emission
            message_data = {
                'id': message.id,
                'conversation_id': conversation_id,
                'sender_id': message.sender_id,
                'sender_type': sender_type,
                'sender_name': user_info['full_name'] or user_info['email'],
                'type': message_type,
                'content': content,
                'media_url': media_url,
                'amount': float(amount) if amount else None,
                'status': message.status.value,
                'created_at': message.created_at.isoformat()
            }
            
            # Emit to conversation room
            room_name = f"conversation:{conversation_id}"
            await self.emit('new_message', message_data, room=room_name)
            
            # Also emit to specific users who might not be in the room
            # Model user
            if conversation.model:
                model = await db.get(Model, conversation.model_id)
                if model and model.user_id:
                    await self._emit_to_user(str(model.user_id), 'new_message', message_data)
            
            # Assigned chatter
            if conversation.assigned_chatter_id:
                await self._emit_to_user(
                    str(conversation.assigned_chatter_id), 
                    'new_message', 
                    message_data
                )
            
            logger.info(f"Message sent in conversation {conversation_id} by {user_info['email']}")
    
    async def on_typing_start(self, sid: str, data: Dict[str, Any]):
        """Handle typing indicator start."""
        user_info = self.active_users.get(sid)
        if not user_info:
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        # Emit to conversation room
        room_name = f"conversation:{conversation_id}"
        await self.emit('user_typing', {
            'conversation_id': conversation_id,
            'user_id': user_info['user_id'],
            'user_name': user_info['full_name'] or user_info['email'],
            'is_typing': True
        }, room=room_name, skip_sid=sid)
    
    async def on_typing_stop(self, sid: str, data: Dict[str, Any]):
        """Handle typing indicator stop."""
        user_info = self.active_users.get(sid)
        if not user_info:
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        # Emit to conversation room
        room_name = f"conversation:{conversation_id}"
        await self.emit('user_typing', {
            'conversation_id': conversation_id,
            'user_id': user_info['user_id'],
            'user_name': user_info['full_name'] or user_info['email'],
            'is_typing': False
        }, room=room_name, skip_sid=sid)
    
    async def on_mark_read(self, sid: str, data: Dict[str, Any]):
        """Mark messages as read."""
        user_info = self.active_users.get(sid)
        if not user_info:
            return
        
        conversation_id = data.get('conversation_id')
        message_ids = data.get('message_ids', [])
        
        if not conversation_id:
            return
        
        async for db in get_db():
            # Mark specific messages or all unread messages
            if message_ids:
                await db.execute(
                    update(Message).where(
                        and_(
                            Message.conversation_id == conversation_id,
                            Message.id.in_(message_ids),
                            Message.sender_type == 'fan',
                            Message.read_at.is_(None)
                        )
                    ).values(
                        read_at=datetime.utcnow().isoformat(),
                        status=MessageStatus.READ
                    )
                )
            else:
                # Mark all unread fan messages
                await self._mark_messages_read(db, conversation_id, user_info['user_id'])
            
            await db.commit()
            
            # Notify others in conversation
            room_name = f"conversation:{conversation_id}"
            await self.emit('messages_read', {
                'conversation_id': conversation_id,
                'reader_id': user_info['user_id'],
                'message_ids': message_ids
            }, room=room_name, skip_sid=sid)
    
    async def on_update_conversation_status(self, sid: str, data: Dict[str, Any]):
        """Update conversation status (archive, block, etc)."""
        user_info = self.active_users.get(sid)
        if not user_info:
            return
        
        # Only admins, agency owners, and models can update status
        if user_info['role'] not in ['admin', 'agency_owner', 'model']:
            await self.emit('error', {'message': 'Insufficient permissions'}, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        status = data.get('status')
        
        if not conversation_id or not status:
            return
        
        async for db in get_db():
            conversation = await self._get_conversation_for_user(
                db, conversation_id, user_info
            )
            
            if not conversation:
                return
            
            conversation.status = status
            await db.commit()
            
            # Notify all participants
            room_name = f"conversation:{conversation_id}"
            await self.emit('conversation_updated', {
                'conversation_id': conversation_id,
                'status': status,
                'updated_by': user_info['user_id']
            }, room=room_name)
    
    # Helper methods
    async def _get_conversation_for_user(
        self, 
        db: AsyncSession, 
        conversation_id: int, 
        user_info: Dict[str, Any]
    ) -> Optional[Conversation]:
        """Get conversation with permission check."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        
        # Apply agency filter for multi-tenant access
        if user_info['role'] not in ['super_admin', 'admin']:
            if user_info['agency_id']:
                stmt = stmt.where(Conversation.agency_id == user_info['agency_id'])
        
        conversation = await db.scalar(stmt)
        if not conversation:
            return None
        
        # Additional permission checks
        if user_info['role'] == 'model':
            # Models can only see their own conversations
            model = await db.scalar(
                select(Model).where(Model.user_id == int(user_info['user_id']))
            )
            if not model or conversation.model_id != model.id:
                return None
        elif user_info['role'] == 'chatter':
            # Chatters can only see assigned conversations
            if conversation.assigned_chatter_id != int(user_info['user_id']):
                return None
        
        return conversation
    
    def _get_sender_type(self, role: str) -> str:
        """Determine sender type based on user role."""
        if role == 'model':
            return 'model'
        elif role == 'chatter':
            return 'chatter'
        else:
            return 'system'
    
    async def _mark_messages_read(
        self, 
        db: AsyncSession, 
        conversation_id: int, 
        user_id: str
    ):
        """Mark all unread messages in a conversation as read."""
        result = await db.execute(
            update(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_type == 'fan',
                    Message.read_at.is_(None)
                )
            ).values(
                read_at=datetime.utcnow().isoformat(),
                status=MessageStatus.READ
            ).returning(Message.id)
        )
        
        read_count = len(result.fetchall())
        
        if read_count > 0:
            # Update conversation unread count
            conversation = await db.get(Conversation, conversation_id)
            if conversation:
                conversation.unread_count = max(0, conversation.unread_count - read_count)
    
    async def _emit_to_user(self, user_id: str, event: str, data: Any):
        """Emit event to all connections of a specific user."""
        if user_id in self.user_sids:
            for sid in self.user_sids[user_id]:
                await self.emit(event, data, room=sid)
    
    # Admin/System methods
    async def broadcast_to_agency(self, agency_id: int, event: str, data: Any):
        """Broadcast event to all users in an agency."""
        room_name = f"agency:{agency_id}"
        await self.emit(event, data, room=room_name)
    
    async def broadcast_to_conversation(self, conversation_id: int, event: str, data: Any):
        """Broadcast event to all users in a conversation."""
        room_name = f"conversation:{conversation_id}"
        await self.emit(event, data, room=room_name)
    
    async def get_online_users(self, agency_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get list of online users, optionally filtered by agency."""
        online_users = []
        for sid, user_info in self.active_users.items():
            if agency_id is None or user_info.get('agency_id') == agency_id:
                online_users.append({
                    'user_id': user_info['user_id'],
                    'email': user_info['email'],
                    'full_name': user_info['full_name'],
                    'role': user_info['role'],
                    'connected_at': user_info.get('connected_at')
                })
        return online_users