"""
Enhanced Socket.IO namespace with complete message filtering and data isolation.
"""
import logging
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import json

from socketio import AsyncNamespace
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security_v2.authentication import enhanced_websocket_auth, WebSocketAuthError
from core.websocket_presence import presence_manager, typing_manager
from core.filters.websocket_filter import WebSocketMessageFilter, websocket_room_filter
from api.v1.realtime.message_filter import message_filter_service
from core.logger import get_logger
from models.user import User, UserRole
from models.model import Model
from models.chat import (
    Conversation, ConversationStatus,
    Message, MessageType, MessageStatus
)

logger = get_logger(__name__)


class FilteredChatNamespace(AsyncNamespace):
    """Socket.IO namespace with complete filtering and data isolation."""
    
    def __init__(self, namespace='/chat/v3'):
        super().__init__(namespace)
        self.auth = enhanced_websocket_auth
        self.presence = presence_manager
        self.typing = typing_manager
        self.message_filter = message_filter_service
    
    async def on_connect(self, sid: str, environ: dict, auth: dict):
        """Handle connection with authentication and initial room setup."""
        try:
            # Get client info
            client_info = {
                'ip': environ.get('REMOTE_ADDR', 'unknown'),
                'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
                'origin': environ.get('HTTP_ORIGIN', 'unknown')
            }
            
            # Authenticate
            if not auth or 'token' not in auth:
                logger.warning(f"No auth token provided for {sid}")
                return False
            
            try:
                user_context = await self.auth.authenticate_connection(
                    token=auth['token'],
                    connection_id=sid,
                    client_info=client_info
                )
            except WebSocketAuthError as e:
                logger.warning(f"Auth failed for {sid}: {e}")
                await self.emit('auth_error', {'error': str(e)}, room=sid)
                return False
            
            # Update presence
            presence_update = await self.presence.update_presence(
                user_context, status="online"
            )
            
            # Join default rooms
            await self._join_default_rooms(sid, user_context)
            
            # Get filtered online users
            online_users = await self.presence.get_online_users(user_context)
            
            # Send connection success
            await self.emit('connected', {
                'status': 'connected',
                'user': {
                    'id': user_context['user_id'],
                    'email': user_context['email'],
                    'role': user_context['role'],
                    'permissions': user_context['permissions']
                },
                'online_users': online_users,
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            
            # Broadcast presence update to relevant users
            await self._broadcast_presence_update(user_context, presence_update, "online")
            
            # Check token refresh
            new_token = await self.auth.refresh_token_if_needed(sid)
            if new_token:
                await self.emit('token_refresh', {'new_token': new_token}, room=sid)
            
            logger.info(f"Filtered connection established: {user_context['email']}")
            return True
            
        except Exception as e:
            logger.error(f"Connection error for {sid}: {e}")
            return False
    
    async def on_disconnect(self, sid: str):
        """Handle disconnection with presence update."""
        user_context = self.auth.active_connections.get(sid)
        
        if user_context:
            # Update presence
            await self.presence.set_user_offline(user_context['user_id'])
            
            # Broadcast offline status
            presence_update = {
                "user_id": user_context['user_id'],
                "status": "offline",
                "last_seen": datetime.utcnow().isoformat()
            }
            await self._broadcast_presence_update(user_context, presence_update, "offline")
        
        # Clean up auth
        await self.auth.disconnect(sid)
        logger.info(f"Client {sid} disconnected")
    
    async def on_join_conversation(self, sid: str, data: Dict[str, Any]):
        """Join conversation with filtering validation."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            await self.emit('error', {'message': 'Not authenticated'}, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.emit('error', {'message': 'Conversation ID required'}, room=sid)
            return
        
        # Validate access
        if not await self.auth.validate_room_access(
            user_context, 'conversation', str(conversation_id)
        ):
            await self.emit('error', {
                'message': 'Access denied',
                'code': 'ACCESS_DENIED'
            }, room=sid)
            return
        
        # Join room
        room_name = f"conversation:{conversation_id}"
        await self.enter_room(sid, room_name)
        
        # Get filtered conversation participants
        participants = await self._get_filtered_participants(conversation_id, user_context)
        
        # Get typing users in conversation
        typing_users = self.typing.get_typing_users(str(conversation_id), user_context)
        
        await self.emit('joined_conversation', {
            'conversation_id': conversation_id,
            'participants': participants,
            'typing_users': typing_users
        }, room=sid)
        
        # Mark messages as read
        if user_context['role'] in [UserRole.MODEL, UserRole.CHATTER]:
            async for db in get_db():
                await self._mark_messages_read(db, conversation_id, user_context['user_id'])
    
    async def on_send_message(self, sid: str, data: Dict[str, Any]):
        """Send message with complete filtering."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        # Validate permissions
        if not await self.auth.validate_message_permissions(
            user_context, 'send_message', data
        ):
            await self.emit('error', {'message': 'Permission denied'}, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        content = data.get('content')
        
        if not conversation_id or not content:
            await self.emit('error', {'message': 'Invalid message data'}, room=sid)
            return
        
        async for db in get_db():
            # Create and save message
            message = await self._create_message(db, user_context, data)
            if not message:
                await self.emit('error', {'message': 'Failed to send message'}, room=sid)
                return
            
            # Prepare message data
            message_data = self._prepare_message_data(message, user_context)
            
            # Get all potential recipients
            participants = await self.message_filter.get_conversation_participants(
                conversation_id
            )
            
            # Filter message for each participant
            user_contexts = []
            for participant_id in participants:
                # Get participant context (would need to fetch from active connections or DB)
                participant_context = self._get_user_context(participant_id)
                if participant_context:
                    user_contexts.append(participant_context)
            
            # Filter message for all users
            filtered_messages = await self.message_filter.filter_message_for_users(
                message_data, "chat_message", user_contexts
            )
            
            # Send filtered message to each user
            for user_id, filtered_message in filtered_messages.items():
                if filtered_message:
                    await self._emit_to_user(user_id, 'new_message', filtered_message)
            
            logger.info(f"Filtered message sent in conversation {conversation_id}")
    
    async def on_typing_start(self, sid: str, data: Dict[str, Any]):
        """Handle typing start with visibility filtering."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        # Start typing
        typing_data = await self.typing.start_typing(user_context, str(conversation_id))
        
        # Get conversation participants who should see typing
        participants = await self.message_filter.get_conversation_participants(
            int(conversation_id)
        )
        
        # Notify relevant users
        for participant_id in participants:
            if participant_id != user_context['user_id']:
                await self._emit_to_user(participant_id, 'user_typing', {
                    'conversation_id': conversation_id,
                    'user': typing_data,
                    'is_typing': True
                })
    
    async def on_typing_stop(self, sid: str, data: Dict[str, Any]):
        """Handle typing stop."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        # Stop typing
        await self.typing.stop_typing(user_context['user_id'], str(conversation_id))
        
        # Notify participants
        participants = await self.message_filter.get_conversation_participants(
            int(conversation_id)
        )
        
        for participant_id in participants:
            if participant_id != user_context['user_id']:
                await self._emit_to_user(participant_id, 'user_typing', {
                    'conversation_id': conversation_id,
                    'user_id': user_context['user_id'],
                    'is_typing': False
                })
    
    async def on_get_online_users(self, sid: str, data: Dict[str, Any]):
        """Get filtered list of online users."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        # Get filters from request
        agency_filter = data.get('agency_id')
        role_filter = data.get('roles')
        
        # Get filtered online users
        online_users = await self.presence.get_online_users(
            user_context,
            agency_id=agency_filter,
            role_filter=role_filter
        )
        
        await self.emit('online_users', {
            'users': online_users,
            'count': len(online_users),
            'timestamp': datetime.utcnow().isoformat()
        }, room=sid)
    
    async def on_update_presence(self, sid: str, data: Dict[str, Any]):
        """Update user presence status."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        status = data.get('status', 'online')
        custom_data = data.get('custom_data')
        
        # Update presence
        presence_update = await self.presence.update_presence(
            user_context, status, custom_data
        )
        
        # Broadcast to relevant users
        await self._broadcast_presence_update(user_context, presence_update, status)
    
    async def on_broadcast_agency(self, sid: str, data: Dict[str, Any]):
        """Broadcast message to agency with filtering."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        # Check permission
        if user_context['role'] not in [
            UserRole.SUPER_ADMIN, 
            UserRole.AGENCY_OWNER, 
            UserRole.AGENCY_ADMIN
        ]:
            await self.emit('error', {'message': 'Permission denied'}, room=sid)
            return
        
        agency_id = user_context['agency_id']
        message = data.get('message')
        
        if not agency_id or not message:
            return
        
        # Get all agency users
        agency_users = await self.message_filter.get_users_for_agency_broadcast(
            agency_id
        )
        
        # Broadcast to each user
        broadcast_data = {
            'type': 'agency_broadcast',
            'message': message,
            'from': user_context['email'],
            'agency_id': agency_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for user_id in agency_users:
            await self._emit_to_user(user_id, 'agency_message', broadcast_data)
    
    # Helper methods
    
    async def _join_default_rooms(self, sid: str, user_context: Dict[str, Any]):
        """Join default rooms with filtering."""
        # Personal room
        await self.enter_room(sid, f"user:{user_context['user_id']}")
        
        # Agency room (if applicable)
        if user_context['agency_id']:
            await self.enter_room(sid, f"agency:{user_context['agency_id']}")
        
        # Role room
        await self.enter_room(sid, f"role:{user_context['role']}")
        
        # Presence rooms
        presence_rooms = self.presence.get_presence_rooms(user_context)
        for room in presence_rooms:
            await self.enter_room(sid, room)
    
    async def _broadcast_presence_update(
        self, 
        user_context: Dict[str, Any], 
        presence_update: Dict[str, Any],
        status: str
    ):
        """Broadcast presence update to relevant users."""
        # Get users who should see this presence update
        agency_id = user_context.get('agency_id')
        
        if agency_id:
            # Broadcast to agency presence room
            await self.emit('presence_update', presence_update, 
                          room=f"presence:agency:{agency_id}")
        
        # Also emit to role-specific presence rooms
        role = user_context.get('role')
        if role in [UserRole.MODEL, UserRole.CHATTER]:
            # For models/chatters, only notify specific users based on assignments
            # This would need to check assignments
            pass
    
    async def _get_filtered_participants(
        self, 
        conversation_id: int, 
        requester_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get conversation participants filtered by visibility rules."""
        participants = []
        
        # Get all participant IDs
        participant_ids = await self.message_filter.get_conversation_participants(
            conversation_id
        )
        
        # Get presence for each participant
        for participant_id in participant_ids:
            presence = await self.presence.get_user_presence(
                participant_id, requester_context
            )
            if presence:
                participants.append(presence)
        
        return participants
    
    async def _create_message(
        self, 
        db: AsyncSession, 
        user_context: Dict[str, Any], 
        data: Dict[str, Any]
    ) -> Optional[Message]:
        """Create and save a message."""
        conversation_id = data.get('conversation_id')
        
        # Get conversation
        conversation = await db.get(Conversation, int(conversation_id))
        if not conversation:
            return None
        
        # Determine sender type
        sender_type = self._get_sender_type(user_context['role'])
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            sender_id=int(user_context['user_id']),
            sender_type=sender_type,
            type=data.get('type', 'text'),
            content=data.get('content'),
            media_url=data.get('media_url'),
            amount=data.get('amount'),
            agency_id=conversation.agency_id,
            status=MessageStatus.SENT
        )
        
        db.add(message)
        
        # Update conversation
        conversation.last_message_at = datetime.utcnow()
        if sender_type == 'fan':
            conversation.last_fan_message_at = conversation.last_message_at
            conversation.unread_count += 1
        
        await db.commit()
        await db.refresh(message)
        
        return message
    
    def _prepare_message_data(
        self, 
        message: Message, 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare message data for transmission."""
        return {
            'id': str(message.id),
            'conversation_id': message.conversation_id,
            'sender_id': str(message.sender_id),
            'sender_name': user_context.get('full_name') or user_context.get('email'),
            'sender_role': user_context.get('role'),
            'type': message.type,
            'content': message.content,
            'media_url': message.media_url,
            'amount': float(message.amount) if message.amount else None,
            'status': message.status.value,
            'agency_id': str(message.agency_id) if message.agency_id else None,
            'created_at': message.created_at.isoformat()
        }
    
    def _get_sender_type(self, role: str) -> str:
        """Get sender type from role."""
        if role == UserRole.MODEL:
            return 'model'
        elif role == UserRole.CHATTER:
            return 'chatter'
        else:
            return 'system'
    
    def _get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user context from active connections."""
        # Search through active connections
        for conn_id, context in self.auth.active_connections.items():
            if context.get('user_id') == user_id:
                return context
        return None
    
    async def _emit_to_user(self, user_id: str, event: str, data: Any):
        """Emit event to specific user's connections."""
        room_name = f"user:{user_id}"
        await self.emit(event, data, room=room_name)
    
    async def _mark_messages_read(
        self, 
        db: AsyncSession, 
        conversation_id: int, 
        user_id: str
    ):
        """Mark messages as read in conversation."""
        await db.execute(
            update(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_type == 'fan',
                    Message.read_at.is_(None)
                )
            ).values(
                read_at=datetime.utcnow(),
                status=MessageStatus.READ
            )
        )