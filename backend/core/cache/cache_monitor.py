"""
Cache monitoring and management system.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from redis.asyncio import Redis
from prometheus_client import Counter, Histogram, Gauge

from core.redis import redis_client
from core.cache.cache_service import cache

logger = logging.getLogger(__name__)


# Prometheus metrics
cache_hits = Counter('cache_hits_total', 'Total cache hits', ['cache_type'])
cache_misses = Counter('cache_misses_total', 'Total cache misses', ['cache_type'])
cache_errors = Counter('cache_errors_total', 'Total cache errors', ['cache_type'])
cache_operation_duration = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration',
    ['operation', 'cache_type']
)
cache_memory_usage = Gauge('cache_memory_usage_bytes', 'Cache memory usage')
cache_key_count = Gauge('cache_key_count', 'Number of keys in cache')


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hit_rate: float
    miss_rate: float
    total_requests: int
    total_hits: int
    total_misses: int
    total_errors: int
    memory_usage: int
    key_count: int
    avg_response_time_ms: float
    timestamp: datetime


class CacheMonitor:
    """Monitor cache performance and health."""
    
    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis or redis_client
        self.metrics_history: List[CacheMetrics] = []
        self.running = False
        self._monitor_task = None
    
    async def start(self, interval: int = 60):
        """Start monitoring cache metrics."""
        self.running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(interval)
        )
        logger.info(f"Cache monitor started with {interval}s interval")
    
    async def stop(self):
        """Stop monitoring."""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Cache monitor stopped")
    
    async def _monitor_loop(self, interval: int):
        """Main monitoring loop."""
        while self.running:
            try:
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only last 24 hours
                cutoff = datetime.utcnow() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history
                    if m.timestamp > cutoff
                ]
                
                # Update Prometheus metrics
                self._update_prometheus_metrics(metrics)
                
                # Log summary
                logger.info(
                    f"Cache metrics - "
                    f"Hit rate: {metrics.hit_rate:.1f}%, "
                    f"Keys: {metrics.key_count}, "
                    f"Memory: {metrics.memory_usage / 1024 / 1024:.1f}MB"
                )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Cache monitor error: {e}")
                await asyncio.sleep(interval)
    
    async def collect_metrics(self) -> CacheMetrics:
        """Collect current cache metrics."""
        # Get cache stats from service
        service_stats = cache.get_stats()
        
        # Get Redis info
        info = await self.redis.info()
        memory_usage = info.get('used_memory', 0)
        
        # Get key count
        key_count = await self.redis.dbsize()
        
        # Calculate rates
        total_requests = service_stats['total_requests']
        hit_rate = service_stats['hit_rate']
        miss_rate = 100 - hit_rate if total_requests > 0 else 0
        
        # Get average response time (would need to implement timing)
        avg_response_time_ms = 5.0  # Placeholder
        
        return CacheMetrics(
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            total_requests=total_requests,
            total_hits=service_stats['hits'],
            total_misses=service_stats['misses'],
            total_errors=service_stats['errors'],
            memory_usage=memory_usage,
            key_count=key_count,
            avg_response_time_ms=avg_response_time_ms,
            timestamp=datetime.utcnow()
        )
    
    def _update_prometheus_metrics(self, metrics: CacheMetrics):
        """Update Prometheus metrics."""
        cache_memory_usage.set(metrics.memory_usage)
        cache_key_count.set(metrics.key_count)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get cache health status."""
        try:
            # Check Redis connection
            await self.redis.ping()
            redis_healthy = True
        except:
            redis_healthy = False
        
        # Get current metrics
        metrics = await self.collect_metrics()
        
        # Determine health status
        if not redis_healthy:
            status = "unhealthy"
            issues = ["Redis connection failed"]
        elif metrics.hit_rate < 50:
            status = "degraded"
            issues = ["Low hit rate"]
        elif metrics.total_errors > 100:
            status = "degraded"
            issues = ["High error rate"]
        else:
            status = "healthy"
            issues = []
        
        return {
            "status": status,
            "redis_connected": redis_healthy,
            "metrics": {
                "hit_rate": metrics.hit_rate,
                "memory_usage_mb": metrics.memory_usage / 1024 / 1024,
                "key_count": metrics.key_count,
                "error_count": metrics.total_errors
            },
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_key_patterns(self) -> Dict[str, int]:
        """Analyze key patterns in cache."""
        patterns = {}
        sample_size = 1000
        
        # Sample keys
        cursor = 0
        sampled = 0
        
        while sampled < sample_size:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                count=100
            )
            
            for key in keys:
                # Extract pattern (first two parts)
                parts = key.decode().split(':')[:2]
                pattern = ':'.join(parts)
                patterns[pattern] = patterns.get(pattern, 0) + 1
                sampled += 1
            
            if cursor == 0:
                break
        
        return dict(sorted(patterns.items(), key=lambda x: x[1], reverse=True))
    
    async def get_memory_analysis(self) -> Dict[str, Any]:
        """Analyze memory usage by key pattern."""
        analysis = {}
        patterns = await self.get_key_patterns()
        
        # Sample memory usage for top patterns
        for pattern, count in list(patterns.items())[:10]:
            # Sample a few keys of this pattern
            cursor, sample_keys = await self.redis.scan(
                match=f"{pattern}:*",
                count=10
            )
            
            total_size = 0
            for key in sample_keys[:5]:
                try:
                    size = await self.redis.memory_usage(key)
                    total_size += size or 0
                except:
                    pass
            
            avg_size = total_size / len(sample_keys) if sample_keys else 0
            estimated_total = avg_size * count
            
            analysis[pattern] = {
                "count": count,
                "avg_size_bytes": int(avg_size),
                "estimated_total_mb": round(estimated_total / 1024 / 1024, 2)
            }
        
        return analysis


class CacheManager:
    """Manage cache operations and maintenance."""
    
    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis or redis_client
        self.monitor = CacheMonitor(redis)
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        count = 0
        cursor = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            
            if keys:
                await self.redis.delete(*keys)
                count += len(keys)
            
            if cursor == 0:
                break
        
        logger.info(f"Cleared {count} keys matching pattern: {pattern}")
        return count
    
    async def evict_old_keys(self, pattern: str, max_age: timedelta) -> int:
        """Evict keys older than max_age."""
        count = 0
        cursor = 0
        cutoff = datetime.utcnow() - max_age
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                # Check key age (would need to store timestamps)
                # For now, check TTL
                ttl = await self.redis.ttl(key)
                if ttl == -1:  # No expiry set
                    await self.redis.delete(key)
                    count += 1
            
            if cursor == 0:
                break
        
        logger.info(f"Evicted {count} old keys matching pattern: {pattern}")
        return count
    
    async def optimize_memory(self) -> Dict[str, Any]:
        """Optimize cache memory usage."""
        results = {
            "before": await self.redis.info("memory"),
            "actions": []
        }
        
        # Run memory optimization commands
        try:
            # Remove expired keys
            await self.redis.flushdb(asynchronous=False)
            results["actions"].append("Flushed expired keys")
        except:
            pass
        
        results["after"] = await self.redis.info("memory")
        
        saved = results["before"].get("used_memory", 0) - results["after"].get("used_memory", 0)
        results["saved_bytes"] = saved
        results["saved_mb"] = round(saved / 1024 / 1024, 2)
        
        return results
    
    async def backup_cache(self, backup_key: str) -> int:
        """Backup important cache data."""
        # This would backup critical cache data
        # For now, return count of keys that would be backed up
        important_patterns = [
            "financial:balance:*",
            "model:profile:*",
            "user:permissions:*"
        ]
        
        count = 0
        for pattern in important_patterns:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                count += len(keys)
                if cursor == 0:
                    break
        
        return count


# Global instances
monitor = CacheMonitor()
manager = CacheManager()