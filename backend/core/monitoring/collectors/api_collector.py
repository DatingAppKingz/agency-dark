"""
API metrics collector for request tracking and performance monitoring.
"""
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from core.monitoring.models import Metric, MetricType, PerformanceProfile
from core.database import get_db
from core.config import settings

logger = logging.getLogger(__name__)


class APIMetricsCollector:
    """Collects API-related metrics."""
    
    def __init__(self):
        self.request_counters = defaultdict(int)
        self.request_durations = defaultdict(list)
        self.error_counters = defaultdict(int)
        self.active_requests = 0
        self.collection_interval = 60  # seconds
        self.is_running = False
        
    async def start(self):
        """Start the metrics aggregation loop."""
        self.is_running = True
        logger.info("Starting API metrics collector")
        
        while self.is_running:
            try:
                async for db in get_db():
                    await self.aggregate_metrics(db)
                    break
            except Exception as e:
                logger.error(f"Error aggregating API metrics: {e}")
            
            await asyncio.sleep(self.collection_interval)
    
    async def stop(self):
        """Stop the metrics collection."""
        self.is_running = False
        logger.info("Stopping API metrics collector")
    
    def track_request(self, endpoint: str, method: str, status_code: int, duration_ms: float):
        """Track a single API request."""
        key = f"{method}:{endpoint}"
        
        # Increment counters
        self.request_counters[key] += 1
        self.request_durations[key].append(duration_ms)
        
        # Track errors
        if status_code >= 400:
            error_key = f"{key}:{status_code}"
            self.error_counters[error_key] += 1
    
    def increment_active_requests(self):
        """Increment active request counter."""
        self.active_requests += 1
    
    def decrement_active_requests(self):
        """Decrement active request counter."""
        self.active_requests = max(0, self.active_requests - 1)
    
    async def aggregate_metrics(self, db: AsyncSession):
        """Aggregate and save collected metrics."""
        timestamp = datetime.utcnow()
        metrics = []
        
        # Request count metrics
        for key, count in self.request_counters.items():
            if count > 0:
                method, endpoint = key.split(":", 1)
                metrics.append(Metric(
                    metric_type=MetricType.API_REQUEST_COUNT,
                    metric_name="api_requests_total",
                    value=float(count),
                    unit="count",
                    tags={
                        "method": method,
                        "endpoint": endpoint
                    },
                    entity_type="api_endpoint",
                    entity_id=endpoint,
                    hostname=settings.HOSTNAME,
                    service_name="api",
                    timestamp=timestamp
                ))
        
        # Request duration metrics
        for key, durations in self.request_durations.items():
            if durations:
                method, endpoint = key.split(":", 1)
                
                # Calculate statistics
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                
                # Average duration
                metrics.append(Metric(
                    metric_type=MetricType.API_REQUEST_DURATION,
                    metric_name="api_request_duration_avg_ms",
                    value=avg_duration,
                    unit="milliseconds",
                    tags={
                        "method": method,
                        "endpoint": endpoint
                    },
                    entity_type="api_endpoint",
                    entity_id=endpoint,
                    hostname=settings.HOSTNAME,
                    service_name="api",
                    timestamp=timestamp
                ))
                
                # Min duration
                metrics.append(Metric(
                    metric_type=MetricType.API_REQUEST_DURATION,
                    metric_name="api_request_duration_min_ms",
                    value=min_duration,
                    unit="milliseconds",
                    tags={
                        "method": method,
                        "endpoint": endpoint
                    },
                    entity_type="api_endpoint",
                    entity_id=endpoint,
                    hostname=settings.HOSTNAME,
                    service_name="api",
                    timestamp=timestamp
                ))
                
                # Max duration
                metrics.append(Metric(
                    metric_type=MetricType.API_REQUEST_DURATION,
                    metric_name="api_request_duration_max_ms",
                    value=max_duration,
                    unit="milliseconds",
                    tags={
                        "method": method,
                        "endpoint": endpoint
                    },
                    entity_type="api_endpoint",
                    entity_id=endpoint,
                    hostname=settings.HOSTNAME,
                    service_name="api",
                    timestamp=timestamp
                ))
        
        # Error rate metrics
        total_requests = sum(self.request_counters.values())
        total_errors = sum(self.error_counters.values())
        
        if total_requests > 0:
            error_rate = (total_errors / total_requests) * 100
            metrics.append(Metric(
                metric_type=MetricType.API_ERROR_RATE,
                metric_name="api_error_rate_percent",
                value=error_rate,
                unit="percent",
                hostname=settings.HOSTNAME,
                service_name="api",
                timestamp=timestamp
            ))
        
        # Error count by status code
        for error_key, count in self.error_counters.items():
            if count > 0:
                parts = error_key.split(":")
                method, endpoint, status_code = parts[0], parts[1], parts[2]
                metrics.append(Metric(
                    metric_type=MetricType.API_ERROR_RATE,
                    metric_name="api_errors_total",
                    value=float(count),
                    unit="count",
                    tags={
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": status_code
                    },
                    entity_type="api_endpoint",
                    entity_id=endpoint,
                    hostname=settings.HOSTNAME,
                    service_name="api",
                    timestamp=timestamp
                ))
        
        # Throughput metric (requests per minute)
        throughput = total_requests  # Since we collect every minute
        metrics.append(Metric(
            metric_type=MetricType.API_THROUGHPUT,
            metric_name="api_throughput_rpm",
            value=float(throughput),
            unit="requests_per_minute",
            hostname=settings.HOSTNAME,
            service_name="api",
            timestamp=timestamp
        ))
        
        # Active requests
        metrics.append(Metric(
            metric_type=MetricType.API_REQUEST_COUNT,
            metric_name="api_active_requests",
            value=float(self.active_requests),
            unit="count",
            hostname=settings.HOSTNAME,
            service_name="api",
            timestamp=timestamp
        ))
        
        # Save all metrics
        if metrics:
            db.add_all(metrics)
            await db.commit()
            logger.debug(f"Saved {len(metrics)} API metrics")
        
        # Reset counters
        self.request_counters.clear()
        self.request_durations.clear()
        self.error_counters.clear()
    
    async def analyze_endpoint_performance(
        self,
        db: AsyncSession,
        endpoint: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze performance for a specific endpoint."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get request count
        count_result = await db.execute(
            select(func.sum(Metric.value)).where(
                Metric.metric_type == MetricType.API_REQUEST_COUNT,
                Metric.entity_id == endpoint,
                Metric.timestamp >= since
            )
        )
        total_requests = count_result.scalar() or 0
        
        # Get average duration
        duration_result = await db.execute(
            select(func.avg(Metric.value)).where(
                Metric.metric_type == MetricType.API_REQUEST_DURATION,
                Metric.metric_name == "api_request_duration_avg_ms",
                Metric.entity_id == endpoint,
                Metric.timestamp >= since
            )
        )
        avg_duration = duration_result.scalar() or 0
        
        # Get error count
        error_result = await db.execute(
            select(func.sum(Metric.value)).where(
                Metric.metric_type == MetricType.API_ERROR_RATE,
                Metric.metric_name == "api_errors_total",
                Metric.entity_id == endpoint,
                Metric.timestamp >= since
            )
        )
        total_errors = error_result.scalar() or 0
        
        # Calculate error rate
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        # Get performance profiles
        profile_result = await db.execute(
            select(
                func.avg(PerformanceProfile.total_duration_ms),
                func.max(PerformanceProfile.total_duration_ms),
                func.avg(PerformanceProfile.db_duration_ms),
                func.avg(PerformanceProfile.cache_duration_ms),
                func.avg(PerformanceProfile.query_count)
            ).where(
                PerformanceProfile.endpoint == endpoint,
                PerformanceProfile.timestamp >= since
            )
        )
        profile_stats = profile_result.first()
        
        return {
            "endpoint": endpoint,
            "period_hours": hours,
            "total_requests": int(total_requests),
            "avg_duration_ms": round(avg_duration, 2),
            "total_errors": int(total_errors),
            "error_rate_percent": round(error_rate, 2),
            "performance_breakdown": {
                "avg_total_ms": round(profile_stats[0] or 0, 2),
                "max_total_ms": round(profile_stats[1] or 0, 2),
                "avg_db_ms": round(profile_stats[2] or 0, 2),
                "avg_cache_ms": round(profile_stats[3] or 0, 2),
                "avg_query_count": round(profile_stats[4] or 0, 2)
            } if profile_stats else None
        }
    
    async def get_top_endpoints(
        self,
        db: AsyncSession,
        hours: int = 24,
        limit: int = 10,
        order_by: str = "requests"
    ) -> list:
        """Get top endpoints by various metrics."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        if order_by == "requests":
            # Top by request count
            result = await db.execute(
                select(
                    Metric.entity_id,
                    func.sum(Metric.value).label("total")
                ).where(
                    Metric.metric_type == MetricType.API_REQUEST_COUNT,
                    Metric.timestamp >= since,
                    Metric.entity_id.isnot(None)
                ).group_by(
                    Metric.entity_id
                ).order_by(
                    func.sum(Metric.value).desc()
                ).limit(limit)
            )
        elif order_by == "duration":
            # Top by average duration
            result = await db.execute(
                select(
                    Metric.entity_id,
                    func.avg(Metric.value).label("total")
                ).where(
                    Metric.metric_type == MetricType.API_REQUEST_DURATION,
                    Metric.metric_name == "api_request_duration_avg_ms",
                    Metric.timestamp >= since,
                    Metric.entity_id.isnot(None)
                ).group_by(
                    Metric.entity_id
                ).order_by(
                    func.avg(Metric.value).desc()
                ).limit(limit)
            )
        elif order_by == "errors":
            # Top by error count
            result = await db.execute(
                select(
                    Metric.entity_id,
                    func.sum(Metric.value).label("total")
                ).where(
                    Metric.metric_type == MetricType.API_ERROR_RATE,
                    Metric.metric_name == "api_errors_total",
                    Metric.timestamp >= since,
                    Metric.entity_id.isnot(None)
                ).group_by(
                    Metric.entity_id
                ).order_by(
                    func.sum(Metric.value).desc()
                ).limit(limit)
            )
        else:
            return []
        
        endpoints = []
        for row in result:
            endpoints.append({
                "endpoint": row.entity_id,
                "value": round(row.total, 2),
                "metric": order_by
            })
        
        return endpoints


# Global instance
api_collector = APIMetricsCollector()