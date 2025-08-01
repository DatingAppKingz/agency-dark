"""
Performance Monitoring Dashboard

Real-time performance monitoring with:
- Request/response time tracking
- Database query performance
- Cache hit rates
- Resource utilization
- Bottleneck detection
"""
import asyncio
import time
import psutil
import gc
from typing import Dict, Any, List, Optional, Deque
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
import statistics

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import prometheus_client

from core.logger import get_logger
from core.redis import redis_client

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    timestamp: float
    duration: float
    endpoint: str
    method: str
    status_code: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryMetric:
    """Database query metric."""
    timestamp: float
    duration: float
    query_type: str
    table: str
    row_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """Comprehensive performance monitoring system."""
    
    def __init__(self):
        # Metrics storage (in-memory circular buffers)
        self.request_metrics: Deque[PerformanceMetric] = deque(maxlen=10000)
        self.query_metrics: Deque[QueryMetric] = deque(maxlen=10000)
        self.cache_metrics = defaultdict(lambda: {"hits": 0, "misses": 0})
        
        # Real-time stats
        self.active_requests = 0
        self.total_requests = 0
        self.total_errors = 0
        
        # Resource monitoring
        self.last_resource_check = time.time()
        self.resource_history: Deque[Dict[str, Any]] = deque(maxlen=60)  # 1 minute
        
        # Prometheus metrics
        self._setup_prometheus_metrics()
        
        # Start background monitoring
        self._monitoring_task = None
    
    def _setup_prometheus_metrics(self):
        """Set up Prometheus metrics."""
        self.request_duration = prometheus_client.Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint', 'status']
        )
        
        self.db_query_duration = prometheus_client.Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['query_type', 'table']
        )
        
        self.cache_hit_rate = prometheus_client.Gauge(
            'cache_hit_rate',
            'Cache hit rate percentage',
            ['cache_type']
        )
        
        self.active_connections = prometheus_client.Gauge(
            'active_db_connections',
            'Active database connections'
        )
        
        self.memory_usage = prometheus_client.Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes'
        )
        
        self.cpu_usage = prometheus_client.Gauge(
            'cpu_usage_percent',
            'CPU usage percentage'
        )
    
    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitor_resources())
            logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Performance monitoring stopped")
    
    async def track_request(
        self,
        request: Request,
        response: Response,
        duration: float
    ):
        """Track HTTP request performance."""
        endpoint = str(request.url.path)
        method = request.method
        status_code = response.status_code
        
        # Store metric
        metric = PerformanceMetric(
            timestamp=time.time(),
            duration=duration,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            metadata={
                "client_host": request.client.host if request.client else None,
                "content_length": response.headers.get("content-length", 0)
            }
        )
        self.request_metrics.append(metric)
        
        # Update counters
        self.total_requests += 1
        if status_code >= 400:
            self.total_errors += 1
        
        # Update Prometheus metrics
        self.request_duration.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).observe(duration)
    
    async def track_query(
        self,
        query_type: str,
        table: str,
        duration: float,
        row_count: int = 0
    ):
        """Track database query performance."""
        metric = QueryMetric(
            timestamp=time.time(),
            duration=duration,
            query_type=query_type,
            table=table,
            row_count=row_count
        )
        self.query_metrics.append(metric)
        
        # Update Prometheus metrics
        self.db_query_duration.labels(
            query_type=query_type,
            table=table
        ).observe(duration)
    
    def track_cache_access(self, cache_type: str, hit: bool):
        """Track cache access."""
        if hit:
            self.cache_metrics[cache_type]["hits"] += 1
        else:
            self.cache_metrics[cache_type]["misses"] += 1
        
        # Update Prometheus metric
        total = (
            self.cache_metrics[cache_type]["hits"] +
            self.cache_metrics[cache_type]["misses"]
        )
        if total > 0:
            hit_rate = self.cache_metrics[cache_type]["hits"] / total * 100
            self.cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)
    
    async def get_performance_summary(
        self,
        time_window: int = 300  # 5 minutes
    ) -> Dict[str, Any]:
        """Get performance summary for the specified time window."""
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Filter recent metrics
        recent_requests = [
            m for m in self.request_metrics
            if m.timestamp >= cutoff_time
        ]
        recent_queries = [
            m for m in self.query_metrics
            if m.timestamp >= cutoff_time
        ]
        
        # Calculate request statistics
        request_stats = self._calculate_request_stats(recent_requests)
        query_stats = self._calculate_query_stats(recent_queries)
        
        # Get resource usage
        resource_usage = self._get_current_resource_usage()
        
        # Calculate cache statistics
        cache_stats = {}
        for cache_type, metrics in self.cache_metrics.items():
            total = metrics["hits"] + metrics["misses"]
            if total > 0:
                cache_stats[cache_type] = {
                    "hit_rate": metrics["hits"] / total * 100,
                    "total_accesses": total
                }
        
        return {
            "time_window_seconds": time_window,
            "requests": request_stats,
            "queries": query_stats,
            "cache": cache_stats,
            "resources": resource_usage,
            "health_score": self._calculate_health_score(
                request_stats,
                query_stats,
                resource_usage
            )
        }
    
    async def get_endpoint_metrics(
        self,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed metrics for specific endpoint(s)."""
        metrics_by_endpoint = defaultdict(list)
        
        for metric in self.request_metrics:
            if endpoint is None or metric.endpoint == endpoint:
                metrics_by_endpoint[metric.endpoint].append(metric)
        
        results = {}
        for ep, metrics in metrics_by_endpoint.items():
            if metrics:
                durations = [m.duration for m in metrics]
                results[ep] = {
                    "count": len(metrics),
                    "avg_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "p95_duration": self._percentile(durations, 95),
                    "p99_duration": self._percentile(durations, 99),
                    "error_rate": sum(
                        1 for m in metrics if m.status_code >= 400
                    ) / len(metrics) * 100
                }
        
        return results
    
    async def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """Detect performance bottlenecks."""
        bottlenecks = []
        
        # Check slow endpoints
        endpoint_metrics = await self.get_endpoint_metrics()
        for endpoint, stats in endpoint_metrics.items():
            if stats["p95_duration"] > 1.0:  # 1 second threshold
                bottlenecks.append({
                    "type": "slow_endpoint",
                    "endpoint": endpoint,
                    "p95_duration": stats["p95_duration"],
                    "recommendation": "Consider optimizing queries or adding caching"
                })
        
        # Check slow queries
        query_groups = defaultdict(list)
        for metric in self.query_metrics:
            key = f"{metric.query_type}:{metric.table}"
            query_groups[key].append(metric.duration)
        
        for query_key, durations in query_groups.items():
            avg_duration = statistics.mean(durations)
            if avg_duration > 0.5:  # 500ms threshold
                bottlenecks.append({
                    "type": "slow_query",
                    "query": query_key,
                    "avg_duration": avg_duration,
                    "recommendation": "Consider adding indexes or query optimization"
                })
        
        # Check resource usage
        resource_usage = self._get_current_resource_usage()
        if resource_usage["cpu_percent"] > 80:
            bottlenecks.append({
                "type": "high_cpu",
                "usage": resource_usage["cpu_percent"],
                "recommendation": "Consider scaling horizontally or optimizing CPU-intensive operations"
            })
        
        if resource_usage["memory_percent"] > 80:
            bottlenecks.append({
                "type": "high_memory",
                "usage": resource_usage["memory_percent"],
                "recommendation": "Consider increasing memory or optimizing memory usage"
            })
        
        return bottlenecks
    
    async def _monitor_resources(self):
        """Background task to monitor system resources."""
        while True:
            try:
                # Collect resource metrics
                resource_data = self._get_current_resource_usage()
                self.resource_history.append(resource_data)
                
                # Update Prometheus metrics
                self.memory_usage.set(resource_data["memory_used"])
                self.cpu_usage.set(resource_data["cpu_percent"])
                
                # Sleep for 1 second
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(5)
    
    def _calculate_request_stats(
        self,
        requests: List[PerformanceMetric]
    ) -> Dict[str, Any]:
        """Calculate request statistics."""
        if not requests:
            return {
                "total": 0,
                "avg_duration": 0,
                "error_rate": 0
            }
        
        durations = [r.duration for r in requests]
        errors = sum(1 for r in requests if r.status_code >= 400)
        
        return {
            "total": len(requests),
            "avg_duration": statistics.mean(durations),
            "median_duration": statistics.median(durations),
            "p95_duration": self._percentile(durations, 95),
            "p99_duration": self._percentile(durations, 99),
            "error_rate": errors / len(requests) * 100,
            "requests_per_second": len(requests) / (
                max(r.timestamp for r in requests) -
                min(r.timestamp for r in requests)
            ) if len(requests) > 1 else 0
        }
    
    def _calculate_query_stats(
        self,
        queries: List[QueryMetric]
    ) -> Dict[str, Any]:
        """Calculate query statistics."""
        if not queries:
            return {
                "total": 0,
                "avg_duration": 0
            }
        
        durations = [q.duration for q in queries]
        
        return {
            "total": len(queries),
            "avg_duration": statistics.mean(durations),
            "median_duration": statistics.median(durations),
            "p95_duration": self._percentile(durations, 95),
            "queries_per_second": len(queries) / (
                max(q.timestamp for q in queries) -
                min(q.timestamp for q in queries)
            ) if len(queries) > 1 else 0
        }
    
    def _get_current_resource_usage(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        process = psutil.Process()
        
        return {
            "timestamp": time.time(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used": process.memory_info().rss,
            "disk_io": process.io_counters()._asdict() if hasattr(process, "io_counters") else {},
            "open_files": len(process.open_files()),
            "num_threads": process.num_threads(),
            "gc_stats": gc.get_stats()
        }
    
    def _calculate_health_score(
        self,
        request_stats: Dict[str, Any],
        query_stats: Dict[str, Any],
        resource_usage: Dict[str, Any]
    ) -> float:
        """Calculate overall system health score (0-100)."""
        score = 100.0
        
        # Penalize for slow response times
        if request_stats.get("p95_duration", 0) > 1.0:
            score -= 20
        elif request_stats.get("p95_duration", 0) > 0.5:
            score -= 10
        
        # Penalize for high error rate
        error_rate = request_stats.get("error_rate", 0)
        if error_rate > 5:
            score -= 30
        elif error_rate > 1:
            score -= 15
        
        # Penalize for slow queries
        if query_stats.get("p95_duration", 0) > 0.5:
            score -= 15
        
        # Penalize for high resource usage
        if resource_usage.get("cpu_percent", 0) > 80:
            score -= 20
        elif resource_usage.get("cpu_percent", 0) > 60:
            score -= 10
        
        if resource_usage.get("memory_percent", 0) > 80:
            score -= 20
        elif resource_usage.get("memory_percent", 0) > 60:
            score -= 10
        
        return max(0, min(100, score))
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        
        if index >= len(sorted_values):
            return sorted_values[-1]
        
        return sorted_values[index]


# Global performance monitor instance
performance_monitor = PerformanceMonitor()