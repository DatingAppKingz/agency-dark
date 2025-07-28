"""
Advanced Rate Limiting System with Distributed Support

Features:
- Multiple rate limiting strategies (IP, User, API Key, Global)
- Sliding window algorithm for accurate rate limiting
- Distributed rate limiting with Redis
- Configurable limits per endpoint
- Automatic blocking for repeat offenders
"""
import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import json
from dataclasses import dataclass, asdict

from core.redis import redis_client
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies"""
    IP = "ip"
    USER = "user"
    API_KEY = "api_key"
    GLOBAL = "global"
    COMBINED = "combined"  # Combines multiple strategies


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds
    burst: Optional[int] = None  # Burst allowance
    block_duration: Optional[int] = None  # Auto-block duration in seconds


@dataclass
class RateLimitResult:
    """Result of rate limit check"""
    allowed: bool
    remaining: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry
    blocked_until: Optional[int] = None  # Unix timestamp if blocked


class AdvancedRateLimiter:
    """Advanced rate limiting with multiple strategies and distributed support"""
    
    def __init__(self):
        self.endpoint_limits = self._initialize_endpoint_limits()
        self.default_limits = {
            RateLimitStrategy.IP: RateLimitConfig(requests=100, window=60, burst=20),
            RateLimitStrategy.USER: RateLimitConfig(requests=1000, window=3600, burst=100),
            RateLimitStrategy.API_KEY: RateLimitConfig(requests=5000, window=3600, burst=500),
            RateLimitStrategy.GLOBAL: RateLimitConfig(requests=100000, window=3600)
        }
        
        # Auto-blocking configuration
        self.violation_threshold = 10  # Number of violations before blocking
        self.violation_window = 3600   # Window for tracking violations (1 hour)
        self.block_duration = 86400    # Default block duration (24 hours)
    
    def _initialize_endpoint_limits(self) -> Dict[str, Dict[RateLimitStrategy, RateLimitConfig]]:
        """Initialize per-endpoint rate limits"""
        return {
            # Authentication endpoints - stricter limits
            "/api/v1/auth/login": {
                RateLimitStrategy.IP: RateLimitConfig(requests=5, window=300, block_duration=3600),
                RateLimitStrategy.GLOBAL: RateLimitConfig(requests=1000, window=60)
            },
            "/api/v1/auth/register": {
                RateLimitStrategy.IP: RateLimitConfig(requests=3, window=3600, block_duration=7200),
                RateLimitStrategy.GLOBAL: RateLimitConfig(requests=100, window=3600)
            },
            "/api/v1/auth/reset-password": {
                RateLimitStrategy.IP: RateLimitConfig(requests=3, window=3600, block_duration=3600),
                RateLimitStrategy.USER: RateLimitConfig(requests=5, window=86400)
            },
            
            # API key operations - moderate limits
            "/api/v1/api-keys": {
                RateLimitStrategy.USER: RateLimitConfig(requests=10, window=3600),
                RateLimitStrategy.IP: RateLimitConfig(requests=20, window=3600)
            },
            
            # Integration endpoints - higher limits
            "/api/v1/integrations/inflow": {
                RateLimitStrategy.API_KEY: RateLimitConfig(requests=1000, window=60, burst=100),
                RateLimitStrategy.USER: RateLimitConfig(requests=5000, window=3600)
            },
            "/api/v1/integrations/onlyfans": {
                RateLimitStrategy.API_KEY: RateLimitConfig(requests=500, window=60, burst=50),
                RateLimitStrategy.USER: RateLimitConfig(requests=3000, window=3600)
            },
            
            # Analytics - read-heavy, higher limits
            "/api/v1/analytics": {
                RateLimitStrategy.USER: RateLimitConfig(requests=1000, window=60),
                RateLimitStrategy.API_KEY: RateLimitConfig(requests=10000, window=3600)
            },
            
            # Financial operations - strict limits
            "/api/v1/financial/transactions": {
                RateLimitStrategy.USER: RateLimitConfig(requests=100, window=3600, block_duration=7200),
                RateLimitStrategy.IP: RateLimitConfig(requests=50, window=3600)
            },
            "/api/v1/financial/withdrawals": {
                RateLimitStrategy.USER: RateLimitConfig(requests=10, window=86400, block_duration=86400),
                RateLimitStrategy.IP: RateLimitConfig(requests=5, window=86400)
            },
            
            # Bulk operations - very limited
            "/api/v1/bulk": {
                RateLimitStrategy.USER: RateLimitConfig(requests=10, window=3600),
                RateLimitStrategy.API_KEY: RateLimitConfig(requests=50, window=3600)
            },
            
            # Webhook endpoints - moderate limits
            "/api/v1/webhooks": {
                RateLimitStrategy.IP: RateLimitConfig(requests=1000, window=60),
                RateLimitStrategy.GLOBAL: RateLimitConfig(requests=50000, window=60)
            }
        }
    
    async def check_rate_limit(
        self,
        identifier: str,
        strategy: RateLimitStrategy,
        endpoint: Optional[str] = None,
        custom_config: Optional[RateLimitConfig] = None
    ) -> RateLimitResult:
        """Check if request is within rate limits"""
        
        # Check if identifier is blocked
        blocked_until = await self._check_blocked(identifier, strategy)
        if blocked_until:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=blocked_until,
                retry_after=blocked_until - int(time.time()),
                blocked_until=blocked_until
            )
        
        # Get rate limit configuration
        config = custom_config or self._get_config(endpoint, strategy)
        
        # Use sliding window algorithm
        result = await self._sliding_window_check(
            identifier=identifier,
            strategy=strategy,
            config=config,
            endpoint=endpoint
        )
        
        # Track violations if rate limit exceeded
        if not result.allowed:
            await self._track_violation(identifier, strategy)
        
        return result
    
    async def check_combined_rate_limit(
        self,
        identifiers: Dict[RateLimitStrategy, str],
        endpoint: Optional[str] = None
    ) -> RateLimitResult:
        """Check rate limits for multiple strategies combined"""
        
        results = []
        for strategy, identifier in identifiers.items():
            result = await self.check_rate_limit(identifier, strategy, endpoint)
            results.append(result)
        
        # If any strategy denies, deny the request
        for result in results:
            if not result.allowed:
                return result
        
        # All passed, return the most restrictive remaining count
        min_remaining = min(r.remaining for r in results)
        earliest_reset = min(r.reset_at for r in results)
        
        return RateLimitResult(
            allowed=True,
            remaining=min_remaining,
            reset_at=earliest_reset
        )
    
    async def _sliding_window_check(
        self,
        identifier: str,
        strategy: RateLimitStrategy,
        config: RateLimitConfig,
        endpoint: Optional[str] = None
    ) -> RateLimitResult:
        """Implement sliding window rate limiting algorithm"""
        
        current_time = time.time()
        window_start = current_time - config.window
        
        # Create unique key for this rate limit
        key = self._create_key(identifier, strategy, endpoint)
        
        # Use Redis sorted set for sliding window
        pipe = redis_client.pipeline()
        
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count requests in current window
        pipe.zcard(key)
        
        # Add current request with timestamp as score
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiry on the key
        pipe.expire(key, config.window + 60)  # Extra 60s buffer
        
        # Get earliest timestamp in window for reset calculation
        pipe.zrange(key, 0, 0, withscores=True)
        
        results = await pipe.execute()
        
        request_count = results[1]  # Count before adding current request
        earliest_timestamp = results[4][0][1] if results[4] else current_time
        
        # Check burst allowance if configured
        if config.burst and request_count < config.requests:
            # Check burst window (usually shorter)
            burst_window = config.window / 10  # 10% of main window
            burst_start = current_time - burst_window
            burst_count = await redis_client.zcount(key, burst_start, current_time)
            
            if burst_count > config.burst:
                # Burst limit exceeded
                reset_at = int(current_time + burst_window)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=int(burst_window)
                )
        
        # Check main rate limit
        if request_count >= config.requests:
            # Rate limit exceeded
            reset_at = int(earliest_timestamp + config.window)
            retry_after = reset_at - int(current_time)
            
            # Remove the request we just added since it's denied
            await redis_client.zrem(key, str(current_time))
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after=max(1, retry_after)
            )
        
        # Request allowed
        remaining = config.requests - request_count - 1
        reset_at = int(earliest_timestamp + config.window)
        
        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            reset_at=reset_at
        )
    
    async def _check_blocked(self, identifier: str, strategy: RateLimitStrategy) -> Optional[int]:
        """Check if identifier is blocked"""
        block_key = f"rate_limit:blocked:{strategy}:{identifier}"
        blocked_until = await redis_client.get(block_key)
        
        if blocked_until:
            return int(blocked_until)
        
        return None
    
    async def _track_violation(self, identifier: str, strategy: RateLimitStrategy):
        """Track rate limit violations for auto-blocking"""
        violation_key = f"rate_limit:violations:{strategy}:{identifier}"
        
        # Increment violation count
        violations = await redis_client.incr(violation_key)
        
        # Set expiry on first violation
        if violations == 1:
            await redis_client.expire(violation_key, self.violation_window)
        
        # Check if we should block
        if violations >= self.violation_threshold:
            # Block the identifier
            block_key = f"rate_limit:blocked:{strategy}:{identifier}"
            block_until = int(time.time() + self.block_duration)
            
            await redis_client.setex(
                block_key,
                self.block_duration,
                str(block_until)
            )
            
            # Log the blocking
            logger.warning(
                f"Blocked {strategy}:{identifier} due to {violations} violations"
            )
            
            # Reset violation count
            await redis_client.delete(violation_key)
    
    def _get_config(self, endpoint: Optional[str], strategy: RateLimitStrategy) -> RateLimitConfig:
        """Get rate limit configuration for endpoint and strategy"""
        if endpoint and endpoint in self.endpoint_limits:
            endpoint_config = self.endpoint_limits[endpoint].get(strategy)
            if endpoint_config:
                return endpoint_config
        
        return self.default_limits.get(strategy, self.default_limits[RateLimitStrategy.IP])
    
    def _create_key(self, identifier: str, strategy: RateLimitStrategy, endpoint: Optional[str]) -> str:
        """Create Redis key for rate limiting"""
        parts = ["rate_limit", strategy.value, identifier]
        if endpoint:
            # Hash endpoint to keep key size reasonable
            endpoint_hash = hashlib.md5(endpoint.encode()).hexdigest()[:8]
            parts.append(endpoint_hash)
        
        return ":".join(parts)
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        strategy: RateLimitStrategy,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current rate limit status without incrementing counter"""
        
        # Check if blocked
        blocked_until = await self._check_blocked(identifier, strategy)
        if blocked_until:
            return {
                "blocked": True,
                "blocked_until": blocked_until,
                "blocked_for": blocked_until - int(time.time())
            }
        
        config = self._get_config(endpoint, strategy)
        key = self._create_key(identifier, strategy, endpoint)
        
        current_time = time.time()
        window_start = current_time - config.window
        
        # Count current requests
        request_count = await redis_client.zcount(key, window_start, current_time)
        
        # Get earliest timestamp
        earliest = await redis_client.zrange(key, 0, 0, withscores=True)
        earliest_timestamp = earliest[0][1] if earliest else current_time
        
        return {
            "blocked": False,
            "limit": config.requests,
            "remaining": max(0, config.requests - request_count),
            "reset_at": int(earliest_timestamp + config.window),
            "window": config.window,
            "current_usage": request_count
        }
    
    async def reset_rate_limit(
        self,
        identifier: str,
        strategy: RateLimitStrategy,
        endpoint: Optional[str] = None
    ):
        """Reset rate limit for an identifier (admin function)"""
        key = self._create_key(identifier, strategy, endpoint)
        block_key = f"rate_limit:blocked:{strategy}:{identifier}"
        violation_key = f"rate_limit:violations:{strategy}:{identifier}"
        
        # Delete all related keys
        await redis_client.delete(key, block_key, violation_key)
        
        logger.info(f"Reset rate limit for {strategy}:{identifier}")
    
    async def get_blocked_identifiers(self, strategy: Optional[RateLimitStrategy] = None) -> List[Dict[str, Any]]:
        """Get list of currently blocked identifiers"""
        pattern = f"rate_limit:blocked:{strategy.value if strategy else '*'}:*"
        blocked_keys = []
        
        # Scan for blocked keys
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            blocked_keys.extend(keys)
            if cursor == 0:
                break
        
        blocked_list = []
        for key in blocked_keys:
            parts = key.split(":")
            if len(parts) >= 4:
                blocked_until = await redis_client.get(key)
                if blocked_until:
                    blocked_list.append({
                        "strategy": parts[2],
                        "identifier": ":".join(parts[3:]),
                        "blocked_until": int(blocked_until),
                        "remaining_seconds": int(blocked_until) - int(time.time())
                    })
        
        return blocked_list


# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()