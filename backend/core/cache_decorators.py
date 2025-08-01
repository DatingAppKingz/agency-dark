"""Cache decorators for common caching patterns."""

from typing import Optional, List, Callable, Any
from functools import wraps
import hashlib
import json

from core.cache_manager import cache_manager, CacheTag
from core.logger import get_logger

logger = get_logger(__name__)


def cached_result(
    ttl: int = 3600,
    namespace: str = "api",
    tags: Optional[List[str]] = None,
    key_prefix: Optional[str] = None,
    condition: Optional[Callable] = None
):
    """
    Cache decorator for API endpoints and service methods.
    
    Args:
        ttl: Time to live in seconds
        namespace: Cache namespace
        tags: Cache tags for invalidation
        key_prefix: Custom key prefix
        condition: Function to determine if result should be cached
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if caching should be applied
            if condition and not condition(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Generate cache key
            cache_key = _generate_cache_key(func, args, kwargs, key_prefix)
            
            # Try to get from cache
            cached = await cache_manager.get(cache_key, namespace)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(
                cache_key,
                result,
                namespace,
                ttl,
                tags=tags
            )
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, bypass cache (or implement sync cache)
            return func(*args, **kwargs)
        
        return async_wrapper if hasattr(func, '__aenter__') or hasattr(func, '__await__') else sync_wrapper
    
    return decorator


def cache_user_data(ttl: int = 300):
    """Cache decorator specifically for user-related data."""
    def decorator(func):
        @wraps(func)
        async def wrapper(user_id: str, *args, **kwargs):
            cache_key = f"user:{user_id}:{func.__name__}"
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "users")
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(user_id, *args, **kwargs)
            
            # Cache with user tag
            await cache_manager.set(
                cache_key,
                result,
                "users",
                ttl,
                tags=[CacheTag.USER, f"user:{user_id}"]
            )
            
            return result
        
        return wrapper
    
    return decorator


def cache_model_data(ttl: int = 600):
    """Cache decorator specifically for model-related data."""
    def decorator(func):
        @wraps(func)
        async def wrapper(model_id: str, *args, **kwargs):
            cache_key = f"model:{model_id}:{func.__name__}"
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "models")
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(model_id, *args, **kwargs)
            
            # Cache with model tag
            await cache_manager.set(
                cache_key,
                result,
                "models",
                ttl,
                tags=[CacheTag.MODEL, f"model:{model_id}"]
            )
            
            return result
        
        return wrapper
    
    return decorator


def cache_analytics(ttl: int = 900, granularity: str = "hour"):
    """Cache decorator for analytics data with time-based invalidation."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Include granularity in cache key
            cache_key = _generate_cache_key(
                func,
                args,
                kwargs,
                prefix=f"analytics:{granularity}"
            )
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "analytics")
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache with analytics tag
            await cache_manager.set(
                cache_key,
                result,
                "analytics",
                ttl,
                tags=[CacheTag.ANALYTICS, f"analytics:{granularity}"]
            )
            
            return result
        
        return wrapper
    
    return decorator


def cache_search_results(ttl: int = 300):
    """Cache decorator for search results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(query: str, *args, **kwargs):
            # Normalize query for caching
            normalized_query = query.strip().lower()
            cache_key = f"search:{hashlib.md5(normalized_query.encode()).hexdigest()}"
            
            # Add filters to cache key
            if 'filters' in kwargs:
                filters_hash = hashlib.md5(
                    json.dumps(kwargs['filters'], sort_keys=True).encode()
                ).hexdigest()
                cache_key += f":{filters_hash}"
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "search")
            if cached is not None:
                return cached
            
            # Execute search
            result = await func(query, *args, **kwargs)
            
            # Cache with search tag
            await cache_manager.set(
                cache_key,
                result,
                "search",
                ttl,
                tags=[CacheTag.SEARCH]
            )
            
            return result
        
        return wrapper
    
    return decorator


def invalidate_user_cache(user_id: str):
    """Invalidate all cache entries for a specific user."""
    async def _invalidate():
        count = await cache_manager.invalidate_by_tag(f"user:{user_id}")
        logger.info(f"Invalidated {count} cache entries for user {user_id}")
    
    return _invalidate()


def invalidate_model_cache(model_id: str):
    """Invalidate all cache entries for a specific model."""
    async def _invalidate():
        count = await cache_manager.invalidate_by_tag(f"model:{model_id}")
        logger.info(f"Invalidated {count} cache entries for model {model_id}")
    
    return _invalidate()


def invalidate_analytics_cache(granularity: Optional[str] = None):
    """Invalidate analytics cache."""
    async def _invalidate():
        if granularity:
            count = await cache_manager.invalidate_by_tag(f"analytics:{granularity}")
        else:
            count = await cache_manager.invalidate_by_tag(CacheTag.ANALYTICS)
        logger.info(f"Invalidated {count} analytics cache entries")
    
    return _invalidate()


def cache_computation(ttl: int = 3600, max_size: int = 1000):
    """
    Cache decorator for expensive computations with size limit.
    
    Args:
        ttl: Time to live in seconds
        max_size: Maximum size of cached data in KB
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = _generate_cache_key(func, args, kwargs, prefix="compute")
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "computations")
            if cached is not None:
                return cached
            
            # Execute computation
            result = await func(*args, **kwargs)
            
            # Check size before caching
            import sys
            size_kb = sys.getsizeof(result) / 1024
            
            if size_kb <= max_size:
                await cache_manager.set(
                    cache_key,
                    result,
                    "computations",
                    ttl
                )
            else:
                logger.warning(
                    f"Computation result too large to cache: {size_kb:.2f}KB > {max_size}KB"
                )
            
            return result
        
        return wrapper
    
    return decorator


def cache_paginated(ttl: int = 300):
    """Cache decorator for paginated results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract pagination params
            page = kwargs.get('page', 1)
            page_size = kwargs.get('page_size', 20)
            
            # Generate cache key including pagination
            cache_key = _generate_cache_key(
                func,
                args,
                kwargs,
                prefix=f"page:{page}:{page_size}"
            )
            
            # Get from cache
            cached = await cache_manager.get(cache_key, "paginated")
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the page
            await cache_manager.set(
                cache_key,
                result,
                "paginated",
                ttl
            )
            
            return result
        
        return wrapper
    
    return decorator


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    prefix: Optional[str] = None
) -> str:
    """Generate a cache key from function and arguments."""
    key_parts = []
    
    if prefix:
        key_parts.append(prefix)
    
    key_parts.append(func.__name__)
    
    # Add args
    for arg in args:
        if hasattr(arg, 'id'):
            key_parts.append(f"id:{arg.id}")
        elif isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # Hash complex objects
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # Add kwargs
    for k, v in sorted(kwargs.items()):
        if k in ['self', 'cls', 'db', 'session']:  # Skip common params
            continue
        
        if hasattr(v, 'id'):
            key_parts.append(f"{k}:id:{v.id}")
        elif isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")
        elif isinstance(v, (list, dict)):
            # Hash collections
            key_parts.append(
                f"{k}:{hashlib.md5(json.dumps(v, sort_keys=True).encode()).hexdigest()[:8]}"
            )
    
    # Generate final key
    key = ":".join(key_parts)
    
    # Hash if too long
    if len(key) > 200:
        key = f"{key_parts[0]}:{hashlib.md5(key.encode()).hexdigest()}"
    
    return key