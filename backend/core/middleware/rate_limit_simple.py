"""
Simple rate limiting decorator for testing.
"""
from functools import wraps
from typing import Callable
import time

# Simple rate limiter decorator that does nothing for now
def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 3600, requests_per_day: int = 86400, burst_size: int = 10):
    """
    Simple rate limit decorator (placeholder for testing).
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # For now, just pass through
            return await func(*args, **kwargs)
        return wrapper
    return decorator