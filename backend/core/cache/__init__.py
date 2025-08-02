"""
Cache module initialization and exports.
"""
from .cache_service import (
    cache,
    CacheService,
    CacheKey,
    CacheSerializer,
    CacheStrategy,
    cached,
    cache_aside,
    cache_invalidate
)
from .cache_monitor import (
    monitor,
    manager,
    CacheMonitor,
    CacheManager,
    CacheMetrics
)
from .model_cache import (
    ModelCache,
    FanCache,
    CachePreloader,
    get_cached_model_profile,
    get_cached_user_profile
)

__all__ = [
    # Service
    'cache',
    'CacheService',
    'CacheKey',
    'CacheSerializer',
    'CacheStrategy',
    
    # Decorators
    'cached',
    'cache_aside',
    'cache_invalidate',
    'cache_result',
    'invalidate_cache',
    
    # Monitor
    'monitor',
    'manager',
    'CacheMonitor',
    'CacheManager',
    'CacheMetrics',
    
    # Model cache
    'ModelCache',
    'FanCache',
    'CachePreloader',
    'get_cached_model_profile',
    'get_cached_user_profile'
]

# Aliases for backward compatibility will be added at the end of file


async def initialize_cache():
    """Initialize cache system."""
    # Start monitor
    await monitor.start(interval=60)
    
    # Log initialization
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Cache system initialized")


async def shutdown_cache():
    """Shutdown cache system gracefully."""
    # Stop monitor
    await monitor.stop()
    
    # Clear stats
    await cache.clear_stats()


# Import decorators from core.simple_cache to export them here
try:
    from core.simple_cache import cache_result as _cache_result, invalidate_cache as _invalidate_cache
    cache_result = _cache_result
    invalidate_cache = _invalidate_cache
    # Add them to __all__
    if 'cache_result' not in __all__:
        __all__.extend(['cache_result', 'invalidate_cache'])
except ImportError:
    # If import fails, create stubs that will be replaced at runtime
    cache_result = None
    invalidate_cache = None