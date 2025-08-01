"""Redis connection and caching utilities."""

import json
from typing import Optional, Any, Union
from datetime import timedelta
import redis.asyncio as redis
from redis.asyncio import Redis
from functools import wraps
import hashlib
import pickle

from core.config import settings


class RedisManager:
    """Manages Redis connections and operations."""
    
    def __init__(self):
        self.client: Optional[Redis] = None
        self.pool = None
    
    async def connect(self) -> Redis:
        """Create Redis connection pool and return client."""
        if not self.client:
            # Use REDIS_URL if provided, otherwise fall back to individual settings
            if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                self.client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    max_connections=50
                )
            else:
                # Fall back to individual settings
                pool_kwargs = {
                    "host": settings.REDIS_HOST,
                    "port": settings.REDIS_PORT,
                    "db": settings.REDIS_DB,
                    "decode_responses": False,  # We'll handle encoding/decoding ourselves
                    "max_connections": 50,
                }
                
                if hasattr(settings, 'REDIS_PASSWORD') and settings.REDIS_PASSWORD:
                    pool_kwargs["password"] = settings.REDIS_PASSWORD
                    
                self.pool = redis.ConnectionPool(**pool_kwargs)
                self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            
        return self.client
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            if self.pool:
                await self.pool.disconnect()
            self.client = None
            self.pool = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self.client:
            await self.connect()
        
        value = await self.client.get(key)
        if value:
            try:
                # Try to unpickle first (for complex objects)
                return pickle.loads(value)
            except:
                try:
                    # Try JSON decode
                    return json.loads(value)
                except:
                    # Return as string
                    return value.decode('utf-8') if isinstance(value, bytes) else value
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in Redis with optional expiration."""
        if not self.client:
            await self.connect()
        
        # Serialize value
        if isinstance(value, (str, int, float)):
            serialized = str(value).encode('utf-8')
        else:
            try:
                # Try JSON serialization first
                serialized = json.dumps(value).encode('utf-8')
            except:
                # Fall back to pickle for complex objects
                serialized = pickle.dumps(value)
        
        # Convert timedelta to seconds
        if isinstance(expire, timedelta):
            expire = int(expire.total_seconds())
        
        return await self.client.set(key, serialized, ex=expire)
    
    async def delete(self, key: str) -> int:
        """Delete key from Redis."""
        if not self.client:
            await self.connect()
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.client:
            await self.connect()
        return bool(await self.client.exists(key))
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        if not self.client:
            await self.connect()
        return await self.client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key."""
        if not self.client:
            await self.connect()
        return await self.client.ttl(key)
    
    async def flush_pattern(self, pattern: str):
        """Delete all keys matching a pattern."""
        if not self.client:
            await self.connect()
        
        cursor = 0
        while True:
            cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
            if keys:
                await self.client.delete(*keys)
            if cursor == 0:
                break


# Global Redis manager instance
redis_manager = RedisManager()


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_data = {
        'args': args,
        'kwargs': kwargs
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(
    expire: Union[int, timedelta] = 300,
    prefix: str = "cache",
    key_func: Optional[callable] = None
):
    """
    Decorator for caching function results in Redis.
    
    Args:
        expire: Expiration time in seconds or timedelta
        prefix: Cache key prefix
        key_func: Custom function to generate cache key
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = f"{prefix}:{key_func(*args, **kwargs)}"
            else:
                # Skip 'self' for instance methods
                cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
                key = f"{prefix}:{func.__name__}:{cache_key(*cache_args, **kwargs)}"
            
            # Try to get from cache
            cached_value = await redis_manager.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await redis_manager.set(key, result, expire=expire)
            
            return result
        
        return wrapper
    return decorator


class SessionManager:
    """Manages user sessions in Redis."""
    
    def __init__(self, prefix: str = "session", expire: int = 86400):
        self.prefix = prefix
        self.expire = expire  # Default 24 hours
    
    def _get_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.prefix}:{session_id}"
    
    async def create(self, session_id: str, data: dict) -> bool:
        """Create a new session."""
        key = self._get_key(session_id)
        return await redis_manager.set(key, data, expire=self.expire)
    
    async def get(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        key = self._get_key(session_id)
        return await redis_manager.get(key)
    
    async def update(self, session_id: str, data: dict) -> bool:
        """Update session data."""
        key = self._get_key(session_id)
        current = await self.get(session_id)
        if current:
            current.update(data)
            return await redis_manager.set(key, current, expire=self.expire)
        return False
    
    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        key = self._get_key(session_id)
        return bool(await redis_manager.delete(key))
    
    async def extend(self, session_id: str, seconds: Optional[int] = None) -> bool:
        """Extend session expiration."""
        key = self._get_key(session_id)
        expire_time = seconds or self.expire
        return await redis_manager.expire(key, expire_time)
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        key = self._get_key(session_id)
        return await redis_manager.exists(key)


# Global session manager
session_manager = SessionManager()


class RateLimiter:
    """Rate limiting using Redis."""
    
    @staticmethod
    async def check_rate_limit(
        key: str,
        max_requests: int,
        window: int = 60  # seconds
    ) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded.
        
        Returns:
            tuple: (is_allowed, remaining_requests)
        """
        full_key = f"rate_limit:{key}"
        
        client = await redis_manager.connect()
        
        # Use Redis pipeline for atomic operations
        pipe = client.pipeline()
        pipe.incr(full_key)
        pipe.expire(full_key, window)
        results = await pipe.execute()
        
        current_requests = results[0]
        
        if current_requests > max_requests:
            return False, 0
        
        return True, max_requests - current_requests
    
    @staticmethod
    async def reset_limit(key: str):
        """Reset rate limit for a key."""
        full_key = f"rate_limit:{key}"
        await redis_manager.delete(full_key)


# Cache invalidation helpers
async def invalidate_cache(pattern: str):
    """Invalidate cache entries matching pattern."""
    await redis_manager.flush_pattern(f"cache:{pattern}*")


async def invalidate_user_cache(user_id: int):
    """Invalidate all cache entries for a user."""
    await invalidate_cache(f"*user_{user_id}*")


async def invalidate_model_cache(model_id: int):
    """Invalidate all cache entries for a model."""
    await invalidate_cache(f"*model_{model_id}*")


async def invalidate_agency_cache(agency_id: int):
    """Invalidate all cache entries for an agency."""
    await invalidate_cache(f"*agency_{agency_id}*")


# Create redis_client alias for backward compatibility
redis_client = redis_manager  # Alias for backward compatibility