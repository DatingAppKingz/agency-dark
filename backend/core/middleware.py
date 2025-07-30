"""Custom middleware for the application."""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import time

from core.redis import session_manager, RateLimiter
from core.logging import logger


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware for managing user sessions with Redis."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or create session ID from cookie
        session_id = request.cookies.get("session_id")
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get session data from Redis
        session_data = await session_manager.get(session_id) or {}
        
        # Add session to request state
        request.state.session_id = session_id
        request.state.session = session_data
        
        # Process request
        response = await call_next(request)
        
        # Save session if modified
        if hasattr(request.state, "session_modified") and request.state.session_modified:
            await session_manager.update(session_id, request.state.session)
        
        # Set session cookie if new session
        if not request.cookies.get("session_id"):
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=86400  # 24 hours
            )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting."""
    
    def __init__(self, app, calls: int = 100, window: int = 60):
        super().__init__(app)
        self.calls = calls
        self.window = window
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)
        
        # Get client identifier (IP address or user ID)
        client_id = request.client.host if request.client else "unknown"
        
        # Check if user is authenticated
        if hasattr(request.state, "user") and request.state.user:
            client_id = f"user_{request.state.user.id}"
        
        # Check rate limit
        is_allowed, remaining = await RateLimiter.check_rate_limit(
            key=client_id,
            max_requests=self.calls,
            window=self.window
        )
        
        if not is_allowed:
            return Response(
                content={"detail": "Rate limit exceeded"},
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + self.window)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.window)
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {response.status_code} in {duration:.3f}s",
            extra={
                "status_code": response.status_code,
                "duration": duration,
                "path": request.url.path
            }
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response