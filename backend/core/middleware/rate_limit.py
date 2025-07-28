"""
Rate Limiting Middleware with Advanced Features

Integrates with the advanced rate limiter to provide:
- Multiple strategy support
- Distributed rate limiting
- Automatic blocking
- Detailed headers
"""
import time
import json
from typing import Optional, Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from fastapi import status

from core.security.rate_limiter import rate_limiter, RateLimitStrategy, RateLimitConfig
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting middleware with multiple strategies"""
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = [
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc"
    ]
    
    # Paths that use specific strategies
    PATH_STRATEGIES = {
        "/api/v1/auth": [RateLimitStrategy.IP],
        "/api/v1/integrations": [RateLimitStrategy.API_KEY, RateLimitStrategy.USER],
        "/api/v1/financial": [RateLimitStrategy.USER, RateLimitStrategy.IP],
        "/api/v1/analytics": [RateLimitStrategy.USER, RateLimitStrategy.API_KEY],
        "/api/v1/bulk": [RateLimitStrategy.USER],
        "/api/v1/webhooks": [RateLimitStrategy.IP, RateLimitStrategy.GLOBAL]
    }
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting based on multiple strategies"""
        
        # Check if path is exempt
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Skip rate limiting in development if configured
        if settings.ENVIRONMENT == "development" and getattr(settings, "DISABLE_RATE_LIMIT_DEV", False):
            return await call_next(request)
        
        # Determine strategies to apply
        strategies = self._get_applicable_strategies(request)
        if not strategies:
            return await call_next(request)
        
        # Extract identifiers for each strategy
        identifiers = await self._extract_identifiers(request, strategies)
        
        # Check rate limits
        if len(identifiers) > 1:
            # Combined check for multiple strategies
            result = await rate_limiter.check_combined_rate_limit(
                identifiers=identifiers,
                endpoint=request.url.path
            )
        else:
            # Single strategy check
            strategy, identifier = next(iter(identifiers.items()))
            result = await rate_limiter.check_rate_limit(
                identifier=identifier,
                strategy=strategy,
                endpoint=request.url.path
            )
        
        # Handle rate limit result
        if not result.allowed:
            return self._create_rate_limit_response(result, identifiers)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.remaining + 1)  # Include current request
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        
        # Add strategy information
        response.headers["X-RateLimit-Strategy"] = ",".join(s.value for s in identifiers.keys())
        
        return response
    
    def _get_applicable_strategies(self, request: Request) -> List[RateLimitStrategy]:
        """Determine which rate limiting strategies to apply"""
        strategies = []
        
        # Check path-specific strategies
        for path_prefix, path_strategies in self.PATH_STRATEGIES.items():
            if request.url.path.startswith(path_prefix):
                strategies.extend(path_strategies)
                break
        
        # Default strategies if none specified
        if not strategies:
            # Always apply IP-based limiting as baseline
            strategies.append(RateLimitStrategy.IP)
            
            # Add user-based if authenticated
            if hasattr(request.state, "user"):
                strategies.append(RateLimitStrategy.USER)
            
            # Add API key-based if using API key
            if hasattr(request.state, "api_key"):
                strategies.append(RateLimitStrategy.API_KEY)
        
        # Add global rate limiting for public endpoints
        if not hasattr(request.state, "user") and not hasattr(request.state, "api_key"):
            strategies.append(RateLimitStrategy.GLOBAL)
        
        return list(set(strategies))  # Remove duplicates
    
    async def _extract_identifiers(
        self,
        request: Request,
        strategies: List[RateLimitStrategy]
    ) -> Dict[RateLimitStrategy, str]:
        """Extract identifiers for each rate limiting strategy"""
        identifiers = {}
        
        for strategy in strategies:
            if strategy == RateLimitStrategy.IP:
                identifier = self._get_client_ip(request)
            elif strategy == RateLimitStrategy.USER:
                identifier = self._get_user_id(request)
            elif strategy == RateLimitStrategy.API_KEY:
                identifier = self._get_api_key_id(request)
            elif strategy == RateLimitStrategy.GLOBAL:
                identifier = "global"
            else:
                continue
            
            if identifier:
                identifiers[strategy] = identifier
        
        return identifiers
    
    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address"""
        # Check for IP in headers (reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.get('user_id', 'unknown')}"
        return None
    
    def _get_api_key_id(self, request: Request) -> Optional[str]:
        """Extract API key ID from request"""
        if hasattr(request.state, "api_key") and request.state.api_key:
            return f"api_key:{request.state.api_key.get('id', 'unknown')}"
        return None
    
    def _create_rate_limit_response(
        self,
        result,
        identifiers: Dict[RateLimitStrategy, str]
    ) -> JSONResponse:
        """Create rate limit exceeded response"""
        
        # Determine primary reason
        if result.blocked_until:
            message = "Access temporarily blocked due to repeated violations"
            status_code = status.HTTP_403_FORBIDDEN
        else:
            message = "Rate limit exceeded"
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        
        # Build detailed error response
        error_detail = {
            "error": "rate_limit_exceeded",
            "message": message,
            "strategies": [s.value for s in identifiers.keys()],
            "retry_after": result.retry_after,
            "reset_at": result.reset_at
        }
        
        if result.blocked_until:
            error_detail["blocked_until"] = result.blocked_until
            error_detail["blocked_for_seconds"] = result.retry_after
        
        response = JSONResponse(
            status_code=status_code,
            content=error_detail
        )
        
        # Add headers
        response.headers["X-RateLimit-Limit"] = "0"
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        response.headers["Retry-After"] = str(result.retry_after)
        
        if result.blocked_until:
            response.headers["X-RateLimit-Blocked-Until"] = str(result.blocked_until)
        
        return response


class CustomRateLimitMiddleware(BaseHTTPMiddleware):
    """Custom rate limit middleware for specific use cases"""
    
    def __init__(self, app, config: RateLimitConfig, strategy: RateLimitStrategy = RateLimitStrategy.IP):
        super().__init__(app)
        self.config = config
        self.strategy = strategy
    
    async def dispatch(self, request: Request, call_next):
        """Apply custom rate limiting"""
        
        # Extract identifier based on strategy
        if self.strategy == RateLimitStrategy.IP:
            identifier = self._get_client_ip(request)
        elif self.strategy == RateLimitStrategy.USER:
            identifier = self._get_user_id(request)
        elif self.strategy == RateLimitStrategy.API_KEY:
            identifier = self._get_api_key_id(request)
        else:
            identifier = "custom"
        
        if not identifier:
            return await call_next(request)
        
        # Check rate limit
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            strategy=self.strategy,
            custom_config=self.config
        )
        
        if not result.allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "retry_after": result.retry_after
                },
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Reset": str(result.reset_at)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        
        return response
    
    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        if hasattr(request.state, "user") and request.state.user:
            return str(request.state.user.get("user_id", "unknown"))
        return None
    
    def _get_api_key_id(self, request: Request) -> Optional[str]:
        """Extract API key ID from request"""
        if hasattr(request.state, "api_key") and request.state.api_key:
            return str(request.state.api_key.get("id", "unknown"))
        return None