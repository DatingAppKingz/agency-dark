"""
WebSocket middleware for authentication and authorization.
"""
import logging
from typing import Callable, Optional, Dict, Any
from fastapi import WebSocket, status
import json

from core.websocket_auth import enhanced_websocket_auth, WebSocketAuthError
from core.logger import get_logger

logger = get_logger(__name__)


class WebSocketAuthMiddleware:
    """Middleware for WebSocket authentication and authorization."""
    
    def __init__(self):
        self.auth = enhanced_websocket_auth
    
    async def __call__(
        self, 
        websocket: WebSocket, 
        call_next: Callable,
        require_auth: bool = True,
        allowed_roles: Optional[list] = None
    ):
        """
        WebSocket middleware for authentication.
        
        Args:
            websocket: WebSocket connection
            call_next: Next handler in chain
            require_auth: Whether authentication is required
            allowed_roles: List of allowed roles (None = all authenticated users)
        """
        if not require_auth:
            return await call_next(websocket)
        
        # Get token from various sources
        token = await self._extract_token(websocket)
        
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="No authentication token provided"
            )
            return
        
        # Get connection ID (use WebSocket ID or generate one)
        connection_id = getattr(websocket, 'id', id(websocket))
        
        # Get client info
        client_info = {
            'ip': websocket.client.host if websocket.client else 'unknown',
            'port': websocket.client.port if websocket.client else 0,
            'headers': dict(websocket.headers)
        }
        
        try:
            # Authenticate connection
            user_context = await self.auth.authenticate_connection(
                token=token,
                connection_id=str(connection_id),
                client_info=client_info
            )
            
            # Check role restrictions
            if allowed_roles and user_context['role'] not in allowed_roles:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=f"Role {user_context['role']} not allowed"
                )
                logger.warning(
                    f"Access denied for {user_context['email']} "
                    f"(Role: {user_context['role']}) - Required roles: {allowed_roles}"
                )
                return
            
            # Attach user context to WebSocket
            websocket.user_context = user_context
            
            # Call next handler
            try:
                result = await call_next(websocket)
                return result
            finally:
                # Clean up on disconnect
                await self.auth.disconnect(str(connection_id))
                
        except WebSocketAuthError as e:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=str(e)
            )
            logger.warning(f"WebSocket auth failed: {e}")
            return
        except Exception as e:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR,
                reason="Authentication error"
            )
            logger.error(f"WebSocket auth error: {e}")
            return
    
    async def _extract_token(self, websocket: WebSocket) -> Optional[str]:
        """Extract token from WebSocket connection."""
        # Try query parameters first
        token = websocket.query_params.get("token")
        if token:
            return token
        
        # Try Authorization header
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
        
        # Try cookies
        token = websocket.cookies.get("access_token")
        if token:
            return token
        
        # Try subprotocol (some clients send auth as subprotocol)
        if websocket.subprotocols:
            for subprotocol in websocket.subprotocols:
                if subprotocol.startswith("auth-"):
                    return subprotocol[5:]  # Remove "auth-" prefix
        
        return None


class WebSocketRateLimitMiddleware:
    """Rate limiting middleware for WebSocket connections."""
    
    def __init__(
        self, 
        max_connections_per_user: int = 5,
        max_messages_per_minute: int = 60
    ):
        self.max_connections_per_user = max_connections_per_user
        self.max_messages_per_minute = max_messages_per_minute
        self.message_counts: Dict[str, list] = {}
    
    async def __call__(self, websocket: WebSocket, call_next: Callable):
        """Apply rate limiting to WebSocket connections."""
        # Get user context (assumes auth middleware ran first)
        user_context = getattr(websocket, 'user_context', None)
        if not user_context:
            return await call_next(websocket)
        
        user_id = user_context['user_id']
        
        # Check connection limit
        user_connections = await self._get_user_connection_count(user_id)
        if user_connections >= self.max_connections_per_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Too many connections"
            )
            logger.warning(
                f"Rate limit: User {user_id} exceeded connection limit "
                f"({user_connections}/{self.max_connections_per_user})"
            )
            return
        
        # Track message rate
        websocket.rate_limit_check = lambda: self._check_message_rate(user_id)
        
        return await call_next(websocket)
    
    async def _get_user_connection_count(self, user_id: str) -> int:
        """Get number of active connections for a user."""
        # In production, this would check Redis or a shared cache
        connections = enhanced_websocket_auth.active_connections
        count = sum(1 for ctx in connections.values() if ctx['user_id'] == user_id)
        return count
    
    def _check_message_rate(self, user_id: str) -> bool:
        """Check if user is within message rate limit."""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        # Get or create message history
        if user_id not in self.message_counts:
            self.message_counts[user_id] = []
        
        # Remove old entries
        self.message_counts[user_id] = [
            ts for ts in self.message_counts[user_id] if ts > cutoff
        ]
        
        # Check limit
        if len(self.message_counts[user_id]) >= self.max_messages_per_minute:
            return False
        
        # Add current message
        self.message_counts[user_id].append(now)
        return True


# Global middleware instances
websocket_auth_middleware = WebSocketAuthMiddleware()
websocket_rate_limit_middleware = WebSocketRateLimitMiddleware()


# Decorator for WebSocket endpoints
def require_websocket_auth(allowed_roles: Optional[list] = None):
    """
    Decorator to require authentication for WebSocket endpoints.
    
    Usage:
        @app.websocket("/ws")
        @require_websocket_auth(allowed_roles=[UserRole.MODEL, UserRole.CHATTER])
        async def websocket_endpoint(websocket: WebSocket):
            # websocket.user_context is available here
            user = websocket.user_context
            await websocket.send_text(f"Hello {user['email']}")
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(websocket: WebSocket, *args, **kwargs):
            async def call_endpoint(ws):
                return await func(ws, *args, **kwargs)
            
            return await websocket_auth_middleware(
                websocket, 
                call_endpoint,
                require_auth=True,
                allowed_roles=allowed_roles
            )
        
        return wrapper
    return decorator