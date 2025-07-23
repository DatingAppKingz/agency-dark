"""
Socket.IO namespace for chat functionality.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from socketio import AsyncNamespace
from sqlalchemy import select, and_

from backend.core.database import AsyncSessionLocal
from backend.core.domain.models import User, ModelProfile, Fan, Message, UserRole
from backend.modules.chat.application.claim_manager import ClaimManager
from backend.modules.chat.application.message_queue import MessageQueue
from backend.modules.api_orchestration.application.orchestrator import APIOrchestrator
from backend.modules.api_orchestration.domain.schemas import MessageRequest


logger = logging.getLogger(__name__)


class ChatNamespace(AsyncNamespace):
    """Socket.IO namespace for real-time chat."""
    
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.claim_manager = ClaimManager()
        self.message_queue = MessageQueue()
    
    async def on_connect(self, sid: str, environ: dict):
        """Handle namespace connection."""
        session = await self.get_session(sid)
        if not session:
            return False
        
        logger.info(f"User {session['username']} connected to chat namespace")
        
        # Load user's active claims if they're a chatter
        if session['role'] == 'chatter':
            claims = await self.claim_manager.get_active_claims(
                model_id=None,  # Get all claims for this chatter
                chatter_id=session['user_id']
            )
            
            # Send active claims to the chatter
            await self.emit('active_claims', claims, room=sid)
        
        # Check for queued messages
        queued_messages = await self.message_queue.get_queued_messages(
            session['user_id']
        )
        if queued_messages:
            await self.emit('queued_messages', queued_messages, room=sid)
        
        return True
    
    async def on_join_model_room(self, sid: str, data: Dict[str, Any]):
        """Join a model-specific chat room."""
        session = await self.get_session(sid)
        if not session:
            return
        
        model_id = data.get('model_id')
        if not model_id:
            await self.emit('error', {
                'message': 'Model ID required'
            }, room=sid)
            return
        
        # Verify user has access to this model
        async with AsyncSessionLocal() as db:
            model = await db.get(ModelProfile, model_id)
            if not model:
                await self.emit('error', {
                    'message': 'Model not found'
                }, room=sid)
                return
            
            # Check permissions
            user = await db.get(User, session['user_id'])
            if not user:
                return
            
            if user.role == UserRole.SUPER_ADMIN:
                pass  # Super admin can access any model
            elif user.role in [UserRole.AGENCY_OWNER, UserRole.MANAGER, UserRole.CHATTER]:
                if str(model.agency_id) != session['agency_id']:
                    await self.emit('error', {
                        'message': 'Model not in your agency'
                    }, room=sid)
                    return
            elif user.role == UserRole.MODEL:
                if str(model.user_id) != session['user_id']:
                    await self.emit('error', {
                        'message': 'Not your model profile'
                    }, room=sid)
                    return
            else:
                await self.emit('error', {
                    'message': 'Insufficient permissions'
                }, room=sid)
                return
        
        # Join the model room
        room_name = f"model:{model_id}"
        self.enter_room(sid, room_name)
        
        # Send room joined confirmation
        await self.emit('joined_model_room', {
            'model_id': model_id,
            'model_username': model.username
        }, room=sid)
        
        # Load fans for this model
        await self._send_model_fans(sid, model_id)
        
        # Subscribe to claim changes for this model
        await self._subscribe_to_claims(sid, model_id)
    
    async def on_claim_fan(self, sid: str, data: Dict[str, Any]):
        """Handle fan claiming request."""
        session = await self.get_session(sid)
        if not session or session['role'] != 'chatter':
            await self.emit('error', {
                'message': 'Only chatters can claim fans'
            }, room=sid)
            return
        
        fan_id = data.get('fan_id')
        model_id = data.get('model_id')
        duration_hours = data.get('duration_hours')
        
        if not fan_id or not model_id:
            await self.emit('error', {
                'message': 'Fan ID and Model ID required'
            }, room=sid)
            return
        
        # Attempt to claim the fan
        result = await self.claim_manager.claim_fan(
            fan_id=fan_id,
            chatter_id=session['user_id'],
            model_id=model_id,
            duration_hours=duration_hours
        )
        
        if result['success']:
            await self.emit('claim_success', result, room=sid)
            
            # Notify all users in the model room
            room_name = f"model:{model_id}"
            await self.emit('fan_claimed', {
                'fan_id': fan_id,
                'chatter_id': session['user_id'],
                'chatter_username': session['username'],
                'expires_at': result['expires_at']
            }, room=room_name, skip_sid=sid)
        else:
            await self.emit('claim_failed', result, room=sid)
    
    async def on_release_claim(self, sid: str, data: Dict[str, Any]):
        """Handle claim release request."""
        session = await self.get_session(sid)
        if not session:
            return
        
        fan_id = data.get('fan_id')
        if not fan_id:
            await self.emit('error', {
                'message': 'Fan ID required'
            }, room=sid)
            return
        
        # Release the claim
        result = await self.claim_manager.release_claim(
            fan_id=fan_id,
            chatter_id=session['user_id']
        )
        
        if result['success']:
            await self.emit('claim_released', result, room=sid)
            
            # Get model_id for notification
            async with AsyncSessionLocal() as db:
                fan = await db.get(Fan, fan_id)
                if fan:
                    room_name = f"model:{fan.model_id}"
                    await self.emit('fan_released', {
                        'fan_id': fan_id,
                        'released_by': session['username']
                    }, room=room_name, skip_sid=sid)
        else:
            await self.emit('release_failed', result, room=sid)
    
    async def on_send_message(self, sid: str, data: Dict[str, Any]):
        """Handle message send request."""
        session = await self.get_session(sid)
        if not session:
            return
        
        fan_id = data.get('fan_id')
        model_id = data.get('model_id')
        text = data.get('text')
        media_ids = data.get('media_ids', [])
        price = data.get('price')
        
        if not fan_id or not model_id or not text:
            await self.emit('error', {
                'message': 'Fan ID, Model ID, and text required'
            }, room=sid)
            return
        
        # Check if user can send to this fan
        claim_status = await self.claim_manager.check_claim_status(fan_id)
        
        if claim_status['is_claimed']:
            if claim_status['chatter_id'] != session['user_id']:
                await self.emit('error', {
                    'message': 'This fan is claimed by another chatter'
                }, room=sid)
                return
        
        # Send message through orchestrator
        async with AsyncSessionLocal() as db:
            model = await db.get(ModelProfile, model_id)
            user = await db.get(User, session['user_id'])
            
            if not model or not user:
                await self.emit('error', {
                    'message': 'Model or user not found'
                }, room=sid)
                return
            
            orchestrator = APIOrchestrator(db)
            
            try:
                # Create message request
                message_request = MessageRequest(
                    fan_id=fan_id,
                    text=text,
                    media_ids=media_ids,
                    price=price
                )
                
                # Send through orchestrator
                result = await orchestrator.send_message(
                    model_profile=model,
                    request=message_request,
                    user=user
                )
                
                # Emit success
                await self.emit('message_sent', {
                    'fan_id': fan_id,
                    'message_id': result['message_id'],
                    'source': result['source'],
                    'created_at': result['created_at']
                }, room=sid)
                
                # Notify others in the model room
                room_name = f"model:{model_id}"
                await self.emit('new_message', {
                    'fan_id': fan_id,
                    'sender': session['username'],
                    'text': text[:100],  # Preview
                    'has_media': len(media_ids) > 0,
                    'is_ppv': price is not None
                }, room=room_name, skip_sid=sid)
                
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                await self.emit('error', {
                    'message': f'Failed to send message: {str(e)}'
                }, room=sid)
    
    async def on_get_fan_messages(self, sid: str, data: Dict[str, Any]):
        """Get message history for a fan."""
        session = await self.get_session(sid)
        if not session:
            return
        
        fan_id = data.get('fan_id')
        model_id = data.get('model_id')
        limit = data.get('limit', 50)
        
        if not fan_id or not model_id:
            await self.emit('error', {
                'message': 'Fan ID and Model ID required'
            }, room=sid)
            return
        
        # TODO: Implement message history retrieval
        # For now, return empty list
        await self.emit('fan_messages', {
            'fan_id': fan_id,
            'messages': []
        }, room=sid)
    
    async def on_typing_start(self, sid: str, data: Dict[str, Any]):
        """Handle typing indicator start."""
        session = await self.get_session(sid)
        if not session:
            return
        
        fan_id = data.get('fan_id')
        model_id = data.get('model_id')
        
        if not fan_id or not model_id:
            return
        
        # Broadcast typing indicator to model room
        room_name = f"model:{model_id}"
        await self.emit('user_typing', {
            'fan_id': fan_id,
            'user': session['username'],
            'is_typing': True
        }, room=room_name, skip_sid=sid)
    
    async def on_typing_stop(self, sid: str, data: Dict[str, Any]):
        """Handle typing indicator stop."""
        session = await self.get_session(sid)
        if not session:
            return
        
        fan_id = data.get('fan_id')
        model_id = data.get('model_id')
        
        if not fan_id or not model_id:
            return
        
        # Broadcast typing indicator to model room
        room_name = f"model:{model_id}"
        await self.emit('user_typing', {
            'fan_id': fan_id,
            'user': session['username'],
            'is_typing': False
        }, room=room_name, skip_sid=sid)
    
    async def _send_model_fans(self, sid: str, model_id: str):
        """Send list of fans for a model."""
        async with AsyncSessionLocal() as db:
            # Get model
            model = await db.get(ModelProfile, model_id)
            if not model:
                return
            
            # Get fans with claim status
            orchestrator = APIOrchestrator(db)
            fans = await orchestrator.get_unified_fans(
                model_profile=model,
                limit=100,
                include_unclaimed=True
            )
            
            # Convert to dict format
            fan_list = []
            for fan in fans:
                fan_list.append({
                    'id': fan.id,
                    'username': fan.username,
                    'display_name': fan.display_name,
                    'avatar_url': fan.avatar_url,
                    'is_subscriber': fan.is_subscriber,
                    'is_paying': fan.is_paying,
                    'last_active_at': fan.last_active_at.isoformat() if fan.last_active_at else None,
                    'is_claimed': fan.is_claimed,
                    'claimed_by': fan.claimed_by,
                    'claim_expires_at': fan.claim_expires_at.isoformat() if fan.claim_expires_at else None
                })
            
            await self.emit('model_fans', {
                'model_id': model_id,
                'fans': fan_list
            }, room=sid)
    
    async def _subscribe_to_claims(self, sid: str, model_id: str):
        """Subscribe to claim changes for a model."""
        # This would typically set up a Redis subscription
        # For now, we'll rely on direct notifications
        pass