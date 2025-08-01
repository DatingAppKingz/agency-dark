"""Logging context middleware for structured logging."""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from core.logging_context import set_request_context, clear_request_context, get_structured_logger


logger = get_structured_logger(__name__)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Add logging context to all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request context and log request/response."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-ID", request_id)
        
        # Set initial context
        set_request_context(
            request_id=request_id,
            correlation_id=correlation_id
        )
        
        # Store request ID in request state
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.log_event(
            "request_started",
            {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log request completed
            logger.log_api_call(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error_type": type(e).__name__
                }
            )
            
            # Re-raise the exception
            raise
            
        finally:
            # Clear context
            clear_request_context()


class UserContextMiddleware(BaseHTTPMiddleware):
    """Add user context to logging after authentication."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add user context if available."""
        response = await call_next(request)
        
        # If user is authenticated, add to context
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            set_request_context(
                user_id=str(user.id),
                agency_id=str(user.agency_id) if user.agency_id else None
            )
        
        return response