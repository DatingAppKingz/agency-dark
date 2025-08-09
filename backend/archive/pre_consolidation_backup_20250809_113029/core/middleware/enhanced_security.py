"""
Enhanced Security Middleware with Encrypted API Key Support
"""
import time
import hashlib
from typing import Optional, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.tasks.db_context import get_db_context
from core.security.api_key_manager import secure_api_key_manager
from core.redis import redis_client
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class EnhancedAPIKeyMiddleware(BaseHTTPMiddleware):
    """Enhanced API key validation with encryption and scoping"""
    
    # Paths that require API key authentication
    API_KEY_PATHS = {
        "/api/v1/integrations": ["integrations:read", "integrations:write"],
        "/api/v1/external": ["external:access"],
        "/api/v1/analytics": ["analytics:read"],
        "/api/v1/financial": ["financial:read"],
        "/api/v1/webhooks": ["webhooks:manage"],
    }
    
    # Paths that are exempt from API key auth
    EXEMPT_PATHS = [
        "/api/v1/auth",
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/openapi.json"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Validate API key for protected paths with scope checking"""
        
        # Check if path is exempt
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Check if path requires API key
        required_scopes = self._get_required_scopes(request)
        if not required_scopes:
            return await call_next(request)
        
        # Extract API key from headers
        api_key = self._extract_api_key(request)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "API key required",
                    "headers": ["X-API-Key", "Authorization: Bearer <api_key>"]
                },
                headers={"WWW-Authenticate": "ApiKey"}
            )
        
        # Validate API key
        try:
            async with get_db_context() as db:
                api_key_record = await secure_api_key_manager.verify_api_key(
                    db=db,
                    api_key=api_key,
                    required_scopes=required_scopes
                )
                
                if not api_key_record:
                    # Log failed attempt
                    await self._log_failed_attempt(request, api_key)
                    
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "invalid_api_key",
                            "message": "Invalid or expired API key"
                        },
                        headers={"WWW-Authenticate": "ApiKey"}
                    )
                
                # Add API key info to request state
                request.state.api_key = {
                    "id": api_key_record.id,
                    "user_id": str(api_key_record.user_id),
                    "scopes": api_key_record.scopes,
                    "environment": api_key_record.environment
                }
                
                # Add rate limit headers specific to API key
                response = await call_next(request)
                response.headers["X-API-Key-ID"] = str(api_key_record.id)
                response.headers["X-API-Environment"] = api_key_record.environment
                
                return response
                
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Authentication failed"}
            )
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers"""
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Check query parameter (only for specific endpoints)
        if request.url.path.startswith("/api/v1/webhooks"):
            return request.query_params.get("api_key")
        
        return None
    
    def _get_required_scopes(self, request: Request) -> Optional[List[str]]:
        """Get required scopes for the request path"""
        for path_prefix, scopes in self.API_KEY_PATHS.items():
            if request.url.path.startswith(path_prefix):
                # Determine specific scopes based on method
                if request.method in ["GET", "HEAD", "OPTIONS"]:
                    return [s for s in scopes if ":read" in s or not ":" in s]
                else:
                    return scopes
        
        return None
    
    async def _log_failed_attempt(self, request: Request, api_key: str):
        """Log failed API key attempt for security monitoring"""
        # Get client info
        client_ip = request.headers.get("X-Forwarded-For", "")
        if not client_ip and request.client:
            client_ip = request.client.host
        
        # Log to Redis for rate limiting bad keys
        fail_key = f"api_key_fail:{hashlib.md5(api_key.encode()).hexdigest()}"
        await redis_client.incr(fail_key)
        await redis_client.expire(fail_key, 3600)  # Track for 1 hour
        
        # Check if this key has too many failures
        failures = await redis_client.get(fail_key)
        if failures and int(failures) > 10:
            # Block this API key temporarily
            block_key = f"api_key_blocked:{hashlib.md5(api_key.encode()).hexdigest()}"
            await redis_client.setex(block_key, 3600, "blocked")
            
            logger.warning(
                f"Blocked API key after 10 failures: {api_key[:8]}*** from {client_ip}"
            )


class APIKeyRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting specific to API keys"""
    
    def __init__(self, app):
        super().__init__(app)
        self.default_limits = {
            "test": {"calls": 100, "period": 3600},  # 100 calls per hour for test keys
            "live": {"calls": 1000, "period": 3600},  # 1000 calls per hour for live keys
        }
    
    async def dispatch(self, request: Request, call_next):
        """Apply API key specific rate limits"""
        
        # Check if request has API key info
        if not hasattr(request.state, "api_key"):
            return await call_next(request)
        
        api_key_info = request.state.api_key
        environment = api_key_info.get("environment", "live")
        
        # Get rate limit for environment
        limits = self.default_limits.get(environment, self.default_limits["live"])
        
        # Create rate limit key
        rate_key = f"api_rate:{api_key_info['id']}:{request.url.path}"
        
        try:
            # Check rate limit
            current = await redis_client.incr(rate_key)
            
            if current == 1:
                await redis_client.expire(rate_key, limits["period"])
            
            remaining = max(0, limits["calls"] - current)
            
            if current > limits["calls"]:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": f"API rate limit exceeded for {environment} key",
                        "limit": limits["calls"],
                        "period": limits["period"],
                        "retry_after": limits["period"]
                    },
                    headers={
                        "X-RateLimit-Limit": str(limits["calls"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + limits["period"]),
                        "Retry-After": str(limits["period"])
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(limits["calls"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + limits["period"])
            
            return response
            
        except Exception as e:
            logger.error(f"API rate limit error: {e}")
            return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers"""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS (only in production)
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # CSP (Content Security Policy)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https://api.stripe.com wss:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        return response