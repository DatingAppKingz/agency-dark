"""
Analytics caching strategy implementation.

Provides intelligent caching for analytics data with
cache warming, invalidation, and tiered storage.
"""
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import json
import hashlib
import asyncio
from enum import Enum

import redis.asyncio as redis
from redis.asyncio.lock import Lock

from core.config import settings
from modules.analytics.domain.models import AggregationPeriod


logger = logging.getLogger(__name__)


class CacheTier(str, Enum):
    """Cache storage tiers."""
    HOT = "hot"      # In-memory (Redis)
    WARM = "warm"    # Redis with longer TTL
    COLD = "cold"    # Database or S3


class CacheStrategy:
    """
    Implements multi-tier caching strategy for analytics data.
    
    Features:
    - Multi-tier storage (hot/warm/cold)
    - Intelligent cache warming
    - Pattern-based invalidation
    - Compression for large datasets
    - Distributed locking for cache coherence
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize cache strategy."""
        self.redis = redis_client or redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        
        # Cache configuration
        self.ttl_config = {
            # Hot tier (frequently accessed, short TTL)
            (CacheTier.HOT, AggregationPeriod.HOURLY): 300,      # 5 minutes
            (CacheTier.HOT, AggregationPeriod.DAILY): 900,       # 15 minutes
            
            # Warm tier (moderate access, medium TTL)
            (CacheTier.WARM, AggregationPeriod.HOURLY): 3600,    # 1 hour
            (CacheTier.WARM, AggregationPeriod.DAILY): 86400,    # 24 hours
            (CacheTier.WARM, AggregationPeriod.WEEKLY): 604800,  # 7 days
            
            # Default TTL
            'default': 3600
        }
        
        # Cache key patterns for invalidation
        self.invalidation_patterns = {
            'revenue': 'analytics:*:revenue:*',
            'engagement': 'analytics:*:engagement:*',
            'fans': 'analytics:*:fans:*',
            'all': 'analytics:*'
        }
        
    async def get(
        self,
        key: str,
        tier: CacheTier = CacheTier.HOT
    ) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            tier: Cache tier to check
            
        Returns:
            Cached value or None
        """
        try:
            # Add tier prefix to key
            tiered_key = f"{tier}:{key}"
            
            # Get from Redis
            value = await self.redis.get(tiered_key)
            
            if value:
                # Update access time for LRU
                await self._update_access_time(tiered_key)
                
                # Deserialize
                return json.loads(value)
            
            # Try next tier if not found
            if tier == CacheTier.HOT:
                return await self.get(key, CacheTier.WARM)
            elif tier == CacheTier.WARM:
                return await self._get_from_cold_storage(key)
                
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
            
    async def set(
        self,
        key: str,
        value: Any,
        tier: CacheTier = CacheTier.HOT,
        ttl: Optional[int] = None,
        period: Optional[AggregationPeriod] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            tier: Cache tier
            ttl: Time to live in seconds
            period: Aggregation period for TTL lookup
            
        Returns:
            Success status
        """
        try:
            # Serialize value
            serialized = json.dumps(value, default=str)
            
            # Compress if large
            if len(serialized) > 1024 * 10:  # 10KB threshold
                serialized = await self._compress(serialized)
                key = f"compressed:{key}"
                
            # Determine TTL
            if not ttl:
                if period:
                    ttl = self.ttl_config.get(
                        (tier, period),
                        self.ttl_config['default']
                    )
                else:
                    ttl = self.ttl_config['default']
                    
            # Add tier prefix
            tiered_key = f"{tier}:{key}"
            
            # Set in Redis with TTL
            await self.redis.setex(tiered_key, ttl, serialized)
            
            # Update metadata
            await self._update_cache_metadata(tiered_key, tier, len(serialized))
            
            # Promote to hot tier if accessed from warm
            if tier == CacheTier.WARM:
                await self._promote_to_hot(key, value, period)
                
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
            
    async def delete(self, key: str) -> bool:
        """
        Delete key from all cache tiers.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        try:
            # Delete from all tiers
            keys_to_delete = [
                f"{CacheTier.HOT}:{key}",
                f"{CacheTier.WARM}:{key}",
                f"compressed:{CacheTier.HOT}:{key}",
                f"compressed:{CacheTier.WARM}:{key}"
            ]
            
            deleted = await self.redis.delete(*keys_to_delete)
            
            # Also remove from cold storage
            await self._delete_from_cold_storage(key)
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
            
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Key pattern (supports wildcards)
            
        Returns:
            Number of keys invalidated
        """
        try:
            # Find all matching keys
            invalidated = 0
            
            async for key in self.redis.scan_iter(match=pattern):
                if await self.redis.delete(key):
                    invalidated += 1
                    
            logger.info(f"Invalidated {invalidated} keys matching pattern: {pattern}")
            return invalidated
            
        except Exception as e:
            logger.error(f"Pattern invalidation error for {pattern}: {e}")
            return 0
            
    async def invalidate_analytics(
        self,
        agency_id: str,
        model_id: Optional[str] = None,
        metric_type: Optional[str] = None
    ) -> int:
        """
        Invalidate analytics cache for specific entity.
        
        Args:
            agency_id: Agency ID
            model_id: Optional model ID
            metric_type: Optional metric type to invalidate
            
        Returns:
            Number of keys invalidated
        """
        # Build pattern
        if model_id:
            base_pattern = f"analytics:{agency_id}:{model_id}"
        else:
            base_pattern = f"analytics:{agency_id}:*"
            
        if metric_type and metric_type in self.invalidation_patterns:
            pattern = f"{base_pattern}:{metric_type}:*"
        else:
            pattern = f"{base_pattern}:*"
            
        # Invalidate all tiers
        total_invalidated = 0
        for tier in CacheTier:
            tier_pattern = f"{tier}:{pattern}"
            total_invalidated += await self.invalidate_pattern(tier_pattern)
            
        return total_invalidated
        
    async def warm_cache(
        self,
        keys: List[str],
        data_loader,
        tier: CacheTier = CacheTier.WARM
    ) -> int:
        """
        Pre-warm cache with specified keys.
        
        Args:
            keys: List of cache keys to warm
            data_loader: Async function to load data for a key
            tier: Target cache tier
            
        Returns:
            Number of keys warmed
        """
        warmed = 0
        
        # Batch process keys
        batch_size = 10
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            
            # Load data in parallel
            tasks = []
            for key in batch:
                # Check if already cached
                if not await self.get(key, tier):
                    tasks.append(self._warm_single_key(key, data_loader, tier))
                    
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                warmed += sum(1 for r in results if r is True)
                
        logger.info(f"Warmed {warmed} cache keys in {tier} tier")
        return warmed
        
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics including hit rates, memory usage, etc.
        """
        try:
            info = await self.redis.info()
            
            # Calculate hit rate
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total_requests = hits + misses
            
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
            
            # Get memory info
            memory_info = await self.redis.info('memory')
            
            # Count keys by tier
            tier_counts = {}
            for tier in CacheTier:
                count = 0
                async for _ in self.redis.scan_iter(match=f"{tier}:*"):
                    count += 1
                tier_counts[tier] = count
                
            return {
                'hit_rate': hit_rate,
                'total_hits': hits,
                'total_misses': misses,
                'memory_used': memory_info.get('used_memory_human', 'N/A'),
                'memory_peak': memory_info.get('used_memory_peak_human', 'N/A'),
                'total_keys': await self.redis.dbsize(),
                'keys_by_tier': tier_counts,
                'evicted_keys': info.get('evicted_keys', 0),
                'connected_clients': info.get('connected_clients', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
            
    async def clear_cache(self, pattern: Optional[str] = None) -> int:
        """
        Clear cache, optionally by pattern.
        
        Args:
            pattern: Optional pattern to clear (None clears all)
            
        Returns:
            Number of keys cleared
        """
        if pattern:
            return await self.invalidate_pattern(pattern)
        else:
            # Clear all analytics keys
            return await self.invalidate_pattern("analytics:*")
            
    # Private helper methods
    
    async def _warm_single_key(
        self,
        key: str,
        data_loader,
        tier: CacheTier
    ) -> bool:
        """Warm a single cache key."""
        try:
            # Acquire lock to prevent duplicate warming
            lock_key = f"warming:{key}"
            lock = Lock(self.redis, lock_key, timeout=60)
            
            async with lock:
                # Double-check cache after acquiring lock
                if await self.get(key, tier):
                    return False
                    
                # Load data
                data = await data_loader(key)
                if data:
                    await self.set(key, data, tier)
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error warming key {key}: {e}")
            return False
            
    async def _update_access_time(self, key: str):
        """Update last access time for LRU tracking."""
        access_key = f"access:{key}"
        await self.redis.setex(access_key, 86400, datetime.utcnow().isoformat())
        
    async def _update_cache_metadata(self, key: str, tier: CacheTier, size: int):
        """Update cache metadata for monitoring."""
        metadata = {
            'tier': tier,
            'size': size,
            'created': datetime.utcnow().isoformat()
        }
        
        metadata_key = f"metadata:{key}"
        await self.redis.setex(
            metadata_key,
            86400,  # 24 hour TTL for metadata
            json.dumps(metadata)
        )
        
    async def _promote_to_hot(
        self,
        key: str,
        value: Any,
        period: Optional[AggregationPeriod] = None
    ):
        """Promote frequently accessed item to hot tier."""
        # Check access frequency
        access_key = f"access:{CacheTier.WARM}:{key}"
        access_count = await self.redis.incr(access_key)
        await self.redis.expire(access_key, 3600)  # Reset hourly
        
        # Promote if accessed frequently
        if access_count > 3:  # More than 3 times per hour
            await self.set(key, value, CacheTier.HOT, period=period)
            
    async def _compress(self, data: str) -> str:
        """Compress data for storage."""
        import gzip
        import base64
        
        compressed = gzip.compress(data.encode())
        return base64.b64encode(compressed).decode()
        
    async def _decompress(self, data: str) -> str:
        """Decompress data from storage."""
        import gzip
        import base64
        
        compressed = base64.b64decode(data.encode())
        return gzip.decompress(compressed).decode()
        
    async def _get_from_cold_storage(self, key: str) -> Optional[Any]:
        """Get data from cold storage (database/S3)."""
        # This would be implemented based on cold storage backend
        # For now, return None
        return None
        
    async def _delete_from_cold_storage(self, key: str) -> bool:
        """Delete data from cold storage."""
        # This would be implemented based on cold storage backend
        return True
        
    def generate_cache_key(
        self,
        prefix: str,
        agency_id: str,
        model_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period: Optional[AggregationPeriod] = None,
        **kwargs
    ) -> str:
        """
        Generate consistent cache key.
        
        Args:
            prefix: Key prefix (e.g., 'analytics', 'revenue')
            agency_id: Agency ID
            model_id: Optional model ID
            start_date: Optional start date
            end_date: Optional end date
            period: Optional aggregation period
            **kwargs: Additional key components
            
        Returns:
            Generated cache key
        """
        components = [
            prefix,
            agency_id,
            model_id or 'all'
        ]
        
        if start_date:
            components.append(start_date.strftime('%Y%m%d'))
        if end_date:
            components.append(end_date.strftime('%Y%m%d'))
        if period:
            components.append(period.value)
            
        # Add any additional components
        for key, value in sorted(kwargs.items()):
            if value is not None:
                components.append(str(value))
                
        # Create key
        key = ':'.join(components)
        
        # Add hash for very long keys
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()[:8]
            key = f"{':'.join(components[:3])}:hash:{key_hash}"
            
        return key


# Global cache strategy instance
cache_strategy = CacheStrategy()