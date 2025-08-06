"""
Advanced caching strategies for the security system.

Provides multi-layer caching, intelligent cache invalidation,
and distributed cache synchronization.
"""
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
import hashlib
import json
import pickle
from enum import Enum
from collections import OrderedDict
import msgpack

from core.redis import redis_client
from core.logger import get_logger
from models.user import User
from models.feature_permission import FeaturePermission, FeatureType


logger = get_logger(__name__)


class CacheLayer(Enum):
    """Cache layer definitions."""
    L1_MEMORY = "l1_memory"  # In-process memory cache
    L2_REDIS = "l2_redis"    # Redis distributed cache
    L3_DATABASE = "l3_database"  # Database cache tables


class CacheStrategy(Enum):
    """Cache strategy types."""
    WRITE_THROUGH = "write_through"  # Write to cache and DB simultaneously
    WRITE_BACK = "write_back"  # Write to cache first, DB later
    CACHE_ASIDE = "cache_aside"  # Application manages cache
    REFRESH_AHEAD = "refresh_ahead"  # Proactively refresh before expiry


class LRUCache:
    """Thread-safe LRU cache implementation for L1 memory cache."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]["value"]
            self.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set value in cache with TTL."""
        async with self._lock:
            expires_at = time.time() + ttl_seconds
            
            # Remove expired entries
            await self._evict_expired()
            
            # Add new entry
            self.cache[key] = {
                "value": value,
                "expires_at": expires_at
            }
            
            # Evict LRU if over capacity
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    async def delete(self, key: str):
        """Delete key from cache."""
        async with self._lock:
            self.cache.pop(key, None)
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    async def _evict_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if v["expires_at"] < current_time
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0,
            "utilization": len(self.cache) / self.max_size
        }


class MultiLayerCache:
    """Multi-layer caching system with L1 (memory) and L2 (Redis) caches."""
    
    def __init__(
        self,
        l1_max_size: int = 1000,
        l2_ttl_seconds: int = 300,
        enable_compression: bool = True
    ):
        self.l1_cache = LRUCache(max_size=l1_max_size)
        self.l2_ttl = l2_ttl_seconds
        self.enable_compression = enable_compression
        self.metrics = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "writes": 0
        }
    
    async def get(
        self,
        key: str,
        deserializer: Optional[callable] = None
    ) -> Optional[Any]:
        """Get value from cache, checking L1 then L2."""
        # Check L1 cache
        value = await self.l1_cache.get(key)
        if value is not None:
            self.metrics["l1_hits"] += 1
            return value
        
        # Check L2 cache (Redis)
        try:
            redis_value = await redis_client.get(key)
            if redis_value:
                # Deserialize value
                if self.enable_compression:
                    value = msgpack.unpackb(redis_value, raw=False)
                else:
                    value = json.loads(redis_value)
                
                if deserializer:
                    value = deserializer(value)
                
                # Populate L1 cache
                await self.l1_cache.set(key, value, ttl_seconds=60)
                
                self.metrics["l2_hits"] += 1
                return value
        except Exception as e:
            logger.error(f"Error reading from L2 cache: {e}")
        
        self.metrics["misses"] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        serializer: Optional[callable] = None
    ):
        """Set value in both cache layers."""
        if ttl_seconds is None:
            ttl_seconds = self.l2_ttl
        
        # Set in L1 cache
        await self.l1_cache.set(key, value, ttl_seconds=min(ttl_seconds, 300))
        
        # Serialize for L2 cache
        try:
            if serializer:
                value_to_cache = serializer(value)
            else:
                value_to_cache = value
            
            if self.enable_compression:
                serialized = msgpack.packb(value_to_cache)
            else:
                serialized = json.dumps(value_to_cache)
            
            # Set in L2 cache
            await redis_client.setex(key, ttl_seconds, serialized)
            self.metrics["writes"] += 1
        except Exception as e:
            logger.error(f"Error writing to L2 cache: {e}")
    
    async def delete(self, key: str):
        """Delete from all cache layers."""
        await self.l1_cache.delete(key)
        await redis_client.delete(key)
    
    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        # Clear from L1 (simple pattern matching)
        if "*" in pattern:
            prefix = pattern.split("*")[0]
            keys_to_delete = [
                k for k in self.l1_cache.cache.keys()
                if k.startswith(prefix)
            ]
            for key in keys_to_delete:
                await self.l1_cache.delete(key)
        
        # Clear from L2
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor, match=pattern, count=100
            )
            if keys:
                await redis_client.delete(*keys)
            if cursor == 0:
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        l1_stats = self.l1_cache.get_stats()
        total_requests = (
            self.metrics["l1_hits"] +
            self.metrics["l2_hits"] +
            self.metrics["misses"]
        )
        
        return {
            "l1": l1_stats,
            "l2": {
                "hits": self.metrics["l2_hits"],
                "writes": self.metrics["writes"]
            },
            "overall": {
                "total_requests": total_requests,
                "l1_hit_rate": self.metrics["l1_hits"] / total_requests if total_requests > 0 else 0,
                "l2_hit_rate": self.metrics["l2_hits"] / total_requests if total_requests > 0 else 0,
                "miss_rate": self.metrics["misses"] / total_requests if total_requests > 0 else 0
            }
        }


class CacheInvalidator:
    """Intelligent cache invalidation system."""
    
    def __init__(self, cache: MultiLayerCache):
        self.cache = cache
        self.invalidation_rules = {}
        self.dependency_graph = {}
    
    def register_dependency(
        self,
        cache_key_pattern: str,
        depends_on: List[str]
    ):
        """Register cache dependencies for automatic invalidation."""
        self.dependency_graph[cache_key_pattern] = depends_on
    
    async def invalidate(self, key: str):
        """Invalidate a cache key and its dependents."""
        # Direct invalidation
        await self.cache.delete(key)
        
        # Find and invalidate dependent keys
        for pattern, dependencies in self.dependency_graph.items():
            if any(key.startswith(dep) for dep in dependencies):
                await self.cache.delete_pattern(pattern)
    
    async def invalidate_user_permissions(self, user_id: str):
        """Invalidate all permission caches for a user."""
        patterns = [
            f"perm:{user_id[:8]}:*",
            f"user_perms:{user_id}:*",
            f"rate_limit:user:{user_id}:*"
        ]
        
        for pattern in patterns:
            await self.cache.delete_pattern(pattern)
        
        logger.info(f"Invalidated all caches for user {user_id}")
    
    async def invalidate_feature_permissions(
        self,
        feature_type: FeatureType,
        agency_id: Optional[str] = None
    ):
        """Invalidate feature permission caches."""
        if agency_id:
            pattern = f"perm:*:{feature_type.value[:3]}:*:agency:{agency_id[:8]}"
        else:
            pattern = f"perm:*:{feature_type.value[:3]}:*"
        
        await self.cache.delete_pattern(pattern)
        logger.info(f"Invalidated {feature_type.value} permissions cache")


class CacheWarmer:
    """Proactive cache warming system."""
    
    def __init__(
        self,
        cache: MultiLayerCache,
        warm_interval_seconds: int = 300
    ):
        self.cache = cache
        self.warm_interval = warm_interval_seconds
        self.warming_tasks = {}
        self._running = False
    
    async def start(self):
        """Start cache warming background tasks."""
        self._running = True
        asyncio.create_task(self._warm_loop())
        logger.info("Cache warmer started")
    
    async def stop(self):
        """Stop cache warming."""
        self._running = False
        for task in self.warming_tasks.values():
            task.cancel()
        logger.info("Cache warmer stopped")
    
    async def _warm_loop(self):
        """Main warming loop."""
        while self._running:
            try:
                await self._warm_active_users()
                await self._warm_common_permissions()
                await asyncio.sleep(self.warm_interval)
            except Exception as e:
                logger.error(f"Error in cache warming: {e}")
                await asyncio.sleep(60)
    
    async def _warm_active_users(self):
        """Warm cache for recently active users."""
        # Get active users from Redis
        active_users_key = "active_users:last_hour"
        active_users = await redis_client.smembers(active_users_key)
        
        for user_id in active_users:
            # Warm permission cache for each active user
            for feature_type in FeatureType:
                cache_key = f"user_perms:{user_id}:{feature_type.value}"
                
                # Check if already cached
                existing = await self.cache.get(cache_key)
                if not existing:
                    # Would fetch from database and cache
                    # This is a placeholder
                    pass
    
    async def _warm_common_permissions(self):
        """Warm cache for commonly accessed permissions."""
        # Track most accessed permission patterns
        common_patterns = await self._get_common_access_patterns()
        
        for pattern in common_patterns:
            # Pre-fetch and cache common permissions
            # This is a placeholder
            pass
    
    async def _get_common_access_patterns(self) -> List[str]:
        """Get most commonly accessed permission patterns."""
        # Would analyze access logs to find patterns
        # This is a placeholder
        return []


class CacheSynchronizer:
    """Distributed cache synchronization for multi-instance deployments."""
    
    def __init__(self, instance_id: str, cache: MultiLayerCache):
        self.instance_id = instance_id
        self.cache = cache
        self.sync_channel = "cache_sync"
        self._subscription = None
    
    async def start(self):
        """Start listening for cache sync messages."""
        self._subscription = redis_client.pubsub()
        await self._subscription.subscribe(self.sync_channel)
        asyncio.create_task(self._listen_for_updates())
        logger.info(f"Cache synchronizer started for instance {self.instance_id}")
    
    async def stop(self):
        """Stop cache synchronization."""
        if self._subscription:
            await self._subscription.unsubscribe(self.sync_channel)
            await self._subscription.close()
    
    async def broadcast_invalidation(self, key: str):
        """Broadcast cache invalidation to other instances."""
        message = {
            "action": "invalidate",
            "key": key,
            "instance_id": self.instance_id,
            "timestamp": time.time()
        }
        
        await redis_client.publish(
            self.sync_channel,
            json.dumps(message)
        )
    
    async def _listen_for_updates(self):
        """Listen for cache sync messages from other instances."""
        async for message in self._subscription.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    
                    # Ignore messages from self
                    if data["instance_id"] == self.instance_id:
                        continue
                    
                    # Process cache sync action
                    if data["action"] == "invalidate":
                        # Only invalidate L1 cache (L2 is shared)
                        await self.cache.l1_cache.delete(data["key"])
                        
                except Exception as e:
                    logger.error(f"Error processing cache sync message: {e}")


# Global cache instances
multi_layer_cache = MultiLayerCache(
    l1_max_size=2000,
    l2_ttl_seconds=300,
    enable_compression=True
)

cache_invalidator = CacheInvalidator(multi_layer_cache)
cache_warmer = CacheWarmer(multi_layer_cache)
cache_synchronizer = CacheSynchronizer(
    instance_id=f"instance_{int(time.time())}",
    cache=multi_layer_cache
)


async def init_cache_system():
    """Initialize the cache system."""
    await cache_warmer.start()
    await cache_synchronizer.start()
    
    # Register cache dependencies
    cache_invalidator.register_dependency(
        "perm:*:reports:*",
        ["user_perms:*:reports"]
    )
    cache_invalidator.register_dependency(
        "perm:*:analytics:*",
        ["user_perms:*:analytics"]
    )
    
    logger.info("Cache system initialized")


async def shutdown_cache_system():
    """Shutdown the cache system gracefully."""
    await cache_warmer.stop()
    await cache_synchronizer.stop()
    logger.info("Cache system shutdown complete")