"""
Authentication dependencies that support both Bearer tokens and cookies.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from core.database import get_db
from core.config import settings
from core.security import decode_token
from models.user import User


class HTTPBearerOrCookie(HTTPBearer):
    """
    Custom security scheme that accepts tokens from either:
    1. Authorization header (Bearer token)
    2. Cookie (access_token)
    """
    
    async def __call__(self, request: Request) -> Optional[str]:
        # First try to get token from Authorization header
        try:
            credentials: HTTPAuthorizationCredentials = await super().__call__(request)
            if credentials:
                return credentials.credentials
        except HTTPException:
            pass
        
        # If no header token, try cookie
        access_token = request.cookies.get("access_token")
        if access_token:
            return access_token
        
        # No token found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )


security = HTTPBearerOrCookie()


async def get_current_user(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from token (header or cookie)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY or settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM or "HS256"]
        )
        user_id = payload.get("user_id") or payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database using raw SQL to avoid ORM mapper issues
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": user_id}
    )
    user_row = result.fetchone()
    
    if user_row is None:
        raise credentials_exception
    
    if not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Convert row to User object
    user = User()
    for key, value in user_row._mapping.items():
        setattr(user, key, value)
    
    return user


async def get_optional_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None."""
    try:
        # Try to get token from header or cookie
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        elif "access_token" in request.cookies:
            token = request.cookies.get("access_token")
        
        if not token:
            return None
        
        # Decode token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY or settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM or "HS256"]
        )
        user_id = payload.get("user_id") or payload.get("sub")
        if not user_id:
            return None
        
        # Get user using raw SQL to avoid ORM mapper issues
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT * FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user_row = result.fetchone()
        
        if user_row and user_row.is_active:
            # Convert row to User object
            user = User()
            for key, value in user_row._mapping.items():
                setattr(user, key, value)
            return user
        return None
        
    except (JWTError, HTTPException):
        return None