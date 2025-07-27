"""
Rate limiting for external API calls
"""
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta
import time


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: int, period: int = 60):
        """
        Initialize rate limiter
        
        Args:
            rate: Number of requests allowed
            period: Time period in seconds (default: 60)
        """
        self.rate = rate
        self.period = period
        self.tokens = float(rate)
        self.max_tokens = float(rate)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()
        
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary
        
        Returns:
            Wait time before the request was allowed
        """
        async with self.lock:
            wait_time = await self._acquire_tokens(tokens)
            
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            
        return wait_time
        
    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting
        
        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self.lock:
            wait_time = await self._acquire_tokens(tokens, wait=False)
            return wait_time == 0
            
    async def _acquire_tokens(self, tokens: int, wait: bool = True) -> float:
        """Internal method to acquire tokens"""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now
        
        # Refill tokens based on elapsed time
        refill = elapsed * (self.max_tokens / self.period)
        self.tokens = min(self.max_tokens, self.tokens + refill)
        
        if self.tokens >= tokens:
            # We have enough tokens
            self.tokens -= tokens
            return 0
        elif wait:
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed * (self.period / self.max_tokens)
            self.tokens = 0
            return wait_time
        else:
            # Don't wait
            return -1
            
    def reset(self):
        """Reset the rate limiter"""
        self.tokens = self.max_tokens
        self.last_update = time.monotonic()


class MultiRateLimiter:
    """Rate limiter with multiple limits (e.g., per minute, per hour)"""
    
    def __init__(self, limits: Dict[int, int]):
        """
        Initialize multi-rate limiter
        
        Args:
            limits: Dict of {period_seconds: max_requests}
                   e.g., {60: 100, 3600: 1000} for 100/min and 1000/hour
        """
        self.limiters = {
            period: RateLimiter(rate, period)
            for period, rate in limits.items()
        }
        
    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens from all limiters"""
        max_wait = 0.0
        
        # Check all limiters
        for limiter in self.limiters.values():
            async with limiter.lock:
                wait_time = await limiter._acquire_tokens(tokens, wait=False)
                if wait_time > 0:
                    max_wait = max(max_wait, wait_time)
                elif wait_time < 0:
                    # This limiter doesn't have tokens, calculate wait
                    tokens_needed = tokens - limiter.tokens
                    wait = tokens_needed * (limiter.period / limiter.max_tokens)
                    max_wait = max(max_wait, wait)
                    
        # If we need to wait, restore tokens and wait
        if max_wait > 0:
            await asyncio.sleep(max_wait)
            
        # Now acquire from all limiters
        for limiter in self.limiters.values():
            await limiter.acquire(tokens)
            
        return max_wait
        
    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting"""
        # Check if all limiters have tokens
        for limiter in self.limiters.values():
            if not await limiter.try_acquire(tokens):
                return False
        return True
        
    def reset(self):
        """Reset all rate limiters"""
        for limiter in self.limiters.values():
            limiter.reset()


class APIRateLimitManager:
    """Manage rate limits for multiple APIs"""
    
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        
    def add_limiter(self, api_name: str, rate: int, period: int = 60):
        """Add rate limiter for an API"""
        self.limiters[api_name] = RateLimiter(rate, period)
        
    def add_multi_limiter(self, api_name: str, limits: Dict[int, int]):
        """Add multi-rate limiter for an API"""
        self.limiters[api_name] = MultiRateLimiter(limits)
        
    async def acquire(self, api_name: str, tokens: int = 1) -> float:
        """Acquire tokens for an API"""
        limiter = self.limiters.get(api_name)
        if limiter:
            return await limiter.acquire(tokens)
        return 0  # No limiter, no wait
        
    async def try_acquire(self, api_name: str, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting"""
        limiter = self.limiters.get(api_name)
        if limiter:
            return await limiter.try_acquire(tokens)
        return True  # No limiter, always allow
        
    def reset(self, api_name: Optional[str] = None):
        """Reset rate limiter(s)"""
        if api_name:
            limiter = self.limiters.get(api_name)
            if limiter:
                limiter.reset()
        else:
            # Reset all
            for limiter in self.limiters.values():
                limiter.reset()