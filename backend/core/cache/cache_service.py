"""
Enhanced Redis caching service with performance optimization.
"""
import logging
import json
import pickle
from typing import Any, Optional, Union, List, Dict, Callable, TypeVar, Type
from datetime import timedelta
from functools import wraps
import hashlib
from enum import Enum

from redis.asyncio import Redis
from pydantic import BaseModel

from core.redis import redis_client
from core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheStrategy(str, Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time-based expiration
    LRU = "lru"  # Least recently used
    WRITE_THROUGH = "write_through"  # Update cache on write
    WRITE_BEHIND = "write_behind"  # Async cache update


class CacheSerializer:
    """Handle serialization for different data types."""
    
    @staticmethod
    def serialize(value: Any) -> bytes:
        """Serialize value for Redis storage."""
        if isinstance(value, BaseModel):
            return value.json().encode()
        elif isinstance(value, (dict, list)):
            return json.dumps(value, default=str).encode()
        elif isinstance(value, (str, int, float)):
            return str(value).encode()
        else:
            # Fallback to pickle for complex objects
            return pickle.dumps(value)
    
    @staticmethod
    def deserialize(data: bytes, model_class: Optional[Type[BaseModel]] = None) -> Any:
        """Deserialize value from Redis."""
        if not data:
            return None
        
        try:
            # Try JSON first
            json_data = json.loads(data.decode())
            if model_class and issubclass(model_class, BaseModel):
                return model_class(**json_data)
            return json_data
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                # Try plain string
                return data.decode()
            except UnicodeDecodeError:
                # Fallback to pickle
                return pickle.loads(data)


class CacheKey:
    """Generate and manage cache keys."""
    
    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and parameters."""
        parts = [settings.CACHE_PREFIX, prefix]
        
        # Add positional args
        for arg in args:
            if isinstance(arg, BaseModel):
                parts.append(arg.json())
            else:
                parts.append(str(arg))
        
        # Add keyword args (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        
        # Create hash for long keys
        key_str = ":".join(parts)
        if len(key_str) > 200:  # Redis key limit is 512MB, but keep it reasonable
            hash_suffix = hashlib.md5(key_str.encode()).hexdigest()
            return f"{settings.CACHE_PREFIX}:{prefix}:{hash_suffix}"
        
        return key_str


class CacheService:
    """Enhanced caching service with multiple strategies."""
    
    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis or redis_client
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    async def get(
        self,
        key: str,
        model_class: Optional[Type[BaseModel]] = None
    ) -> Optional[Any]:
        """Get value from cache."""
        try:
            data = await self.redis.get(key)
            if data:
                self._cache_stats['hits'] += 1
                return CacheSerializer.deserialize(data, model_class)
            else:
                self._cache_stats['misses'] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self._cache_stats['errors'] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with optional TTL."""
        try:
            serialized = CacheSerializer.serialize(value)
            
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            
            self._cache_stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self._cache_stats['errors'] += 1
            return False
    
    async def delete(self, key: Union[str, List[str]]) -> int:
        """Delete one or more keys."""
        try:
            if isinstance(key, str):
                result = await self.redis.delete(key)
            else:
                result = await self.redis.delete(*key)
            
            self._cache_stats['deletes'] += result
            return result
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self._cache_stats['errors'] += 1
            return 0
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.delete(keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            self._cache_stats['errors'] += 1
            return 0
    
    async def get_many(
        self,
        keys: List[str],
        model_class: Optional[Type[BaseModel]] = None
    ) -> Dict[str, Any]:
        """Get multiple values at once."""
        try:
            values = await self.redis.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value:
                    self._cache_stats['hits'] += 1
                    result[key] = CacheSerializer.deserialize(value, model_class)
                else:
                    self._cache_stats['misses'] += 1
                    result[key] = None
            
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            self._cache_stats['errors'] += 1
            return {key: None for key in keys}
    
    async def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set multiple values at once."""
        try:
            # Serialize all values
            serialized_mapping = {
                key: CacheSerializer.serialize(value)
                for key, value in mapping.items()
            }
            
            # Use pipeline for atomic operation
            pipe = self.redis.pipeline()
            
            for key, value in serialized_mapping.items():
                if ttl:
                    if isinstance(ttl, timedelta):
                        ttl_seconds = int(ttl.total_seconds())
                    else:
                        ttl_seconds = ttl
                    pipe.setex(key, ttl_seconds, value)
                else:
                    pipe.set(key, value)
            
            await pipe.execute()
            self._cache_stats['sets'] += len(mapping)
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            self._cache_stats['errors'] += 1
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter."""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return None
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[Union[int, timedelta]] = None,
        model_class: Optional[Type[BaseModel]] = None
    ) -> Any:
        """Get value from cache or compute and set it."""
        # Try to get from cache first
        value = await self.get(key, model_class)
        if value is not None:
            return value
        
        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        # Cache it
        if value is not None:
            await self.set(key, value, ttl)
        
        return value
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._cache_stats,
            'total_requests': total,
            'hit_rate': round(hit_rate, 2)
        }
    
    async def clear_stats(self):
        """Clear cache statistics."""
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }


# Global cache instance
cache = CacheService()


# Cache decorators
def cached(
    prefix: str,
    ttl: Optional[Union[int, timedelta]] = None,
    key_func: Optional[Callable] = None,
    model_class: Optional[Type[BaseModel]] = None
):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                cache_key = CacheKey.generate(
                    f"{prefix}:{func.__name__}",
                    *args[1:] if args else [],  # Skip 'self' if present
                    **kwargs
                )
            
            # Try to get from cache
            result = await cache.get(cache_key, model_class)
            if result is not None:
                return result
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                await cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache management methods
        wrapper.invalidate = lambda *args, **kwargs: cache.delete(
            key_func(*args, **kwargs) if key_func else 
            CacheKey.generate(f"{prefix}:{func.__name__}", *args[1:], **kwargs)
        )
        
        return wrapper
    return decorator


def cache_aside(
    prefix: str,
    ttl: Optional[Union[int, timedelta]] = None
):
    """Cache-aside pattern decorator."""
    return cached(prefix, ttl)


def cache_invalidate(prefix: str, key_func: Optional[Callable] = None):
    """Decorator to invalidate cache on function call."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Call function first
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{prefix}:*"
            
            if '*' in cache_key:
                await cache.delete_pattern(cache_key)
            else:
                await cache.delete(cache_key)
            
            return result
        return wrapper
    return decorator


# Import asyncio for async function detection
import asyncio