"""Sync error monitoring endpoints."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from pydantic import BaseModel

from core.database import get_db
from core.security import get_current_active_user
from core.rbac import check_permission
from models.user import User
from models.sync_error_log import SyncErrorLog
from models.api_key import APIKey
from services.sync.error_recovery import SyncErrorRecoveryService
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sync/errors")


class ErrorSummaryResponse(BaseModel):
    """Error summary response."""
    total_errors: int
    errors_last_hour: int
    errors_last_24h: int
    errors_by_type: Dict[str, int]
    errors_by_service: Dict[str, int]
    top_error_messages: List[Dict[str, Any]]
    circuit_breaker_status: Dict[str, str]


class ErrorDetailResponse(BaseModel):
    """Detailed error information."""
    id: str
    error_type: str
    error_message: str
    error_code: Optional[str]
    retry_count: int
    sync_job_id: Optional[str]
    api_key_id: Optional[int]
    api_key_name: Optional[str]
    service_id: Optional[str]
    item_id: Optional[str]
    operation_type: Optional[str]
    recovery_strategy: Optional[str]
    recovery_successful: Optional[bool]
    occurred_at: str
    resolved_at: Optional[str]
    stack_trace: Optional[str]
    context_data: Optional[Dict[str, Any]]


class ErrorTrendResponse(BaseModel):
    """Error trend data."""
    time_bucket: str
    error_count: int
    error_types: Dict[str, int]
    success_rate: float


class ServiceHealthResponse(BaseModel):
    """Service health status."""
    service_id: str
    status: str  # healthy, degraded, unhealthy
    error_rate: float
    success_rate: float
    circuit_breaker_state: Optional[str]
    last_error: Optional[str]
    last_success: Optional[str]
    recommendation: Optional[str]


@router.get("/summary", response_model=ErrorSummaryResponse)
async def get_error_summary(
    service_id: Optional[str] = None,
    api_key_id: Optional[int] = None,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get error summary for monitoring.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Time windows
    now = datetime.utcnow()
    time_1h_ago = now - timedelta(hours=1)
    time_window = now - timedelta(hours=hours)
    
    # Build base query
    base_query = select(SyncErrorLog).where(
        and_(
            SyncErrorLog.agency_id == current_user.agency_id,
            SyncErrorLog.occurred_at >= time_window
        )
    )
    
    if service_id:
        base_query = base_query.where(SyncErrorLog.service_id == service_id)
    if api_key_id:
        base_query = base_query.where(SyncErrorLog.api_key_id == api_key_id)
    
    # Total errors
    total_result = await db.execute(
        select(func.count(SyncErrorLog.id)).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window
            )
        )
    )
    total_errors = total_result.scalar() or 0
    
    # Errors last hour
    hour_result = await db.execute(
        select(func.count(SyncErrorLog.id)).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_1h_ago
            )
        )
    )
    errors_last_hour = hour_result.scalar() or 0
    
    # Errors by type
    type_result = await db.execute(
        select(
            SyncErrorLog.error_type,
            func.count(SyncErrorLog.id)
        ).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window
            )
        ).group_by(SyncErrorLog.error_type)
    )
    errors_by_type = dict(type_result)
    
    # Errors by service
    service_result = await db.execute(
        select(
            SyncErrorLog.service_id,
            func.count(SyncErrorLog.id)
        ).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window,
                SyncErrorLog.service_id.isnot(None)
            )
        ).group_by(SyncErrorLog.service_id)
    )
    errors_by_service = dict(service_result)
    
    # Top error messages
    message_result = await db.execute(
        select(
            SyncErrorLog.error_message,
            func.count(SyncErrorLog.id).label('count'),
            func.max(SyncErrorLog.occurred_at).label('last_seen')
        ).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window
            )
        ).group_by(SyncErrorLog.error_message)
        .order_by(desc('count'))
        .limit(10)
    )
    
    top_error_messages = [
        {
            "message": row[0][:200],  # Truncate long messages
            "count": row[1],
            "last_seen": row[2].isoformat()
        }
        for row in message_result
    ]
    
    # Get circuit breaker status (mock for now)
    circuit_breaker_status = {}
    error_recovery = SyncErrorRecoveryService(db)
    for service in errors_by_service.keys():
        if service:
            cb = error_recovery.get_circuit_breaker(service)
            circuit_breaker_status[service] = cb.state
    
    return ErrorSummaryResponse(
        total_errors=total_errors,
        errors_last_hour=errors_last_hour,
        errors_last_24h=total_errors if hours >= 24 else 0,
        errors_by_type=errors_by_type,
        errors_by_service=errors_by_service,
        top_error_messages=top_error_messages,
        circuit_breaker_status=circuit_breaker_status
    )


@router.get("/list", response_model=List[ErrorDetailResponse])
async def list_errors(
    service_id: Optional[str] = None,
    api_key_id: Optional[int] = None,
    error_type: Optional[str] = None,
    unresolved_only: bool = False,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List sync errors with filtering.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Build query
    query = select(SyncErrorLog).where(
        SyncErrorLog.agency_id == current_user.agency_id
    )
    
    if service_id:
        query = query.where(SyncErrorLog.service_id == service_id)
    if api_key_id:
        query = query.where(SyncErrorLog.api_key_id == api_key_id)
    if error_type:
        query = query.where(SyncErrorLog.error_type == error_type)
    if unresolved_only:
        query = query.where(SyncErrorLog.resolved_at.is_(None))
    if start_date:
        query = query.where(SyncErrorLog.occurred_at >= start_date)
    if end_date:
        query = query.where(SyncErrorLog.occurred_at <= end_date)
    
    # Order and paginate
    query = query.order_by(desc(SyncErrorLog.occurred_at))
    query = query.limit(limit).offset(offset)
    
    # Execute
    result = await db.execute(query)
    errors = result.scalars().all()
    
    # Get API key names
    api_key_ids = [e.api_key_id for e in errors if e.api_key_id]
    api_keys_map = {}
    if api_key_ids:
        api_keys_result = await db.execute(
            select(APIKey).where(APIKey.id.in_(api_key_ids))
        )
        api_keys_map = {k.id: k.name for k in api_keys_result.scalars()}
    
    # Build response
    response = []
    for error in errors:
        response.append(ErrorDetailResponse(
            id=str(error.id),
            error_type=error.error_type,
            error_message=error.error_message,
            error_code=error.error_code,
            retry_count=error.retry_count,
            sync_job_id=error.sync_job_id,
            api_key_id=error.api_key_id,
            api_key_name=api_keys_map.get(error.api_key_id),
            service_id=error.service_id,
            item_id=error.item_id,
            operation_type=error.operation_type,
            recovery_strategy=error.recovery_strategy,
            recovery_successful=error.recovery_successful,
            occurred_at=error.occurred_at.isoformat(),
            resolved_at=error.resolved_at.isoformat() if error.resolved_at else None,
            stack_trace=error.stack_trace,
            context_data=error.context_data
        ))
    
    return response


@router.get("/trends", response_model=List[ErrorTrendResponse])
async def get_error_trends(
    service_id: Optional[str] = None,
    interval: str = Query("hour", regex="^(hour|day|week)$"),
    periods: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get error trends over time.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Determine time bucket and window
    if interval == "hour":
        time_window = datetime.utcnow() - timedelta(hours=periods)
        bucket_expr = func.date_trunc('hour', SyncErrorLog.occurred_at)
    elif interval == "day":
        time_window = datetime.utcnow() - timedelta(days=periods)
        bucket_expr = func.date_trunc('day', SyncErrorLog.occurred_at)
    else:  # week
        time_window = datetime.utcnow() - timedelta(weeks=periods)
        bucket_expr = func.date_trunc('week', SyncErrorLog.occurred_at)
    
    # Query for error counts
    query = (
        select(
            bucket_expr.label('time_bucket'),
            func.count(SyncErrorLog.id).label('error_count'),
            SyncErrorLog.error_type
        )
        .where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window
            )
        )
        .group_by('time_bucket', SyncErrorLog.error_type)
        .order_by('time_bucket')
    )
    
    if service_id:
        query = query.where(SyncErrorLog.service_id == service_id)
    
    result = await db.execute(query)
    
    # Process results into trends
    trends_map: Dict[str, Dict[str, Any]] = {}
    
    for row in result:
        bucket = row.time_bucket.isoformat()
        if bucket not in trends_map:
            trends_map[bucket] = {
                "time_bucket": bucket,
                "error_count": 0,
                "error_types": {},
                "success_rate": 0.0  # Will calculate if we have success data
            }
        
        trends_map[bucket]["error_count"] += row.error_count
        trends_map[bucket]["error_types"][row.error_type] = row.error_count
    
    # Convert to list and sort
    trends = list(trends_map.values())
    trends.sort(key=lambda x: x["time_bucket"])
    
    return [ErrorTrendResponse(**trend) for trend in trends]


@router.get("/service-health", response_model=List[ServiceHealthResponse])
async def get_service_health(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get health status for all sync services.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get all services with recent activity
    time_window = datetime.utcnow() - timedelta(hours=24)
    
    # Get error stats by service
    error_stats = await db.execute(
        select(
            SyncErrorLog.service_id,
            func.count(SyncErrorLog.id).label('error_count'),
            func.max(SyncErrorLog.occurred_at).label('last_error')
        ).where(
            and_(
                SyncErrorLog.agency_id == current_user.agency_id,
                SyncErrorLog.occurred_at >= time_window,
                SyncErrorLog.service_id.isnot(None)
            )
        ).group_by(SyncErrorLog.service_id)
    )
    
    service_health = []
    error_recovery = SyncErrorRecoveryService(db)
    
    for row in error_stats:
        service_id = row.service_id
        error_count = row.error_count
        last_error = row.last_error
        
        # Calculate rates (simplified - would need success data for accurate rates)
        error_rate = error_count / 24  # Errors per hour
        success_rate = max(0, 100 - (error_rate * 10))  # Simplified calculation
        
        # Get circuit breaker state
        cb = error_recovery.get_circuit_breaker(service_id)
        
        # Determine status
        if cb.state == "open" or error_rate > 10:
            status = "unhealthy"
        elif cb.state == "half-open" or error_rate > 5:
            status = "degraded"
        else:
            status = "healthy"
        
        # Generate recommendation
        recommendation = None
        if status == "unhealthy":
            recommendation = "Service experiencing high error rate. Consider investigating logs and reducing sync frequency."
        elif status == "degraded":
            recommendation = "Service showing signs of instability. Monitor closely."
        
        service_health.append(ServiceHealthResponse(
            service_id=service_id,
            status=status,
            error_rate=error_rate,
            success_rate=success_rate,
            circuit_breaker_state=cb.state,
            last_error=last_error.isoformat() if last_error else None,
            last_success=None,  # Would need success tracking
            recommendation=recommendation
        ))
    
    return service_health


@router.post("/errors/{error_id}/resolve")
async def resolve_error(
    error_id: str,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark an error as resolved.
    
    Requires sync write permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    # Get error
    error = await db.get(SyncErrorLog, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error not found"
        )
    
    if error.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to resolve this error"
        )
    
    # Update error
    error.resolved_at = datetime.utcnow()
    if notes:
        if error.recovery_metadata:
            error.recovery_metadata["resolution_notes"] = notes
        else:
            error.recovery_metadata = {"resolution_notes": notes}
    
    await db.commit()
    
    logger.info(
        f"Error {error_id} resolved by user {current_user.id}",
        extra={"error_type": error.error_type, "service_id": error.service_id}
    )
    
    return {"success": True, "message": "Error marked as resolved"}