"""
Monitoring API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.monitoring.models import (
    MetricType, ServiceStatus, AlertSeverity, AlertStatus,
    AlertRule, Alert, ServiceHealth, MonitoringDashboard
)
from core.monitoring.services.monitoring_service import monitoring_service
from core.monitoring.collectors.api_collector import api_collector
from core.monitoring.collectors.database_collector import database_collector
from core.monitoring.collectors.cache_collector import cache_collector

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# Schemas
class MetricQuery(BaseModel):
    """Query parameters for metrics."""
    metric_type: Optional[MetricType] = None
    metric_name: Optional[str] = None
    service_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    aggregation: Optional[str] = Field(None, enum=["avg", "sum", "max", "min"])
    interval: Optional[str] = Field(None, enum=["1m", "5m", "15m", "1h", "1d"])


class AlertRuleCreate(BaseModel):
    """Create a new alert rule."""
    name: str
    description: Optional[str] = None
    metric_type: MetricType
    condition: str = Field(..., enum=["greater_than", "less_than", "equals"])
    threshold: float
    query: Optional[str] = None
    aggregation: Optional[str] = Field("avg", enum=["avg", "sum", "max", "min"])
    time_window_minutes: int = Field(5, ge=1, le=60)
    severity: AlertSeverity = AlertSeverity.WARNING
    notification_channels: List[Dict[str, Any]] = Field(default_factory=list)
    cooldown_minutes: int = Field(30, ge=5, le=1440)


class AlertUpdate(BaseModel):
    """Update alert status."""
    status: AlertStatus
    notes: Optional[str] = None


class DashboardCreate(BaseModel):
    """Create a monitoring dashboard."""
    name: str
    description: Optional[str] = None
    layout: Dict[str, Any]
    widgets: List[Dict[str, Any]]
    refresh_interval_seconds: int = Field(30, ge=10, le=300)
    is_public: bool = False
    shared_with: List[UUID] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


# Endpoints

@router.get("/status")
async def get_system_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get overall system status and health."""
    return await monitoring_service.get_system_status(db)


@router.get("/metrics")
async def query_metrics(
    query: MetricQuery = Depends(),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Query metrics with filters."""
    from sqlalchemy import select, and_
    from core.monitoring.models import Metric
    
    # Build query
    stmt = select(Metric)
    conditions = []
    
    if query.metric_type:
        conditions.append(Metric.metric_type == query.metric_type)
    if query.metric_name:
        conditions.append(Metric.metric_name == query.metric_name)
    if query.service_name:
        conditions.append(Metric.service_name == query.service_name)
    if query.start_time:
        conditions.append(Metric.timestamp >= query.start_time)
    if query.end_time:
        conditions.append(Metric.timestamp <= query.end_time)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Metric.timestamp.desc()).limit(limit)
    
    result = await db.execute(stmt)
    metrics = result.scalars().all()
    
    return [
        {
            "id": str(m.id),
            "metric_type": m.metric_type,
            "metric_name": m.metric_name,
            "value": m.value,
            "unit": m.unit,
            "tags": m.tags,
            "hostname": m.hostname,
            "service_name": m.service_name,
            "timestamp": m.timestamp.isoformat()
        }
        for m in metrics
    ]


@router.get("/health")
async def get_service_health(
    service_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get service health status."""
    from sqlalchemy import select
    
    stmt = select(ServiceHealth)
    if service_name:
        stmt = stmt.where(ServiceHealth.service_name == service_name)
    
    result = await db.execute(stmt)
    health_checks = result.scalars().all()
    
    return [
        {
            "id": str(h.id),
            "service_name": h.service_name,
            "check_name": h.check_name,
            "status": h.status,
            "response_time_ms": h.response_time_ms,
            "details": h.details,
            "checked_at": h.checked_at.isoformat(),
            "last_healthy_at": h.last_healthy_at.isoformat() if h.last_healthy_at else None,
            "consecutive_failures": h.consecutive_failures
        }
        for h in health_checks
    ]


@router.get("/alerts")
async def get_alerts(
    status: Optional[AlertStatus] = None,
    severity: Optional[AlertSeverity] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get alerts with filters."""
    from sqlalchemy import select, and_
    
    stmt = select(Alert).join(AlertRule)
    conditions = []
    
    if status:
        conditions.append(Alert.status == status)
    if severity:
        conditions.append(Alert.severity == severity)
    if start_date:
        conditions.append(Alert.triggered_at >= start_date)
    if end_date:
        conditions.append(Alert.triggered_at <= end_date)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Alert.triggered_at.desc())
    
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    
    return [
        {
            "id": str(a.id),
            "rule_name": a.rule.name if a.rule else None,
            "title": a.title,
            "message": a.message,
            "severity": a.severity,
            "status": a.status,
            "metric_value": a.metric_value,
            "threshold_value": a.threshold_value,
            "triggered_at": a.triggered_at.isoformat(),
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "notes": a.notes
        }
        for a in alerts
    ]


@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: UUID,
    update: AlertUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update alert status."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = update.status
    if update.notes:
        alert.notes = update.notes
    
    if update.status == AlertStatus.ACKNOWLEDGED:
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = current_user.id
    elif update.status == AlertStatus.RESOLVED:
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = current_user.id
    
    await db.commit()
    
    return {"success": True, "message": f"Alert {update.status}"}


@router.get("/alert-rules")
async def get_alert_rules(
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get alert rules."""
    from sqlalchemy import select
    
    stmt = select(AlertRule)
    if is_active is not None:
        stmt = stmt.where(AlertRule.is_active == is_active)
    
    result = await db.execute(stmt)
    rules = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "metric_type": r.metric_type,
            "condition": r.condition,
            "threshold": r.threshold,
            "aggregation": r.aggregation,
            "time_window_minutes": r.time_window_minutes,
            "severity": r.severity,
            "is_active": r.is_active,
            "cooldown_minutes": r.cooldown_minutes
        }
        for r in rules
    ]


@router.post("/alert-rules")
async def create_alert_rule(
    rule: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new alert rule."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Only admins can create alert rules"
        )
    
    # Check for duplicate name
    from sqlalchemy import select
    result = await db.execute(
        select(AlertRule).where(AlertRule.name == rule.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Alert rule with this name already exists"
        )
    
    # Create rule
    alert_rule = AlertRule(
        name=rule.name,
        description=rule.description,
        metric_type=rule.metric_type,
        condition=rule.condition,
        threshold=rule.threshold,
        query=rule.query,
        aggregation=rule.aggregation,
        time_window_minutes=rule.time_window_minutes,
        severity=rule.severity,
        notification_channels=rule.notification_channels,
        cooldown_minutes=rule.cooldown_minutes,
        is_active=True
    )
    
    db.add(alert_rule)
    await db.commit()
    await db.refresh(alert_rule)
    
    return {
        "id": str(alert_rule.id),
        "name": alert_rule.name,
        "message": "Alert rule created successfully"
    }


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Delete an alert rule."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete alert rules"
        )
    
    from sqlalchemy import select
    result = await db.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"success": True, "message": "Alert rule deleted"}


@router.get("/performance/endpoints")
async def get_endpoint_performance(
    hours: int = Query(24, ge=1, le=168),
    order_by: str = Query("requests", enum=["requests", "duration", "errors"]),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get top endpoints by various metrics."""
    return await api_collector.get_top_endpoints(db, hours, limit, order_by)


@router.get("/performance/endpoints/{endpoint:path}")
async def analyze_endpoint_performance(
    endpoint: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze performance for a specific endpoint."""
    return await api_collector.analyze_endpoint_performance(db, endpoint, hours)


@router.get("/performance/database")
async def get_database_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get database performance metrics."""
    slow_queries = await database_collector.analyze_slow_queries(db)
    
    # Get recent metrics
    from sqlalchemy import select, func
    from core.monitoring.models import Metric
    
    since = datetime.utcnow() - timedelta(hours=1)
    
    # Average query time
    query_time_result = await db.execute(
        select(func.avg(Metric.value)).where(
            Metric.metric_name == "db_long_running_queries",
            Metric.timestamp >= since
        )
    )
    avg_slow_queries = query_time_result.scalar() or 0
    
    # Connection pool usage
    conn_result = await db.execute(
        select(func.avg(Metric.value)).where(
            Metric.metric_name == "db_connections_active",
            Metric.timestamp >= since
        )
    )
    avg_connections = conn_result.scalar() or 0
    
    return {
        "slow_queries": slow_queries[:10],  # Top 10
        "avg_slow_queries_per_hour": round(avg_slow_queries, 2),
        "avg_active_connections": round(avg_connections, 2),
        "recommendations": [
            "Consider adding indexes for frequently queried columns" if slow_queries else None,
            "Monitor connection pool usage during peak hours" if avg_connections > 50 else None
        ]
    }


@router.get("/performance/cache")
async def get_cache_performance(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get cache performance analysis."""
    return await cache_collector.analyze_cache_performance(db, hours)


@router.get("/dashboards")
async def get_dashboards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get monitoring dashboards."""
    from sqlalchemy import select, or_
    
    stmt = select(MonitoringDashboard).where(
        or_(
            MonitoringDashboard.is_public == True,
            MonitoringDashboard.owner_id == current_user.id,
            MonitoringDashboard.shared_with.contains([str(current_user.id)])
        )
    )
    
    result = await db.execute(stmt)
    dashboards = result.scalars().all()
    
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "description": d.description,
            "tags": d.tags,
            "owner_id": str(d.owner_id) if d.owner_id else None,
            "is_public": d.is_public,
            "created_at": d.created_at.isoformat() if d.created_at else None
        }
        for d in dashboards
    ]


@router.post("/dashboards")
async def create_dashboard(
    dashboard: DashboardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a monitoring dashboard."""
    new_dashboard = MonitoringDashboard(
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        widgets=dashboard.widgets,
        refresh_interval_seconds=dashboard.refresh_interval_seconds,
        is_public=dashboard.is_public,
        owner_id=current_user.id,
        shared_with=[str(uid) for uid in dashboard.shared_with],
        tags=dashboard.tags
    )
    
    db.add(new_dashboard)
    await db.commit()
    await db.refresh(new_dashboard)
    
    return {
        "id": str(new_dashboard.id),
        "name": new_dashboard.name,
        "message": "Dashboard created successfully"
    }


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(
    dashboard_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get a specific dashboard."""
    from sqlalchemy import select, or_
    
    result = await db.execute(
        select(MonitoringDashboard).where(
            MonitoringDashboard.id == dashboard_id,
            or_(
                MonitoringDashboard.is_public == True,
                MonitoringDashboard.owner_id == current_user.id,
                MonitoringDashboard.shared_with.contains([str(current_user.id)])
            )
        )
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    return {
        "id": str(dashboard.id),
        "name": dashboard.name,
        "description": dashboard.description,
        "layout": dashboard.layout,
        "widgets": dashboard.widgets,
        "refresh_interval_seconds": dashboard.refresh_interval_seconds,
        "is_public": dashboard.is_public,
        "owner_id": str(dashboard.owner_id) if dashboard.owner_id else None,
        "shared_with": dashboard.shared_with,
        "tags": dashboard.tags,
        "created_at": dashboard.created_at.isoformat() if dashboard.created_at else None,
        "updated_at": dashboard.updated_at.isoformat() if dashboard.updated_at else None
    }