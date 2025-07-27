"""
Rate limiting middleware for FastAPI.
"""
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Callable
import logging

from datetime import datetime, timedelta
from sqlalchemy import select

from core.rate_limiting.rate_limiter import rate_limiter, RateLimitTier
from core.dependencies import get_current_user_optional
from core.domain.models import UserRole

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware that applies to all requests.
    """
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        excluded_paths = [
            "/health",
            "/health/live",
            "/health/ready",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)
        
        # Extract identifiers
        client_ip = request.client.host if request.client else "unknown"
        
        # Try to get user info
        user_id = None
        api_key_id = None
        tier = RateLimitTier.FREE
        
        # Check if this is an API key request
        auth_header = request.headers.get("Authorization", "")
        x_api_key = request.headers.get("X-API-Key")
        
        if auth_header.startswith("Bearer ") and ":" in auth_header:
            # API key authentication
            identifier = f"api_key:{auth_header}"
            # TODO: Extract api_key_id from validated key
        elif x_api_key:
            # API key in custom header
            identifier = f"api_key:{x_api_key}"
        else:
            # Try to get JWT user
            try:
                user = await get_current_user_optional(request)
                if user:
                    user_id = str(user.id)
                    identifier = f"user:{user_id}"
                    
                    # Determine tier based on user role
                    if user.role == UserRole.SUPER_ADMIN:
                        tier = RateLimitTier.ENTERPRISE
                    elif user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                        tier = RateLimitTier.PROFESSIONAL
                    elif user.role in [UserRole.AGENCY_MEMBER, UserRole.MODEL]:
                        tier = RateLimitTier.BASIC
                    else:
                        tier = RateLimitTier.FREE
                else:
                    # Anonymous user
                    identifier = f"ip:{client_ip}"
            except:
                # Fall back to IP-based limiting
                identifier = f"ip:{client_ip}"
        
        # Check rate limit
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            endpoint=request.url.path,
            method=request.method,
            user_id=user_id,
            api_key_id=api_key_id,
            ip_address=client_ip,
            tier=tier
        )
        
        # Add rate limit headers to response
        response = await call_next(request)
        
        # Add rate limit headers
        for header, value in result.to_headers().items():
            response.headers[header] = value
        
        # If rate limit exceeded, return 429
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please retry after {result.retry_after} seconds.",
                    "retry_after": result.retry_after
                },
                headers=result.to_headers()
            )
        
        return response


def rate_limit(
    requests_per_minute: Optional[int] = None,
    requests_per_hour: Optional[int] = None,
    requests_per_day: Optional[int] = None,
    burst_size: int = 0,
    key_func: Optional[Callable] = None
):
    """
    Decorator for endpoint-specific rate limiting.
    
    Usage:
        @router.get("/expensive-endpoint")
        @rate_limit(requests_per_minute=10, burst_size=3)
        async def expensive_endpoint():
            return {"data": "expensive"}
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args, **kwargs):
            # Extract identifier
            if key_func:
                identifier = key_func(request, *args, **kwargs)
            else:
                # Default identifier
                client_ip = request.client.host if request.client else "unknown"
                identifier = f"endpoint:{func.__name__}:{client_ip}"
            
            # Create custom config
            config = {}
            if requests_per_minute:
                config['requests_per_minute'] = requests_per_minute
            if requests_per_hour:
                config['requests_per_hour'] = requests_per_hour
            if requests_per_day:
                config['requests_per_day'] = requests_per_day
            if burst_size:
                config['burst_size'] = burst_size
            
            # Apply custom rate limit
            results = []
            
            if requests_per_minute:
                result = await rate_limiter._check_window_limit(
                    identifier=identifier,
                    endpoint=func.__name__,
                    window_seconds=60,
                    limit=requests_per_minute,
                    burst_size=burst_size
                )
                results.append(result)
            
            if requests_per_hour:
                result = await rate_limiter._check_window_limit(
                    identifier=identifier,
                    endpoint=func.__name__,
                    window_seconds=3600,
                    limit=requests_per_hour,
                    burst_size=0
                )
                results.append(result)
            
            if requests_per_day:
                result = await rate_limiter._check_window_limit(
                    identifier=identifier,
                    endpoint=func.__name__,
                    window_seconds=86400,
                    limit=requests_per_day,
                    burst_size=0
                )
                results.append(result)
            
            # Combine results
            final_result = rate_limiter._combine_results(results)
            
            if not final_result.allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "retry_after": final_result.retry_after
                    },
                    headers=final_result.to_headers()
                )
            
            # Add headers to response
            response = await func(request, *args, **kwargs)
            if isinstance(response, Response):
                for header, value in final_result.to_headers().items():
                    response.headers[header] = value
            
            return response
        
        return wrapper
    return decorator


class DynamicRateLimiter:
    """
    Dynamic rate limiter that can be configured at runtime.
    """
    
    @staticmethod
    async def set_user_limit(
        user_id: str,
        limit_multiplier: float = 1.0,
        custom_limits: Optional[dict] = None,
        valid_days: int = 30,
        reason: str = ""
    ):
        """Set custom rate limit for a user."""
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import UserRateLimit
        
        async with AsyncSessionLocal() as db:
            # Check if user already has custom limit
            existing = await db.execute(
                select(UserRateLimit).where(UserRateLimit.user_id == user_id)
            )
            user_limit = existing.scalar_one_or_none()
            
            if user_limit:
                # Update existing
                user_limit.limit_multiplier = limit_multiplier
                user_limit.custom_limits = custom_limits or {}
                user_limit.valid_until = datetime.utcnow() + timedelta(days=valid_days)
                user_limit.reason = reason
            else:
                # Create new
                user_limit = UserRateLimit(
                    user_id=user_id,
                    limit_multiplier=limit_multiplier,
                    custom_limits=custom_limits or {},
                    valid_until=datetime.utcnow() + timedelta(days=valid_days),
                    reason=reason
                )
                db.add(user_limit)
            
            await db.commit()
    
    @staticmethod
    async def block_ip(
        ip_address: str,
        duration_hours: int = 24,
        reason: str = ""
    ):
        """Block an IP address for a specified duration."""
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import IPRateLimit
        
        async with AsyncSessionLocal() as db:
            ip_limit = IPRateLimit(
                ip_address=ip_address,
                action="block",
                reason=reason,
                expires_at=datetime.utcnow() + timedelta(hours=duration_hours)
            )
            db.add(ip_limit)
            await db.commit()
        
        # Clear cache
        await rate_limiter.redis.delete(f"ip_block:{ip_address}")
    
    @staticmethod
    async def whitelist_user(
        user_id: str,
        endpoint_pattern: str = "*",
        valid_days: int = 30,
        reason: str = "",
        approved_by_id: str = None
    ):
        """Add user to rate limit whitelist."""
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import RateLimitWhitelist
        
        async with AsyncSessionLocal() as db:
            whitelist = RateLimitWhitelist(
                user_id=user_id,
                endpoint_pattern=endpoint_pattern,
                valid_until=datetime.utcnow() + timedelta(days=valid_days),
                reason=reason,
                approved_by_id=approved_by_id
            )
            db.add(whitelist)
            await db.commit()
        
        # Clear cache
        await rate_limiter.redis.delete(f"whitelist:{user_id}:::")
    
    @staticmethod
    async def get_violations(
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        hours: int = 24
    ) -> list:
        """Get recent rate limit violations."""
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import RateLimitViolation
        from sqlalchemy import select, and_
        
        async with AsyncSessionLocal() as db:
            query = select(RateLimitViolation).where(
                RateLimitViolation.violated_at > datetime.utcnow() - timedelta(hours=hours)
            )
            
            if user_id:
                query = query.where(RateLimitViolation.user_id == user_id)
            if ip_address:
                query = query.where(RateLimitViolation.ip_address == ip_address)
            
            query = query.order_by(RateLimitViolation.violated_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()