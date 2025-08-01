"""
Comprehensive Monitoring System

Provides production monitoring including:
- Application metrics collection
- Health checks
- Resource monitoring
- Business metrics tracking
- Alert management
- Distributed tracing
- Log aggregation
- Custom dashboards
"""
import time
import asyncio
import psutil
import socket
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
import os

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    generate_latest, CollectorRegistry,
    multiprocess, start_http_server
)
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from core.logger import get_logger
from core.redis import redis_client
from core.database import get_db

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HealthStatus(str, Enum):
    """Health check statuses."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_func: Callable
    timeout: int = 5
    critical: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alert definition."""
    name: str
    condition: Callable
    message: str
    severity: AlertSeverity
    cooldown: int = 300  # 5 minutes
    actions: List[Callable] = field(default_factory=list)


@dataclass
class Metric:
    """Metric definition."""
    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None


class MonitoringSystem:
    """Comprehensive monitoring system."""
    
    def __init__(self):
        # Prometheus registry
        self.registry = CollectorRegistry()
        
        # Metrics storage
        self.metrics: Dict[str, Any] = {}
        self.custom_metrics: Dict[str, Any] = {}
        
        # Health checks
        self.health_checks: List[HealthCheck] = []
        self.health_status: Dict[str, Dict[str, Any]] = {}
        
        # Alerts
        self.alerts: List[Alert] = []
        self.alert_history: Dict[str, datetime] = {}
        
        # Tracing
        self.tracer = None
        
        # Initialize default metrics
        self._init_default_metrics()
        
        # Background tasks
        self._monitoring_task = None
        self._health_check_task = None
        self._alert_task = None
    
    def _init_default_metrics(self):
        """Initialize default metrics."""
        # Request metrics
        self.metrics["requests_total"] = Counter(
            "requests_total",
            "Total number of requests",
            ["method", "endpoint", "status"],
            registry=self.registry
        )
        
        self.metrics["request_duration"] = Histogram(
            "request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.metrics["active_requests"] = Gauge(
            "active_requests",
            "Number of active requests",
            registry=self.registry
        )
        
        # Database metrics
        self.metrics["db_connections_active"] = Gauge(
            "db_connections_active",
            "Active database connections",
            ["pool"],
            registry=self.registry
        )
        
        self.metrics["db_query_duration"] = Histogram(
            "db_query_duration_seconds",
            "Database query duration",
            ["operation", "table"],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry
        )
        
        # Cache metrics
        self.metrics["cache_hits"] = Counter(
            "cache_hits_total",
            "Cache hits",
            ["cache_type"],
            registry=self.registry
        )
        
        self.metrics["cache_misses"] = Counter(
            "cache_misses_total",
            "Cache misses",
            ["cache_type"],
            registry=self.registry
        )
        
        # Business metrics
        self.metrics["user_registrations"] = Counter(
            "user_registrations_total",
            "Total user registrations",
            registry=self.registry
        )
        
        self.metrics["api_keys_created"] = Counter(
            "api_keys_created_total",
            "API keys created",
            registry=self.registry
        )
        
        # System metrics
        self.metrics["cpu_usage"] = Gauge(
            "cpu_usage_percent",
            "CPU usage percentage",
            registry=self.registry
        )
        
        self.metrics["memory_usage"] = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry
        )
        
        self.metrics["disk_usage"] = Gauge(
            "disk_usage_percent",
            "Disk usage percentage",
            registry=self.registry
        )
    
    def init_tracing(
        self,
        service_name: str,
        otlp_endpoint: Optional[str] = None
    ):
        """Initialize distributed tracing."""
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer(service_name)
        
        # Configure OTLP exporter if endpoint provided
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            span_processor = BatchSpanProcessor(otlp_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
        
        logger.info(f"Initialized tracing for service: {service_name}")
    
    def instrument_app(self, app):
        """Instrument FastAPI application."""
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Instrument SQLAlchemy
        SQLAlchemyInstrumentor().instrument()
        
        logger.info("Application instrumented for monitoring")
    
    def create_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None
    ) -> Any:
        """Create a custom metric."""
        if name in self.custom_metrics:
            return self.custom_metrics[name]
        
        labels = labels or []
        
        if metric_type == MetricType.COUNTER:
            metric = Counter(name, description, labels, registry=self.registry)
        elif metric_type == MetricType.GAUGE:
            metric = Gauge(name, description, labels, registry=self.registry)
        elif metric_type == MetricType.HISTOGRAM:
            buckets = buckets or [0.01, 0.1, 1.0, 10.0]
            metric = Histogram(name, description, labels, buckets=buckets, registry=self.registry)
        elif metric_type == MetricType.SUMMARY:
            metric = Summary(name, description, labels, registry=self.registry)
        else:
            raise ValueError(f"Unknown metric type: {metric_type}")
        
        self.custom_metrics[name] = metric
        logger.info(f"Created custom metric: {name}")
        
        return metric
    
    def track_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ):
        """Track HTTP request metrics."""
        self.metrics["requests_total"].labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        self.metrics["request_duration"].labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def track_db_query(
        self,
        operation: str,
        table: str,
        duration: float
    ):
        """Track database query metrics."""
        self.metrics["db_query_duration"].labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def track_cache_access(self, cache_type: str, hit: bool):
        """Track cache access."""
        if hit:
            self.metrics["cache_hits"].labels(cache_type=cache_type).inc()
        else:
            self.metrics["cache_misses"].labels(cache_type=cache_type).inc()
    
    def track_business_event(self, event_type: str):
        """Track business events."""
        if event_type == "user_registration":
            self.metrics["user_registrations"].inc()
        elif event_type == "api_key_created":
            self.metrics["api_keys_created"].inc()
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a custom metric value."""
        metric = self.custom_metrics.get(metric_name) or self.metrics.get(metric_name)
        
        if not metric:
            logger.error(f"Metric not found: {metric_name}")
            return
        
        if labels:
            metric = metric.labels(**labels)
        
        if isinstance(metric, Counter):
            metric.inc(value)
        elif isinstance(metric, Gauge):
            metric.set(value)
        elif isinstance(metric, (Histogram, Summary)):
            metric.observe(value)
    
    def add_health_check(
        self,
        name: str,
        check_func: Callable,
        timeout: int = 5,
        critical: bool = True,
        tags: Optional[List[str]] = None
    ):
        """Add a health check."""
        health_check = HealthCheck(
            name=name,
            check_func=check_func,
            timeout=timeout,
            critical=critical,
            tags=tags or []
        )
        self.health_checks.append(health_check)
        logger.info(f"Added health check: {name}")
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks."""
        overall_status = HealthStatus.HEALTHY
        checks_result = {}
        
        for check in self.health_checks:
            try:
                # Run check with timeout
                result = await asyncio.wait_for(
                    check.check_func(),
                    timeout=check.timeout
                )
                
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                checks_result[check.name] = {
                    "status": status,
                    "tags": check.tags,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Update overall status
                if status == HealthStatus.UNHEALTHY and check.critical:
                    overall_status = HealthStatus.UNHEALTHY
                elif status == HealthStatus.UNHEALTHY and overall_status != HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.DEGRADED
                
            except asyncio.TimeoutError:
                checks_result[check.name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": "Timeout",
                    "tags": check.tags,
                    "timestamp": datetime.utcnow().isoformat()
                }
                if check.critical:
                    overall_status = HealthStatus.UNHEALTHY
                    
            except Exception as e:
                checks_result[check.name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(e),
                    "tags": check.tags,
                    "timestamp": datetime.utcnow().isoformat()
                }
                if check.critical:
                    overall_status = HealthStatus.UNHEALTHY
        
        # Store results
        self.health_status = {
            "status": overall_status,
            "checks": checks_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.health_status
    
    def add_alert(
        self,
        name: str,
        condition: Callable,
        message: str,
        severity: AlertSeverity,
        cooldown: int = 300,
        actions: Optional[List[Callable]] = None
    ):
        """Add an alert rule."""
        alert = Alert(
            name=name,
            condition=condition,
            message=message,
            severity=severity,
            cooldown=cooldown,
            actions=actions or []
        )
        self.alerts.append(alert)
        logger.info(f"Added alert: {name}")
    
    async def check_alerts(self):
        """Check all alert conditions."""
        triggered_alerts = []
        
        for alert in self.alerts:
            try:
                # Check if in cooldown
                last_trigger = self.alert_history.get(alert.name)
                if last_trigger:
                    time_since = datetime.utcnow() - last_trigger
                    if time_since.total_seconds() < alert.cooldown:
                        continue
                
                # Check condition
                if await alert.condition():
                    triggered_alerts.append(alert)
                    self.alert_history[alert.name] = datetime.utcnow()
                    
                    # Log alert
                    logger.warning(
                        f"Alert triggered: {alert.name} - {alert.message} "
                        f"(severity: {alert.severity})"
                    )
                    
                    # Execute actions
                    for action in alert.actions:
                        try:
                            if asyncio.iscoroutinefunction(action):
                                await action(alert)
                            else:
                                action(alert)
                        except Exception as e:
                            logger.error(f"Error executing alert action: {e}")
                    
            except Exception as e:
                logger.error(f"Error checking alert {alert.name}: {e}")
        
        return triggered_alerts
    
    async def collect_system_metrics(self):
        """Collect system metrics."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics["cpu_usage"].set(cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.metrics["memory_usage"].set(memory.used)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        self.metrics["disk_usage"].set(disk.percent)
        
        # Database connections
        # This would be fetched from your connection pool
        # For now, using a placeholder
        self.metrics["db_connections_active"].labels(pool="default").set(0)
    
    async def start_monitoring(self):
        """Start background monitoring tasks."""
        # Start Prometheus metrics server
        start_http_server(9090, registry=self.registry)
        logger.info("Started Prometheus metrics server on port 9090")
        
        # Start background tasks
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._alert_task = asyncio.create_task(self._alert_loop())
        
        logger.info("Started monitoring background tasks")
    
    async def stop_monitoring(self):
        """Stop monitoring tasks."""
        tasks = [
            self._monitoring_task,
            self._health_check_task,
            self._alert_task
        ]
        
        for task in tasks:
            if task:
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Stopped monitoring tasks")
    
    async def _monitor_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await self.collect_system_metrics()
                await asyncio.sleep(10)  # Collect every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await self.check_health()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(60)
    
    async def _alert_loop(self):
        """Background alert checking loop."""
        while True:
            try:
                await self.check_alerts()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert loop: {e}")
                await asyncio.sleep(120)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics."""
        return generate_latest(self.registry)
    
    def create_span(self, name: str) -> Any:
        """Create a new trace span."""
        if self.tracer:
            return self.tracer.start_as_current_span(name)
        return None
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard."""
        # Collect current metrics
        metrics_data = {}
        
        # Request metrics
        metrics_data["requests"] = {
            "total": sum(
                self.metrics["requests_total"]._metrics.values()
            ) if hasattr(self.metrics["requests_total"], "_metrics") else 0,
            "active": self.metrics["active_requests"]._value.get() if hasattr(
                self.metrics["active_requests"], "_value"
            ) else 0
        }
        
        # System metrics
        metrics_data["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
        
        # Health status
        metrics_data["health"] = self.health_status
        
        return metrics_data


# Monitoring decorators

def track_execution_time(metric_name: Optional[str] = None):
    """Decorator to track function execution time."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            
            # Create histogram if not exists
            if name not in monitoring.custom_metrics:
                monitoring.create_metric(
                    name=f"{name}_duration",
                    metric_type=MetricType.HISTOGRAM,
                    description=f"Execution time for {name}"
                )
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                monitoring.record_metric(f"{name}_duration", duration)
        
        return wrapper
    return decorator


def count_calls(metric_name: Optional[str] = None):
    """Decorator to count function calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            
            # Create counter if not exists
            if name not in monitoring.custom_metrics:
                monitoring.create_metric(
                    name=f"{name}_calls",
                    metric_type=MetricType.COUNTER,
                    description=f"Call count for {name}"
                )
            
            monitoring.record_metric(f"{name}_calls", 1)
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def trace_function(name: Optional[str] = None):
    """Decorator to add distributed tracing."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            if monitoring.tracer:
                with monitoring.tracer.start_as_current_span(span_name) as span:
                    # Add attributes
                    span.set_attribute("function", func.__name__)
                    span.set_attribute("module", func.__module__)
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("success", True)
                        return result
                    except Exception as e:
                        span.set_attribute("success", False)
                        span.set_attribute("error", str(e))
                        raise
            else:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Default health checks

async def check_database_health():
    """Check database connectivity."""
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_redis_health():
    """Check Redis connectivity."""
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


async def check_disk_space():
    """Check disk space availability."""
    disk = psutil.disk_usage('/')
    return disk.percent < 90  # Alert if > 90% full


# Default alerts

async def high_cpu_alert():
    """Check for high CPU usage."""
    return psutil.cpu_percent(interval=1) > 80


async def high_memory_alert():
    """Check for high memory usage."""
    return psutil.virtual_memory().percent > 80


async def high_error_rate_alert():
    """Check for high error rate."""
    # This would check actual error metrics
    # For now, returning False
    return False


# Global monitoring instance
monitoring = MonitoringSystem()

# Add default health checks
monitoring.add_health_check("database", check_database_health, critical=True)
monitoring.add_health_check("redis", check_redis_health, critical=True)
monitoring.add_health_check("disk_space", check_disk_space, critical=False)

# Add default alerts
monitoring.add_alert(
    "high_cpu",
    high_cpu_alert,
    "CPU usage is above 80%",
    AlertSeverity.WARNING
)

monitoring.add_alert(
    "high_memory",
    high_memory_alert,
    "Memory usage is above 80%",
    AlertSeverity.WARNING
)

monitoring.add_alert(
    "high_error_rate",
    high_error_rate_alert,
    "Error rate is above threshold",
    AlertSeverity.ERROR
)