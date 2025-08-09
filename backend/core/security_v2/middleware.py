"""
Middleware components for security_v2 system.
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging

from .authentication import verify_token, decode_token
from .config import security_config
from core.database import get_db
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling JWT authentication.
    Validates tokens and adds user to request state.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for public endpoints
        public_paths = [
            "/",
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/docs",
            "/api/redoc",
            "/api/v1/openapi.json"
        ]
        
        if request.url.path in public_paths or request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Try to get token from Authorization header
        authorization = request.headers.get("Authorization")
        token = None
        
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
        
        # Try to get token from cookie if not in header
        if not token:
            token = request.cookies.get("access_token")
        
        # Validate token if present
        if token:
            try:
                payload = decode_token(token)
                if payload:
                    # Add user info to request state
                    request.state.user_id = payload.get("sub")
                    request.state.user_email = payload.get("email")
                    request.state.user_role = payload.get("role")
                    request.state.agency_id = payload.get("agency_id")
            except Exception as e:
                logger.debug(f"Token validation failed: {e}")
                # Don't fail here, let endpoint dependencies handle it
        
        response = await call_next(request)
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for adding security headers and CSRF protection.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Process request
        start_time = time.time()
        
        # Add request ID
        request_id = request.headers.get("X-Request-ID", str(time.time()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add CSP header for production
        if security_config.ENVIRONMENT == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self';"
            )
        
        # Add timing and request ID headers
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic rate limiting middleware.
    For advanced rate limiting, use the rate_limiting module.
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}  # Simple in-memory storage
        
    async def dispatch(self, request: Request, call_next):
        # Get client identifier (IP or user ID)
        client_id = request.client.host if request.client else "unknown"
        if hasattr(request.state, "user_id"):
            client_id = f"user_{request.state.user_id}"
        
        # Check rate limit
        current_minute = int(time.time() / 60)
        key = f"{client_id}:{current_minute}"
        
        # Increment request count
        if key not in self.request_counts:
            self.request_counts[key] = 0
        
        self.request_counts[key] += 1
        
        # Clean old entries (older than 2 minutes)
        old_minute = current_minute - 2
        keys_to_delete = [k for k in self.request_counts.keys() 
                         if int(k.split(":")[1]) < old_minute]
        for k in keys_to_delete:
            del self.request_counts[k]
        
        # Check if rate limit exceeded
        if self.request_counts[key] > self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - self.request_counts[key])
        )
        response.headers["X-RateLimit-Reset"] = str((current_minute + 1) * 60)
        
        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.
    Checks for API key in header and validates it.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip for endpoints that don't require API key
        if not request.url.path.startswith("/api/v1/external"):
            return await call_next(request)
        
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )
        
        # Validate API key (implement your validation logic)
        # For now, just check if it's not empty
        if len(api_key) < 32:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Add API key info to request state
        request.state.api_key = api_key
        
        response = await call_next(request)
        return response


# Export middleware classes
__all__ = [
    "AuthenticationMiddleware",
    "SecurityMiddleware",
    "RateLimitMiddleware",
    "APIKeyMiddleware"
]