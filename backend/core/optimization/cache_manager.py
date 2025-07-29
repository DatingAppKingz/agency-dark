"""
Caching strategy implementation for API and database queries.
"""

from typing import Any, Callable, Dict, List, Optional, Union
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Manage caching strategies across the application."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client
        self.local_cache: Dict[str, Any] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "evictions": 0
        }
        
        # Cache configuration
        self.default_ttl = 3600  # 1 hour
        self.max_local_cache_size = 1000
        self.compression_threshold = 1024  # Compress values larger than 1KB
    
    @classmethod
    async def create(cls, redis_url: str = None) -> "CacheManager":
        """Create cache manager with Redis connection."""
        redis_url = redis_url or settings.REDIS_URL
        redis_client = await redis.from_url(redis_url, decode_responses=False)
        return cls(redis_client)
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
    
    def cache_key_generator(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments."""
        # Create a unique key from arguments
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        
        # Hash the data for a consistent key
        key_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        # Try local cache first
        if key in self.local_cache:
            self.cache_stats["hits"] += 1
            return self.local_cache[key]["value"]
        
        # Try Redis
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    self.cache_stats["hits"] += 1
                    # Deserialize
                    deserialized_value = pickle.loads(value)
                    # Update local cache
                    self._update_local_cache(key, deserialized_value)
                    return deserialized_value
            except RedisError as e:
                logger.error(f"Redis get error: {e}")
                self.cache_stats["errors"] += 1
        
        self.cache_stats["misses"] += 1
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        
        # Serialize value
        serialized_value = pickle.dumps(value)
        
        # Store in Redis
        if self.redis:
            try:
                await self.redis.setex(key, ttl, serialized_value)
                
                # Store tags for invalidation
                if tags:
                    for tag in tags:
                        await self.redis.sadd(f"tag:{tag}", key)
                        await self.redis.expire(f"tag:{tag}", ttl)
                
            except RedisError as e:
                logger.error(f"Redis set error: {e}")
                self.cache_stats["errors"] += 1
                return False
        
        # Update local cache
        self._update_local_cache(key, value, ttl)
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        # Remove from local cache
        if key in self.local_cache:
            del self.local_cache[key]
        
        # Remove from Redis
        if self.redis:
            try:
                await self.redis.delete(key)
                return True
            except RedisError as e:
                logger.error(f"Redis delete error: {e}")
                self.cache_stats["errors"] += 1
        
        return False
    
    async def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag."""
        count = 0
        
        if self.redis:
            try:
                # Get all keys with this tag
                keys = await self.redis.smembers(f"tag:{tag}")
                
                if keys:
                    # Delete all keys
                    count = await self.redis.delete(*keys)
                    
                    # Remove from local cache
                    for key in keys:
                        if key.decode() in self.local_cache:
                            del self.local_cache[key.decode()]
                
                # Delete the tag set
                await self.redis.delete(f"tag:{tag}")
                
            except RedisError as e:
                logger.error(f"Redis invalidate tag error: {e}")
                self.cache_stats["errors"] += 1
        
        return count
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        # Clear local cache
        self.local_cache.clear()
        
        # Clear Redis
        if self.redis:
            try:
                await self.redis.flushdb()
                return True
            except RedisError as e:
                logger.error(f"Redis clear error: {e}")
                self.cache_stats["errors"] += 1
        
        return False
    
    def _update_local_cache(self, key: str, value: Any, ttl: int = None):
        """Update local cache with LRU eviction."""
        # Evict oldest entries if cache is full
        if len(self.local_cache) >= self.max_local_cache_size:
            # Find oldest entry
            oldest_key = min(
                self.local_cache.keys(),
                key=lambda k: self.local_cache[k]["timestamp"]
            )
            del self.local_cache[oldest_key]
            self.cache_stats["evictions"] += 1
        
        # Add new entry
        self.local_cache[key] = {
            "value": value,
            "timestamp": datetime.utcnow(),
            "ttl": ttl or self.default_ttl
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (
            self.cache_stats["hits"] / total_requests * 100
            if total_requests > 0
            else 0
        )
        
        return {
            **self.cache_stats,
            "hit_rate": f"{hit_rate:.2f}%",
            "local_cache_size": len(self.local_cache),
            "total_requests": total_requests
        }


def cache_key_generator(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from prefix and arguments."""
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items())
    }
    
    key_hash = hashlib.md5(
        json.dumps(key_data, sort_keys=True, default=str).encode()
    ).hexdigest()
    
    return f"{prefix}:{key_hash}"


def cached(
    ttl: int = 3600,
    key_prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
    condition: Optional[Callable] = None
):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if caching should be applied
            if condition and not condition(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache_key_generator(prefix, *args, **kwargs)
            
            # Get cache manager from app context
            cache_manager = kwargs.get('_cache_manager')
            if not cache_manager:
                return await func(*args, **kwargs)
            
            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(cache_key, result, ttl, tags)
            
            return result
        
        return wrapper
    return decorator


class CacheWarmer:
    """Warm up cache with frequently accessed data."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.warming_tasks = []
    
    async def warm_cache(self, warmup_functions: List[Callable]):
        """Execute cache warming functions."""
        tasks = []
        
        for func in warmup_functions:
            task = asyncio.create_task(func(self.cache_manager))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Cache warming failed for {warmup_functions[i].__name__}: {result}")
            else:
                logger.info(f"Cache warming completed for {warmup_functions[i].__name__}")
        
        return results


# Cache warming functions
async def warm_user_cache(cache_manager: CacheManager):
    """Warm cache with active user data."""
    from app.models import User
    from app.core.database import get_db
    
    async with get_db() as db:
        # Cache active users
        active_users = await db.execute(
            select(User).where(User.is_active == True).limit(100)
        )
        
        for user in active_users.scalars():
            key = f"user:{user.id}"
            await cache_manager.set(key, user.dict(), ttl=7200, tags=["users"])


async def warm_config_cache(cache_manager: CacheManager):
    """Warm cache with configuration data."""
    # Cache application settings
    key = "config:app_settings"
    await cache_manager.set(
        key,
        settings.dict(),
        ttl=86400,  # 24 hours
        tags=["config"]
    )


# Response compression middleware
class CompressionMiddleware:
    """Compress API responses for better performance."""
    
    def __init__(self, app, minimum_size: int = 1024):
        self.app = app
        self.minimum_size = minimum_size
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check if client accepts compression
        headers = dict(scope["headers"])
        accept_encoding = headers.get(b"accept-encoding", b"").decode()
        
        if "gzip" not in accept_encoding:
            await self.app(scope, receive, send)
            return
        
        # Wrap send to compress response
        async def send_compressed(message):
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                
                # Compress if body is large enough
                if len(body) >= self.minimum_size:
                    import gzip
                    compressed_body = gzip.compress(body)
                    
                    # Update headers
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        headers.append((b"content-encoding", b"gzip"))
                        headers.append((b"vary", b"Accept-Encoding"))
                        message["headers"] = headers
                    
                    message["body"] = compressed_body
            
            await send(message)
        
        await self.app(scope, receive, send_compressed)