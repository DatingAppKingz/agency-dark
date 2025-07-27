"""
Tests for monitoring system.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

from core.monitoring.models import (
    Metric, MetricType, ServiceHealth, ServiceStatus,
    AlertRule, Alert, AlertStatus, AlertSeverity
)
from core.monitoring.collectors.system_collector import SystemMetricsCollector
from core.monitoring.collectors.api_collector import APIMetricsCollector
from core.monitoring.collectors.database_collector import DatabaseMetricsCollector
from core.monitoring.collectors.cache_collector import CacheMetricsCollector
from core.monitoring.services.monitoring_service import MonitoringService


@pytest.mark.asyncio
async def test_system_metrics_collector(db_session):
    """Test system metrics collection."""
    collector = SystemMetricsCollector()
    
    # Collect metrics once
    await collector.collect_all_metrics(db_session)
    
    # Check CPU metrics
    cpu_metrics = await db_session.execute(
        db_session.query(Metric).filter(
            Metric.metric_type == MetricType.SYSTEM_CPU
        )
    )
    cpu_metrics = cpu_metrics.scalars().all()
    
    assert len(cpu_metrics) > 0
    assert any(m.metric_name == "cpu_usage_percent" for m in cpu_metrics)
    
    # Check memory metrics
    memory_metrics = await db_session.execute(
        db_session.query(Metric).filter(
            Metric.metric_type == MetricType.SYSTEM_MEMORY
        )
    )
    memory_metrics = memory_metrics.scalars().all()
    
    assert len(memory_metrics) > 0
    assert any(m.metric_name == "memory_usage_percent" for m in memory_metrics)
    
    # Check disk metrics
    disk_metrics = await db_session.execute(
        db_session.query(Metric).filter(
            Metric.metric_type == MetricType.SYSTEM_DISK
        )
    )
    disk_metrics = disk_metrics.scalars().all()
    
    assert len(disk_metrics) > 0
    assert any(m.metric_name == "disk_usage_percent" for m in disk_metrics)


@pytest.mark.asyncio
async def test_api_metrics_collector():
    """Test API metrics collection."""
    collector = APIMetricsCollector()
    
    # Track some requests
    collector.track_request("/api/v1/users", "GET", 200, 50.5)
    collector.track_request("/api/v1/users", "GET", 200, 75.2)
    collector.track_request("/api/v1/users", "POST", 201, 120.3)
    collector.track_request("/api/v1/auth/login", "POST", 401, 25.1)
    
    # Check counters
    assert collector.request_counters["GET:/api/v1/users"] == 2
    assert collector.request_counters["POST:/api/v1/users"] == 1
    assert collector.error_counters["POST:/api/v1/auth/login:401"] == 1
    
    # Check durations
    assert len(collector.request_durations["GET:/api/v1/users"]) == 2
    assert collector.request_durations["GET:/api/v1/users"][0] == 50.5
    assert collector.request_durations["GET:/api/v1/users"][1] == 75.2


@pytest.mark.asyncio
async def test_health_checks(db_session):
    """Test service health checks."""
    service = MonitoringService()
    
    # Perform health checks
    await service._perform_health_checks(db_session)
    
    # Check API health
    api_health = await db_session.execute(
        db_session.query(ServiceHealth).filter(
            ServiceHealth.service_name == "api",
            ServiceHealth.check_name == "api_availability"
        )
    )
    api_health = api_health.scalar_one_or_none()
    
    assert api_health is not None
    assert api_health.status in [ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN]
    
    # Check database health
    db_health = await db_session.execute(
        db_session.query(ServiceHealth).filter(
            ServiceHealth.service_name == "database",
            ServiceHealth.check_name == "database_connectivity"
        )
    )
    db_health = db_health.scalar_one_or_none()
    
    assert db_health is not None
    assert db_health.status == ServiceStatus.HEALTHY
    assert db_health.response_time_ms > 0


@pytest.mark.asyncio
async def test_alert_rules(db_session, test_agency):
    """Test alert rule evaluation."""
    service = MonitoringService()
    
    # Create a test alert rule
    rule = AlertRule(
        name="Test High CPU",
        metric_type=MetricType.SYSTEM_CPU,
        condition="greater_than",
        threshold=80.0,
        severity=AlertSeverity.WARNING,
        time_window_minutes=5,
        cooldown_minutes=30,
        is_active=True
    )
    db_session.add(rule)
    await db_session.commit()
    
    # Add high CPU metric
    metric = Metric(
        metric_type=MetricType.SYSTEM_CPU,
        metric_name="cpu_usage_percent",
        value=85.0,
        unit="percent",
        hostname="test-host",
        service_name="system",
        timestamp=datetime.utcnow()
    )
    db_session.add(metric)
    await db_session.commit()
    
    # Evaluate alert rules
    await service._check_alerts(db_session)
    
    # Check if alert was created
    alerts = await db_session.execute(
        db_session.query(Alert).filter(
            Alert.rule_id == rule.id
        )
    )
    alerts = alerts.scalars().all()
    
    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.ACTIVE
    assert alerts[0].metric_value == 85.0
    assert alerts[0].threshold_value == 80.0


@pytest.mark.asyncio
async def test_alert_cooldown(db_session):
    """Test alert cooldown period."""
    service = MonitoringService()
    
    # Create alert rule with 30 minute cooldown
    rule = AlertRule(
        name="Test Cooldown",
        metric_type=MetricType.SYSTEM_MEMORY,
        condition="greater_than",
        threshold=90.0,
        severity=AlertSeverity.CRITICAL,
        time_window_minutes=5,
        cooldown_minutes=30,
        is_active=True
    )
    db_session.add(rule)
    
    # Create existing alert
    existing_alert = Alert(
        rule_id=rule.id,
        title="Memory Alert",
        message="High memory usage",
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.RESOLVED,
        metric_value=92.0,
        threshold_value=90.0,
        triggered_at=datetime.utcnow() - timedelta(minutes=15)  # 15 minutes ago
    )
    db_session.add(existing_alert)
    await db_session.commit()
    
    # Add new high memory metric
    metric = Metric(
        metric_type=MetricType.SYSTEM_MEMORY,
        metric_name="memory_usage_percent",
        value=95.0,
        unit="percent",
        hostname="test-host",
        service_name="system",
        timestamp=datetime.utcnow()
    )
    db_session.add(metric)
    await db_session.commit()
    
    # Evaluate alert rules
    await service._check_alerts(db_session)
    
    # Check that no new alert was created (still in cooldown)
    new_alerts = await db_session.execute(
        db_session.query(Alert).filter(
            Alert.rule_id == rule.id,
            Alert.id != existing_alert.id
        )
    )
    new_alerts = new_alerts.scalars().all()
    
    assert len(new_alerts) == 0  # No new alert due to cooldown


@pytest.mark.asyncio
async def test_performance_tracking(db_session):
    """Test API performance tracking."""
    from core.monitoring.models import PerformanceProfile
    
    # Create performance profiles
    profiles = [
        PerformanceProfile(
            request_id=str(uuid4()),
            endpoint="/api/v1/users",
            method="GET",
            total_duration_ms=150.5,
            db_duration_ms=80.2,
            cache_duration_ms=5.3,
            processing_duration_ms=65.0,
            query_count=3,
            cache_hits=2,
            cache_misses=1,
            status_code=200,
            timestamp=datetime.utcnow()
        ),
        PerformanceProfile(
            request_id=str(uuid4()),
            endpoint="/api/v1/users",
            method="POST",
            total_duration_ms=250.8,
            db_duration_ms=180.5,
            cache_duration_ms=0,
            processing_duration_ms=70.3,
            query_count=5,
            cache_hits=0,
            cache_misses=0,
            status_code=201,
            timestamp=datetime.utcnow()
        ),
        PerformanceProfile(
            request_id=str(uuid4()),
            endpoint="/api/v1/auth/login",
            method="POST",
            total_duration_ms=1200.0,  # Slow request
            db_duration_ms=1100.0,
            cache_duration_ms=0,
            processing_duration_ms=100.0,
            query_count=15,
            slow_queries=[
                {"query": "SELECT * FROM users WHERE...", "duration_ms": 800}
            ],
            status_code=200,
            timestamp=datetime.utcnow()
        )
    ]
    
    for profile in profiles:
        db_session.add(profile)
    await db_session.commit()
    
    # Analyze endpoint performance
    collector = APIMetricsCollector()
    analysis = await collector.analyze_endpoint_performance(
        db_session,
        "/api/v1/users",
        hours=24
    )
    
    assert analysis["endpoint"] == "/api/v1/users"
    assert analysis["performance_breakdown"]["avg_query_count"] == 4.0  # (3+5)/2


@pytest.mark.asyncio
async def test_system_status(db_session):
    """Test overall system status."""
    service = MonitoringService()
    
    # Add some health checks
    health_checks = [
        ServiceHealth(
            service_name="api",
            check_name="api_availability",
            status=ServiceStatus.HEALTHY,
            response_time_ms=10.5,
            checked_at=datetime.utcnow()
        ),
        ServiceHealth(
            service_name="database",
            check_name="database_connectivity",
            status=ServiceStatus.HEALTHY,
            response_time_ms=5.2,
            checked_at=datetime.utcnow()
        ),
        ServiceHealth(
            service_name="cache",
            check_name="redis_connectivity",
            status=ServiceStatus.DEGRADED,
            response_time_ms=150.0,
            details={"message": "Slow response time"},
            checked_at=datetime.utcnow()
        )
    ]
    
    for health in health_checks:
        db_session.add(health)
    await db_session.commit()
    
    # Get system status
    status = await service.get_system_status(db_session)
    
    assert status["overall_status"] == ServiceStatus.DEGRADED  # Due to cache
    assert "api" in status["services"]
    assert "database" in status["services"]
    assert "cache" in status["services"]
    assert status["services"]["cache"]["status"] == ServiceStatus.DEGRADED