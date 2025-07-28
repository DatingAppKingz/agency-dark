"""
Prometheus metrics collection and management
"""
import time
import asyncio
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from datetime import datetime, timedelta
import psutil
import numpy as np

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST, Info
)
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily

from core.config import settings
from core.logging import logger


# Default registry
registry = CollectorRegistry()

# Application info
app_info = Info(
    'app_build',
    'Application build information',
    registry=registry
)
app_info.info({
    'version': getattr(settings, 'APP_VERSION', '1.0.0'),
    'environment': getattr(settings, 'ENVIRONMENT', 'production')
})

# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

request_size = Summary(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

response_size = Summary(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# Business metrics
task_counter = Counter(
    'celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'status'],
    registry=registry
)

task_duration = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=registry
)

active_users = Gauge(
    'active_users_total',
    'Number of active users',
    registry=registry
)

transaction_counter = Counter(
    'business_transactions_total',
    'Total business transactions',
    ['type', 'status'],
    registry=registry
)

transaction_amount = Summary(
    'business_transaction_amount',
    'Business transaction amounts',
    ['type', 'currency'],
    registry=registry
)

# Database metrics
db_connections = Gauge(
    'database_connections_active',
    'Active database connections',
    ['pool_name'],
    registry=registry
)

db_query_duration = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=registry
)

# Cache metrics
cache_hits = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_name'],
    registry=registry
)

cache_misses = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_name'],
    registry=registry
)

cache_size = Gauge(
    'cache_size_bytes',
    'Cache size in bytes',
    ['cache_name'],
    registry=registry
)

# External API metrics
api_requests = Counter(
    'external_api_requests_total',
    'Total external API requests',
    ['api_name', 'endpoint', 'status'],
    registry=registry
)

api_duration = Histogram(
    'external_api_duration_seconds',
    'External API request duration',
    ['api_name', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=registry
)

# Error metrics
error_counter = Counter(
    'application_errors_total',
    'Total application errors',
    ['error_type', 'severity', 'category'],
    registry=registry
)

# Queue metrics
queue_size = Gauge(
    'queue_size',
    'Queue size',
    ['queue_name'],
    registry=registry
)

queue_processing_time = Histogram(
    'queue_processing_seconds',
    'Queue message processing time',
    ['queue_name'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)


class MetricsCollector:
    """
    Custom metrics collector for advanced metrics
    """
    
    def __init__(self):
        self._metrics_cache = {}
        self._collectors: List[Callable] = []
        self._collection_interval = 60  # seconds
        self._collection_task = None
    
    def register_collector(self, collector: Callable):
        """Register a custom metric collector"""
        self._collectors.append(collector)
    
    async def start_collection(self):
        """Start metrics collection"""
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Metrics collection started")
    
    async def stop_collection(self):
        """Stop metrics collection"""
        if self._collection_task:
            self._collection_task.cancel()
            await asyncio.gather(self._collection_task, return_exceptions=True)
    
    async def _collection_loop(self):
        """Periodically collect metrics"""
        while True:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self._collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in metrics collection: {exc}")
                await asyncio.sleep(self._collection_interval)
    
    async def _collect_metrics(self):
        """Collect all registered metrics"""
        # System metrics
        await self._collect_system_metrics()
        
        # Run custom collectors
        for collector in self._collectors:
            try:
                if asyncio.iscoroutinefunction(collector):
                    await collector()
                else:
                    collector()
            except Exception as exc:
                logger.error(f"Error in custom collector: {exc}")
    
    async def _collect_system_metrics(self):
        """Collect system-level metrics"""
        # CPU usage
        cpu_usage.set(psutil.cpu_percent(interval=1))
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage.set(memory.percent)
        memory_available.set(memory.available)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage.set(disk.percent)
        disk_available.set(disk.free)
        
        # Network I/O
        net_io = psutil.net_io_counters()
        network_bytes_sent.set(net_io.bytes_sent)
        network_bytes_recv.set(net_io.bytes_recv)


# System metrics
cpu_usage = Gauge(
    'system_cpu_usage_percent',
    'CPU usage percentage',
    registry=registry
)

memory_usage = Gauge(
    'system_memory_usage_percent',
    'Memory usage percentage',
    registry=registry
)

memory_available = Gauge(
    'system_memory_available_bytes',
    'Available memory in bytes',
    registry=registry
)

disk_usage = Gauge(
    'system_disk_usage_percent',
    'Disk usage percentage',
    registry=registry
)

disk_available = Gauge(
    'system_disk_available_bytes',
    'Available disk space in bytes',
    registry=registry
)

network_bytes_sent = Gauge(
    'system_network_bytes_sent_total',
    'Total network bytes sent',
    registry=registry
)

network_bytes_recv = Gauge(
    'system_network_bytes_received_total',
    'Total network bytes received',
    registry=registry
)


# Decorators for metric collection
def track_request_metrics(func):
    """Decorator to track HTTP request metrics"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        status = 200
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as exc:
            status = getattr(exc, 'status_code', 500)
            raise
        finally:
            duration = time.time() - start_time
            
            # Extract request info (assumes FastAPI)
            request = kwargs.get('request')
            if request:
                method = request.method
                endpoint = request.url.path
                
                # Record metrics
                request_count.labels(method=method, endpoint=endpoint, status=status).inc()
                request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        status = 200
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as exc:
            status = getattr(exc, 'status_code', 500)
            raise
        finally:
            duration = time.time() - start_time
            # Similar metric recording for sync functions
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def track_task_metrics(task_name: str):
    """Decorator to track Celery task metrics"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = 'failure'
                raise
            finally:
                duration = time.time() - start_time
                task_counter.labels(task_name=task_name, status=status).inc()
                task_duration.labels(task_name=task_name).observe(duration)
        
        return wrapper
    return decorator


def track_db_metrics(operation: str, table: str):
    """Decorator to track database query metrics"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                db_query_duration.labels(operation=operation, table=table).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                db_query_duration.labels(operation=operation, table=table).observe(duration)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def track_cache_metrics(cache_name: str):
    """Decorator to track cache metrics"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Assume func returns (value, hit)
            result, hit = await func(*args, **kwargs)
            
            if hit:
                cache_hits.labels(cache_name=cache_name).inc()
            else:
                cache_misses.labels(cache_name=cache_name).inc()
            
            return result
        
        return async_wrapper
    return decorator


# Metric calculation helpers
class MetricCalculator:
    """Calculate derived metrics and percentiles"""
    
    @staticmethod
    def calculate_sli(success_count: int, total_count: int) -> float:
        """Calculate Service Level Indicator"""
        if total_count == 0:
            return 100.0
        return (success_count / total_count) * 100
    
    @staticmethod
    def calculate_error_rate(error_count: int, total_count: int) -> float:
        """Calculate error rate percentage"""
        if total_count == 0:
            return 0.0
        return (error_count / total_count) * 100
    
    @staticmethod
    def calculate_percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        return float(np.percentile(values, percentile))
    
    @staticmethod
    def calculate_apdex(satisfied: int, tolerating: int, total: int) -> float:
        """Calculate Apdex score"""
        if total == 0:
            return 1.0
        return (satisfied + (tolerating * 0.5)) / total


# FastAPI integration
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse


def setup_metrics(app: FastAPI):
    """Setup metrics for FastAPI application"""
    
    # Metrics endpoint
    @app.get("/metrics", response_class=PlainTextResponse)
    async def get_metrics():
        """Prometheus metrics endpoint"""
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST
        )
    
    # Request metrics middleware
    @app.middleware("http")
    async def track_requests(request: Request, call_next):
        start_time = time.time()
        
        # Track request size
        content_length = request.headers.get('content-length')
        if content_length:
            request_size.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(int(content_length))
        
        # Process request
        response = await call_next(request)
        
        # Track metrics
        duration = time.time() - start_time
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # Track response size
        response_length = response.headers.get('content-length')
        if response_length:
            response_size.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(int(response_length))
        
        return response
    
    # Start metrics collector
    collector = MetricsCollector()
    
    @app.on_event("startup")
    async def startup_metrics():
        await collector.start_collection()
    
    @app.on_event("shutdown")
    async def shutdown_metrics():
        await collector.stop_collection()


# Business metric helpers
def track_business_transaction(transaction_type: str, amount: float, currency: str, status: str = 'success'):
    """Track business transaction metrics"""
    transaction_counter.labels(type=transaction_type, status=status).inc()
    if status == 'success':
        transaction_amount.labels(type=transaction_type, currency=currency).observe(amount)


def track_api_call(api_name: str, endpoint: str, duration: float, status: int):
    """Track external API call metrics"""
    api_requests.labels(
        api_name=api_name,
        endpoint=endpoint,
        status=str(status)
    ).inc()
    
    api_duration.labels(
        api_name=api_name,
        endpoint=endpoint
    ).observe(duration)


def track_error(error_type: str, severity: str, category: str):
    """Track application error"""
    error_counter.labels(
        error_type=error_type,
        severity=severity,
        category=category
    ).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Example custom collectors
async def collect_business_metrics():
    """Collect business-specific metrics"""
    from core.database import get_db_context
    
    async with get_db_context() as db:
        # Active users in last hour
        result = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE last_activity > NOW() - INTERVAL '1 hour'"
        )
        active_count = result.scalar()
        active_users.set(active_count or 0)
        
        # Database connection pool stats
        pool_stats = db.get_pool_stats()
        if pool_stats:
            db_connections.labels(pool_name='main').set(pool_stats.get('active', 0))


async def collect_cache_metrics():
    """Collect cache metrics"""
    from core.redis import redis_client
    
    # Get Redis info
    info = await redis_client.info()
    used_memory = info.get('used_memory', 0)
    cache_size.labels(cache_name='redis').set(used_memory)


# Register collectors
metrics_collector.register_collector(collect_business_metrics)
metrics_collector.register_collector(collect_cache_metrics)
