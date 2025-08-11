"""
OAuth monitoring and metrics collection.
Tracks authorization success rates, token generation, and provider usage.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import logging
import asyncio
from enum import Enum
import redis.asyncio as redis

from core.config import settings

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics to track."""
    
    # OAuth flow metrics
    AUTH_REQUEST = "oauth.auth.request"
    AUTH_SUCCESS = "oauth.auth.success"
    AUTH_FAILURE = "oauth.auth.failure"
    TOKEN_ISSUED = "oauth.token.issued"
    TOKEN_REFRESHED = "oauth.token.refreshed"
    TOKEN_REVOKED = "oauth.token.revoked"
    TOKEN_INTROSPECTION = "oauth.token.introspection"
    
    # Provider metrics
    PROVIDER_AUTH = "oauth.provider.auth"
    PROVIDER_CALLBACK = "oauth.provider.callback"
    PROVIDER_ERROR = "oauth.provider.error"
    
    # Security metrics
    PKCE_VALIDATION = "oauth.security.pkce"
    CSRF_BLOCKED = "oauth.security.csrf"
    RATE_LIMITED = "oauth.security.rate_limit"
    GEO_BLOCKED = "oauth.security.geo_block"
    
    # Performance metrics
    AUTH_LATENCY = "oauth.latency.auth"
    TOKEN_LATENCY = "oauth.latency.token"
    INTROSPECTION_LATENCY = "oauth.latency.introspection"
    
    # Error metrics
    INVALID_CLIENT = "oauth.error.invalid_client"
    INVALID_GRANT = "oauth.error.invalid_grant"
    INVALID_SCOPE = "oauth.error.invalid_scope"
    SERVER_ERROR = "oauth.error.server"


class OAuthMetricsCollector:
    """
    Collects and aggregates OAuth metrics.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        retention_hours: int = 24
    ):
        """
        Initialize metrics collector.
        
        Args:
            redis_client: Redis client for storing metrics
            retention_hours: How long to retain metrics
        """
        self.redis_client = redis_client
        self.retention_hours = retention_hours
        
        # In-memory metrics buffer
        self.metrics_buffer = defaultdict(list)
        self.counters = defaultdict(Counter)
        
        # Performance tracking
        self.latencies = defaultdict(list)
        
        # Provider statistics
        self.provider_stats = defaultdict(lambda: {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "errors": []
        })
    
    async def record_metric(
        self,
        metric_type: MetricType,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record a metric.
        
        Args:
            metric_type: Type of metric
            value: Metric value
            tags: Additional tags
            timestamp: Metric timestamp
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        metric = {
            "type": metric_type,
            "value": value,
            "tags": tags or {},
            "timestamp": timestamp.isoformat()
        }
        
        # Add to buffer
        self.metrics_buffer[metric_type].append(metric)
        
        # Update counters
        self.counters[metric_type][timestamp.hour] += value
        
        # Store in Redis if available
        if self.redis_client:
            try:
                key = f"metrics:{metric_type}:{timestamp.strftime('%Y%m%d:%H')}"
                await self.redis_client.hincrby(key, "count", int(value))
                await self.redis_client.expire(key, self.retention_hours * 3600)
                
                # Store detailed metric for analysis
                detail_key = f"metrics:detail:{metric_type}:{timestamp.timestamp()}"
                await self.redis_client.set(
                    detail_key,
                    json.dumps(metric),
                    ex=self.retention_hours * 3600
                )
            except Exception as e:
                logger.error(f"Failed to store metric in Redis: {e}")
    
    async def record_latency(
        self,
        metric_type: MetricType,
        latency_ms: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record latency metric.
        
        Args:
            metric_type: Type of latency metric
            latency_ms: Latency in milliseconds
            tags: Additional tags
        """
        self.latencies[metric_type].append(latency_ms)
        
        # Keep only recent latencies (last 1000)
        if len(self.latencies[metric_type]) > 1000:
            self.latencies[metric_type] = self.latencies[metric_type][-1000:]
        
        await self.record_metric(metric_type, latency_ms, tags)
    
    async def record_auth_attempt(
        self,
        success: bool,
        client_id: str,
        agency_id: Optional[str] = None,
        grant_type: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Record authentication attempt.
        
        Args:
            success: Whether attempt was successful
            client_id: OAuth client ID
            agency_id: Agency ID
            grant_type: OAuth grant type
            error: Error message if failed
        """
        tags = {
            "client_id": client_id,
            "grant_type": grant_type or "unknown",
            "success": str(success).lower()
        }
        
        if agency_id:
            tags["agency_id"] = agency_id
        
        if success:
            await self.record_metric(MetricType.AUTH_SUCCESS, tags=tags)
        else:
            tags["error"] = error or "unknown"
            await self.record_metric(MetricType.AUTH_FAILURE, tags=tags)
        
        await self.record_metric(MetricType.AUTH_REQUEST, tags=tags)
    
    async def record_token_operation(
        self,
        operation: str,
        client_id: str,
        token_type: str = "access",
        scope: Optional[str] = None
    ) -> None:
        """
        Record token operation.
        
        Args:
            operation: issued, refreshed, revoked
            client_id: OAuth client ID
            token_type: Type of token
            scope: Token scope
        """
        tags = {
            "client_id": client_id,
            "token_type": token_type,
            "scope": scope or "default"
        }
        
        if operation == "issued":
            await self.record_metric(MetricType.TOKEN_ISSUED, tags=tags)
        elif operation == "refreshed":
            await self.record_metric(MetricType.TOKEN_REFRESHED, tags=tags)
        elif operation == "revoked":
            await self.record_metric(MetricType.TOKEN_REVOKED, tags=tags)
    
    async def record_provider_operation(
        self,
        provider: str,
        operation: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Record external provider operation.
        
        Args:
            provider: Provider name
            operation: auth, callback
            success: Whether operation was successful
            error: Error message if failed
        """
        self.provider_stats[provider]["attempts"] += 1
        
        if success:
            self.provider_stats[provider]["successes"] += 1
        else:
            self.provider_stats[provider]["failures"] += 1
            if error:
                self.provider_stats[provider]["errors"].append(error)
        
        tags = {
            "provider": provider,
            "operation": operation,
            "success": str(success).lower()
        }
        
        if operation == "auth":
            await self.record_metric(MetricType.PROVIDER_AUTH, tags=tags)
        elif operation == "callback":
            await self.record_metric(MetricType.PROVIDER_CALLBACK, tags=tags)
        
        if not success:
            tags["error"] = error or "unknown"
            await self.record_metric(MetricType.PROVIDER_ERROR, tags=tags)
    
    async def record_security_event(
        self,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Record security event.
        
        Args:
            event_type: Type of security event
            details: Event details
        """
        tags = {"event_type": event_type}
        tags.update(details)
        
        if event_type == "pkce_validation":
            await self.record_metric(MetricType.PKCE_VALIDATION, tags=tags)
        elif event_type == "csrf_blocked":
            await self.record_metric(MetricType.CSRF_BLOCKED, tags=tags)
        elif event_type == "rate_limited":
            await self.record_metric(MetricType.RATE_LIMITED, tags=tags)
        elif event_type == "geo_blocked":
            await self.record_metric(MetricType.GEO_BLOCKED, tags=tags)
        
        logger.warning(f"Security event: {event_type} - {details}")
    
    async def get_metrics_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get metrics summary for the specified period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Metrics summary
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        
        summary = {
            "period": {
                "start": cutoff.isoformat(),
                "end": now.isoformat(),
                "hours": hours
            },
            "auth": {
                "total_requests": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0
            },
            "tokens": {
                "issued": 0,
                "refreshed": 0,
                "revoked": 0,
                "introspections": 0
            },
            "providers": {},
            "security": {
                "pkce_validations": 0,
                "csrf_blocked": 0,
                "rate_limited": 0,
                "geo_blocked": 0
            },
            "performance": {
                "avg_auth_latency_ms": 0.0,
                "avg_token_latency_ms": 0.0,
                "p95_auth_latency_ms": 0.0,
                "p95_token_latency_ms": 0.0
            },
            "errors": {
                "invalid_client": 0,
                "invalid_grant": 0,
                "invalid_scope": 0,
                "server_errors": 0
            }
        }
        
        # Calculate from buffers
        for metric_type, metrics in self.metrics_buffer.items():
            recent_metrics = [
                m for m in metrics
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]
            
            if metric_type == MetricType.AUTH_REQUEST:
                summary["auth"]["total_requests"] = len(recent_metrics)
            elif metric_type == MetricType.AUTH_SUCCESS:
                summary["auth"]["successful"] = len(recent_metrics)
            elif metric_type == MetricType.AUTH_FAILURE:
                summary["auth"]["failed"] = len(recent_metrics)
            elif metric_type == MetricType.TOKEN_ISSUED:
                summary["tokens"]["issued"] = len(recent_metrics)
            elif metric_type == MetricType.TOKEN_REFRESHED:
                summary["tokens"]["refreshed"] = len(recent_metrics)
            elif metric_type == MetricType.TOKEN_REVOKED:
                summary["tokens"]["revoked"] = len(recent_metrics)
            elif metric_type == MetricType.TOKEN_INTROSPECTION:
                summary["tokens"]["introspections"] = len(recent_metrics)
        
        # Calculate success rate
        if summary["auth"]["total_requests"] > 0:
            summary["auth"]["success_rate"] = (
                summary["auth"]["successful"] / summary["auth"]["total_requests"] * 100
            )
        
        # Provider statistics
        for provider, stats in self.provider_stats.items():
            summary["providers"][provider] = {
                "attempts": stats["attempts"],
                "successes": stats["successes"],
                "failures": stats["failures"],
                "success_rate": (
                    stats["successes"] / stats["attempts"] * 100
                    if stats["attempts"] > 0 else 0
                ),
                "recent_errors": stats["errors"][-5:]  # Last 5 errors
            }
        
        # Performance metrics
        if self.latencies[MetricType.AUTH_LATENCY]:
            latencies = sorted(self.latencies[MetricType.AUTH_LATENCY])
            summary["performance"]["avg_auth_latency_ms"] = (
                sum(latencies) / len(latencies)
            )
            p95_index = int(len(latencies) * 0.95)
            summary["performance"]["p95_auth_latency_ms"] = latencies[p95_index]
        
        if self.latencies[MetricType.TOKEN_LATENCY]:
            latencies = sorted(self.latencies[MetricType.TOKEN_LATENCY])
            summary["performance"]["avg_token_latency_ms"] = (
                sum(latencies) / len(latencies)
            )
            p95_index = int(len(latencies) * 0.95)
            summary["performance"]["p95_token_latency_ms"] = latencies[p95_index]
        
        return summary
    
    async def get_hourly_breakdown(
        self,
        metric_type: MetricType,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get hourly breakdown for a specific metric.
        
        Args:
            metric_type: Type of metric
            hours: Number of hours to look back
            
        Returns:
            Hourly breakdown
        """
        breakdown = []
        now = datetime.now(timezone.utc)
        
        for i in range(hours):
            hour = now - timedelta(hours=i)
            hour_key = hour.hour
            
            count = self.counters[metric_type].get(hour_key, 0)
            
            breakdown.append({
                "hour": hour.strftime("%Y-%m-%d %H:00"),
                "count": count
            })
        
        return list(reversed(breakdown))
    
    async def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for alert conditions.
        
        Returns:
            List of alerts
        """
        alerts = []
        summary = await self.get_metrics_summary(hours=1)
        
        # Check authentication success rate
        if summary["auth"]["total_requests"] > 10:
            if summary["auth"]["success_rate"] < 80:
                alerts.append({
                    "severity": "warning",
                    "type": "low_auth_success_rate",
                    "message": f"Auth success rate is {summary['auth']['success_rate']:.1f}%",
                    "value": summary["auth"]["success_rate"]
                })
            
            if summary["auth"]["success_rate"] < 50:
                alerts.append({
                    "severity": "critical",
                    "type": "critical_auth_failure",
                    "message": f"Critical: Auth success rate is {summary['auth']['success_rate']:.1f}%",
                    "value": summary["auth"]["success_rate"]
                })
        
        # Check provider errors
        for provider, stats in summary["providers"].items():
            if stats["attempts"] > 10 and stats["success_rate"] < 70:
                alerts.append({
                    "severity": "warning",
                    "type": "provider_issues",
                    "message": f"{provider} success rate is {stats['success_rate']:.1f}%",
                    "provider": provider,
                    "value": stats["success_rate"]
                })
        
        # Check latency
        if summary["performance"]["p95_auth_latency_ms"] > 1000:
            alerts.append({
                "severity": "warning",
                "type": "high_latency",
                "message": f"P95 auth latency is {summary['performance']['p95_auth_latency_ms']:.0f}ms",
                "value": summary["performance"]["p95_auth_latency_ms"]
            })
        
        # Check security events
        if summary["security"]["rate_limited"] > 100:
            alerts.append({
                "severity": "info",
                "type": "high_rate_limiting",
                "message": f"Rate limited {summary['security']['rate_limited']} requests",
                "value": summary["security"]["rate_limited"]
            })
        
        return alerts
    
    async def cleanup_old_metrics(self) -> None:
        """
        Clean up old metrics from memory and Redis.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        
        # Clean up in-memory buffers
        for metric_type in list(self.metrics_buffer.keys()):
            self.metrics_buffer[metric_type] = [
                m for m in self.metrics_buffer[metric_type]
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]
        
        # Clean up Redis if available
        if self.redis_client:
            try:
                # Get old metric keys
                pattern = f"metrics:*"
                cursor = 0
                
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor,
                        match=pattern,
                        count=100
                    )
                    
                    for key in keys:
                        # Parse timestamp from key
                        parts = key.split(":")
                        if len(parts) >= 3:
                            try:
                                # Check if key is old
                                date_str = parts[2].split(":")[0]
                                key_date = datetime.strptime(date_str, "%Y%m%d")
                                
                                if key_date.date() < cutoff.date():
                                    await self.redis_client.delete(key)
                            except:
                                pass
                    
                    if cursor == 0:
                        break
                        
            except Exception as e:
                logger.error(f"Failed to cleanup old metrics: {e}")


# Global metrics collector instance
_metrics_collector: Optional[OAuthMetricsCollector] = None


def get_metrics_collector() -> OAuthMetricsCollector:
    """
    Get global metrics collector instance.
    
    Returns:
        Metrics collector
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        # Initialize with Redis if available
        redis_client = None
        if hasattr(settings, "REDIS_URL"):
            try:
                import json
                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for metrics: {e}")
        
        _metrics_collector = OAuthMetricsCollector(redis_client=redis_client)
    
    return _metrics_collector


# Convenience functions
async def track_auth_attempt(
    success: bool,
    client_id: str,
    **kwargs
) -> None:
    """Track authentication attempt."""
    collector = get_metrics_collector()
    await collector.record_auth_attempt(success, client_id, **kwargs)


async def track_token_operation(
    operation: str,
    client_id: str,
    **kwargs
) -> None:
    """Track token operation."""
    collector = get_metrics_collector()
    await collector.record_token_operation(operation, client_id, **kwargs)


async def track_latency(
    metric_type: MetricType,
    latency_ms: float,
    **kwargs
) -> None:
    """Track latency metric."""
    collector = get_metrics_collector()
    await collector.record_latency(metric_type, latency_ms, **kwargs)