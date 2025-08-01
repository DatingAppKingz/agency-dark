"""Advanced caching system with multi-level caching and intelligent invalidation."""

import json
import pickle
import hashlib
import asyncio
from typing import Any, Optional, Union, List, Dict, Callable, TypeVar, Set
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from contextlib import asynccontextmanager
import aioredis
from redis.asyncio import Redis
from redis.asyncio.lock import Lock as RedisLock

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CacheLevel:
    """Cache level enumeration."""
    MEMORY = "memory"
    REDIS = "redis"
    ALL = "all"


class CacheStrategy:
    """Cache strategy enumeration."""
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class CacheTag:
    """Predefined cache tags for invalidation."""
    USER = "user"
    MODEL = "model"
    AGENCY = "agency"
    TRANSACTION = "transaction"
    MESSAGE = "message"
    ANALYTICS = "analytics"
    SEARCH = "search"
    API = "api"


class CacheManager:
    """Advanced cache manager with multi-level caching."""
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_tags: Dict[str, Set[str]] = {}
        self._write_behind_queue: List[Dict[str, Any]] = []
        self._refresh_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False
        
        # LRU cache for memory level
        self._lru_cache = lru_cache(maxsize=settings.CACHE_MEMORY_MAX_SIZE)
    
    async def initialize(self):
        """Initialize cache connections."""
        if self._initialized:
            return
        
        try:
            # Initialize Redis connection
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 2,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                }
            )
            
            # Test connection
            await self._redis.ping()
            
            # Start background tasks
            asyncio.create_task(self._process_write_behind_queue())
            
            self._initialized = True
            logger.info("Cache manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}")
            raise
    
    async def close(self):
        """Close cache connections."""
        if self._redis:
            await self._redis.close()
        
        # Cancel refresh tasks
        for task in self._refresh_tasks.values():
            task.cancel()
        
        self._initialized = False
    
    def _generate_key(self, namespace: str, key: str) -> str:
        """Generate cache key with namespace."""
        return f"{settings.CACHE_KEY_PREFIX}:{namespace}:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            return json.loads(data.decode('utf-8'))
        except:
            return pickle.loads(data)
    
    async def get(
        self,
        key: str,
        namespace: str = "default",
        level: str = CacheLevel.ALL
    ) -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._generate_key(namespace, key)
        
        # Check memory cache first
        if level in [CacheLevel.MEMORY, CacheLevel.ALL]:
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                if entry['expires_at'] is None or entry['expires_at'] > datetime.utcnow():
                    logger.debug(f"Cache hit (memory): {cache_key}")
                    return entry['value']
                else:
                    # Expired, remove from memory
                    del self._memory_cache[cache_key]
        
        # Check Redis
        if level in [CacheLevel.REDIS, CacheLevel.ALL] and self._redis:
            try:
                data = await self._redis.get(cache_key)
                if data:
                    logger.debug(f"Cache hit (redis): {cache_key}")
                    value = self._deserialize(data)
                    
                    # Populate memory cache
                    if level == CacheLevel.ALL:
                        ttl = await self._redis.ttl(cache_key)
                        expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
                        self._memory_cache[cache_key] = {
                            'value': value,
                            'expires_at': expires_at
                        }
                    
                    return value
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        logger.debug(f"Cache miss: {cache_key}")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[int] = None,
        level: str = CacheLevel.ALL,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in cache."""
        cache_key = self._generate_key(namespace, key)
        
        # Set in memory cache
        if level in [CacheLevel.MEMORY, CacheLevel.ALL]:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
            self._memory_cache[cache_key] = {
                'value': value,
                'expires_at': expires_at
            }
        
        # Set in Redis
        if level in [CacheLevel.REDIS, CacheLevel.ALL] and self._redis:
            try:
                serialized = self._serialize(value)
                if ttl:
                    await self._redis.setex(cache_key, ttl, serialized)
                else:
                    await self._redis.set(cache_key, serialized)
                
                # Track tags
                if tags:
                    for tag in tags:
                        tag_key = f"{settings.CACHE_KEY_PREFIX}:tag:{tag}"
                        await self._redis.sadd(tag_key, cache_key)
                        if cache_key not in self._cache_tags:
                            self._cache_tags[cache_key] = set()
                        self._cache_tags[cache_key].add(tag)
                
                logger.debug(f"Cache set: {cache_key}")
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                return False
        
        return True
    
    async def delete(
        self,
        key: str,
        namespace: str = "default",
        level: str = CacheLevel.ALL
    ) -> bool:
        """Delete value from cache."""
        cache_key = self._generate_key(namespace, key)
        
        # Delete from memory cache
        if level in [CacheLevel.MEMORY, CacheLevel.ALL]:
            self._memory_cache.pop(cache_key, None)
        
        # Delete from Redis
        if level in [CacheLevel.REDIS, CacheLevel.ALL] and self._redis:
            try:
                await self._redis.delete(cache_key)
                
                # Remove from tag tracking
                if cache_key in self._cache_tags:
                    for tag in self._cache_tags[cache_key]:
                        tag_key = f"{settings.CACHE_KEY_PREFIX}:tag:{tag}"
                        await self._redis.srem(tag_key, cache_key)
                    del self._cache_tags[cache_key]
                
                logger.debug(f"Cache delete: {cache_key}")
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                return False
        
        return True
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag."""
        count = 0
        
        if self._redis:
            try:
                tag_key = f"{settings.CACHE_KEY_PREFIX}:tag:{tag}"
                keys = await self._redis.smembers(tag_key)
                
                if keys:
                    # Delete from Redis
                    await self._redis.delete(*keys)
                    
                    # Delete from memory cache
                    for key in keys:
                        self._memory_cache.pop(key.decode() if isinstance(key, bytes) else key, None)
                        count += 1
                    
                    # Clean up tag set
                    await self._redis.delete(tag_key)
                
                logger.info(f"Invalidated {count} cache entries for tag: {tag}")
            except Exception as e:
                logger.error(f"Tag invalidation error: {e}")
        
        return count
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern."""
        count = 0
        
        # Invalidate from memory cache
        keys_to_delete = [k for k in self._memory_cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._memory_cache[key]
            count += 1
        
        # Invalidate from Redis
        if self._redis:
            try:
                cursor = '0'
                while cursor != 0:
                    cursor, keys = await self._redis.scan(
                        cursor=cursor,
                        match=f"*{pattern}*",
                        count=100
                    )
                    if keys:
                        await self._redis.delete(*keys)
                        count += len(keys)
            except Exception as e:
                logger.error(f"Pattern invalidation error: {e}")
        
        logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")
        return count
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        namespace: str = "default",
        ttl: Optional[int] = None,
        level: str = CacheLevel.ALL,
        tags: Optional[List[str]] = None
    ) -> Any:
        """Get from cache or compute and set."""
        value = await self.get(key, namespace, level)
        
        if value is None:
            # Acquire lock to prevent cache stampede
            lock_key = f"{self._generate_key(namespace, key)}:lock"
            
            if self._redis:
                async with RedisLock(self._redis, lock_key, timeout=30):
                    # Double-check after acquiring lock
                    value = await self.get(key, namespace, level)
                    if value is None:
                        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
                        await self.set(key, value, namespace, ttl, level, tags)
            else:
                value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
                await self.set(key, value, namespace, ttl, level, tags)
        
        return value
    
    def cache_aside(
        self,
        namespace: str = "default",
        ttl: Optional[int] = 3600,
        key_func: Optional[Callable] = None,
        tags: Optional[List[str]] = None,
        level: str = CacheLevel.ALL
    ):
        """Cache-aside decorator."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_cache_key_from_args(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached = await self.get(cache_key, namespace, level)
                if cached is not None:
                    return cached
                
                # Compute value
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(cache_key, result, namespace, ttl, level, tags)
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, use asyncio.run
                return asyncio.run(async_wrapper(*args, **kwargs))
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return decorator
    
    def write_through(
        self,
        namespace: str = "default",
        ttl: Optional[int] = 3600,
        key_func: Optional[Callable] = None,
        tags: Optional[List[str]] = None,
        level: str = CacheLevel.ALL
    ):
        """Write-through cache decorator."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_cache_key_from_args(func.__name__, args, kwargs)
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Update cache immediately
                await self.set(cache_key, result, namespace, ttl, level, tags)
                
                return result
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else func
        
        return decorator
    
    def write_behind(
        self,
        namespace: str = "default",
        ttl: Optional[int] = 3600,
        key_func: Optional[Callable] = None,
        tags: Optional[List[str]] = None,
        batch_size: int = 100,
        batch_interval: int = 5
    ):
        """Write-behind cache decorator with batching."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_cache_key_from_args(func.__name__, args, kwargs)
                
                # Add to write-behind queue
                self._write_behind_queue.append({
                    'key': cache_key,
                    'namespace': namespace,
                    'func': func,
                    'args': args,
                    'kwargs': kwargs,
                    'ttl': ttl,
                    'tags': tags,
                    'timestamp': datetime.utcnow()
                })
                
                # Return cached value if available
                cached = await self.get(cache_key, namespace)
                if cached is not None:
                    return cached
                
                # Otherwise compute and return
                return await func(*args, **kwargs)
            
            return async_wrapper
        
        return decorator
    
    def refresh_ahead(
        self,
        namespace: str = "default",
        ttl: int = 3600,
        refresh_interval: int = 300,
        key_func: Optional[Callable] = None,
        tags: Optional[List[str]] = None
    ):
        """Refresh-ahead cache decorator."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_cache_key_from_args(func.__name__, args, kwargs)
                
                # Check if refresh task exists
                task_key = f"{namespace}:{cache_key}"
                if task_key not in self._refresh_tasks:
                    # Create refresh task
                    async def refresh_task():
                        while True:
                            try:
                                result = await func(*args, **kwargs)
                                await self.set(cache_key, result, namespace, ttl, tags=tags)
                                await asyncio.sleep(refresh_interval)
                            except asyncio.CancelledError:
                                break
                            except Exception as e:
                                logger.error(f"Refresh task error: {e}")
                                await asyncio.sleep(60)  # Retry after 1 minute
                    
                    self._refresh_tasks[task_key] = asyncio.create_task(refresh_task())
                
                # Get from cache
                cached = await self.get(cache_key, namespace)
                if cached is not None:
                    return cached
                
                # Initial computation
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, namespace, ttl, tags=tags)
                return result
            
            return async_wrapper
        
        return decorator
    
    async def _process_write_behind_queue(self):
        """Process write-behind queue in batches."""
        while True:
            try:
                if self._write_behind_queue:
                    batch = []
                    while self._write_behind_queue and len(batch) < 100:
                        batch.append(self._write_behind_queue.pop(0))
                    
                    # Process batch
                    for item in batch:
                        try:
                            result = await item['func'](*item['args'], **item['kwargs'])
                            await self.set(
                                item['key'],
                                result,
                                item['namespace'],
                                item['ttl'],
                                tags=item['tags']
                            )
                        except Exception as e:
                            logger.error(f"Write-behind processing error: {e}")
                
                await asyncio.sleep(5)  # Process every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Write-behind queue error: {e}")
                await asyncio.sleep(60)
    
    def _generate_cache_key_from_args(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function arguments."""
        key_parts = [func_name]
        
        # Add args
        for arg in args:
            if hasattr(arg, 'id'):
                key_parts.append(f"id:{arg.id}")
            else:
                key_parts.append(str(arg))
        
        # Add kwargs
        for k, v in sorted(kwargs.items()):
            if hasattr(v, 'id'):
                key_parts.append(f"{k}:id:{v.id}")
            else:
                key_parts.append(f"{k}:{v}")
        
        # Generate hash for long keys
        key = ":".join(key_parts)
        if len(key) > 200:
            key = hashlib.md5(key.encode()).hexdigest()
        
        return key
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'memory_cache_size': len(self._memory_cache),
            'memory_cache_keys': list(self._memory_cache.keys())[:10],  # Sample
            'write_behind_queue_size': len(self._write_behind_queue),
            'refresh_tasks_count': len(self._refresh_tasks),
            'redis_connected': self._redis is not None
        }
        
        if self._redis:
            try:
                info = await self._redis.info()
                stats['redis_info'] = {
                    'used_memory_human': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed'),
                    'expired_keys': info.get('expired_keys'),
                    'evicted_keys': info.get('evicted_keys'),
                    'keyspace_hits': info.get('keyspace_hits'),
                    'keyspace_misses': info.get('keyspace_misses'),
                }
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")
        
        return stats
    
    async def warm_cache(self, warmup_funcs: List[Callable]):
        """Warm up cache with predefined functions."""
        logger.info("Starting cache warmup...")
        
        for func in warmup_funcs:
            try:
                await func()
            except Exception as e:
                logger.error(f"Cache warmup error for {func.__name__}: {e}")
        
        logger.info("Cache warmup completed")


# Global cache manager instance
cache_manager = CacheManager()


# Convenience functions
async def cache_get(key: str, namespace: str = "default") -> Optional[Any]:
    """Get value from cache."""
    return await cache_manager.get(key, namespace)


async def cache_set(
    key: str,
    value: Any,
    namespace: str = "default",
    ttl: Optional[int] = None,
    tags: Optional[List[str]] = None
) -> bool:
    """Set value in cache."""
    return await cache_manager.set(key, value, namespace, ttl, tags=tags)


async def cache_delete(key: str, namespace: str = "default") -> bool:
    """Delete value from cache."""
    return await cache_manager.delete(key, namespace)


async def cache_invalidate_tag(tag: str) -> int:
    """Invalidate cache by tag."""
    return await cache_manager.invalidate_by_tag(tag)


async def cache_invalidate_pattern(pattern: str) -> int:
    """Invalidate cache by pattern."""
    return await cache_manager.invalidate_pattern(pattern)