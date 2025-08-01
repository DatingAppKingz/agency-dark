"""
Advanced Caching Strategy for Agency Dark

Implements multi-layer caching with:
- In-memory cache (LRU)
- Redis distributed cache
- Query result caching
- Partial response caching
- Cache invalidation patterns
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Set, Callable, Union
from datetime import datetime, timedelta
from functools import lru_cache, wraps
import hashlib
import pickle
from enum import Enum

from pydantic import BaseModel
import orjson

from core.redis import redis_client
from core.logger import get_logger

logger = get_logger(__name__)


class CacheLevel(str, Enum):
    """Cache levels for multi-tier caching."""
    MEMORY = "memory"
    REDIS = "redis"
    BOTH = "both"


class CacheConfig(BaseModel):
    """Cache configuration."""
    ttl: int = 300  # 5 minutes default
    level: CacheLevel = CacheLevel.BOTH
    key_prefix: str = "cache"
    max_memory_items: int = 1000
    compress: bool = True
    version: int = 1


class CacheTag:
    """Cache tagging for group invalidation."""
    USER = "user"
    AGENCY = "agency"
    ANALYTICS = "analytics"
    SYNC = "sync"
    FINANCIAL = "financial"
    CONTENT = "content"


class AdvancedCacheStrategy:
    """Advanced multi-tier caching with intelligent invalidation."""
    
    def __init__(self):
        self._memory_cache = {}
        self._cache_tags = {}  # tag -> set of cache keys
        self._key_tags = {}    # key -> set of tags
        self._access_counts = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
        self._hot_threshold = 10  # Access count to consider "hot"
        
    def cache(
        self,
        config: Optional[CacheConfig] = None,
        tags: Optional[List[str]] = None,
        key_func: Optional[Callable] = None
    ):
        """
        Advanced caching decorator with multi-tier support.
        
        Args:
            config: Cache configuration
            tags: Cache tags for group invalidation
            key_func: Custom key generation function
        """
        config = config or CacheConfig()
        tags = tags or []
        
        def decorator(func: Callable) -> Callable:
            # Create LRU cache for memory tier
            if config.level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                memory_cached = lru_cache(maxsize=config.max_memory_items)(func)
            else:
                memory_cached = func
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_key(
                        config.key_prefix,
                        func.__name__,
                        args,
                        kwargs,
                        config.version
                    )
                
                # Try memory cache first
                if config.level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                    memory_result = self._get_from_memory(cache_key)
                    if memory_result is not None:
                        self._record_access(cache_key)
                        return memory_result
                
                # Try Redis cache
                if config.level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                    redis_result = await self._get_from_redis(cache_key)
                    if redis_result is not None:
                        # Promote to memory cache if hot
                        if self._is_hot_key(cache_key):
                            self._set_in_memory(cache_key, redis_result)
                        self._record_access(cache_key)
                        return redis_result
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                await self._cache_result(
                    cache_key,
                    result,
                    config,
                    tags
                )
                
                return result
            
            # Add cache management methods
            wrapper.invalidate = lambda: asyncio.create_task(
                self.invalidate_function_cache(func.__name__, config.key_prefix)
            )
            wrapper.warmup = lambda *a, **kw: asyncio.create_task(
                wrapper(*a, **kw)
            )
            
            return wrapper
        return decorator
    
    async def get(
        self,
        key: str,
        default: Any = None,
        level: CacheLevel = CacheLevel.BOTH
    ) -> Any:
        """Get value from cache."""
        # Try memory first
        if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
            result = self._get_from_memory(key)
            if result is not None:
                return result
        
        # Try Redis
        if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
            result = await self._get_from_redis(key)
            if result is not None:
                return result
        
        return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        level: CacheLevel = CacheLevel.BOTH,
        tags: Optional[List[str]] = None
    ):
        """Set value in cache."""
        # Set in memory
        if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
            self._set_in_memory(key, value)
        
        # Set in Redis
        if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
            await self._set_in_redis(key, value, ttl)
        
        # Register tags
        if tags:
            self._register_tags(key, tags)
    
    async def delete(self, key: str):
        """Delete from all cache levels."""
        # Delete from memory
        self._memory_cache.pop(key, None)
        self._access_counts.pop(key, None)
        
        # Delete from Redis
        try:
            await redis_client.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete from Redis: {e}")
        
        # Clean up tags
        self._unregister_tags(key)
    
    async def invalidate_tag(self, tag: str):
        """Invalidate all cache entries with a specific tag."""
        keys = self._cache_tags.get(tag, set()).copy()
        
        for key in keys:
            await self.delete(key)
        
        logger.info(f"Invalidated {len(keys)} cache entries for tag: {tag}")
    
    async def invalidate_tags(self, tags: List[str]):
        """Invalidate multiple tags."""
        tasks = [self.invalidate_tag(tag) for tag in tags]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        # Memory cache
        memory_keys = [
            k for k in self._memory_cache.keys()
            if pattern in k
        ]
        for key in memory_keys:
            self._memory_cache.pop(key, None)
        
        # Redis cache (use SCAN for efficiency)
        try:
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor,
                    match=f"*{pattern}*",
                    count=100
                )
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Failed to invalidate pattern in Redis: {e}")
    
    async def invalidate_function_cache(
        self,
        func_name: str,
        prefix: str = "cache"
    ):
        """Invalidate all cache entries for a function."""
        pattern = f"{prefix}:{func_name}:"
        await self.invalidate_pattern(pattern)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        memory_size = len(self._memory_cache)
        
        # Get Redis stats
        try:
            redis_info = await redis_client.info("memory")
            redis_memory = redis_info.get("used_memory_human", "N/A")
            redis_keys = await redis_client.dbsize()
        except:
            redis_memory = "N/A"
            redis_keys = 0
        
        # Calculate hit rates
        hot_keys = [
            k for k, count in self._access_counts.items()
            if count >= self._hot_threshold
        ]
        
        return {
            "memory_cache": {
                "size": memory_size,
                "hot_keys": len(hot_keys),
                "total_accesses": sum(self._access_counts.values())
            },
            "redis_cache": {
                "memory": redis_memory,
                "keys": redis_keys
            },
            "tags": {
                "total_tags": len(self._cache_tags),
                "total_tagged_keys": len(self._key_tags)
            }
        }
    
    def cache_aside(
        self,
        ttl: int = 300,
        tags: Optional[List[str]] = None
    ):
        """
        Cache-aside pattern decorator.
        
        Loads from cache, computes if missing, then caches result.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(key: str, *args, **kwargs):
                # Try to get from cache
                cached = await self.get(key)
                if cached is not None:
                    return cached
                
                # Compute result
                result = await func(key, *args, **kwargs)
                
                # Cache result
                await self.set(key, result, ttl=ttl, tags=tags)
                
                return result
            
            return wrapper
        return decorator
    
    def _generate_key(
        self,
        prefix: str,
        func_name: str,
        args: tuple,
        kwargs: dict,
        version: int
    ) -> str:
        """Generate cache key."""
        key_parts = [
            prefix,
            func_name,
            str(version),
            str(args),
            str(sorted(kwargs.items()))
        ]
        key_str = ":".join(key_parts)
        
        # Use hash for long keys
        if len(key_str) > 250:
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            return f"{prefix}:{func_name}:{version}:{key_hash}"
        
        return key_str
    
    def _get_from_memory(self, key: str) -> Any:
        """Get from memory cache."""
        self._cleanup_if_needed()
        return self._memory_cache.get(key)
    
    def _set_in_memory(self, key: str, value: Any):
        """Set in memory cache."""
        self._memory_cache[key] = value
        self._cleanup_if_needed()
    
    async def _get_from_redis(self, key: str) -> Any:
        """Get from Redis cache."""
        try:
            data = await redis_client.get(key)
            if data:
                return orjson.loads(data)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None
    
    async def _set_in_redis(self, key: str, value: Any, ttl: int):
        """Set in Redis cache."""
        try:
            data = orjson.dumps(value)
            await redis_client.setex(key, ttl, data)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    async def _cache_result(
        self,
        key: str,
        value: Any,
        config: CacheConfig,
        tags: List[str]
    ):
        """Cache result in configured levels."""
        # Memory cache
        if config.level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
            self._set_in_memory(key, value)
        
        # Redis cache
        if config.level in [CacheLevel.REDIS, CacheLevel.BOTH]:
            await self._set_in_redis(key, value, config.ttl)
        
        # Register tags
        if tags:
            self._register_tags(key, tags)
    
    def _register_tags(self, key: str, tags: List[str]):
        """Register cache tags."""
        self._key_tags[key] = set(tags)
        
        for tag in tags:
            if tag not in self._cache_tags:
                self._cache_tags[tag] = set()
            self._cache_tags[tag].add(key)
    
    def _unregister_tags(self, key: str):
        """Unregister cache tags."""
        tags = self._key_tags.pop(key, set())
        
        for tag in tags:
            if tag in self._cache_tags:
                self._cache_tags[tag].discard(key)
                if not self._cache_tags[tag]:
                    del self._cache_tags[tag]
    
    def _record_access(self, key: str):
        """Record cache access for hot key detection."""
        self._access_counts[key] = self._access_counts.get(key, 0) + 1
    
    def _is_hot_key(self, key: str) -> bool:
        """Check if key is hot (frequently accessed)."""
        return self._access_counts.get(key, 0) >= self._hot_threshold
    
    def _cleanup_if_needed(self):
        """Cleanup memory cache if needed."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = current_time
        
        # Remove least accessed keys if cache is too large
        if len(self._memory_cache) > 10000:
            # Sort by access count
            sorted_keys = sorted(
                self._memory_cache.keys(),
                key=lambda k: self._access_counts.get(k, 0)
            )
            
            # Remove bottom 20%
            remove_count = len(sorted_keys) // 5
            for key in sorted_keys[:remove_count]:
                self._memory_cache.pop(key, None)
                self._access_counts.pop(key, None)
                self._unregister_tags(key)


# Global cache instance
advanced_cache = AdvancedCacheStrategy()