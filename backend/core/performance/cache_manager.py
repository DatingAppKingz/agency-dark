"""
Advanced caching strategies for performance optimization
"""
import json
import hashlib
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from datetime import datetime, timedelta
from functools import wraps
import asyncio
from redis import asyncio as aioredis
from redis.exceptions import RedisError

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

T = TypeVar("T")


class CacheManager:
    """Advanced cache management with multiple strategies"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None
        
        # Cache configuration
        self.default_ttl = 3600  # 1 hour
        self.max_ttl = 86400  # 24 hours
        
        # Cache tiers
        self.tiers = {
            "hot": {"ttl": 300, "prefix": "hot:"},      # 5 minutes
            "warm": {"ttl": 3600, "prefix": "warm:"},   # 1 hour
            "cold": {"ttl": 86400, "prefix": "cold:"}   # 24 hours
        }
    
    async def connect(self):
        """Connect to Redis"""
        if not self._redis:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    @property
    async def redis(self) -> aioredis.Redis:
        """Get Redis connection"""
        if not self._redis:
            await self.connect()
        return self._redis
    
    def _generate_key(self, namespace: str, key: str) -> str:
        """Generate cache key with namespace"""
        return f"{settings.ENVIRONMENT}:{namespace}:{key}"
    
    def _hash_key(self, data: Any) -> str:
        """Generate hash key from data"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        elif not isinstance(data, str):
            data = str(data)
        
        return hashlib.md5(data.encode()).hexdigest()
    
    async def get(
        self,
        key: str,
        namespace: str = "default"
    ) -> Optional[Any]:
        """Get value from cache"""
        try:
            redis = await self.redis
            cache_key = self._generate_key(namespace, key)
            
            value = await redis.get(cache_key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            
            return None
        except RedisError as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> bool:
        """Set value in cache"""
        try:
            redis = await self.redis
            cache_key = self._generate_key(namespace, key)
            
            if not isinstance(value, str):
                value = json.dumps(value)
            
            ttl = ttl or self.default_ttl
            ttl = min(ttl, self.max_ttl)
            
            await redis.setex(cache_key, ttl, value)
            return True
        except RedisError as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(
        self,
        key: str,
        namespace: str = "default"
    ) -> bool:
        """Delete value from cache"""
        try:
            redis = await self.redis
            cache_key = self._generate_key(namespace, key)
            
            result = await redis.delete(cache_key)
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace"""
        try:
            redis = await self.redis
            pattern = self._generate_key(namespace, "*")
            
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await redis.delete(*keys)
            
            return 0
        except RedisError as e:
            logger.error(f"Redis clear namespace error: {e}")
            return 0
    
    async def get_or_set(
        self,
        key: str,
        func: Callable,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> Any:
        """Get from cache or compute and set"""
        value = await self.get(key, namespace)
        
        if value is None:
            if asyncio.iscoroutinefunction(func):
                value = await func()
            else:
                value = func()
            
            await self.set(key, value, ttl, namespace)
        
        return value
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        try:
            redis = await self.redis
            
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await redis.delete(*keys)
            
            return 0
        except RedisError as e:
            logger.error(f"Redis invalidate pattern error: {e}")
            return 0
    
    # Multi-tier caching
    async def set_tiered(
        self,
        key: str,
        value: Any,
        tier: str = "warm"
    ) -> bool:
        """Set value in specific cache tier"""
        if tier not in self.tiers:
            tier = "warm"
        
        tier_config = self.tiers[tier]
        namespace = tier_config["prefix"].rstrip(":")
        ttl = tier_config["ttl"]
        
        return await self.set(key, value, ttl, namespace)
    
    async def get_tiered(
        self,
        key: str,
        promote: bool = True
    ) -> Optional[Any]:
        """Get value from cache tiers with optional promotion"""
        # Check hot tier first
        for tier in ["hot", "warm", "cold"]:
            tier_config = self.tiers[tier]
            namespace = tier_config["prefix"].rstrip(":")
            
            value = await self.get(key, namespace)
            if value is not None:
                # Promote to hot tier if requested and not already there
                if promote and tier != "hot":
                    await self.set_tiered(key, value, "hot")
                
                return value
        
        return None
    
    # Cache warming
    async def warm_cache(
        self,
        keys_data: List[Dict[str, Any]],
        namespace: str = "default"
    ):
        """Warm cache with pre-computed data"""
        tasks = []
        
        for item in keys_data:
            key = item.get("key")
            value = item.get("value")
            ttl = item.get("ttl", self.default_ttl)
            
            if key and value is not None:
                task = self.set(key, value, ttl, namespace)
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # Cache statistics
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            redis = await self.redis
            info = await redis.info()
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0"),
                "total_commands": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "evicted_keys": info.get("evicted_keys", 0),
                "expired_keys": info.get("expired_keys", 0)
            }
        except RedisError as e:
            logger.error(f"Redis stats error: {e}")
            return {}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round(hits / total * 100, 2)


# Cache decorators
def cached(
    ttl: Optional[int] = None,
    namespace: str = "default",
    key_builder: Optional[Callable] = None
):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key builder
                key_parts = [func.__name__]
                if args:
                    key_parts.extend(str(arg) for arg in args)
                if kwargs:
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Get cache manager
            cache = CacheManager()
            
            # Try to get from cache
            result = await cache.get(cache_key, namespace)
            if result is not None:
                return result
            
            # Compute result
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl, namespace)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def invalidate_cache(
    patterns: List[str],
    namespace: str = "default"
):
    """Decorator to invalidate cache after function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute function
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            cache = CacheManager()
            for pattern in patterns:
                full_pattern = cache._generate_key(namespace, pattern)
                await cache.invalidate_pattern(full_pattern)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Invalidate cache
            loop = asyncio.get_event_loop()
            cache = CacheManager()
            for pattern in patterns:
                full_pattern = cache._generate_key(namespace, pattern)
                loop.run_until_complete(cache.invalidate_pattern(full_pattern))
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Cache key builders
class CacheKeyBuilder:
    """Utility class for building cache keys"""
    
    @staticmethod
    def user_key(user_id: int, *args) -> str:
        """Build user-specific cache key"""
        parts = [f"user:{user_id}"]
        parts.extend(str(arg) for arg in args)
        return ":".join(parts)
    
    @staticmethod
    def model_key(model_id: int, *args) -> str:
        """Build model-specific cache key"""
        parts = [f"model:{model_id}"]
        parts.extend(str(arg) for arg in args)
        return ":".join(parts)
    
    @staticmethod
    def agency_key(agency_id: int, *args) -> str:
        """Build agency-specific cache key"""
        parts = [f"agency:{agency_id}"]
        parts.extend(str(arg) for arg in args)
        return ":".join(parts)
    
    @staticmethod
    def analytics_key(
        model_id: int,
        metric_type: str,
        date_range: str
    ) -> str:
        """Build analytics cache key"""
        return f"analytics:{model_id}:{metric_type}:{date_range}"
    
    @staticmethod
    def list_key(
        entity_type: str,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 20
    ) -> str:
        """Build list query cache key"""
        filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return f"list:{entity_type}:{filter_str}:page={page}:limit={per_page}"


# Singleton cache manager instance
cache_manager = CacheManager()