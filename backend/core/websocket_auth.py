"""WebSocket authentication utilities."""

from typing import Optional
from fastapi import WebSocket, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from core.config import settings
from core.security import ALGORITHM
from models.user import User
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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
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