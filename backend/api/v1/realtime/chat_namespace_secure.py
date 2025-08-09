"""
Enhanced Socket.IO namespace for chat with secure authentication and role-based access control.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from socketio import AsyncNamespace
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security_v2.authentication import enhanced_websocket_auth, WebSocketAuthError
from core.errors import AuthenticationError, AuthorizationError, NotFoundError
from core.logger import get_logger
from models.user import User, UserRole
from models.model import Model
from models.chat import (
    Conversation, ConversationStatus,
    Message, MessageType, MessageStatus
)

logger = get_logger(__name__)


class SecureChatNamespace(AsyncNamespace):
    """Enhanced Socket.IO namespace with role-based security for real-time chat."""
    
    def __init__(self, namespace='/chat/secure'):
        super().__init__(namespace)
        self.auth = enhanced_websocket_auth
    
    async def on_connect(self, sid: str, environ: dict, auth: dict):
        """Handle client connection with enhanced authentication."""
        try:
            # Get client info from environ
            client_info = {
                'ip': environ.get('REMOTE_ADDR', 'unknown'),
                'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
                'origin': environ.get('HTTP_ORIGIN', 'unknown')
            }
            
            # Authenticate with enhanced auth
            if not auth or 'token' not in auth:
                logger.warning(f"No auth token provided for {sid} from {client_info['ip']}")
                return False
            
            try:
                user_context = await self.auth.authenticate_connection(
                    token=auth['token'],
                    connection_id=sid,
                    client_info=client_info
                )
            except WebSocketAuthError as e:
                logger.warning(f"Authentication failed for {sid}: {e}")
                await self.emit('auth_error', {
                    'error': str(e),
                    'code': 'AUTH_FAILED'
                }, room=sid)
                return False
            
            # Join user-specific rooms based on role and permissions
            await self._join_default_rooms(sid, user_context)
            
            # Send connection confirmation with user context
            await self.emit('connected', {
                'status': 'connected',
                'user': {
                    'id': user_context['user_id'],
                    'email': user_context['email'],
                    'role': user_context['role'],
                    'agency_id': user_context['agency_id'],
                    'permissions': user_context['permissions']
                },
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            
            # Check if token needs refresh
            new_token = await self.auth.refresh_token_if_needed(sid)
            if new_token:
                await self.emit('token_refresh', {
                    'new_token': new_token,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=sid)
            
            logger.info(
                f"Secure connection established: {user_context['email']} "
                f"(Role: {user_context['role']}) - SID: {sid}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Connection error for {sid}: {e}")
            return False
    
    async def on_disconnect(self, sid: str):
        """Handle client disconnection."""
        await self.auth.disconnect(sid)
        logger.info(f"Client {sid} disconnected")
    
    async def on_join_conversation(self, sid: str, data: Dict[str, Any]):
        """Join a conversation room with permission validation."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            await self.emit('error', {
                'message': 'Not authenticated',
                'code': 'NOT_AUTHENTICATED'
            }, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.emit('error', {
                'message': 'Conversation ID required',
                'code': 'INVALID_REQUEST'
            }, room=sid)
            return
        
        # Validate room access with enhanced auth
        if not await self.auth.validate_room_access(
            user_context, 'conversation', str(conversation_id)
        ):
            await self.emit('error', {
                'message': 'Access denied to conversation',
                'code': 'ACCESS_DENIED',
                'details': {
                    'conversation_id': conversation_id,
                    'user_role': user_context['role']
                }
            }, room=sid)
            logger.warning(
                f"Access denied: {user_context['email']} (Role: {user_context['role']}) "
                f"tried to join conversation {conversation_id}"
            )
            return
        
        # Join conversation room
        room_name = f"conversation:{conversation_id}"
        await self.enter_room(sid, room_name)
        
        # Send confirmation
        await self.emit('joined_conversation', {
            'conversation_id': conversation_id,
            'status': 'joined',
            'permissions': self._get_conversation_permissions(user_context)
        }, room=sid)
        
        # Mark messages as read if applicable
        if user_context['role'] in [UserRole.MODEL, UserRole.CHATTER]:
            async for db in get_db():
                await self._mark_messages_read(db, conversation_id, user_context['user_id'])
        
        logger.info(
            f"User {user_context['email']} (Role: {user_context['role']}) "
            f"joined conversation {conversation_id}"
        )
    
    async def on_send_message(self, sid: str, data: Dict[str, Any]):
        """Handle sending a new message with permission validation."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            await self.emit('error', {
                'message': 'Not authenticated',
                'code': 'NOT_AUTHENTICATED'
            }, room=sid)
            return
        
        # Validate message permissions
        if not await self.auth.validate_message_permissions(
            user_context, 'send_message', data
        ):
            await self.emit('error', {
                'message': 'Permission denied',
                'code': 'PERMISSION_DENIED',
                'action': 'send_message'
            }, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        content = data.get('content')
        message_type = data.get('type', 'text')
        media_url = data.get('media_url')
        amount = data.get('amount')
        
        if not conversation_id or not content:
            await self.emit('error', {
                'message': 'Conversation ID and content required',
                'code': 'INVALID_REQUEST'
            }, room=sid)
            return
        
        async for db in get_db():
            # Get conversation with agency validation
            conversation = await self._get_conversation_secure(
                db, conversation_id, user_context
            )
            
            if not conversation:
                await self.emit('error', {
                    'message': 'Conversation not found or access denied',
                    'code': 'NOT_FOUND'
                }, room=sid)
                return
            
            # Determine sender type based on role
            sender_type = self._get_sender_type(user_context['role'])
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                sender_id=int(user_context['user_id']),
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
            conversation.last_message_at = datetime.utcnow()
            if sender_type == 'fan':
                conversation.last_fan_message_at = conversation.last_message_at
                conversation.unread_count += 1
            
            await db.commit()
            await db.refresh(message)
            
            # Prepare message data
            message_data = {
                'id': str(message.id),
                'conversation_id': conversation_id,
                'sender_id': str(message.sender_id),
                'sender_type': sender_type,
                'sender_name': user_context['full_name'] or user_context['email'],
                'sender_role': user_context['role'],
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
            await self._notify_conversation_participants(
                db, conversation, message_data
            )
            
            logger.info(
                f"Message sent in conversation {conversation_id} by "
                f"{user_context['email']} (Role: {user_context['role']})"
            )
    
    async def on_update_conversation_status(self, sid: str, data: Dict[str, Any]):
        """Update conversation status with permission check."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        # Validate update permissions
        if not await self.auth.validate_message_permissions(
            user_context, 'update_status', data
        ):
            await self.emit('error', {
                'message': 'Permission denied to update conversation status',
                'code': 'PERMISSION_DENIED'
            }, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        status = data.get('status')
        
        if not conversation_id or not status:
            return
        
        async for db in get_db():
            conversation = await self._get_conversation_secure(
                db, conversation_id, user_context
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
                'updated_by': user_context['user_id'],
                'updated_by_role': user_context['role']
            }, room=room_name)
            
            logger.info(
                f"Conversation {conversation_id} status updated to {status} by "
                f"{user_context['email']} (Role: {user_context['role']})"
            )
    
    async def on_assign_chatter(self, sid: str, data: Dict[str, Any]):
        """Assign a chatter to a conversation with permission check."""
        user_context = self.auth.active_connections.get(sid)
        if not user_context:
            return
        
        # Validate assignment permissions
        if not await self.auth.validate_message_permissions(
            user_context, 'assign_chatter', data
        ):
            await self.emit('error', {
                'message': 'Permission denied to assign chatter',
                'code': 'PERMISSION_DENIED'
            }, room=sid)
            return
        
        conversation_id = data.get('conversation_id')
        chatter_id = data.get('chatter_id')
        
        if not conversation_id or not chatter_id:
            return
        
        async for db in get_db():
            # Validate chatter is in same agency
            chatter = await db.get(User, chatter_id)
            if not chatter or str(chatter.agency_id) != user_context['agency_id']:
                await self.emit('error', {
                    'message': 'Invalid chatter or different agency',
                    'code': 'INVALID_CHATTER'
                }, room=sid)
                return
            
            conversation = await self._get_conversation_secure(
                db, conversation_id, user_context
            )
            
            if not conversation:
                return
            
            conversation.assigned_chatter_id = chatter_id
            await db.commit()
            
            # Notify all participants
            room_name = f"conversation:{conversation_id}"
            await self.emit('chatter_assigned', {
                'conversation_id': conversation_id,
                'chatter_id': chatter_id,
                'chatter_name': chatter.full_name or chatter.email,
                'assigned_by': user_context['user_id']
            }, room=room_name)
            
            # Notify the assigned chatter
            await self._emit_to_user(chatter_id, 'new_assignment', {
                'conversation_id': conversation_id,
                'assigned_by': user_context['email']
            })
    
    # Helper methods
    
    async def _join_default_rooms(self, sid: str, user_context: Dict[str, Any]):
        """Join default rooms based on user role."""
        # Join user-specific room
        await self.enter_room(sid, f"user:{user_context['user_id']}")
        
        # Join agency room if applicable
        if user_context['agency_id']:
            await self.enter_room(sid, f"agency:{user_context['agency_id']}")
        
        # Join role room
        await self.enter_room(sid, f"role:{user_context['role']}")
        
        # Super admins join admin room
        if user_context['is_super_admin']:
            await self.enter_room(sid, "admin:super")
    
    async def _get_conversation_secure(
        self, 
        db: AsyncSession, 
        conversation_id: int, 
        user_context: Dict[str, Any]
    ) -> Optional[Conversation]:
        """Get conversation with enhanced security checks."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        
        # Apply agency filter for non-super admins
        if not user_context['is_super_admin'] and user_context['agency_id']:
            stmt = stmt.where(Conversation.agency_id == user_context['agency_id'])
        
        conversation = await db.scalar(stmt)
        
        # Additional role-based validation is handled by validate_room_access
        return conversation
    
    def _get_sender_type(self, role: str) -> str:
        """Determine sender type based on user role."""
        if role == UserRole.MODEL:
            return 'model'
        elif role == UserRole.CHATTER:
            return 'chatter'
        elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return 'system'
        else:
            return 'unknown'
    
    def _get_conversation_permissions(self, user_context: Dict[str, Any]) -> List[str]:
        """Get conversation-specific permissions for a user."""
        role = user_context['role']
        
        permissions = {
            UserRole.SUPER_ADMIN: ['read', 'write', 'delete', 'assign', 'update_status'],
            UserRole.AGENCY_OWNER: ['read', 'write', 'assign', 'update_status'],
            UserRole.AGENCY_ADMIN: ['read', 'write', 'assign', 'update_status'],
            UserRole.MODEL: ['read', 'write', 'update_status'],
            UserRole.CHATTER: ['read', 'write'],
            UserRole.AGENCY_STAFF: ['read'],
            UserRole.MEMBER: []
        }
        
        return permissions.get(role, [])
    
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
                read_at=datetime.utcnow(),
                status=MessageStatus.READ
            ).returning(Message.id)
        )
        
        read_count = len(result.fetchall())
        
        if read_count > 0:
            # Update conversation unread count
            conversation = await db.get(Conversation, conversation_id)
            if conversation:
                conversation.unread_count = max(0, conversation.unread_count - read_count)
    
    async def _notify_conversation_participants(
        self, 
        db: AsyncSession,
        conversation: Conversation,
        message_data: Dict[str, Any]
    ):
        """Notify all conversation participants about new message."""
        # Notify model
        if conversation.model:
            model = await db.get(Model, conversation.model_id)
            if model and model.user_id:
                await self._emit_to_user(str(model.user_id), 'new_message', message_data)
        
        # Notify assigned chatter
        if conversation.assigned_chatter_id:
            await self._emit_to_user(
                str(conversation.assigned_chatter_id), 
                'new_message', 
                message_data
            )
    
    async def _emit_to_user(self, user_id: str, event: str, data: Any):
        """Emit event to all connections of a specific user."""
        room_name = f"user:{user_id}"
        await self.emit(event, data, room=room_name)
    
    # Admin broadcast methods
    
    async def broadcast_to_agency(self, agency_id: str, event: str, data: Any):
        """Broadcast event to all users in an agency."""
        room_name = f"agency:{agency_id}"
        await self.emit(event, data, room=room_name)
    
    async def broadcast_system_message(self, data: Dict[str, Any]):
        """Broadcast system message to all connected users."""
        await self.emit('system_message', {
            'message': data.get('message'),
            'type': data.get('type', 'info'),
            'timestamp': datetime.utcnow().isoformat()
        })