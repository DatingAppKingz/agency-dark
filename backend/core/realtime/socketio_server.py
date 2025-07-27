"""
Enhanced Socket.IO server with all namespaces.
"""
import logging
import json
from typing import Dict, Any, Optional
import asyncio

import socketio
from socketio import AsyncServer
import redis.asyncio as redis

from core.config import settings
from core.redis import redis_client
from core.database import AsyncSessionLocal
from core.domain.models import User, UserRole
from modules.chat.realtime.namespace import ChatNamespace
from modules.notifications.realtime.namespace import (
    NotificationNamespace,
    DashboardNamespace
)
from modules.financial.realtime.namespace import FinancialNamespace

logger = logging.getLogger(__name__)


class AuthMiddleware(socketio.AsyncNamespace):
    """Base namespace with authentication."""
    
    async def get_session(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get authenticated session data."""
        # In production, this would validate JWT tokens or session cookies
        # For now, return mock session data stored in server session
        session_data = await self.server.get_session(sid)
        return session_data


# Create Socket.IO server
sio = AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=True,
    engineio_logger=True
)

# Register namespaces
chat_namespace = ChatNamespace('/chat')
notification_namespace = NotificationNamespace('/notifications')
dashboard_namespace = DashboardNamespace('/dashboard')
financial_namespace = FinancialNamespace('/financial')

sio.register_namespace(chat_namespace)
sio.register_namespace(notification_namespace)
sio.register_namespace(dashboard_namespace)
sio.register_namespace(financial_namespace)


@sio.event
async def connect(sid, environ, auth):
    """Handle initial connection."""
    logger.info(f"Client {sid} connected")
    
    # In production, validate auth token here
    if auth and 'token' in auth:
        # Validate token and get user data
        user_data = await validate_token(auth['token'])
        if user_data:
            # Store session data
            await sio.save_session(sid, {
                'user_id': user_data['user_id'],
                'username': user_data['username'],
                'agency_id': user_data.get('agency_id'),
                'role': user_data['role']
            })
            
            # Join user-specific room
            sio.enter_room(sid, f"user:{user_data['user_id']}")
            
            # Join agency room if applicable
            if user_data.get('agency_id'):
                sio.enter_room(sid, f"agency:{user_data['agency_id']}")
            
            return True
    
    return False


@sio.event
async def disconnect(sid):
    """Handle disconnection."""
    logger.info(f"Client {sid} disconnected")
    
    # Clean up any active subscriptions
    session = await sio.get_session(sid)
    if session:
        # Leave all rooms
        for room in sio.rooms(sid):
            sio.leave_room(sid, room)


async def validate_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate auth token and return user data."""
    # TODO: Implement actual token validation
    # For now, return mock data
    return {
        'user_id': 'test_user_id',
        'username': 'test_user',
        'agency_id': 'test_agency_id',
        'role': UserRole.AGENCY_MEMBER
    }


# Redis pub/sub listener for cross-server communication
async def redis_listener():
    """Listen to Redis pub/sub for notifications."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe('global_notifications')
    
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    event_type = data.get('type')
                    
                    # Route to appropriate handler
                    if event_type == 'payment_confirmed':
                        await handle_payment_notification(data)
                    elif event_type == 'new_message':
                        await handle_message_notification(data)
                    elif event_type == 'payout_completed':
                        await handle_payout_notification(data)
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Redis message: {message['data']}")
                except Exception as e:
                    logger.error(f"Error handling Redis message: {e}")
                    
    except asyncio.CancelledError:
        await pubsub.unsubscribe('global_notifications')
        await pubsub.close()


async def handle_payment_notification(data: Dict[str, Any]):
    """Handle payment notifications from Redis."""
    # Send to financial namespace
    await sio.emit(
        'payment_notification',
        data,
        room=f"agency:{data.get('agency_id')}",
        namespace='/financial'
    )
    
    # Also send to notifications namespace
    await sio.emit(
        'notification',
        {
            'type': 'payment',
            'title': 'Payment Received',
            'message': f"Payment of {data.get('amount')} {data.get('currency')} confirmed",
            'data': data
        },
        room=f"agency:{data.get('agency_id')}",
        namespace='/notifications'
    )


async def handle_message_notification(data: Dict[str, Any]):
    """Handle new message notifications."""
    model_id = data.get('model_id')
    
    # Send to chat namespace
    await sio.emit(
        'new_message',
        data,
        room=f"model:{model_id}",
        namespace='/chat'
    )
    
    # Send desktop notification
    await sio.emit(
        'notification',
        {
            'type': 'message',
            'title': 'New Message',
            'message': f"New message from {data.get('sender')}",
            'data': data
        },
        room=f"model:{model_id}",
        namespace='/notifications'
    )


async def handle_payout_notification(data: Dict[str, Any]):
    """Handle payout notifications."""
    await sio.emit(
        'payout_notification',
        data,
        room=f"model:{data.get('model_id')}",
        namespace='/financial'
    )


# Performance monitoring
class PerformanceMonitor:
    """Monitor Socket.IO performance metrics."""
    
    def __init__(self):
        self.connections = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
    
    async def log_metrics(self):
        """Log performance metrics periodically."""
        while True:
            logger.info(
                f"Socket.IO Metrics - "
                f"Connections: {self.connections}, "
                f"Sent: {self.messages_sent}, "
                f"Received: {self.messages_received}, "
                f"Errors: {self.errors}"
            )
            
            # Reset counters
            self.messages_sent = 0
            self.messages_received = 0
            self.errors = 0
            
            # Wait 5 minutes
            await asyncio.sleep(300)


monitor = PerformanceMonitor()


# Middleware to track metrics
@sio.on('*')
async def catch_all(event, sid, *args):
    """Catch all events for monitoring."""
    monitor.messages_received += 1
    
    # Log specific events
    if event not in ['connect', 'disconnect']:
        logger.debug(f"Event '{event}' from {sid}")


# Export server and utilities
__all__ = [
    'sio',
    'redis_listener',
    'monitor'
]