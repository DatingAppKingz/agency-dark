"""
Simplified caching strategies for common use cases
"""
import json
import hashlib
from typing import Any, Optional, Callable, Union, List, Set
from functools import wraps
from datetime import timedelta
import asyncio
from redis import asyncio as aioredis

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class CacheStrategy:
    """Base cache strategy with common functionality"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        
        key_str = ":".join(key_parts)
        if len(key_str) > 200:  # Redis key length limit
            # Hash long keys
            hash_val = hashlib.md5(key_str.encode()).hexdigest()
            return f"{prefix}:hash:{hash_val}"
        return key_str
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "total_requests": total
        }


class SimpleCache(CacheStrategy):
    """Simple key-value caching"""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.redis.get(key)
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        try:
            self._stats["sets"] += 1
            return await self.redis.setex(
                key, 
                ttl, 
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            self._stats["deletes"] += 1
            return await self.redis.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                self._stats["deletes"] += len(keys)
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0


class QueryCache(CacheStrategy):
    """Database query result caching"""
    
    def __init__(self, redis_client: aioredis.Redis, default_ttl: int = 300):
        super().__init__(redis_client)
        self.default_ttl = default_ttl
    
    async def get_or_set(
        self, 
        key: str, 
        fetch_func: Callable, 
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or fetch and cache"""
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # Fetch from source
        value = await fetch_func()
        
        # Cache the result
        await self.set(key, value, ttl or self.default_ttl)
        
        return value
    
    async def get(self, key: str) -> Optional[Any]:
        """Get query result from cache"""
        try:
            value = await self.redis.get(f"query:{key}")
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"Query cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Cache query result"""
        try:
            self._stats["sets"] += 1
            return await self.redis.setex(
                f"query:{key}",
                ttl or self.default_ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Query cache set error: {e}")
            return False
    
    async def invalidate_by_table(self, table_name: str):
        """Invalidate all queries for a table"""
        pattern = f"query:*{table_name}*"
        return await self.delete_pattern(pattern)
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                self._stats["deletes"] += len(keys)
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Query cache delete pattern error: {e}")
            return 0


class UserCache(CacheStrategy):
    """User-specific data caching"""
    
    async def get_user_data(self, user_id: str, data_type: str) -> Optional[Any]:
        """Get user-specific cached data"""
        key = self._make_key("user", user_id, data_type)
        return await self.get(key)
    
    async def set_user_data(
        self, 
        user_id: str, 
        data_type: str, 
        value: Any, 
        ttl: int = 300
    ) -> bool:
        """Cache user-specific data"""
        key = self._make_key("user", user_id, data_type)
        return await self.set(key, value, ttl)
    
    async def invalidate_user(self, user_id: str):
        """Invalidate all cache for a user"""
        pattern = f"user:{user_id}:*"
        return await self.delete_pattern(pattern)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.redis.get(key)
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"User cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache"""
        try:
            self._stats["sets"] += 1
            return await self.redis.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"User cache set error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                self._stats["deletes"] += len(keys)
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"User cache delete pattern error: {e}")
            return 0


class ListCache(CacheStrategy):
    """Caching for list/collection data"""
    
    async def get_list(self, key: str) -> Optional[List[Any]]:
        """Get list from cache"""
        try:
            values = await self.redis.lrange(f"list:{key}", 0, -1)
            if values:
                self._stats["hits"] += 1
                return [json.loads(v) for v in values]
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"List cache get error: {e}")
            return None
    
    async def set_list(self, key: str, values: List[Any], ttl: int = 300) -> bool:
        """Cache a list of values"""
        try:
            self._stats["sets"] += 1
            list_key = f"list:{key}"
            
            # Use pipeline for atomic operation
            pipe = self.redis.pipeline()
            pipe.delete(list_key)
            for value in values:
                pipe.rpush(list_key, json.dumps(value, default=str))
            pipe.expire(list_key, ttl)
            
            await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"List cache set error: {e}")
            return False
    
    async def append_to_list(self, key: str, value: Any) -> bool:
        """Append to cached list"""
        try:
            list_key = f"list:{key}"
            return await self.redis.rpush(
                list_key, 
                json.dumps(value, default=str)
            ) > 0
        except Exception as e:
            logger.error(f"List cache append error: {e}")
            return False


# Cache decorators
def cache_result(ttl: int = 300, key_prefix: str = None):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_prefix or func.__name__
            if args:
                cache_key += ":" + ":".join(str(arg) for arg in args)
            if kwargs:
                cache_key += ":" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            # Get redis client from somewhere (you'll need to set this up)
            from core.redis import redis_manager
            redis = await redis_manager.connect()
            cache = SimpleCache(redis)
            
            # Try cache
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def invalidate_cache(patterns: Union[str, List[str]]):
    """Decorator to invalidate cache patterns after function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute function first
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            from core.redis import redis_manager
            redis = await redis_manager.connect()
            cache = SimpleCache(redis)
            
            pattern_list = patterns if isinstance(patterns, list) else [patterns]
            for pattern in pattern_list:
                await cache.delete_pattern(pattern)
            
            return result
        return wrapper
    return decorator


# Global cache instances (initialized in app startup)
simple_cache: Optional[SimpleCache] = None
query_cache: Optional[QueryCache] = None
user_cache: Optional[UserCache] = None
list_cache: Optional[ListCache] = None


async def init_cache_strategies(redis_client: aioredis.Redis):
    """Initialize global cache instances"""
    global simple_cache, query_cache, user_cache, list_cache
    
    simple_cache = SimpleCache(redis_client)
    query_cache = QueryCache(redis_client)
    user_cache = UserCache(redis_client)
    list_cache = ListCache(redis_client)
    
    logger.info("Cache strategies initialized")