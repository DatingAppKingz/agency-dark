"""
Metrics collection and monitoring
"""
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from contextlib import contextmanager

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class Metric:
    """Base metric class"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"


class MetricsCollector:
    """Collect and export metrics"""
    
    def __init__(self):
        self.metrics: List[Metric] = []
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
        self.timers: Dict[str, float] = {}
        
        # Prometheus registry (if using Prometheus)
        self._prometheus_registry = None
        
        # StatsD client (if using StatsD)
        self._statsd_client = None
    
    def increment(
        self,
        name: str,
        value: float = 1,
        tags: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric"""
        key = self._make_key(name, tags)
        self.counters[key] = self.counters.get(key, 0) + value
        
        # Send to external systems
        if self._statsd_client:
            self._statsd_client.increment(name, value, tags=tags)
        
        # Store metric
        self.metrics.append(
            Metric(name=name, value=value, tags=tags or {}, metric_type="counter")
        )
    
    def gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Set a gauge metric"""
        key = self._make_key(name, tags)
        self.gauges[key] = value
        
        # Send to external systems
        if self._statsd_client:
            self._statsd_client.gauge(name, value, tags=tags)
        
        # Store metric
        self.metrics.append(
            Metric(name=name, value=value, tags=tags or {}, metric_type="gauge")
        )
    
    def timing(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a timing metric (in milliseconds)"""
        key = self._make_key(name, tags)
        
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
        
        # Send to external systems
        if self._statsd_client:
            self._statsd_client.timing(name, value, tags=tags)
        
        # Store metric
        self.metrics.append(
            Metric(name=name, value=value, tags=tags or {}, metric_type="timing")
        )
    
    @contextmanager
    def timer(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Context manager for timing operations"""
        start_time = time.perf_counter()
        
        try:
            yield
        finally:
            duration = (time.perf_counter() - start_time) * 1000  # Convert to ms
            self.timing(name, duration, tags)
    
    def _make_key(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """Create a unique key for a metric"""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name},{tag_str}"
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histogram_counts": {k: len(v) for k, v in self.histograms.items()},
            "total_metrics": len(self.metrics)
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Export counters
        for key, value in self.counters.items():
            name, tags = self._parse_key(key)
            labels = self._format_labels(tags)
            lines.append(f"{name}_total{labels} {value}")
        
        # Export gauges
        for key, value in self.gauges.items():
            name, tags = self._parse_key(key)
            labels = self._format_labels(tags)
            lines.append(f"{name}{labels} {value}")
        
        # Export histograms
        for key, values in self.histograms.items():
            if values:
                name, tags = self._parse_key(key)
                labels = self._format_labels(tags)
                
                # Calculate percentiles
                sorted_values = sorted(values)
                count = len(values)
                sum_values = sum(values)
                
                # Quantiles
                quantiles = [0.5, 0.9, 0.95, 0.99]
                for q in quantiles:
                    index = int(count * q)
                    if index < count:
                        lines.append(
                            f'{name}_bucket{labels.rstrip("}")}'
                            f',quantile="{q}"}} {sorted_values[index]}'
                        )
                
                lines.append(f"{name}_count{labels} {count}")
                lines.append(f"{name}_sum{labels} {sum_values}")
        
        return "\n".join(lines)
    
    def _parse_key(self, key: str) -> tuple:
        """Parse metric key into name and tags"""
        parts = key.split(",", 1)
        name = parts[0]
        
        tags = {}
        if len(parts) > 1:
            for tag in parts[1].split(","):
                k, v = tag.split("=", 1)
                tags[k] = v
        
        return name, tags
    
    def _format_labels(self, tags: Dict[str, str]) -> str:
        """Format tags as Prometheus labels"""
        if not tags:
            return ""
        
        labels = ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
        return f"{{{labels}}}"
    
    def clear(self):
        """Clear all metrics"""
        self.metrics.clear()
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.timers.clear()


# HTTP metrics middleware
class MetricsMiddleware:
    """Middleware for collecting HTTP metrics"""
    
    def __init__(self, app, metrics_collector: MetricsCollector):
        self.app = app
        self.metrics = metrics_collector
    
    async def __call__(self, request, call_next):
        # Start timing
        start_time = time.perf_counter()
        
        # Get request details
        method = request.method
        path = request.url.path
        
        # Process request
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = (time.perf_counter() - start_time) * 1000
            
            tags = {
                "method": method,
                "path": self._normalize_path(path),
                "status": str(response.status_code),
                "status_class": f"{response.status_code // 100}xx"
            }
            
            # Record timing
            self.metrics.timing("http.request.duration", duration, tags)
            
            # Increment request counter
            self.metrics.increment("http.requests.total", tags=tags)
            
            # Track status codes
            if response.status_code >= 400:
                self.metrics.increment("http.errors.total", tags=tags)
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = (time.perf_counter() - start_time) * 1000
            
            tags = {
                "method": method,
                "path": self._normalize_path(path),
                "status": "500",
                "status_class": "5xx",
                "error": type(e).__name__
            }
            
            self.metrics.timing("http.request.duration", duration, tags)
            self.metrics.increment("http.requests.total", tags=tags)
            self.metrics.increment("http.errors.total", tags=tags)
            
            raise
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (remove IDs, etc.)"""
        # Replace UUIDs
        import re
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path
        )
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        return path


# Global metrics collector instance
metrics_collector = MetricsCollector()