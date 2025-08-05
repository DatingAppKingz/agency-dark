"""
Rate limiting algorithms implementation.
"""
import time
import math
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from core.redis import redis_manager
from core.logger import get_logger

logger = get_logger(__name__)


class RateLimitAlgorithm(ABC):
    """Base class for rate limiting algorithms."""
    
    @abstractmethod
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed and update state.
        
        Returns:
            Tuple of (is_allowed, info_dict)
        """
        pass
    
    @abstractmethod
    async def get_state(self, key: str) -> Dict[str, Any]:
        """Get current state of the rate limiter."""
        pass


class TokenBucketAlgorithm(RateLimitAlgorithm):
    """
    Token bucket algorithm implementation.
    
    Allows burst traffic while maintaining average rate.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client or redis_manager
    
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0,
        burst_size: Optional[int] = None,
        refill_rate: Optional[float] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check and update token bucket.
        
        Args:
            key: Unique identifier for the bucket
            limit: Maximum requests in the window
            window_seconds: Time window in seconds
            cost: Cost of this request in tokens
            burst_size: Maximum bucket capacity (defaults to limit)
            refill_rate: Tokens added per second (defaults to limit/window)
        """
        if not self.redis:
            return True, {"algorithm": "token_bucket", "redis_available": False}
        
        # Calculate parameters
        burst_size = burst_size or limit
        refill_rate = refill_rate or (limit / window_seconds)
        
        # Redis keys
        tokens_key = f"tb:tokens:{key}"
        updated_key = f"tb:updated:{key}"
        
        # Get current state
        now = time.time()
        
        # Lua script for atomic token bucket update
        lua_script = """
        local tokens_key = KEYS[1]
        local updated_key = KEYS[2]
        local burst_size = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local cost = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        local ttl = tonumber(ARGV[5])
        
        -- Get current tokens and last update time
        local tokens = tonumber(redis.call('get', tokens_key) or burst_size)
        local last_updated = tonumber(redis.call('get', updated_key) or now)
        
        -- Calculate tokens to add based on time elapsed
        local elapsed = now - last_updated
        local tokens_to_add = elapsed * refill_rate
        tokens = math.min(burst_size, tokens + tokens_to_add)
        
        -- Check if we have enough tokens
        if tokens >= cost then
            -- Consume tokens
            tokens = tokens - cost
            redis.call('setex', tokens_key, ttl, tokens)
            redis.call('setex', updated_key, ttl, now)
            return {1, tokens, burst_size}
        else
            -- Not enough tokens
            redis.call('setex', tokens_key, ttl, tokens)
            redis.call('setex', updated_key, ttl, now)
            return {0, tokens, burst_size}
        end
        """
        
        try:
            # Execute script
            result = await self.redis.eval(
                lua_script,
                2,  # Number of keys
                tokens_key,
                updated_key,
                burst_size,
                refill_rate,
                cost,
                now,
                window_seconds * 2  # TTL
            )
            
            allowed = bool(result[0])
            tokens_remaining = float(result[1])
            
            # Calculate when bucket will be full again
            if not allowed:
                tokens_needed = cost - tokens_remaining
                seconds_until_available = tokens_needed / refill_rate
                retry_after = math.ceil(seconds_until_available)
            else:
                retry_after = 0
            
            return allowed, {
                "algorithm": "token_bucket",
                "allowed": allowed,
                "tokens_remaining": tokens_remaining,
                "burst_size": burst_size,
                "refill_rate": refill_rate,
                "cost": cost,
                "retry_after_seconds": retry_after
            }
            
        except Exception as e:
            logger.error(f"Token bucket error: {e}")
            # Fail open on errors
            return True, {"algorithm": "token_bucket", "error": str(e)}
    
    async def get_state(self, key: str) -> Dict[str, Any]:
        """Get current token bucket state."""
        if not self.redis:
            return {"error": "Redis not available"}
        
        tokens_key = f"tb:tokens:{key}"
        updated_key = f"tb:updated:{key}"
        
        try:
            tokens = await self.redis.get(tokens_key)
            last_updated = await self.redis.get(updated_key)
            
            return {
                "tokens": float(tokens) if tokens else None,
                "last_updated": float(last_updated) if last_updated else None
            }
        except Exception as e:
            return {"error": str(e)}


class SlidingWindowAlgorithm(RateLimitAlgorithm):
    """
    Sliding window log algorithm implementation.
    
    More accurate than fixed windows but uses more memory.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client or redis_manager
    
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check and update sliding window."""
        if not self.redis:
            return True, {"algorithm": "sliding_window", "redis_available": False}
        
        # Redis key for sorted set
        window_key = f"sw:{key}"
        
        # Current timestamp in milliseconds
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - (window_seconds * 1000)
        
        # Lua script for atomic sliding window update
        lua_script = """
        local window_key = KEYS[1]
        local now_ms = tonumber(ARGV[1])
        local window_start_ms = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])
        local ttl = tonumber(ARGV[5])
        
        -- Remove old entries outside the window
        redis.call('zremrangebyscore', window_key, 0, window_start_ms)
        
        -- Count current requests in window
        local current_count = redis.call('zcard', window_key)
        
        -- Check if adding this request would exceed limit
        if current_count + cost <= limit then
            -- Add request to window
            for i = 1, cost do
                redis.call('zadd', window_key, now_ms, now_ms .. ':' .. i)
            end
            redis.call('expire', window_key, ttl)
            return {1, current_count + cost, limit}
        else
            -- Request would exceed limit
            return {0, current_count, limit}
        end
        """
        
        try:
            result = await self.redis.eval(
                lua_script,
                1,  # Number of keys
                window_key,
                now_ms,
                window_start_ms,
                limit,
                int(cost),
                window_seconds * 2  # TTL
            )
            
            allowed = bool(result[0])
            current_count = int(result[1])
            
            # Calculate retry after
            if not allowed:
                # Get oldest request in window
                oldest = await self.redis.zrange(window_key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = int(oldest[0][1])
                    retry_after_ms = (oldest_timestamp + window_seconds * 1000) - now_ms
                    retry_after = max(1, math.ceil(retry_after_ms / 1000))
                else:
                    retry_after = 1
            else:
                retry_after = 0
            
            return allowed, {
                "algorithm": "sliding_window",
                "allowed": allowed,
                "current_count": current_count,
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after
            }
            
        except Exception as e:
            logger.error(f"Sliding window error: {e}")
            return True, {"algorithm": "sliding_window", "error": str(e)}
    
    async def get_state(self, key: str) -> Dict[str, Any]:
        """Get current sliding window state."""
        if not self.redis:
            return {"error": "Redis not available"}
        
        window_key = f"sw:{key}"
        
        try:
            count = await self.redis.zcard(window_key)
            
            # Get time range
            if count > 0:
                oldest = await self.redis.zrange(window_key, 0, 0, withscores=True)
                newest = await self.redis.zrange(window_key, -1, -1, withscores=True)
                
                return {
                    "count": count,
                    "oldest_timestamp": int(oldest[0][1]) if oldest else None,
                    "newest_timestamp": int(newest[0][1]) if newest else None
                }
            else:
                return {"count": 0}
                
        except Exception as e:
            return {"error": str(e)}


class FixedWindowAlgorithm(RateLimitAlgorithm):
    """
    Fixed window counter algorithm.
    
    Simple but can have burst issues at window boundaries.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client or redis_manager
    
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check and update fixed window counter."""
        if not self.redis:
            return True, {"algorithm": "fixed_window", "redis_available": False}
        
        # Calculate window key based on current time
        window_id = int(time.time() / window_seconds)
        window_key = f"fw:{key}:{window_id}"
        
        try:
            # Increment counter
            current_count = await self.redis.incr(window_key)
            
            # Set expiry on first request in window
            if current_count == 1:
                await self.redis.expire(window_key, window_seconds * 2)
            
            # Check limit
            allowed = current_count <= limit
            
            # Calculate retry after
            if not allowed:
                current_window_start = window_id * window_seconds
                next_window_start = (window_id + 1) * window_seconds
                retry_after = int(next_window_start - time.time())
            else:
                retry_after = 0
            
            return allowed, {
                "algorithm": "fixed_window",
                "allowed": allowed,
                "current_count": current_count,
                "limit": limit,
                "window_seconds": window_seconds,
                "window_id": window_id,
                "retry_after_seconds": retry_after
            }
            
        except Exception as e:
            logger.error(f"Fixed window error: {e}")
            return True, {"algorithm": "fixed_window", "error": str(e)}
    
    async def get_state(self, key: str) -> Dict[str, Any]:
        """Get current fixed window state."""
        if not self.redis:
            return {"error": "Redis not available"}
        
        # Get current window
        window_id = int(time.time() / 60)  # Assume 60-second windows
        window_key = f"fw:{key}:{window_id}"
        
        try:
            count = await self.redis.get(window_key)
            ttl = await self.redis.ttl(window_key)
            
            return {
                "window_id": window_id,
                "count": int(count) if count else 0,
                "ttl": ttl
            }
        except Exception as e:
            return {"error": str(e)}


class AdaptiveRateLimiter(RateLimitAlgorithm):
    """
    Adaptive rate limiter that adjusts based on system load and user behavior.
    """
    
    def __init__(self, redis_client=None, base_algorithm=None):
        self.redis = redis_client or redis_manager
        self.base_algorithm = base_algorithm or TokenBucketAlgorithm(redis_client)
    
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0,
        user_reputation: float = 1.0,
        system_load: float = 0.5
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Adaptive rate limiting based on reputation and system load.
        
        Args:
            user_reputation: 0.0 (bad) to 2.0 (excellent)
            system_load: 0.0 (idle) to 1.0 (overloaded)
        """
        # Adjust limit based on reputation
        adjusted_limit = int(limit * user_reputation)
        
        # Further adjust based on system load
        if system_load > 0.8:
            # High load: reduce limits
            adjusted_limit = int(adjusted_limit * 0.5)
        elif system_load > 0.6:
            # Medium load: slightly reduce
            adjusted_limit = int(adjusted_limit * 0.8)
        
        # Ensure minimum limit
        adjusted_limit = max(1, adjusted_limit)
        
        # Use base algorithm with adjusted limits
        allowed, info = await self.base_algorithm.check_and_update(
            key, adjusted_limit, window_seconds, cost
        )
        
        # Add adaptive info
        info.update({
            "algorithm": "adaptive",
            "base_limit": limit,
            "adjusted_limit": adjusted_limit,
            "user_reputation": user_reputation,
            "system_load": system_load
        })
        
        return allowed, info
    
    async def get_state(self, key: str) -> Dict[str, Any]:
        """Get adaptive rate limiter state."""
        base_state = await self.base_algorithm.get_state(key)
        return {
            "algorithm": "adaptive",
            "base_state": base_state
        }


class GeographicRateLimiter:
    """
    Geographic-based rate limiting with country-specific rules.
    """
    
    def __init__(self, base_algorithm=None):
        self.base_algorithm = base_algorithm or TokenBucketAlgorithm()
        
        # Default geographic multipliers
        self.default_multipliers = {
            "US": 1.0,
            "CA": 1.0,
            "GB": 1.0,
            "DE": 1.0,
            "FR": 1.0,
            "JP": 1.0,
            "AU": 1.0,
            # Reduced limits for high-risk countries
            "CN": 0.5,
            "RU": 0.5,
            "IN": 0.7,
            "BR": 0.8,
            # Blocked countries
            "KP": 0.0,  # North Korea
            "IR": 0.0,  # Iran (sanctions)
        }
    
    async def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: float = 1.0,
        country_code: Optional[str] = None,
        custom_multipliers: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Apply geographic rate limiting."""
        # Get multiplier for country
        multipliers = custom_multipliers or self.default_multipliers
        multiplier = multipliers.get(country_code, 0.9)  # Default slightly reduced
        
        # Block if multiplier is 0
        if multiplier == 0:
            return False, {
                "algorithm": "geographic",
                "allowed": False,
                "country_code": country_code,
                "blocked": True,
                "reason": "Country blocked"
            }
        
        # Adjust limit based on geography
        adjusted_limit = int(limit * multiplier)
        adjusted_limit = max(1, adjusted_limit)
        
        # Apply base algorithm
        allowed, info = await self.base_algorithm.check_and_update(
            f"{key}:{country_code}", adjusted_limit, window_seconds, cost
        )
        
        # Add geographic info
        info.update({
            "algorithm": "geographic",
            "country_code": country_code,
            "multiplier": multiplier,
            "base_limit": limit,
            "adjusted_limit": adjusted_limit
        })
        
        return allowed, info