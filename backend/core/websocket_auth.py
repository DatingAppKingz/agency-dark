"""
Enhanced WebSocket authentication with JWT validation and role-based access control.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import WebSocket, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
import uuid

from core.config import settings
from core.database import AsyncSessionLocal
from core.redis import redis_manager
from models.user import User, UserRole
from core.logger import get_logger

logger = get_logger(__name__)


async def get_current_user_from_websocket(
    websocket: WebSocket,
    db: AsyncSession,
    token: Optional[str] = Query(None)
) -> Optional[User]:
    """
    Authenticate user from WebSocket connection.
    
    Token can be provided either:
    1. As a query parameter: ws://localhost/ws?token=xxx
    2. In the first message after connection
    """
    if not token:
        # Try to get token from headers
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token:
        # Try to get token from cookies
        token = websocket.cookies.get("access_token")
    
    if not token:
        logger.warning("No authentication token provided for WebSocket")
        return None
    
    try:
        # Decode token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            logger.warning("Invalid token payload - no user ID")
            return None
        
        # Get user from database
        user = await db.get(User, user_id)
        
        if user is None:
            logger.warning(f"User not found: {user_id}")
            return None
        
        if not user.is_active:
            logger.warning(f"Inactive user attempted WebSocket connection: {user_id}")
            return None
        
        return user
        
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during WebSocket authentication: {e}")
        return None


async def require_websocket_auth(
    websocket: WebSocket,
    db: AsyncSession,
    token: Optional[str] = Query(None)
) -> User:
    """
    Require authentication for WebSocket connection.
    
    Closes the connection if authentication fails.
    """
    user = await get_current_user_from_websocket(websocket, db, token)
    
    if not user:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication required"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    return user


class WebSocketAuthError(Exception):
    """WebSocket authentication error."""
    pass


class EnhancedWebSocketAuth:
    """Enhanced WebSocket authentication handler with role-based access control."""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.token_refresh_window = timedelta(minutes=5)
    
    async def authenticate_connection(
        self, 
        token: str, 
        connection_id: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Authenticate a WebSocket connection using JWT token with enhanced security.
        
        Args:
            token: JWT access token
            connection_id: Unique connection identifier (e.g., Socket.IO sid)
            client_info: Optional client information (IP, user agent, etc.)
            
        Returns:
            User information dictionary with role and permissions
            
        Raises:
            WebSocketAuthError: If authentication fails
        """
        try:
            # Decode and validate JWT token
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("sub")
            
            if not user_id:
                raise WebSocketAuthError("Invalid token: missing user ID")
            
            # Check if token is blacklisted
            if await self._is_token_blacklisted(token):
                raise WebSocketAuthError("Token has been revoked")
            
            # Get user from database with role information
            async with AsyncSessionLocal() as db:
                user = await self._get_user_with_role(db, user_id)
                
                if not user:
                    raise WebSocketAuthError("User not found")
                
                if not user.is_active:
                    raise WebSocketAuthError("User account is inactive")
                
                # Check if user is banned from WebSocket
                if await self._is_user_banned_from_websocket(str(user.id)):
                    raise WebSocketAuthError("User is banned from real-time features")
                
                # Create enhanced user context with role information
                user_context = {
                    "connection_id": connection_id,
                    "user_id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "agency_id": str(user.agency_id) if user.agency_id else None,
                    "is_super_admin": user.role == UserRole.SUPER_ADMIN,
                    "permissions": self._get_role_permissions(user.role),
                    "connected_at": datetime.utcnow().isoformat(),
                    "token_exp": payload.get("exp"),
                    "client_info": client_info or {}
                }
                
                # Store connection info
                self.active_connections[connection_id] = user_context
                
                # Store in Redis for distributed systems
                await self._store_connection_redis(connection_id, user_context)
                
                # Log successful authentication
                logger.info(
                    f"WebSocket authenticated: {user.email} (Role: {user.role}) "
                    f"from {client_info.get('ip', 'unknown')} - Connection: {connection_id}"
                )
                
                return user_context
                
        except JWTError as e:
            logger.warning(f"Invalid token for connection {connection_id}: {e}")
            raise WebSocketAuthError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Authentication error for connection {connection_id}: {e}")
            raise WebSocketAuthError("Authentication failed")
    
    async def validate_room_access(
        self, 
        user_context: Dict[str, Any], 
        room_type: str, 
        room_id: str
    ) -> bool:
        """
        Validate if user has access to join a specific room based on their role.
        
        Args:
            user_context: User context from authentication
            room_type: Type of room (conversation, agency, model, etc.)
            room_id: Unique room identifier
            
        Returns:
            True if access is granted, False otherwise
        """
        role = user_context["role"]
        user_id = user_context["user_id"]
        agency_id = user_context["agency_id"]
        
        # Super admins can access any room
        if user_context["is_super_admin"]:
            logger.debug(f"Super admin {user_id} granted access to {room_type}:{room_id}")
            return True
        
        # Room type specific validation
        if room_type == "agency":
            # Users can only join their own agency room
            allowed = room_id == agency_id
            if not allowed:
                logger.warning(f"User {user_id} denied access to agency room {room_id}")
            return allowed
        
        elif room_type == "conversation":
            # Check conversation access based on role
            allowed = await self._validate_conversation_access(user_id, role, room_id, agency_id)
            if not allowed:
                logger.warning(f"User {user_id} denied access to conversation {room_id}")
            return allowed
        
        elif room_type == "model":
            # Models can join their own room, chatters need assignment
            if role == UserRole.MODEL:
                allowed = await self._is_user_model(user_id, room_id)
            elif role == UserRole.CHATTER:
                allowed = await self._is_chatter_assigned_to_model(user_id, room_id)
            elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Agency owners/admins can monitor their models
                allowed = await self._is_model_in_agency(room_id, agency_id)
            else:
                allowed = False
            
            if not allowed:
                logger.warning(f"User {user_id} (role: {role}) denied access to model room {room_id}")
            return allowed
        
        elif room_type == "user":
            # Users can only join their own user room
            return room_id == user_id
        
        elif room_type == "role":
            # Users can join their role room
            return room_id == role
        
        else:
            # Unknown room type - deny by default
            logger.warning(f"Unknown room type: {room_type}")
            return False
    
    async def validate_message_permissions(
        self, 
        user_context: Dict[str, Any], 
        action: str, 
        target_data: Dict[str, Any]
    ) -> bool:
        """
        Validate if user has permission to perform an action based on RBAC.
        
        Args:
            user_context: User context
            action: Action to perform (send_message, update_status, etc.)
            target_data: Target data (conversation_id, etc.)
            
        Returns:
            True if permitted, False otherwise
        """
        permissions = user_context.get("permissions", [])
        
        # Check if action is in user's permissions
        if action not in permissions and "*" not in permissions:
            logger.warning(
                f"User {user_context['user_id']} (role: {user_context['role']}) "
                f"denied permission for action: {action}"
            )
            return False
        
        # Additional validation for specific actions
        if action == "send_message":
            return await self._validate_send_message_permission(user_context, target_data)
        elif action == "update_status":
            return await self._validate_update_permission(user_context, target_data)
        elif action == "assign_chatter":
            return await self._validate_assign_permission(user_context, target_data)
        
        return True
    
    async def refresh_token_if_needed(self, connection_id: str) -> Optional[str]:
        """Check if token needs refresh and return new token if needed."""
        user_context = self.active_connections.get(connection_id)
        if not user_context:
            return None
        
        token_exp = user_context.get("token_exp")
        if not token_exp:
            return None
        
        # Check if token expires soon
        exp_time = datetime.fromtimestamp(token_exp)
        if datetime.utcnow() + self.token_refresh_window >= exp_time:
            # Generate new token
            new_token = self._generate_new_token(user_context)
            logger.info(f"Refreshed token for connection {connection_id}")
            return new_token
        
        return None
    
    async def disconnect(self, connection_id: str):
        """Handle WebSocket disconnection and cleanup."""
        user_context = self.active_connections.get(connection_id)
        if user_context:
            # Remove from active connections
            del self.active_connections[connection_id]
            
            # Remove from Redis
            await self._remove_connection_redis(connection_id)
            
            # Log disconnection
            logger.info(
                f"WebSocket disconnected: {user_context['email']} - "
                f"Connection: {connection_id}"
            )
    
    # Private helper methods
    
    def _get_role_permissions(self, role: str) -> List[str]:
        """Get permissions for a role based on RBAC."""
        permissions = {
            UserRole.SUPER_ADMIN: ["*"],  # All permissions
            UserRole.AGENCY_OWNER: [
                "send_message", "update_status", "assign_chatter", 
                "view_analytics", "manage_conversations", "manage_models"
            ],
            UserRole.AGENCY_ADMIN: [
                "send_message", "update_status", "assign_chatter", 
                "view_analytics", "manage_conversations"
            ],
            UserRole.MODEL: [
                "send_message", "update_status", "view_own_conversations"
            ],
            UserRole.CHATTER: [
                "send_message", "view_assigned_conversations"
            ],
            UserRole.AGENCY_STAFF: ["view_analytics"],
            UserRole.MEMBER: []  # No WebSocket permissions
        }
        
        return permissions.get(role, [])
    
    async def _get_user_with_role(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Get user from database with role information."""
        try:
            user_uuid = uuid.UUID(user_id)
            result = await db.execute(
                select(User).where(User.id == user_uuid)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return None
    
    async def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted in Redis."""
        if not redis_manager:
            return False
        blacklist_key = f"blacklist:token:{token[:20]}"
        return await redis_manager.exists(blacklist_key)
    
    async def _is_user_banned_from_websocket(self, user_id: str) -> bool:
        """Check if user is banned from WebSocket connections."""
        if not redis_manager:
            return False
        ban_key = f"websocket:ban:{user_id}"
        return await redis_manager.exists(ban_key)
    
    async def _store_connection_redis(self, connection_id: str, user_context: Dict[str, Any]):
        """Store connection info in Redis for distributed systems."""
        if not redis_manager:
            return
        
        key = f"websocket:connection:{connection_id}"
        await redis_manager.set(
            key, 
            json.dumps(user_context),
            expire=86400  # 24 hours
        )
        
        # Also store in user's connection set
        user_key = f"websocket:user:{user_context['user_id']}"
        await redis_manager.client.sadd(user_key, connection_id)
        await redis_manager.client.expire(user_key, 86400)
    
    async def _remove_connection_redis(self, connection_id: str):
        """Remove connection info from Redis."""
        if not redis_manager:
            return
        
        # Get user context first
        key = f"websocket:connection:{connection_id}"
        data = await redis_manager.get(key)
        
        if data:
            user_context = json.loads(data)
            # Remove from user's connection set
            user_key = f"websocket:user:{user_context['user_id']}"
            await redis_manager.client.srem(user_key, connection_id)
        
        # Remove connection data
        await redis_manager.delete(key)
    
    async def _validate_conversation_access(
        self, user_id: str, role: str, conversation_id: str, agency_id: str
    ) -> bool:
        """Validate if user has access to a conversation based on role."""
        async with AsyncSessionLocal() as db:
            from models.chat import Conversation
            from models.model import Model
            
            result = await db.execute(
                select(Conversation).where(Conversation.id == int(conversation_id))
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return False
            
            # Check agency match first (except super admin)
            if role != UserRole.SUPER_ADMIN:
                if agency_id and str(conversation.agency_id) != agency_id:
                    return False
            
            # Role-specific checks
            if role == UserRole.MODEL:
                # Check if user is the model in conversation
                result = await db.execute(
                    select(Model).where(Model.user_id == uuid.UUID(user_id))
                )
                model = result.scalar_one_or_none()
                return model and conversation.model_id == model.id
            
            elif role == UserRole.CHATTER:
                # Check if user is assigned chatter
                return str(conversation.assigned_chatter_id) == user_id
            
            elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Already checked agency match above
                return True
            
            return False
    
    async def _is_user_model(self, user_id: str, model_id: str) -> bool:
        """Check if user is the specified model."""
        async with AsyncSessionLocal() as db:
            from models.model import Model
            
            result = await db.execute(
                select(Model).where(
                    Model.id == int(model_id),
                    Model.user_id == uuid.UUID(user_id)
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def _is_chatter_assigned_to_model(self, chatter_id: str, model_id: str) -> bool:
        """Check if chatter is assigned to model."""
        async with AsyncSessionLocal() as db:
            from models.model_assignment import ModelAssignment
            
            result = await db.execute(
                select(ModelAssignment).where(
                    ModelAssignment.chatter_id == uuid.UUID(chatter_id),
                    ModelAssignment.model_id == uuid.UUID(model_id),
                    ModelAssignment.is_active == True
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def _is_model_in_agency(self, model_id: str, agency_id: str) -> bool:
        """Check if model belongs to agency."""
        if not agency_id:
            return False
            
        async with AsyncSessionLocal() as db:
            from models.model import Model
            
            result = await db.execute(
                select(Model).where(
                    Model.id == int(model_id),
                    Model.agency_id == uuid.UUID(agency_id)
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def _validate_send_message_permission(
        self, user_context: Dict[str, Any], target_data: Dict[str, Any]
    ) -> bool:
        """Validate send message permission with conversation context."""
        conversation_id = target_data.get("conversation_id")
        if not conversation_id:
            return False
        
        return await self._validate_conversation_access(
            user_context["user_id"],
            user_context["role"],
            conversation_id,
            user_context["agency_id"]
        )
    
    async def _validate_update_permission(
        self, user_context: Dict[str, Any], target_data: Dict[str, Any]
    ) -> bool:
        """Validate update permission based on role."""
        # Models can only update their own conversations
        # Agency owners/admins can update any conversation in their agency
        if user_context["role"] in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return True
        elif user_context["role"] == UserRole.MODEL:
            return await self._validate_conversation_access(
                user_context["user_id"],
                user_context["role"],
                target_data.get("conversation_id"),
                user_context["agency_id"]
            )
        return False
    
    async def _validate_assign_permission(
        self, user_context: Dict[str, Any], target_data: Dict[str, Any]
    ) -> bool:
        """Validate chatter assignment permission."""
        # Only agency owners and admins can assign chatters
        return user_context["role"] in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]
    
    def _generate_new_token(self, user_context: Dict[str, Any]) -> str:
        """Generate a new JWT token for token refresh."""
        from datetime import timezone
        
        payload = {
            "sub": user_context["user_id"],
            "email": user_context["email"],
            "role": user_context["role"],
            "agency_id": user_context["agency_id"],
            "exp": datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            ),
            "iat": datetime.now(timezone.utc)
        }
        
        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )


# Global enhanced WebSocket auth instance
enhanced_websocket_auth = EnhancedWebSocketAuth()