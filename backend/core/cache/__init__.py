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