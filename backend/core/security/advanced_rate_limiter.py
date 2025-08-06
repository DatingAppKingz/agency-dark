"""
Advanced Rate Limiting System

Provides sophisticated rate limiting including:
- Multiple rate limit strategies (sliding window, token bucket, leaky bucket)
- User-based and IP-based limiting
- Endpoint-specific limits
- Distributed rate limiting with Redis
- Adaptive rate limiting based on system load
- Whitelist/blacklist support
- Rate limit headers in responses
"""
import time
import asyncio
from typing import Dict, Optional, List, Tuple, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
from ipaddress import ip_address, ip_network
import hashlib

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from core.logger import get_logger
from core.redis import redis_client

logger = get_logger(__name__)


class RateLimitExceeded(HTTPException):
    """Rate limit exceeded exception."""
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            status_code=429,
            detail=detail,
            headers=headers
        )


class RateLimitStrategy:
    """Base class for rate limit strategies."""
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed."""
        raise NotImplementedError
    
    async def reset(self, key: str):
        """Reset rate limit for key."""
        raise NotImplementedError


class SlidingWindowStrategy(RateLimitStrategy):
    """Sliding window rate limiting using Redis sorted sets."""
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed using sliding window."""
        current_time = time.time()
        window_start = current_time - window
        
        # Use Redis pipeline for atomic operations
        pipe = redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current entries
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiry
        pipe.expire(key, window + 1)
        
        results = await pipe.execute()
        current_count = results[1]
        
        # Check if limit exceeded
        allowed = current_count < limit
        
        # Calculate remaining and reset time
        if allowed:
            remaining = limit - current_count - 1
        else:
            remaining = 0
            # Remove the request we just added
            await redis_client.zrem(key, str(current_time))
        
        # Get oldest entry for reset calculation
        oldest = await redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            reset_at = int(oldest[0][1] + window)
        else:
            reset_at = int(current_time + window)
        
        return allowed, {
            "limit": limit,
            "remaining": max(0, remaining),
            "reset": reset_at,
            "retry_after": reset_at - int(current_time) if not allowed else None
        }
    
    async def reset(self, key: str):
        """Reset rate limit by deleting the key."""
        await redis_client.delete(key)


class TokenBucketStrategy(RateLimitStrategy):
    """Token bucket rate limiting."""
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed using token bucket."""
        current_time = time.time()
        refill_rate = limit / window  # tokens per second
        
        # Get current bucket state
        bucket_key = f"{key}:bucket"
        last_refill_key = f"{key}:last_refill"
        
        # Get current tokens and last refill time
        pipe = redis_client.pipeline()
        pipe.get(bucket_key)
        pipe.get(last_refill_key)
        results = await pipe.execute()
        
        tokens = float(results[0] or limit)
        last_refill = float(results[1] or current_time)
        
        # Calculate tokens to add
        time_passed = current_time - last_refill
        tokens_to_add = time_passed * refill_rate
        tokens = min(limit, tokens + tokens_to_add)
        
        # Check if we have tokens
        allowed = tokens >= 1
        
        if allowed:
            tokens -= 1
            remaining = int(tokens)
        else:
            remaining = 0
        
        # Update bucket state
        pipe = redis_client.pipeline()
        pipe.set(bucket_key, tokens)
        pipe.set(last_refill_key, current_time)
        pipe.expire(bucket_key, window + 60)
        pipe.expire(last_refill_key, window + 60)
        await pipe.execute()
        
        # Calculate when bucket will have tokens again
        if not allowed:
            retry_after = int((1 - tokens) / refill_rate)
        else:
            retry_after = None
        
        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset": int(current_time + window),
            "retry_after": retry_after
        }
    
    async def reset(self, key: str):
        """Reset token bucket."""
        bucket_key = f"{key}:bucket"
        last_refill_key = f"{key}:last_refill"
        
        pipe = redis_client.pipeline()
        pipe.delete(bucket_key)
        pipe.delete(last_refill_key)
        await pipe.execute()


class LeakyBucketStrategy(RateLimitStrategy):
    """Leaky bucket rate limiting."""
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed using leaky bucket."""
        current_time = time.time()
        leak_rate = limit / window  # requests per second
        
        # Get queue of requests
        queue_key = f"{key}:queue"
        
        # Remove leaked requests
        leak_until = current_time - (1 / leak_rate)
        await redis_client.zremrangebyscore(queue_key, 0, leak_until)
        
        # Get current queue size
        queue_size = await redis_client.zcard(queue_key)
        
        # Check if we can add request
        allowed = queue_size < limit
        
        if allowed:
            # Add request to queue
            await redis_client.zadd(queue_key, {str(current_time): current_time})
            await redis_client.expire(queue_key, window + 60)
            remaining = limit - queue_size - 1
        else:
            remaining = 0
        
        # Calculate retry after
        if not allowed:
            oldest = await redis_client.zrange(queue_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int((oldest[0][1] + (1 / leak_rate)) - current_time)
            else:
                retry_after = 1
        else:
            retry_after = None
        
        return allowed, {
            "limit": limit,
            "remaining": max(0, remaining),
            "reset": int(current_time + window),
            "retry_after": retry_after
        }
    
    async def reset(self, key: str):
        """Reset leaky bucket."""
        queue_key = f"{key}:queue"
        await redis_client.delete(queue_key)


class AdvancedRateLimiter:
    """Advanced rate limiting system with multiple strategies."""
    
    def __init__(self):
        self.strategies = {
            "sliding_window": SlidingWindowStrategy(),
            "token_bucket": TokenBucketStrategy(),
            "leaky_bucket": LeakyBucketStrategy()
        }
        
        # Default limits
        self.default_limits = {
            "global": (1000, 3600),  # 1000 requests per hour
            "auth": (5, 300),        # 5 auth attempts per 5 minutes
            "api": (100, 60),        # 100 API calls per minute
            "upload": (10, 3600),    # 10 uploads per hour
        }
        
        # Whitelist/blacklist
        self.whitelist_ips: Set[str] = set()
        self.blacklist_ips: Set[str] = set()
        self.whitelist_networks: List[ip_network] = []
        
        # Adaptive rate limiting
        self.adaptive_enabled = True
        self.load_factor = 1.0  # Multiplier based on system load
    
    def create_limiter(
        self,
        limit: int,
        window: int,
        strategy: str = "sliding_window",
        key_func: Optional[Callable] = None,
        cost: int = 1,
        burst: Optional[int] = None,
        scope: str = "global"
    ):
        """
        Create a rate limiter decorator.
        
        Args:
            limit: Number of requests allowed
            window: Time window in seconds
            strategy: Rate limiting strategy to use
            key_func: Custom function to generate rate limit key
            cost: Cost of this request (for weighted rate limiting)
            burst: Allow burst up to this limit
            scope: Scope for the rate limit
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Check if IP is blacklisted
                client_ip = self._get_client_ip(request)
                if self._is_blacklisted(client_ip):
                    raise RateLimitExceeded("Access denied")
                
                # Skip rate limiting for whitelisted IPs
                if self._is_whitelisted(client_ip):
                    return await func(request, *args, **kwargs)
                
                # Generate rate limit key
                if key_func:
                    key_suffix = key_func(request)
                else:
                    key_suffix = self._get_default_key(request)
                
                key = f"ratelimit:{scope}:{key_suffix}"
                
                # Apply adaptive rate limiting
                effective_limit = limit
                if self.adaptive_enabled:
                    effective_limit = int(limit * self.load_factor)
                
                # Check rate limit
                strategy_impl = self.strategies.get(strategy, self.strategies["sliding_window"])
                
                # Handle burst
                if burst:
                    burst_key = f"{key}:burst"
                    burst_allowed, _ = await strategy_impl.is_allowed(
                        burst_key, burst, 60  # 1 minute burst window
                    )
                    if burst_allowed:
                        effective_limit = burst
                
                # Check main rate limit
                allowed, info = await strategy_impl.is_allowed(
                    key, effective_limit * cost, window
                )
                
                # Add rate limit headers to response
                response = None
                if hasattr(func, "__self__") and hasattr(func.__self__, "response"):
                    response = func.__self__.response
                
                if not allowed:
                    # Log rate limit exceeded
                    logger.warning(
                        f"Rate limit exceeded for {key_suffix} "
                        f"(scope: {scope}, ip: {client_ip})"
                    )
                    
                    # Create response with headers
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limit_exceeded",
                            "message": f"Rate limit exceeded. Retry after {info['retry_after']} seconds"
                        },
                        headers=self._create_rate_limit_headers(info)
                    )
                    return response
                
                # Execute function
                result = await func(request, *args, **kwargs)
                
                # Add rate limit headers to successful response
                if isinstance(result, Response):
                    for header, value in self._create_rate_limit_headers(info).items():
                        result.headers[header] = value
                
                return result
            
            return wrapper
        return decorator
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        strategy: str = "sliding_window"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit without decorating."""
        strategy_impl = self.strategies.get(strategy, self.strategies["sliding_window"])
        return await strategy_impl.is_allowed(key, limit, window)
    
    async def reset_rate_limit(self, key: str, strategy: str = "sliding_window"):
        """Reset rate limit for a key."""
        strategy_impl = self.strategies.get(strategy, self.strategies["sliding_window"])
        await strategy_impl.reset(key)
    
    async def get_usage_stats(self, pattern: str = "*") -> Dict[str, Any]:
        """Get rate limit usage statistics."""
        stats = {
            "total_keys": 0,
            "by_scope": {},
            "top_users": []
        }
        
        # Scan for rate limit keys
        cursor = 0
        keys = []
        while True:
            cursor, batch = await redis_client.scan(
                cursor, match=f"ratelimit:{pattern}", count=100
            )
            keys.extend(batch)
            if cursor == 0:
                break
        
        stats["total_keys"] = len(keys)
        
        # Group by scope
        scope_counts = {}
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 2:
                scope = parts[1]
                scope_counts[scope] = scope_counts.get(scope, 0) + 1
        
        stats["by_scope"] = scope_counts
        
        return stats
    
    def add_whitelist(self, ip: str):
        """Add IP to whitelist."""
        try:
            # Check if it's a network
            network = ip_network(ip)
            self.whitelist_networks.append(network)
            logger.info(f"Added network {network} to whitelist")
        except ValueError:
            # Single IP
            self.whitelist_ips.add(ip)
            logger.info(f"Added IP {ip} to whitelist")
    
    def add_blacklist(self, ip: str):
        """Add IP to blacklist."""
        self.blacklist_ips.add(ip)
        logger.info(f"Added IP {ip} to blacklist")
    
    def remove_whitelist(self, ip: str):
        """Remove IP from whitelist."""
        self.whitelist_ips.discard(ip)
        # Also remove from networks if applicable
        self.whitelist_networks = [
            n for n in self.whitelist_networks
            if str(n) != ip
        ]
    
    def remove_blacklist(self, ip: str):
        """Remove IP from blacklist."""
        self.blacklist_ips.discard(ip)
    
    async def update_load_factor(self, cpu_percent: float, memory_percent: float):
        """Update load factor for adaptive rate limiting."""
        if not self.adaptive_enabled:
            return
        
        # Calculate load factor based on system resources
        # Higher load = lower rate limits
        if cpu_percent > 80 or memory_percent > 80:
            self.load_factor = 0.5  # Half rate limits
        elif cpu_percent > 60 or memory_percent > 60:
            self.load_factor = 0.75  # 3/4 rate limits
        else:
            self.load_factor = 1.0  # Full rate limits
        
        logger.info(f"Updated rate limit load factor to {self.load_factor}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        # Check for forwarded IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first IP in chain
            return forwarded.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_default_key(self, request: Request) -> str:
        """Generate default rate limit key."""
        # Use combination of IP and user ID (if authenticated)
        client_ip = self._get_client_ip(request)
        
        # Check if user is authenticated
        user_id = getattr(request.state, "user_id", None)
        
        if user_id:
            return f"user:{user_id}"
        else:
            return f"ip:{client_ip}"
    
    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted."""
        if ip in self.whitelist_ips:
            return True
        
        try:
            ip_obj = ip_address(ip)
            for network in self.whitelist_networks:
                if ip_obj in network:
                    return True
        except ValueError:
            pass
        
        return False
    
    def _is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted."""
        return ip in self.blacklist_ips
    
    def _create_rate_limit_headers(self, info: Dict[str, Any]) -> Dict[str, str]:
        """Create rate limit headers for response."""
        headers = {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"])
        }
        
        if info.get("retry_after"):
            headers["Retry-After"] = str(info["retry_after"])
        
        return headers


# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()


# Convenience decorators
def rate_limit(
    requests: int = 100,
    window: int = 60,
    strategy: str = "sliding_window",
    scope: str = "api"
):
    """Simple rate limit decorator."""
    return rate_limiter.create_limiter(
        limit=requests,
        window=window,
        strategy=strategy,
        scope=scope
    )


def auth_rate_limit(attempts: int = 5, window: int = 300):
    """Rate limit for authentication endpoints."""
    return rate_limiter.create_limiter(
        limit=attempts,
        window=window,
        strategy="sliding_window",
        scope="auth"
    )


def upload_rate_limit(uploads: int = 10, window: int = 3600):
    """Rate limit for file uploads."""
    return rate_limiter.create_limiter(
        limit=uploads,
        window=window,
        strategy="token_bucket",
        scope="upload",
        cost=1
    )