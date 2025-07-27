"""
Main monitoring service that orchestrates all collectors.
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import logging

from core.monitoring.models import (
    Metric, MetricType, ServiceHealth, ServiceStatus,
    AlertRule, Alert, AlertStatus, AlertSeverity,
    PerformanceProfile
)
from core.monitoring.collectors.system_collector import system_collector
from core.monitoring.collectors.api_collector import api_collector
from core.monitoring.collectors.database_collector import database_collector
from core.monitoring.collectors.cache_collector import cache_collector
from core.database import get_db
from core.config import settings

logger = logging.getLogger(__name__)


class MonitoringService:
    """Orchestrates all monitoring activities."""
    
    def __init__(self):
        self.collectors = {
            "system": system_collector,
            "api": api_collector,
            "database": database_collector,
            "cache": cache_collector
        }
        self.health_check_interval = 30  # seconds
        self.alert_check_interval = 60  # seconds
        self.is_running = False
        self._tasks = []
    
    async def start(self):
        """Start all monitoring tasks."""
        self.is_running = True
        logger.info("Starting monitoring service")
        
        # Start collectors
        for name, collector in self.collectors.items():
            task = asyncio.create_task(collector.start())
            self._tasks.append(task)
            logger.info(f"Started {name} collector")
        
        # Start health checks
        health_task = asyncio.create_task(self._health_check_loop())
        self._tasks.append(health_task)
        
        # Start alert checking
        alert_task = asyncio.create_task(self._alert_check_loop())
        self._tasks.append(alert_task)
        
        logger.info("All monitoring tasks started")
    
    async def stop(self):
        """Stop all monitoring tasks."""
        self.is_running = False
        logger.info("Stopping monitoring service")
        
        # Stop collectors
        for collector in self.collectors.values():
            await collector.stop()
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("Monitoring service stopped")
    
    async def _health_check_loop(self):
        """Periodically check service health."""
        while self.is_running:
            try:
                async for db in get_db():
                    await self._perform_health_checks(db)
                    break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
            
            await asyncio.sleep(self.health_check_interval)
    
    async def _alert_check_loop(self):
        """Periodically check for alert conditions."""
        while self.is_running:
            try:
                async for db in get_db():
                    await self._check_alerts(db)
                    break
            except Exception as e:
                logger.error(f"Error in alert check loop: {e}")
            
            await asyncio.sleep(self.alert_check_interval)
    
    async def _perform_health_checks(self, db: AsyncSession):
        """Perform all health checks."""
        timestamp = datetime.utcnow()
        
        # API health
        api_health = await self._check_api_health(db)
        await self._update_health_status(
            db, "api", "api_availability", api_health["status"],
            api_health["details"], api_health["response_time"]
        )
        
        # Database health
        db_health = await self._check_database_health(db)
        await self._update_health_status(
            db, "database", "database_connectivity", db_health["status"],
            db_health["details"], db_health["response_time"]
        )
        
        # Cache health
        cache_health = await self._check_cache_health()
        await self._update_health_status(
            db, "cache", "redis_connectivity", cache_health["status"],
            cache_health["details"], cache_health["response_time"]
        )
        
        # Disk space health
        disk_health = await self._check_disk_space(db)
        await self._update_health_status(
            db, "system", "disk_space", disk_health["status"],
            disk_health["details"], 0
        )
        
        # Memory health
        memory_health = await self._check_memory_usage(db)
        await self._update_health_status(
            db, "system", "memory_usage", memory_health["status"],
            memory_health["details"], 0
        )
        
        await db.commit()
    
    async def _check_api_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Check API service health."""
        import time
        start = time.time()
        
        try:
            # Check if we're receiving metrics
            result = await db.execute(
                select(func.count(Metric.id)).where(
                    Metric.metric_type == MetricType.API_REQUEST_COUNT,
                    Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                )
            )
            recent_requests = result.scalar() or 0
            
            # Check error rate
            error_result = await db.execute(
                select(func.avg(Metric.value)).where(
                    Metric.metric_name == "api_error_rate_percent",
                    Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                )
            )
            error_rate = error_result.scalar() or 0
            
            response_time = (time.time() - start) * 1000
            
            if recent_requests == 0:
                return {
                    "status": ServiceStatus.UNKNOWN,
                    "details": {"message": "No recent API activity"},
                    "response_time": response_time
                }
            elif error_rate > 10:
                return {
                    "status": ServiceStatus.DEGRADED,
                    "details": {"error_rate": error_rate, "message": "High error rate"},
                    "response_time": response_time
                }
            else:
                return {
                    "status": ServiceStatus.HEALTHY,
                    "details": {"error_rate": error_rate, "recent_requests": recent_requests},
                    "response_time": response_time
                }
        
        except Exception as e:
            return {
                "status": ServiceStatus.UNHEALTHY,
                "details": {"error": str(e)},
                "response_time": (time.time() - start) * 1000
            }
    
    async def _check_database_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Check database health."""
        import time
        from sqlalchemy import text
        
        start = time.time()
        
        try:
            # Simple connectivity check
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            
            # Check connection pool
            pool_result = await db.execute(
                select(func.avg(Metric.value)).where(
                    Metric.metric_name == "db_connections_active",
                    Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                )
            )
            active_connections = pool_result.scalar() or 0
            
            response_time = (time.time() - start) * 1000
            
            if active_connections > 80:  # Assuming max pool size of 100
                return {
                    "status": ServiceStatus.DEGRADED,
                    "details": {"active_connections": active_connections, "message": "High connection usage"},
                    "response_time": response_time
                }
            else:
                return {
                    "status": ServiceStatus.HEALTHY,
                    "details": {"active_connections": active_connections},
                    "response_time": response_time
                }
        
        except Exception as e:
            return {
                "status": ServiceStatus.UNHEALTHY,
                "details": {"error": str(e)},
                "response_time": (time.time() - start) * 1000
            }
    
    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache (Redis) health."""
        import time
        from core.redis import redis_client
        
        start = time.time()
        
        try:
            # Ping Redis
            await redis_client.ping()
            
            # Get basic info
            info = await redis_client.info()
            connected_clients = info.get('connected_clients', 0)
            used_memory_mb = info.get('used_memory', 0) / 1024 / 1024
            
            response_time = (time.time() - start) * 1000
            
            if response_time > 100:
                return {
                    "status": ServiceStatus.DEGRADED,
                    "details": {
                        "response_time_ms": response_time,
                        "message": "Slow Redis response"
                    },
                    "response_time": response_time
                }
            else:
                return {
                    "status": ServiceStatus.HEALTHY,
                    "details": {
                        "connected_clients": connected_clients,
                        "memory_mb": round(used_memory_mb, 2)
                    },
                    "response_time": response_time
                }
        
        except Exception as e:
            return {
                "status": ServiceStatus.UNHEALTHY,
                "details": {"error": str(e)},
                "response_time": (time.time() - start) * 1000
            }
    
    async def _check_disk_space(self, db: AsyncSession) -> Dict[str, Any]:
        """Check disk space usage."""
        try:
            # Get latest disk usage metric
            result = await db.execute(
                select(Metric).where(
                    Metric.metric_name == "disk_usage_percent",
                    Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                ).order_by(Metric.timestamp.desc()).limit(1)
            )
            metric = result.scalar_one_or_none()
            
            if not metric:
                return {
                    "status": ServiceStatus.UNKNOWN,
                    "details": {"message": "No recent disk metrics"}
                }
            
            usage = metric.value
            
            if usage > 90:
                return {
                    "status": ServiceStatus.CRITICAL,
                    "details": {"usage_percent": usage, "message": "Critical disk space"}
                }
            elif usage > 80:
                return {
                    "status": ServiceStatus.DEGRADED,
                    "details": {"usage_percent": usage, "message": "Low disk space"}
                }
            else:
                return {
                    "status": ServiceStatus.HEALTHY,
                    "details": {"usage_percent": usage}
                }
        
        except Exception as e:
            return {
                "status": ServiceStatus.UNKNOWN,
                "details": {"error": str(e)}
            }
    
    async def _check_memory_usage(self, db: AsyncSession) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            # Get latest memory usage metric
            result = await db.execute(
                select(Metric).where(
                    Metric.metric_name == "memory_usage_percent",
                    Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                ).order_by(Metric.timestamp.desc()).limit(1)
            )
            metric = result.scalar_one_or_none()
            
            if not metric:
                return {
                    "status": ServiceStatus.UNKNOWN,
                    "details": {"message": "No recent memory metrics"}
                }
            
            usage = metric.value
            
            if usage > 90:
                return {
                    "status": ServiceStatus.CRITICAL,
                    "details": {"usage_percent": usage, "message": "Critical memory usage"}
                }
            elif usage > 80:
                return {
                    "status": ServiceStatus.DEGRADED,
                    "details": {"usage_percent": usage, "message": "High memory usage"}
                }
            else:
                return {
                    "status": ServiceStatus.HEALTHY,
                    "details": {"usage_percent": usage}
                }
        
        except Exception as e:
            return {
                "status": ServiceStatus.UNKNOWN,
                "details": {"error": str(e)}
            }
    
    async def _update_health_status(
        self,
        db: AsyncSession,
        service_name: str,
        check_name: str,
        status: ServiceStatus,
        details: Dict[str, Any],
        response_time_ms: float
    ):
        """Update health status for a service."""
        # Get existing health record
        result = await db.execute(
            select(ServiceHealth).where(
                and_(
                    ServiceHealth.service_name == service_name,
                    ServiceHealth.check_name == check_name
                )
            )
        )
        health = result.scalar_one_or_none()
        
        if not health:
            # Create new health record
            health = ServiceHealth(
                service_name=service_name,
                check_name=check_name,
                status=status,
                response_time_ms=response_time_ms,
                details=details,
                checked_at=datetime.utcnow()
            )
            if status == ServiceStatus.HEALTHY:
                health.last_healthy_at = datetime.utcnow()
            db.add(health)
        else:
            # Update existing record
            old_status = health.status
            health.status = status
            health.response_time_ms = response_time_ms
            health.details = details
            health.checked_at = datetime.utcnow()
            
            if status == ServiceStatus.HEALTHY:
                health.last_healthy_at = datetime.utcnow()
                health.consecutive_failures = 0
            else:
                health.consecutive_failures += 1
            
            # Track status changes
            if old_status != status:
                health.previous_status = old_status
                health.status_changed_at = datetime.utcnow()
    
    async def _check_alerts(self, db: AsyncSession):
        """Check all active alert rules."""
        # Get active alert rules
        result = await db.execute(
            select(AlertRule).where(AlertRule.is_active == True)
        )
        rules = result.scalars().all()
        
        for rule in rules:
            try:
                await self._evaluate_alert_rule(db, rule)
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.name}: {e}")
        
        await db.commit()
    
    async def _evaluate_alert_rule(self, db: AsyncSession, rule: AlertRule):
        """Evaluate a single alert rule."""
        # Calculate time window
        since = datetime.utcnow() - timedelta(minutes=rule.time_window_minutes)
        
        # Get metrics for evaluation
        query = select(Metric).where(
            Metric.metric_type == rule.metric_type,
            Metric.timestamp >= since
        )
        
        # Apply additional filters from rule query
        if rule.query:
            # Parse and apply custom query conditions
            # This is simplified - in production, use a proper query parser
            pass
        
        result = await db.execute(query)
        metrics = result.scalars().all()
        
        if not metrics:
            return
        
        # Calculate aggregate value
        values = [m.value for m in metrics]
        if rule.aggregation == "avg":
            aggregate_value = sum(values) / len(values)
        elif rule.aggregation == "sum":
            aggregate_value = sum(values)
        elif rule.aggregation == "max":
            aggregate_value = max(values)
        elif rule.aggregation == "min":
            aggregate_value = min(values)
        else:
            aggregate_value = values[-1]  # Latest value
        
        # Check condition
        should_alert = False
        if rule.condition == "greater_than" and aggregate_value > rule.threshold:
            should_alert = True
        elif rule.condition == "less_than" and aggregate_value < rule.threshold:
            should_alert = True
        elif rule.condition == "equals" and aggregate_value == rule.threshold:
            should_alert = True
        
        if should_alert:
            await self._create_or_update_alert(db, rule, aggregate_value, metrics)
    
    async def _create_or_update_alert(
        self,
        db: AsyncSession,
        rule: AlertRule,
        metric_value: float,
        metrics: List[Metric]
    ):
        """Create or update an alert."""
        # Check for existing active alert
        result = await db.execute(
            select(Alert).where(
                and_(
                    Alert.rule_id == rule.id,
                    Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED])
                )
            )
        )
        existing_alert = result.scalar_one_or_none()
        
        if existing_alert:
            # Update existing alert
            existing_alert.metric_value = metric_value
            existing_alert.metric_details = {
                "latest_value": metric_value,
                "sample_count": len(metrics),
                "aggregation": rule.aggregation
            }
        else:
            # Check cooldown period
            last_alert_result = await db.execute(
                select(Alert).where(
                    Alert.rule_id == rule.id
                ).order_by(Alert.triggered_at.desc()).limit(1)
            )
            last_alert = last_alert_result.scalar_one_or_none()
            
            if last_alert and last_alert.triggered_at > datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes):
                return  # Still in cooldown
            
            # Create new alert
            alert = Alert(
                rule_id=rule.id,
                title=f"{rule.name} Alert",
                message=f"{rule.metric_type} {rule.condition} {rule.threshold}. Current value: {metric_value}",
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                metric_value=metric_value,
                threshold_value=rule.threshold,
                metric_details={
                    "latest_value": metric_value,
                    "sample_count": len(metrics),
                    "aggregation": rule.aggregation,
                    "time_window_minutes": rule.time_window_minutes
                },
                tags=rule.tags
            )
            db.add(alert)
            
            # TODO: Send notifications
            # await self._send_alert_notifications(alert, rule)
    
    async def get_system_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Get overall system status."""
        # Get all recent health checks
        result = await db.execute(
            select(ServiceHealth).where(
                ServiceHealth.checked_at >= datetime.utcnow() - timedelta(minutes=5)
            )
        )
        health_checks = result.scalars().all()
        
        # Get active alerts
        alert_result = await db.execute(
            select(Alert).where(
                Alert.status == AlertStatus.ACTIVE
            )
        )
        active_alerts = alert_result.scalars().all()
        
        # Determine overall status
        statuses = [h.status for h in health_checks]
        if ServiceStatus.UNHEALTHY in statuses:
            overall_status = ServiceStatus.UNHEALTHY
        elif ServiceStatus.DEGRADED in statuses:
            overall_status = ServiceStatus.DEGRADED
        else:
            overall_status = ServiceStatus.HEALTHY
        
        # Build response
        services = {}
        for health in health_checks:
            if health.service_name not in services:
                services[health.service_name] = {
                    "status": health.status,
                    "checks": {}
                }
            services[health.service_name]["checks"][health.check_name] = {
                "status": health.status,
                "response_time_ms": health.response_time_ms,
                "last_checked": health.checked_at.isoformat(),
                "details": health.details
            }
        
        return {
            "overall_status": overall_status,
            "services": services,
            "active_alerts": len(active_alerts),
            "alerts": [
                {
                    "id": str(alert.id),
                    "title": alert.title,
                    "severity": alert.severity,
                    "triggered_at": alert.triggered_at.isoformat()
                }
                for alert in active_alerts[:5]  # Top 5 alerts
            ]
        }


# Global instance
monitoring_service = MonitoringService()