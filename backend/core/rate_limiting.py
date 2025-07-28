"""
Enhanced rate limiting with per-user and per-agency limits
"""
import time
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from redis import asyncio as aioredis
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import logger
from core.domain.models import User, UserRole


class RateLimitTier(str, Enum):
    """Rate limit tiers"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int  # Allow burst of requests
    
    # API-specific limits
    api_limits: Dict[str, int] = None  # Path-specific limits
    
    def __post_init__(self):
        if self.api_limits is None:
            self.api_limits = {}


# Default rate limit configurations by tier
RATE_LIMIT_CONFIGS = {
    RateLimitTier.FREE: RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=100,
        requests_per_day=1000,
        burst_size=5,
        api_limits={
            "/api/v1/ml/": 10,  # ML endpoints are expensive
            "/api/v1/analytics/": 50,
            "/api/v1/sync/": 20,
        }
    ),
    RateLimitTier.BASIC: RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        burst_size=10,
        api_limits={
            "/api/v1/ml/": 30,
            "/api/v1/analytics/": 200,
            "/api/v1/sync/": 100,
        }
    ),
    RateLimitTier.PREMIUM: RateLimitConfig(
        requests_per_minute=200,
        requests_per_hour=5000,
        requests_per_day=50000,
        burst_size=20,
        api_limits={
            "/api/v1/ml/": 100,
            "/api/v1/analytics/": 1000,
            "/api/v1/sync/": 500,
        }
    ),
    RateLimitTier.ENTERPRISE: RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=20000,
        requests_per_day=200000,
        burst_size=50,
        api_limits={
            "/api/v1/ml/": 500,
            "/api/v1/analytics/": 5000,
            "/api/v1/sync/": 2000,
        }
    ),
    RateLimitTier.UNLIMITED: RateLimitConfig(
        requests_per_minute=10000,
        requests_per_hour=100000,
        requests_per_day=1000000,
        burst_size=100,
        api_limits={}  # No specific limits
    ),
}

# Role to tier mapping
ROLE_TIER_MAPPING = {
    UserRole.SUPER_ADMIN: RateLimitTier.UNLIMITED,
    UserRole.AGENCY_OWNER: RateLimitTier.ENTERPRISE,
    UserRole.AGENCY_ADMIN: RateLimitTier.PREMIUM,
    UserRole.MODEL: RateLimitTier.BASIC,
    UserRole.CHATTER: RateLimitTier.FREE,
}


class RateLimiter:
    """Enhanced rate limiter with multiple strategies"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._stats = {
            "allowed": 0,
            "blocked": 0,
            "total": 0
        }
    
    async def check_rate_limit(
        self,
        identifier: str,
        tier: RateLimitTier,
        path: str,
        window: str = "minute"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limits
        
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        config = RATE_LIMIT_CONFIGS[tier]
        current_time = int(time.time())
        
        # Determine limit based on window
        if window == "minute":
            limit = config.requests_per_minute
            window_size = 60
        elif window == "hour":
            limit = config.requests_per_hour
            window_size = 3600
        elif window == "day":
            limit = config.requests_per_day
            window_size = 86400
        else:
            limit = config.requests_per_minute
            window_size = 60
        
        # Check API-specific limits
        for api_pattern, api_limit in config.api_limits.items():
            if path.startswith(api_pattern):
                limit = min(limit, api_limit)
                break
        
        # Use sliding window algorithm
        key = f"rate_limit:{identifier}:{window}:{path}"
        window_start = current_time - window_size
        
        # Remove old entries and count current requests
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(current_time): current_time})
        pipe.expire(key, window_size + 1)
        
        results = await pipe.execute()
        request_count = results[1]
        
        # Check if within limits (including burst)
        is_allowed = request_count <= (limit + config.burst_size)
        
        # Update stats
        self._stats["total"] += 1
        if is_allowed:
            self._stats["allowed"] += 1
        else:
            self._stats["blocked"] += 1
        
        # Calculate rate limit info
        rate_info = {
            "limit": limit,
            "remaining": max(0, limit - request_count),
            "reset": current_time + window_size,
            "window": window,
            "tier": tier,
            "request_count": request_count,
            "burst_allowed": request_count <= limit + config.burst_size and request_count > limit
        }
        
        return is_allowed, rate_info
    
    async def check_user_rate_limit(
        self,
        user: User,
        path: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for authenticated user"""
        # Determine tier based on role
        tier = ROLE_TIER_MAPPING.get(user.role, RateLimitTier.FREE)
        
        # Override with user-specific tier if set
        if hasattr(user, 'rate_limit_tier') and user.rate_limit_tier:
            tier = user.rate_limit_tier
        
        # Check multiple windows
        for window in ["minute", "hour", "day"]:
            identifier = f"user:{user.id}"
            is_allowed, rate_info = await self.check_rate_limit(
                identifier, tier, path, window
            )
            
            if not is_allowed:
                return False, rate_info
        
        return True, rate_info
    
    async def check_agency_rate_limit(
        self,
        agency_id: str,
        path: str,
        tier: Optional[RateLimitTier] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for agency"""
        # Use provided tier or default to PREMIUM
        tier = tier or RateLimitTier.PREMIUM
        
        # Check agency-wide limits
        for window in ["minute", "hour", "day"]:
            identifier = f"agency:{agency_id}"
            is_allowed, rate_info = await self.check_rate_limit(
                identifier, tier, path, window
            )
            
            if not is_allowed:
                return False, rate_info
        
        return True, rate_info
    
    async def check_ip_rate_limit(
        self,
        ip_address: str,
        path: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for IP address (unauthenticated requests)"""
        # Use FREE tier for IP-based limiting
        tier = RateLimitTier.FREE
        
        # Stricter limits for unauthenticated requests
        identifier = f"ip:{ip_address}"
        is_allowed, rate_info = await self.check_rate_limit(
            identifier, tier, path, "minute"
        )
        
        return is_allowed, rate_info
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        tier: RateLimitTier,
        path: str = "/"
    ) -> Dict[str, Any]:
        """Get current rate limit status without incrementing"""
        status = {}
        config = RATE_LIMIT_CONFIGS[tier]
        current_time = int(time.time())
        
        for window, (limit, window_size) in [
            ("minute", (config.requests_per_minute, 60)),
            ("hour", (config.requests_per_hour, 3600)),
            ("day", (config.requests_per_day, 86400))
        ]:
            key = f"rate_limit:{identifier}:{window}:{path}"
            window_start = current_time - window_size
            
            # Count requests in window
            count = await self.redis.zcount(key, window_start, current_time)
            
            status[window] = {
                "limit": limit,
                "used": count,
                "remaining": max(0, limit - count),
                "reset": current_time + window_size
            }
        
        return status
    
    async def reset_rate_limit(self, identifier: str, path: str = None):
        """Reset rate limits for an identifier"""
        pattern = f"rate_limit:{identifier}:*"
        if path:
            pattern += f":{path}"
        
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        
        if keys:
            await self.redis.delete(*keys)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        return {
            **self._stats,
            "blocked_percentage": (
                self._stats["blocked"] / self._stats["total"] * 100
                if self._stats["total"] > 0 else 0
            )
        }


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.rate_limiter = RateLimiter(redis_client)
    
    async def __call__(self, request: Request, call_next):
        """Apply rate limiting to requests"""
        # Skip rate limiting for health checks and docs
        skip_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
        if request.url.path in skip_paths:
            return await call_next(request)
        
        # Get user from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        path = request.url.path
        
        is_allowed = False
        rate_info = {}
        
        if user:
            # Authenticated request - check user and agency limits
            is_allowed, rate_info = await self.rate_limiter.check_user_rate_limit(
                user, path
            )
            
            if is_allowed and user.agency_id:
                # Also check agency limits
                is_allowed, agency_info = await self.rate_limiter.check_agency_rate_limit(
                    str(user.agency_id), path
                )
                if not is_allowed:
                    rate_info = agency_info
        else:
            # Unauthenticated request - check IP limits
            client_ip = request.client.host if request.client else "unknown"
            if request.headers.get("X-Forwarded-For"):
                client_ip = request.headers["X-Forwarded-For"].split(",")[0]
            
            is_allowed, rate_info = await self.rate_limiter.check_ip_rate_limit(
                client_ip, path
            )
        
        if not is_allowed:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {rate_info['limit']} per {rate_info['window']}",
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "X-RateLimit-Window": rate_info["window"],
                    "Retry-After": str(rate_info["reset"] - int(time.time()))
                }
            )
        
        # Process request and add rate limit headers
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset", 0))
        
        return response


# Dependency for manual rate limit checks in endpoints
async def check_rate_limit(
    request: Request,
    user: User,
    custom_limit: Optional[int] = None
) -> None:
    """
    Dependency to check rate limits in specific endpoints
    
    Usage:
        @router.post("/expensive-operation")
        async def expensive_operation(
            _: None = Depends(check_rate_limit),
            user: User = Depends(get_current_user)
        ):
            ...
    """
    from core.redis import get_redis
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    is_allowed, rate_info = await rate_limiter.check_user_rate_limit(
        user, request.url.path
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please try again in {rate_info['reset'] - int(time.time())} seconds",
            headers={
                "Retry-After": str(rate_info["reset"] - int(time.time()))
            }
        )