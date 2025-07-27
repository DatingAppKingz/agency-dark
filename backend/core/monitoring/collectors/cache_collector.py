"""
Cache metrics collector for Redis performance monitoring.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.monitoring.models import Metric, MetricType
from core.redis import redis_client
from core.database import get_db
from core.config import settings

logger = logging.getLogger(__name__)


class CacheMetricsCollector:
    """Collects cache-related metrics from Redis."""
    
    def __init__(self):
        self.collection_interval = 60  # seconds
        self.is_running = False
        self.last_stats = {}
        
    async def start(self):
        """Start the metrics collection loop."""
        self.is_running = True
        logger.info("Starting cache metrics collector")
        
        while self.is_running:
            try:
                async for db in get_db():
                    await self.collect_all_metrics(db)
                    break
            except Exception as e:
                logger.error(f"Error collecting cache metrics: {e}")
            
            await asyncio.sleep(self.collection_interval)
    
    async def stop(self):
        """Stop the metrics collection."""
        self.is_running = False
        logger.info("Stopping cache metrics collector")
    
    async def collect_all_metrics(self, db: AsyncSession):
        """Collect all cache metrics."""
        timestamp = datetime.utcnow()
        metrics = []
        
        try:
            # Get Redis info
            info = await redis_client.info()
            
            # Memory metrics
            memory_metrics = self._collect_memory_metrics(info, timestamp)
            metrics.extend(memory_metrics)
            
            # Performance metrics
            performance_metrics = self._collect_performance_metrics(info, timestamp)
            metrics.extend(performance_metrics)
            
            # Connection metrics
            connection_metrics = self._collect_connection_metrics(info, timestamp)
            metrics.extend(connection_metrics)
            
            # Keyspace metrics
            keyspace_metrics = await self._collect_keyspace_metrics(info, timestamp)
            metrics.extend(keyspace_metrics)
            
            # Save current stats for rate calculations
            self.last_stats = info
            
            # Save all metrics
            if metrics:
                db.add_all(metrics)
                await db.commit()
                logger.debug(f"Collected {len(metrics)} cache metrics")
        
        except Exception as e:
            logger.error(f"Error collecting cache metrics: {e}")
    
    def _collect_memory_metrics(self, info: Dict, timestamp: datetime) -> List[Metric]:
        """Collect memory-related metrics."""
        metrics = []
        
        # Memory usage
        if 'used_memory' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_MEMORY_USAGE,
                metric_name="cache_memory_used_bytes",
                value=float(info['used_memory']),
                unit="bytes",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Memory RSS (resident set size)
        if 'used_memory_rss' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_MEMORY_USAGE,
                metric_name="cache_memory_rss_bytes",
                value=float(info['used_memory_rss']),
                unit="bytes",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Memory peak
        if 'used_memory_peak' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_MEMORY_USAGE,
                metric_name="cache_memory_peak_bytes",
                value=float(info['used_memory_peak']),
                unit="bytes",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Memory fragmentation ratio
        if 'mem_fragmentation_ratio' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_MEMORY_USAGE,
                metric_name="cache_memory_fragmentation_ratio",
                value=float(info['mem_fragmentation_ratio']),
                unit="ratio",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        return metrics
    
    def _collect_performance_metrics(self, info: Dict, timestamp: datetime) -> List[Metric]:
        """Collect performance-related metrics."""
        metrics = []
        
        # Hit rate calculation
        keyspace_hits = float(info.get('keyspace_hits', 0))
        keyspace_misses = float(info.get('keyspace_misses', 0))
        total_commands = keyspace_hits + keyspace_misses
        
        if total_commands > 0:
            hit_rate = (keyspace_hits / total_commands) * 100
            metrics.append(Metric(
                metric_type=MetricType.CACHE_HIT_RATE,
                metric_name="cache_hit_rate_percent",
                value=hit_rate,
                unit="percent",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Total hits
        metrics.append(Metric(
            metric_type=MetricType.CACHE_HIT_RATE,
            metric_name="cache_hits_total",
            value=keyspace_hits,
            unit="count",
            hostname=settings.HOSTNAME,
            service_name="cache",
            timestamp=timestamp
        ))
        
        # Total misses
        metrics.append(Metric(
            metric_type=MetricType.CACHE_HIT_RATE,
            metric_name="cache_misses_total",
            value=keyspace_misses,
            unit="count",
            hostname=settings.HOSTNAME,
            service_name="cache",
            timestamp=timestamp
        ))
        
        # Operations per second
        if 'instantaneous_ops_per_sec' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_ops_per_second",
                value=float(info['instantaneous_ops_per_sec']),
                unit="ops/sec",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Total commands processed
        if 'total_commands_processed' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_commands_total",
                value=float(info['total_commands_processed']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Evicted keys
        if 'evicted_keys' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_evicted_keys_total",
                value=float(info['evicted_keys']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Expired keys
        if 'expired_keys' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_expired_keys_total",
                value=float(info['expired_keys']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        return metrics
    
    def _collect_connection_metrics(self, info: Dict, timestamp: datetime) -> List[Metric]:
        """Collect connection-related metrics."""
        metrics = []
        
        # Connected clients
        if 'connected_clients' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_connected_clients",
                value=float(info['connected_clients']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Blocked clients
        if 'blocked_clients' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_blocked_clients",
                value=float(info['blocked_clients']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        # Rejected connections
        if 'rejected_connections' in info:
            metrics.append(Metric(
                metric_type=MetricType.CACHE_OPERATIONS,
                metric_name="cache_rejected_connections_total",
                value=float(info['rejected_connections']),
                unit="count",
                hostname=settings.HOSTNAME,
                service_name="cache",
                timestamp=timestamp
            ))
        
        return metrics
    
    async def _collect_keyspace_metrics(self, info: Dict, timestamp: datetime) -> List[Metric]:
        """Collect keyspace-related metrics."""
        metrics = []
        
        # Total keys across all databases
        total_keys = 0
        total_expires = 0
        
        for key, value in info.items():
            if key.startswith('db'):
                db_num = key[2:]  # Extract database number
                if isinstance(value, dict):
                    keys = value.get('keys', 0)
                    expires = value.get('expires', 0)
                    
                    total_keys += keys
                    total_expires += expires
                    
                    # Keys per database
                    metrics.append(Metric(
                        metric_type=MetricType.CACHE_OPERATIONS,
                        metric_name="cache_keys_total",
                        value=float(keys),
                        unit="count",
                        tags={"database": db_num},
                        hostname=settings.HOSTNAME,
                        service_name="cache",
                        timestamp=timestamp
                    ))
                    
                    # Keys with expiration
                    metrics.append(Metric(
                        metric_type=MetricType.CACHE_OPERATIONS,
                        metric_name="cache_keys_with_ttl",
                        value=float(expires),
                        unit="count",
                        tags={"database": db_num},
                        hostname=settings.HOSTNAME,
                        service_name="cache",
                        timestamp=timestamp
                    ))
        
        # Total keys across all databases
        metrics.append(Metric(
            metric_type=MetricType.CACHE_OPERATIONS,
            metric_name="cache_total_keys",
            value=float(total_keys),
            unit="count",
            hostname=settings.HOSTNAME,
            service_name="cache",
            timestamp=timestamp
        ))
        
        # Analyze key patterns (sample-based)
        try:
            # Sample keys to understand patterns
            sample_size = min(100, total_keys)
            if sample_size > 0:
                keys = await redis_client.keys('*')
                sample_keys = keys[:sample_size] if keys else []
                
                # Count keys by prefix
                prefix_counts = {}
                for key in sample_keys:
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')
                    prefix = key.split(':')[0] if ':' in key else 'other'
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                
                # Create metrics for key patterns
                for prefix, count in prefix_counts.items():
                    estimated_total = (count / sample_size) * total_keys
                    metrics.append(Metric(
                        metric_type=MetricType.CACHE_OPERATIONS,
                        metric_name="cache_keys_by_pattern",
                        value=float(estimated_total),
                        unit="count",
                        tags={"pattern": prefix},
                        hostname=settings.HOSTNAME,
                        service_name="cache",
                        timestamp=timestamp
                    ))
        
        except Exception as e:
            logger.error(f"Error analyzing key patterns: {e}")
        
        return metrics
    
    async def analyze_cache_performance(self, db: AsyncSession, hours: int = 24) -> Dict[str, Any]:
        """Analyze cache performance over time."""
        from datetime import timedelta
        from sqlalchemy import select, func
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get average hit rate
        hit_rate_result = await db.execute(
            select(func.avg(Metric.value)).where(
                Metric.metric_name == "cache_hit_rate_percent",
                Metric.timestamp >= since
            )
        )
        avg_hit_rate = hit_rate_result.scalar() or 0
        
        # Get memory usage trend
        memory_result = await db.execute(
            select(
                func.avg(Metric.value),
                func.max(Metric.value)
            ).where(
                Metric.metric_name == "cache_memory_used_bytes",
                Metric.timestamp >= since
            )
        )
        avg_memory, max_memory = memory_result.first() or (0, 0)
        
        # Get operations per second
        ops_result = await db.execute(
            select(func.avg(Metric.value)).where(
                Metric.metric_name == "cache_ops_per_second",
                Metric.timestamp >= since
            )
        )
        avg_ops = ops_result.scalar() or 0
        
        return {
            "period_hours": hours,
            "avg_hit_rate_percent": round(avg_hit_rate, 2),
            "avg_memory_mb": round((avg_memory or 0) / 1024 / 1024, 2),
            "max_memory_mb": round((max_memory or 0) / 1024 / 1024, 2),
            "avg_ops_per_second": round(avg_ops, 2),
            "recommendations": self._generate_recommendations(avg_hit_rate, avg_memory)
        }
    
    def _generate_recommendations(self, hit_rate: float, memory_bytes: float) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        if hit_rate < 80:
            recommendations.append("Cache hit rate is below 80%. Consider reviewing cache key strategies.")
        
        if memory_bytes > 1024 * 1024 * 1024:  # > 1GB
            recommendations.append("High memory usage detected. Consider implementing cache eviction policies.")
        
        return recommendations


# Global instance
cache_collector = CacheMetricsCollector()