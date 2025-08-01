"""API usage tracking middleware."""

import time
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logger import get_logger
from services.api_usage_tracker import get_usage_tracker, UsageMetric
from services.api_audit_logger import AuditLoggerMiddleware

logger = get_logger(__name__)


class APIUsageMiddleware(BaseHTTPMiddleware):
    """Middleware to track API usage and enforce rate limits."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.usage_tracker = get_usage_tracker()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track usage."""
        # Skip tracking for non-API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Skip tracking for auth endpoints
        if "/auth/" in request.url.path:
            return await call_next(request)
        
        # Get API key from request
        api_key_id = self._get_api_key_id(request)
        if not api_key_id:
            # No API key, proceed without tracking
            return await call_next(request)
        
        # Check rate limits
        if not await self.usage_tracker.check_limit(api_key_id, UsageMetric.REQUESTS):
            logger.warning(
                f"Rate limit exceeded for API key {api_key_id}",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client": request.client.host if request.client else None
                }
            )
            
            # Log rate limit exceeded
            await AuditLoggerMiddleware.log_api_access(
                request,
                api_key_id,
                granted=False,
                reason="Rate limit exceeded"
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Track request
        start_time = time.time()
        response = None
        error_occurred = False
        
        try:
            # Process request
            response = await call_next(request)
            
            # Check for errors
            if response.status_code >= 400:
                error_occurred = True
            
            return response
            
        except Exception as e:
            error_occurred = True
            raise
            
        finally:
            # Track usage
            duration = time.time() - start_time
            
            # Track request
            await self.usage_tracker.track_usage(
                api_key_id,
                UsageMetric.REQUESTS,
                metadata={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code if response else 500,
                    "duration_ms": int(duration * 1000),
                    "error": error_occurred
                }
            )
            
            # Track errors
            if error_occurred:
                await self.usage_tracker.track_usage(
                    api_key_id,
                    UsageMetric.ERRORS,
                    metadata={
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code if response else 500
                    }
                )
            
            # Track specific operations
            await self._track_operation_specific_usage(request, response, api_key_id)
    
    def _get_api_key_id(self, request: Request) -> Optional[str]:
        """Extract API key ID from request."""
        # Check state (set by authentication middleware)
        if hasattr(request.state, "api_key_id"):
            return request.state.api_key_id
        
        # Check headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Extract key ID from prefix (first 8 chars)
            return api_key[:8]
        
        return None
    
    async def _track_operation_specific_usage(
        self,
        request: Request,
        response: Optional[Response],
        api_key_id: str
    ) -> None:
        """Track usage for specific operations."""
        path = request.url.path
        
        # Track sync operations
        if "/sync/" in path and request.method == "POST":
            await self.usage_tracker.track_usage(
                api_key_id,
                UsageMetric.SYNC_OPERATIONS,
                metadata={
                    "path": path,
                    "status": "success" if response and response.status_code < 400 else "failed"
                }
            )
        
        # Track webhook operations
        elif "/webhooks/" in path and request.method == "POST":
            await self.usage_tracker.track_usage(
                api_key_id,
                UsageMetric.WEBHOOKS_SENT,
                metadata={
                    "path": path,
                    "status": "success" if response and response.status_code < 400 else "failed"
                }
            )
        
        # Track data fetching (estimate based on response size)
        elif request.method == "GET" and response:
            # Get response size from headers
            content_length = response.headers.get("content-length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > 0.1:  # Only track if > 100KB
                    await self.usage_tracker.track_usage(
                        api_key_id,
                        UsageMetric.DATA_FETCHED,
                        value=int(size_mb * 10),  # Track in 0.1MB units
                        metadata={
                            "path": path,
                            "size_bytes": int(content_length)
                        }
                    )