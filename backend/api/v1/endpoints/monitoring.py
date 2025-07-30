"""Monitoring endpoints for system health and performance tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.monitoring_service import MonitoringService
from core.exceptions import ValidationError

router = APIRouter()


# Response schemas
class SystemMetricsResponse(BaseModel):
    """System metrics response."""
    timestamp: str
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    process: Dict[str, Any]
    database: Dict[str, Any]
    redis: Dict[str, Any]


class ApplicationMetricsResponse(BaseModel):
    """Application metrics response."""
    timestamp: str
    time_range_minutes: int
    users: Dict[str, int]
    requests: Dict[str, Any]
    errors: Dict[str, Any]
    websockets: Dict[str, int]
    cache: Dict[str, Any]


class ErrorLogEntry(BaseModel):
    """Error log entry."""
    id: str
    type: str
    message: str
    severity: str
    details: Dict[str, Any]
    timestamp: str


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response."""
    timestamp: str
    time_range_minutes: int
    response_times: Dict[str, Any]
    database: Dict[str, Any]
    background_jobs: Dict[str, Any]


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    checks: Dict[str, Dict[str, Any]]


class LogErrorRequest(BaseModel):
    """Log error request."""
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    severity: str = Field(default="error", pattern="^(debug|info|warning|error|critical)$")


@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(
    current_user: User = Depends(get_current_user)
) -> SystemMetricsResponse:
    """
    Get current system metrics.
    
    - CPU usage and count
    - Memory usage
    - Disk usage
    - Process metrics
    - Database connection pool stats
    - Redis stats
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    metrics = await MonitoringService.get_system_metrics()
    return SystemMetricsResponse(**metrics)


@router.get("/application", response_model=ApplicationMetricsResponse)
async def get_application_metrics(
    time_range_minutes: int = Query(60, ge=1, le=1440),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApplicationMetricsResponse:
    """
    Get application-specific metrics.
    
    - Active users
    - Request counts and error rates
    - WebSocket connections
    - Cache hit rates
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager", "agency_admin", "agency_owner", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    metrics = await MonitoringService.get_application_metrics(
        db=db,
        time_range_minutes=time_range_minutes
    )
    return ApplicationMetricsResponse(**metrics)


@router.get("/errors", response_model=List[ErrorLogEntry])
async def get_recent_errors(
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None, pattern="^(debug|info|warning|error|critical)$"),
    current_user: User = Depends(get_current_user)
) -> List[ErrorLogEntry]:
    """
    Get recent application errors.
    
    - Filter by severity level
    - Returns most recent errors first
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager", "agency_admin", "agency_owner", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    errors = await MonitoringService.get_recent_errors(
        limit=limit,
        severity=severity
    )
    
    return [
        ErrorLogEntry(
            id=error["id"],
            type=error["type"],
            message=error["message"],
            severity=error["severity"],
            details=error["details"],
            timestamp=error["timestamp"]
        )
        for error in errors
    ]


@router.post("/errors")
async def log_error(
    request: LogErrorRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Log an error for monitoring.
    
    - Used by frontend to report client-side errors
    - Stored for analysis and alerting
    """
    await MonitoringService.log_error(
        error_type=request.error_type,
        message=request.message,
        details={
            **request.details,
            "user_id": current_user.id,
            "user_role": current_user.role,
            "user_agent": request.details.get("user_agent", "unknown")
        },
        severity=request.severity
    )
    
    return {"message": "Error logged successfully"}


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    time_range_minutes: int = Query(60, ge=1, le=1440),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PerformanceMetricsResponse:
    """
    Get performance metrics.
    
    - Response time percentiles
    - Database query performance
    - Background job metrics
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    metrics = await MonitoringService.get_performance_metrics(
        db=db,
        time_range_minutes=time_range_minutes
    )
    return PerformanceMetricsResponse(**metrics)


@router.get("/health", response_model=HealthCheckResponse)
async def get_health_status(
    current_user: User = Depends(get_current_user)
) -> HealthCheckResponse:
    """
    Get overall system health status.
    
    - Database connectivity
    - Redis connectivity
    - Disk space
    - Memory usage
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager", "agency_admin", "agency_owner", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    health = await MonitoringService.get_health_status()
    return HealthCheckResponse(**health)


@router.get("/dashboard")
async def get_monitoring_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive monitoring dashboard data.
    
    - Combines system, application, and performance metrics
    - For admin dashboard display
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all metrics
    system_metrics = await MonitoringService.get_system_metrics()
    app_metrics = await MonitoringService.get_application_metrics(db)
    performance = await MonitoringService.get_performance_metrics(db)
    health = await MonitoringService.get_health_status()
    recent_errors = await MonitoringService.get_recent_errors(limit=10)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": system_metrics,
        "application": app_metrics,
        "performance": performance,
        "health": health,
        "recent_errors": recent_errors
    }


@router.get("/alerts/rules")
async def get_alert_rules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get configured monitoring alert rules.
    
    - CPU/Memory thresholds
    - Error rate thresholds
    - Response time thresholds
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "cpu_threshold_percent": 80,
        "memory_threshold_percent": 80,
        "disk_threshold_percent": 90,
        "error_rate_threshold_percent": 5,
        "response_time_threshold_ms": 1000,
        "alert_channels": ["email", "slack", "webhook"]
    }


@router.post("/test")
async def test_monitoring(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test monitoring functionality.
    
    - Creates test error
    - Returns sample metrics
    """
    # Log test error
    await MonitoringService.log_error(
        error_type="test_error",
        message="This is a test error from monitoring endpoint",
        details={
            "user_id": current_user.id,
            "timestamp": datetime.utcnow().isoformat()
        },
        severity="info"
    )
    
    # Get metrics
    system = await MonitoringService.get_system_metrics()
    health = await MonitoringService.get_health_status()
    
    return {
        "message": "Monitoring test completed",
        "test_error_logged": True,
        "system_metrics": system,
        "health_status": health
    }