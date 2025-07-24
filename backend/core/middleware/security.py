"""
Security middleware for API protection.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
import time
import hashlib
import hmac
from typing import Dict, Optional
import re
from datetime import datetime, timedelta
import logging

from core.config import settings
from core.redis import redis_client

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for request validation and protection."""
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bor\b\s*\d+\s*=\s*\d+)",
        r"(\band\b\s*\d+\s*=\s*\d+)",
        r"(';|\";\s*--)",
        r"(\bwhere\b.*\b1\s*=\s*1)",
        r"(\bsleep\b\s*\()",
        r"(\bbenchmark\b\s*\()",
        r"(xp_cmdshell)",
        r"(eval\s*\()",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
        r"<img[^>]*onerror\s*=",
        r"<svg[^>]*onload\s*=",
    ]
    
    def __init__(self, app):
        super().__init__(app)
        self.sql_pattern = re.compile("|".join(self.SQL_INJECTION_PATTERNS), re.IGNORECASE)
        self.xss_pattern = re.compile("|".join(self.XSS_PATTERNS), re.IGNORECASE)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security checks."""
        start_time = time.time()
        
        try:
            # Check for SQL injection in query parameters
            if request.query_params:
                for value in request.query_params.values():
                    if self._contains_sql_injection(value):
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Invalid request parameters"}
                        )
            
            # Check for XSS in request body (for POST/PUT/PATCH)
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await self._get_request_body(request)
                if body and self._contains_xss(str(body)):
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid request content"}
                    )
            
            # Add security headers
            response = await call_next(request)
            
            # Security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # CSP header
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.inflow.com https://onlyfansapi.com; "
                "frame-ancestors 'none';"
            )
            
            # Log response time
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check if value contains SQL injection patterns."""
        return bool(self.sql_pattern.search(value))
    
    def _contains_xss(self, value: str) -> bool:
        """Check if value contains XSS patterns."""
        return bool(self.xss_pattern.search(value))
    
    async def _get_request_body(self, request: Request) -> Optional[bytes]:
        """Get request body for inspection."""
        body = await request.body()
        
        # Reconstruct request body for downstream processing
        async def receive() -> Message:
            return {"type": "http.request", "body": body}
        
        request._receive = receive
        return body


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting."""
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        key = f"rate_limit:{client_id}:{request.url.path}"
        
        try:
            # Check rate limit
            current = await redis_client.incr(key)
            
            if current == 1:
                # First request, set expiry
                await redis_client.expire(key, self.period)
            
            if current > self.calls:
                # Rate limit exceeded
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. Maximum {self.calls} requests per {self.period} seconds."
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.calls),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + self.period)
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.calls)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.calls - current))
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.period)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limit error: {str(e)}")
            # If Redis fails, allow request
            return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier."""
        # Try to get from JWT token first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return hashlib.md5(auth_header.encode()).hexdigest()
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0]
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return client_ip


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API key validation for external integrations."""
    
    # Paths that require API key
    API_KEY_PATHS = [
        "/api/v1/integrations/webhook",
        "/api/v1/external",
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Validate API key for protected paths."""
        # Check if path requires API key
        requires_api_key = any(
            request.url.path.startswith(path) 
            for path in self.API_KEY_PATHS
        )
        
        if requires_api_key:
            api_key = request.headers.get("X-API-Key")
            
            if not api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "API key required"}
                )
            
            # Validate API key
            if not await self._validate_api_key(api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid API key"}
                )
        
        return await call_next(request)
    
    async def _validate_api_key(self, api_key: str) -> bool:
        """Validate API key against stored keys."""
        # Check in Redis cache first
        cached = await redis_client.get(f"api_key:{api_key}")
        if cached:
            return cached == "valid"
        
        # TODO: Implement database lookup for API keys
        # For now, check against environment variable
        valid = api_key == settings.INFLOW_API_KEY
        
        # Cache result
        if valid:
            await redis_client.setex(f"api_key:{api_key}", 3600, "valid")
        
        return valid