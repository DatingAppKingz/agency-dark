"""
Socket.IO server configuration and initialization.
"""
import logging
from typing import Optional, Dict, Any
import socketio
from socketio import AsyncNamespace

from backend.core.config import settings
from backend.core.redis import redis_client


logger = logging.getLogger(__name__)


# Create Socket.IO server with Redis adapter for horizontal scaling
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.ALLOWED_ORIGINS,
    logger=logger,
    engineio_logger=logger if settings.DEBUG else False,
    # Use Redis for multi-server support
    client_manager=socketio.AsyncRedisManager(
        f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}'
    ) if settings.REDIS_HOST else None
)

# Create ASGI app
socket_app = socketio.ASGIApp(
    sio,
    # Socket.IO will be mounted at /socket.io/ by default
)


class AuthMiddleware:
    """Middleware to authenticate Socket.IO connections."""
    
    @staticmethod
    async def authenticate(sid: str, environ: dict, auth: dict) -> Optional[Dict[str, Any]]:
        """
        Authenticate a Socket.IO connection.
        
        Returns user data if authenticated, None otherwise.
        """
        if not auth:
            logger.warning(f"No auth data provided for connection {sid}")
            return None
        
        token = auth.get('token')
        if not token:
            logger.warning(f"No token in auth data for connection {sid}")
            return None
        
        # Import here to avoid circular imports
        from backend.core.security import decode_token
        
        try:
            # Decode JWT token
            payload = decode_token(token)
            user_id = payload.get('sub')
            
            if not user_id:
                logger.warning(f"No user_id in token for connection {sid}")
                return None
            
            # Get user data from database
            from backend.core.database import AsyncSessionLocal
            from backend.core.domain.models import User
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.warning(f"User {user_id} not found for connection {sid}")
                    return None
                
                # Return user data for session
                return {
                    'user_id': str(user.id),
                    'username': user.username,
                    'role': user.role.value,
                    'agency_id': str(user.agency_id) if user.agency_id else None
                }
                
        except Exception as e:
            logger.error(f"Authentication error for connection {sid}: {e}")
            return None


@sio.event
async def connect(sid: str, environ: dict, auth: dict):
    """Handle client connection."""
    logger.info(f"Client {sid} attempting to connect")
    
    # Authenticate the connection
    user_data = await AuthMiddleware.authenticate(sid, environ, auth)
    
    if not user_data:
        logger.warning(f"Rejecting unauthenticated connection {sid}")
        return False
    
    # Save session data
    await sio.save_session(sid, user_data)
    
    # Join agency room
    if user_data['agency_id']:
        await sio.enter_room(sid, f"agency:{user_data['agency_id']}")
        logger.info(f"User {user_data['username']} joined agency room {user_data['agency_id']}")
    
    # Join user-specific room
    await sio.enter_room(sid, f"user:{user_data['user_id']}")
    
    # Join role-specific room
    await sio.enter_room(sid, f"role:{user_data['role']}")
    
    logger.info(f"Client {sid} connected as {user_data['username']} ({user_data['role']})")
    
    # Send connection confirmation
    await sio.emit('connected', {
        'user_id': user_data['user_id'],
        'username': user_data['username'],
        'role': user_data['role']
    }, room=sid)
    
    return True


@sio.event
async def disconnect(sid: str):
    """Handle client disconnection."""
    session = await sio.get_session(sid)
    if session:
        logger.info(f"Client {sid} ({session.get('username')}) disconnected")
        
        # Clean up any active claims or states
        if session.get('role') == 'chatter':
            # Release any active fan claims
            from backend.modules.chat.application.claim_manager import ClaimManager
            claim_manager = ClaimManager()
            await claim_manager.release_all_claims(session['user_id'])
    else:
        logger.info(f"Client {sid} disconnected")


@sio.on('ping')
async def handle_ping(sid: str):
    """Handle ping to keep connection alive."""
    await sio.emit('pong', room=sid)


# Error handler
@sio.on('*')
async def catch_all(event, sid, *args):
    """Catch-all handler for unknown events."""
    logger.warning(f"Unknown event '{event}' from {sid}")
    await sio.emit('error', {
        'message': f"Unknown event: {event}"
    }, room=sid)


# Register namespaces
from backend.modules.chat.realtime.namespace import ChatNamespace
from backend.modules.notifications.realtime.namespace import NotificationNamespace, DashboardNamespace

sio.register_namespace(ChatNamespace('/chat'))
sio.register_namespace(NotificationNamespace('/notifications'))
sio.register_namespace(DashboardNamespace('/dashboard'))