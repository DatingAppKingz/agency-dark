"""
Advanced rate limiting implementation with Redis backend.
"""
import time
import json
import asyncio
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
import logging
from enum import Enum

from core.redis import redis_client
from core.rate_limiting.models import (
    RateLimitTier, RateLimitType, RateLimitConfig,
    UserRateLimit, IPRateLimit, RateLimitViolation
)

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Result of rate limit check."""
    
    def __init__(
        self,
        allowed: bool,
        limit: int,
        remaining: int,
        reset_at: datetime,
        retry_after: Optional[int] = None,
        reason: Optional[str] = None
    ):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at
        self.retry_after = retry_after  # Seconds until retry
        self.reason = reason
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at.timestamp()))
        }
        
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        
        return headers


class RateLimiter:
    """Advanced rate limiter with multiple strategies."""
    
    def __init__(self):
        self.redis = redis_client
        self._config_cache = {}
        self._config_cache_ttl = 300  # 5 minutes
        
    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        method: str = "GET",
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        tier: RateLimitTier = RateLimitTier.FREE
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Unique identifier for the client
            endpoint: API endpoint being accessed
            method: HTTP method
            user_id: Optional user ID
            api_key_id: Optional API key ID
            ip_address: Client IP address
            tier: Rate limit tier
            
        Returns:
            RateLimitResult with allow/deny decision
        """
        # Check whitelist first
        if await self._is_whitelisted(user_id, api_key_id, ip_address, endpoint):
            return RateLimitResult(
                allowed=True,
                limit=999999,
                remaining=999999,
                reset_at=datetime.utcnow() + timedelta(hours=1),
                reason="whitelisted"
            )
        
        # Check IP blacklist
        if ip_address and await self._is_ip_blocked(ip_address):
            return RateLimitResult(
                allowed=False,
                limit=0,
                remaining=0,
                reset_at=datetime.utcnow() + timedelta(hours=1),
                retry_after=3600,
                reason="ip_blocked"
            )
        
        # Get rate limit configuration
        config = await self._get_rate_limit_config(endpoint, tier)
        if not config:
            # No specific config, use defaults
            config = self._get_default_config(tier)
        
        # Apply user-specific overrides
        if user_id:
            config = await self._apply_user_overrides(user_id, config)
        
        # Check multiple time windows
        results = []
        
        if config.get('requests_per_minute'):
            result = await self._check_window_limit(
                identifier,
                endpoint,
                window_seconds=60,
                limit=config['requests_per_minute'],
                burst_size=config.get('burst_size', 0)
            )
            results.append(result)
        
        if config.get('requests_per_hour'):
            result = await self._check_window_limit(
                identifier,
                endpoint,
                window_seconds=3600,
                limit=config['requests_per_hour'],
                burst_size=0  # No burst for hourly limits
            )
            results.append(result)
        
        if config.get('requests_per_day'):
            result = await self._check_window_limit(
                identifier,
                endpoint,
                window_seconds=86400,
                limit=config['requests_per_day'],
                burst_size=0  # No burst for daily limits
            )
            results.append(result)
        
        # Return the most restrictive result
        final_result = self._combine_results(results)
        
        # Log violation if rate limit exceeded
        if not final_result.allowed:
            await self._log_violation(
                user_id=user_id,
                api_key_id=api_key_id,
                ip_address=ip_address,
                endpoint=endpoint,
                method=method,
                limit_type="combined",
                limit_value=final_result.limit,
                actual_value=final_result.limit - final_result.remaining
            )
        
        return final_result
    
    async def _check_window_limit(
        self,
        identifier: str,
        endpoint: str,
        window_seconds: int,
        limit: int,
        burst_size: int = 0
    ) -> RateLimitResult:
        """Check rate limit for a specific time window using sliding window."""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Create Redis key
        key = f"rate_limit:{identifier}:{endpoint}:{window_seconds}"
        
        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiry
        pipe.expire(key, window_seconds + 60)
        
        results = await pipe.execute()
        request_count = results[1]
        
        # Check burst allowance
        if burst_size > 0 and request_count <= burst_size:
            # Within burst window
            allowed = True
        else:
            # Normal rate limit check
            allowed = request_count < limit
        
        remaining = max(0, limit - request_count - 1) if allowed else 0
        reset_at = datetime.utcnow() + timedelta(seconds=window_seconds)
        
        retry_after = None
        if not allowed:
            # Calculate when the oldest request will expire
            oldest_request = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest_request:
                oldest_time = oldest_request[0][1]
                retry_after = int(oldest_time + window_seconds - current_time + 1)
        
        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after
        )
    
    async def _is_whitelisted(
        self,
        user_id: Optional[str],
        api_key_id: Optional[str],
        ip_address: Optional[str],
        endpoint: str
    ) -> bool:
        """Check if request is whitelisted."""
        # Check cache first
        cache_key = f"whitelist:{user_id or ''}:{api_key_id or ''}:{ip_address or ''}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached == "1"
        
        # Check database
        from sqlalchemy import select, and_, or_
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import RateLimitWhitelist
        
        async with AsyncSessionLocal() as db:
            query = select(RateLimitWhitelist).where(
                and_(
                    RateLimitWhitelist.valid_from <= datetime.utcnow(),
                    or_(
                        RateLimitWhitelist.valid_until.is_(None),
                        RateLimitWhitelist.valid_until > datetime.utcnow()
                    )
                )
            )
            
            # Add conditions based on available identifiers
            conditions = []
            if user_id:
                conditions.append(RateLimitWhitelist.user_id == user_id)
            if api_key_id:
                conditions.append(RateLimitWhitelist.api_key_id == api_key_id)
            if ip_address:
                conditions.append(RateLimitWhitelist.ip_address == ip_address)
            
            if conditions:
                query = query.where(or_(*conditions))
            
            result = await db.execute(query)
            whitelist_entry = result.scalar_one_or_none()
            
            is_whitelisted = whitelist_entry is not None
            
            # Cache result
            await self.redis.setex(cache_key, 300, "1" if is_whitelisted else "0")
            
            return is_whitelisted
    
    async def _is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked."""
        # Check cache
        cache_key = f"ip_block:{ip_address}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached == "1"
        
        # Check database
        from sqlalchemy import select, and_, or_
        from core.database import AsyncSessionLocal
        from core.rate_limiting.models import IPRateLimit
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(IPRateLimit).where(
                    and_(
                        IPRateLimit.ip_address == ip_address,
                        IPRateLimit.action == "block",
                        or_(
                            IPRateLimit.expires_at.is_(None),
                            IPRateLimit.expires_at > datetime.utcnow()
                        )
                    )
                )
            )
            
            is_blocked = result.scalar_one_or_none() is not None
            
            # Cache result
            await self.redis.setex(cache_key, 300, "1" if is_blocked else "0")
            
            return is_blocked
    
    async def _get_rate_limit_config(
        self,
        endpoint: str,
        tier: RateLimitTier
    ) -> Optional[Dict[str, Any]]:
        """Get rate limit configuration for endpoint and tier."""
        # Check cache
        cache_key = f"config:{tier}:{endpoint}"
        if cache_key in self._config_cache:
            cached_time, config = self._config_cache[cache_key]
            if time.time() - cached_time < self._config_cache_ttl:
                return config
        
        # Load from database
        from sqlalchemy import select, and_
        from core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # Find matching config (support wildcards)
            result = await db.execute(
                select(RateLimitConfig).where(
                    and_(
                        RateLimitConfig.tier == tier,
                        RateLimitConfig.is_active == True
                    )
                ).order_by(RateLimitConfig.endpoint_pattern.desc())
            )
            
            for config in result.scalars():
                if self._matches_endpoint(endpoint, config.endpoint_pattern):
                    config_dict = {
                        'requests_per_minute': config.requests_per_minute,
                        'requests_per_hour': config.requests_per_hour,
                        'requests_per_day': config.requests_per_day,
                        'burst_size': config.burst_size,
                        'burst_window_seconds': config.burst_window_seconds
                    }
                    
                    # Cache it
                    self._config_cache[cache_key] = (time.time(), config_dict)
                    
                    return config_dict
        
        return None
    
    async def _apply_user_overrides(
        self,
        user_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply user-specific rate limit overrides."""
        from sqlalchemy import select, and_
        from core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserRateLimit).where(
                    and_(
                        UserRateLimit.user_id == user_id,
                        UserRateLimit.valid_from <= datetime.utcnow(),
                        or_(
                            UserRateLimit.valid_until.is_(None),
                            UserRateLimit.valid_until > datetime.utcnow()
                        )
                    )
                )
            )
            
            user_limit = result.scalar_one_or_none()
            if user_limit:
                # Apply multiplier
                if user_limit.limit_multiplier != 1.0:
                    for key in ['requests_per_minute', 'requests_per_hour', 'requests_per_day']:
                        if config.get(key):
                            config[key] = int(config[key] * user_limit.limit_multiplier)
                
                # Apply custom limits
                if user_limit.custom_limits:
                    config.update(user_limit.custom_limits)
        
        return config
    
    def _get_default_config(self, tier: RateLimitTier) -> Dict[str, Any]:
        """Get default configuration for a tier."""
        defaults = {
            RateLimitTier.FREE: {
                'requests_per_minute': 20,
                'requests_per_hour': 500,
                'requests_per_day': 5000,
                'burst_size': 5,
                'burst_window_seconds': 10
            },
            RateLimitTier.BASIC: {
                'requests_per_minute': 60,
                'requests_per_hour': 2000,
                'requests_per_day': 20000,
                'burst_size': 10,
                'burst_window_seconds': 10
            },
            RateLimitTier.PROFESSIONAL: {
                'requests_per_minute': 200,
                'requests_per_hour': 8000,
                'requests_per_day': 80000,
                'burst_size': 20,
                'burst_window_seconds': 10
            },
            RateLimitTier.ENTERPRISE: {
                'requests_per_minute': 1000,
                'requests_per_hour': 40000,
                'requests_per_day': 400000,
                'burst_size': 50,
                'burst_window_seconds': 10
            }
        }
        
        return defaults.get(tier, defaults[RateLimitTier.FREE])
    
    def _matches_endpoint(self, endpoint: str, pattern: str) -> bool:
        """Check if endpoint matches pattern (supports wildcards)."""
        import fnmatch
        return fnmatch.fnmatch(endpoint, pattern)
    
    def _combine_results(self, results: List[RateLimitResult]) -> RateLimitResult:
        """Combine multiple rate limit results, returning the most restrictive."""
        if not results:
            # No limits apply
            return RateLimitResult(
                allowed=True,
                limit=999999,
                remaining=999999,
                reset_at=datetime.utcnow() + timedelta(hours=1)
            )
        
        # Find the most restrictive result
        most_restrictive = results[0]
        for result in results[1:]:
            if not result.allowed and most_restrictive.allowed:
                most_restrictive = result
            elif not result.allowed and not most_restrictive.allowed:
                # Both denied, pick the one with longer retry
                if (result.retry_after or 0) > (most_restrictive.retry_after or 0):
                    most_restrictive = result
            elif result.allowed and most_restrictive.allowed:
                # Both allowed, pick the one with fewer remaining
                if result.remaining < most_restrictive.remaining:
                    most_restrictive = result
        
        return most_restrictive
    
    async def _log_violation(
        self,
        user_id: Optional[str],
        api_key_id: Optional[str],
        ip_address: Optional[str],
        endpoint: str,
        method: str,
        limit_type: str,
        limit_value: int,
        actual_value: int
    ):
        """Log rate limit violation to database."""
        try:
            from core.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                violation = RateLimitViolation(
                    user_id=user_id,
                    api_key_id=api_key_id,
                    ip_address=ip_address or "unknown",
                    endpoint=endpoint,
                    method=method,
                    limit_type=limit_type,
                    limit_value=limit_value,
                    actual_value=actual_value,
                    blocked_until=datetime.utcnow() + timedelta(minutes=1)
                )
                db.add(violation)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to log rate limit violation: {e}")
    
    async def get_usage_stats(
        self,
        identifier: str,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current usage statistics for an identifier."""
        stats = {}
        
        # Check different time windows
        for window_name, window_seconds in [
            ('minute', 60),
            ('hour', 3600),
            ('day', 86400)
        ]:
            if endpoint:
                key = f"rate_limit:{identifier}:{endpoint}:{window_seconds}"
            else:
                # Aggregate across all endpoints
                key = f"rate_limit:{identifier}:*:{window_seconds}"
            
            count = await self.redis.zcard(key)
            stats[f'requests_per_{window_name}'] = count
        
        return stats


# Global rate limiter instance
rate_limiter = RateLimiter()