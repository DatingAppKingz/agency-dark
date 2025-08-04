"""
Cookie utilities for secure JWT token handling.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Response
from core.config import settings


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_token_expires_delta: Optional[timedelta] = None,
) -> None:
    """
    Set secure HTTP-only cookies for authentication tokens.
    
    Args:
        response: FastAPI response object
        access_token: JWT access token
        refresh_token: JWT refresh token
        access_token_expires_delta: Optional custom expiration time
    """
    # Set access token cookie
    access_expires = access_token_expires_delta or timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=int(access_expires.total_seconds()),
        expires=datetime.utcnow() + access_expires,
        path="/",
        domain=None,
        secure=settings.ENVIRONMENT == "production",  # HTTPS only in production
        httponly=True,  # Not accessible via JavaScript
        samesite="lax",  # CSRF protection
    )
    
    # Set refresh token cookie (longer expiration)
    refresh_expires = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=int(refresh_expires.total_seconds()),
        expires=datetime.utcnow() + refresh_expires,
        path="/api/v1/auth/refresh",  # Only sent to refresh endpoint
        domain=None,
        secure=settings.ENVIRONMENT == "production",
        httponly=True,
        samesite="lax",
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clear authentication cookies on logout.
    
    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key="access_token",
        path="/",
        domain=None,
    )
    
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh",
        domain=None,
    )


def get_cookie_settings() -> dict:
    """
    Get cookie configuration settings.
    
    Returns:
        Dictionary with cookie settings
    """
    return {
        "secure": settings.ENVIRONMENT == "production",
        "httponly": True,
        "samesite": "lax",
        "domain": None,
        "path": "/",
    }