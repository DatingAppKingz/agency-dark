"""
Advanced caching strategies for performance optimization with intelligent tiering
"""
import json
import hashlib
import pickle
import zlib
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Tuple
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from enum import Enum
import asyncio
from redis import asyncio as aioredis
from redis.exceptions import RedisError

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

T = TypeVar("T")


class CacheTier(str, Enum):
    """Cache tier levels"""
    HOT = "hot"           # Frequently accessed, 5 min TTL
    WARM = "warm"         # Moderate access, 1 hour TTL
    COLD = "cold"         # Infrequent access, 24 hour TTL
    PERSISTENT = "persist" # Long-term cache, 7 days TTL


class CacheManager:
    """Advanced cache management with intelligent tiering and optimization"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None
        
        # Cache configuration
        self.default_ttl = 3600  # 1 hour
        self.max_ttl = 604800    # 7 days
        
        # Enhanced cache tiers with compression settings
        self.tiers = {
            CacheTier.HOT: {
                "ttl": 300,
                "prefix": "hot:",
                "compress": False,
                "max_size": 1000000,  # 1MB
                "serialize": "json"
            },
            CacheTier.WARM: {
                "ttl": 3600,
                "prefix": "warm:",
                "compress": True,
                "max_size": 5000000,  # 5MB
                "serialize": "json"
            },
            CacheTier.COLD: {
                "ttl": 86400,
                "prefix": "cold:",
                "compress": True,
                "max_size": 10000000,  # 10MB
                "serialize": "pickle"
            },
            CacheTier.PERSISTENT: {
                "ttl": 604800,
                "prefix": "persist:",
                "compress": True,
                "max_size": 50000000,  # 50MB
                "serialize": "pickle"
            }
        }
        
        # Access tracking for intelligent promotion
        self._access_counts = defaultdict(int)
        self._access_times = defaultdict(list)
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "promotions": 0,
            "evictions": 0,
            "compression_saved": 0
        }
    
    async def connect(self):
        """Connect to Redis"""
        if not self._redis:
            self._redis = await aioredis.from_url(
                self.redis_url,
                decode_responses=False  # We handle encoding/decoding ourselves
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
        namespace: str = "default",
        tier: Optional[CacheTier] = None
    ) -> Optional[Any]:
        """Get value from cache with intelligent tier checking"""
        try:
            redis = await self.redis
            
            # Check specific tier or all tiers
            tiers_to_check = [tier] if tier else [
                CacheTier.HOT, CacheTier.WARM, CacheTier.COLD, CacheTier.PERSISTENT
            ]
            
            for check_tier in tiers_to_check:
                tier_config = self.tiers[check_tier]
                cache_key = self._generate_key(
                    f"{tier_config['prefix']}{namespace}", key
                )
                
                value = await redis.get(cache_key)
                if value:
                    self._stats["hits"] += 1
                    
                    # Track access for promotion
                    self._track_access(key, check_tier)
                    
                    # Deserialize and decompress
                    deserialized = await self._deserialize_value(
                        value, tier_config
                    )
                    
                    # Promote if frequently accessed
                    if check_tier != CacheTier.HOT:
                        await self._promote_if_hot(key, deserialized, check_tier)
                    
                    return deserialized
            
            self._stats["misses"] += 1
            return None
            
        except RedisError as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default",
        tier: CacheTier = CacheTier.WARM
    ) -> bool:
        """Set value in cache with intelligent tiering and compression"""
        try:
            redis = await self.redis
            tier_config = self.tiers[tier]
            
            cache_key = self._generate_key(
                f"{tier_config['prefix']}{namespace}", key
            )
            
            # Serialize and compress
            serialized = await self._serialize_value(value, tier_config)
            
            # Check size limits
            if len(serialized) > tier_config["max_size"]:
                logger.warning(f"Value too large for tier {tier}: {len(serialized)} bytes")
                # Try next tier
                if tier == CacheTier.HOT:
                    return await self.set(key, value, ttl, namespace, CacheTier.WARM)
                elif tier == CacheTier.WARM:
                    return await self.set(key, value, ttl, namespace, CacheTier.COLD)
                else:
                    return False
            
            ttl = ttl or tier_config["ttl"]
            ttl = min(ttl, self.max_ttl)
            
            await redis.setex(cache_key, ttl, serialized)
            
            # Track for statistics
            if tier_config["compress"]:
                original_size = len(str(value).encode())
                self._stats["compression_saved"] += original_size - len(serialized)
            
            return True
            
        except RedisError as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def _serialize_value(self, value: Any, tier_config: Dict[str, Any]) -> bytes:
        """Serialize and optionally compress value"""
        # Choose serialization method
        if tier_config["serialize"] == "json":
            serialized = json.dumps(value).encode()
        else:  # pickle
            serialized = pickle.dumps(value)
        
        # Compress if needed
        if tier_config["compress"] and len(serialized) > 1000:  # Only compress larger values
            compressed = zlib.compress(serialized, level=6)
            # Only use compressed if it's actually smaller
            if len(compressed) < len(serialized):
                return b"COMPRESSED:" + compressed
        
        return serialized
    
    async def _deserialize_value(self, data: Union[str, bytes], tier_config: Dict[str, Any]) -> Any:
        """Deserialize and decompress value"""
        # Handle string data from Redis
        if isinstance(data, str):
            data = data.encode()
        
        # Check if compressed
        if data.startswith(b"COMPRESSED:"):
            data = zlib.decompress(data[11:])  # Skip "COMPRESSED:" prefix
        
        # Deserialize
        if tier_config["serialize"] == "json":
            return json.loads(data.decode())
        else:  # pickle
            return pickle.loads(data)
    
    def _track_access(self, key: str, tier: CacheTier):
        """Track access patterns for cache optimization"""
        self._access_counts[key] += 1
        
        # Keep only recent access times (last 100)
        access_times = self._access_times[key]
        access_times.append(datetime.utcnow())
        if len(access_times) > 100:
            access_times.pop(0)
    
    async def _promote_if_hot(self, key: str, value: Any, current_tier: CacheTier):
        """Promote frequently accessed items to hotter tiers"""
        access_count = self._access_counts.get(key, 0)
        access_times = self._access_times.get(key, [])
        
        # Calculate access frequency (accesses per hour)
        if len(access_times) >= 5:
            time_span = (access_times[-1] - access_times[0]).total_seconds() / 3600
            if time_span > 0:
                access_frequency = len(access_times) / time_span
                
                # Promotion thresholds
                if current_tier == CacheTier.COLD and access_frequency > 10:
                    # Promote to WARM
                    await self.set(key, value, tier=CacheTier.WARM)
                    self._stats["promotions"] += 1
                    logger.info(f"Promoted key {key} from COLD to WARM tier")
                elif current_tier == CacheTier.WARM and access_frequency > 50:
                    # Promote to HOT
                    await self.set(key, value, tier=CacheTier.HOT)
                    self._stats["promotions"] += 1
                    logger.info(f"Promoted key {key} from WARM to HOT tier")
    
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
    
    # Batch operations
    async def mget(
        self,
        keys: List[str],
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get multiple values from cache efficiently"""
        try:
            redis = await self.redis
            results = {}
            
            # Check all tiers
            for tier in [CacheTier.HOT, CacheTier.WARM, CacheTier.COLD, CacheTier.PERSISTENT]:
                tier_config = self.tiers[tier]
                
                # Build cache keys
                cache_keys = [
                    self._generate_key(f"{tier_config['prefix']}{namespace}", key)
                    for key in keys if key not in results
                ]
                
                if cache_keys:
                    # Batch get
                    values = await redis.mget(cache_keys)
                    
                    # Process results
                    for i, value in enumerate(values):
                        if value is not None:
                            key = keys[i]
                            try:
                                results[key] = await self._deserialize_value(value, tier_config)
                                self._track_access(key, tier)
                                self._stats["hits"] += 1
                            except Exception as e:
                                logger.error(f"Error deserializing {key}: {e}")
            
            # Track misses
            for key in keys:
                if key not in results:
                    self._stats["misses"] += 1
            
            return results
            
        except RedisError as e:
            logger.error(f"Redis mget error: {e}")
            return {}
    
    async def mset(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
        namespace: str = "default",
        tier: CacheTier = CacheTier.WARM
    ) -> bool:
        """Set multiple values in cache efficiently"""
        try:
            redis = await self.redis
            tier_config = self.tiers[tier]
            
            # Prepare pipeline
            pipe = redis.pipeline()
            successful_keys = []
            
            for key, value in items.items():
                try:
                    cache_key = self._generate_key(
                        f"{tier_config['prefix']}{namespace}", key
                    )
                    
                    # Serialize value
                    serialized = await self._serialize_value(value, tier_config)
                    
                    # Check size limit
                    if len(serialized) <= tier_config["max_size"]:
                        pipe.setex(
                            cache_key,
                            ttl or tier_config["ttl"],
                            serialized
                        )
                        successful_keys.append(key)
                    else:
                        logger.warning(f"Value too large for key {key}")
                        
                except Exception as e:
                    logger.error(f"Error serializing {key}: {e}")
            
            # Execute pipeline
            if successful_keys:
                await pipe.execute()
                
                # Update statistics
                if tier_config["compress"]:
                    for key in successful_keys:
                        original_size = len(str(items[key]).encode())
                        self._stats["compression_saved"] += original_size // 2  # Approximate
            
            return len(successful_keys) == len(items)
            
        except RedisError as e:
            logger.error(f"Redis mset error: {e}")
            return False
    
    async def mdelete(
        self,
        keys: List[str],
        namespace: str = "default"
    ) -> int:
        """Delete multiple keys from cache"""
        try:
            redis = await self.redis
            deleted_count = 0
            
            # Delete from all tiers
            for tier in [CacheTier.HOT, CacheTier.WARM, CacheTier.COLD, CacheTier.PERSISTENT]:
                tier_config = self.tiers[tier]
                
                cache_keys = [
                    self._generate_key(f"{tier_config['prefix']}{namespace}", key)
                    for key in keys
                ]
                
                if cache_keys:
                    deleted_count += await redis.delete(*cache_keys)
            
            # Clear access tracking
            for key in keys:
                self._access_counts.pop(key, None)
                self._access_times.pop(key, None)
            
            return deleted_count
            
        except RedisError as e:
            logger.error(f"Redis mdelete error: {e}")
            return 0
    
    # Enhanced statistics
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            redis = await self.redis
            info = await redis.info()
            
            # Calculate tier-specific stats
            tier_stats = {}
            for tier in CacheTier:
                tier_config = self.tiers[tier]
                pattern = self._generate_key(f"{tier_config['prefix']}*", "")
                
                # Count keys per tier
                keys_count = 0
                async for _ in redis.scan_iter(match=pattern):
                    keys_count += 1
                
                tier_stats[tier.value] = {
                    "keys": keys_count,
                    "ttl": tier_config["ttl"],
                    "compress": tier_config["compress"],
                    "max_size": tier_config["max_size"]
                }
            
            # Calculate access patterns
            hot_keys = sorted(
                self._access_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return {
                # Redis stats
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
                "expired_keys": info.get("expired_keys", 0),
                
                # Custom stats
                "tier_stats": tier_stats,
                "hot_keys": [{"key": k, "accesses": v} for k, v in hot_keys],
                "custom_stats": self._stats,
                "compression_ratio": self._calculate_compression_ratio(),
                
                # Performance metrics
                "avg_access_per_key": (
                    sum(self._access_counts.values()) / len(self._access_counts)
                    if self._access_counts else 0
                ),
                "total_keys_tracked": len(self._access_counts)
            }
        except RedisError as e:
            logger.error(f"Redis stats error: {e}")
            return {}
    
    def _calculate_compression_ratio(self) -> float:
        """Calculate overall compression ratio"""
        if self._stats["compression_saved"] == 0:
            return 0.0
        
        # Estimate based on saved bytes
        estimated_original = self._stats["compression_saved"] * 2
        if estimated_original > 0:
            return round(
                self._stats["compression_saved"] / estimated_original * 100, 2
            )
        return 0.0
    
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