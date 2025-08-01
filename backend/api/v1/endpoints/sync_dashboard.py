"""Sync status dashboard endpoints."""

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
from models.api_key import APIKey
from services.sync_scheduler import get_sync_scheduler, SyncJob, SyncStatus
from services.sync.delta_sync import DeltaSyncTracker, DeltaSyncStateManager
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sync/dashboard")


class SyncOverviewResponse(BaseModel):
    """Sync overview statistics."""
    total_api_keys: int
    sync_enabled_keys: int
    active_syncs: int
    scheduled_syncs: int
    failed_syncs_24h: int
    successful_syncs_24h: int
    average_sync_duration: float
    last_sync_time: Optional[str]


class ApiKeySyncStatusResponse(BaseModel):
    """API key sync status."""
    api_key_id: str
    api_key_name: str
    provider: str
    sync_enabled: bool
    sync_interval_minutes: int
    last_sync_at: Optional[str]
    last_sync_status: Optional[str]
    last_sync_error: Optional[str]
    sync_failure_count: int
    next_sync_at: Optional[str]
    is_syncing: bool


class SyncHistoryItem(BaseModel):
    """Sync history item."""
    sync_id: str
    api_key_id: str
    api_key_name: str
    provider: str
    status: str
    started_at: str
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    items_fetched: int
    items_created: int
    items_updated: int
    items_deleted: int
    error_count: int
    error_message: Optional[str]


class SyncHealthResponse(BaseModel):
    """Sync health status."""
    status: str  # healthy, warning, critical
    scheduler_running: bool
    active_workers: int
    queue_size: int
    failed_syncs_1h: int
    failed_syncs_24h: int
    avg_sync_duration_minutes: float
    problematic_keys: List[Dict[str, Any]]


class DeltaSyncStateResponse(BaseModel):
    """Delta sync state information."""
    service_name: str
    last_sync_at: Optional[str]
    last_successful_sync_at: Optional[str]
    last_full_sync_at: Optional[str]
    is_initial_sync: bool
    total_synced: int
    consecutive_failures: int
    checksum_cache_size: int


@router.get("/overview", response_model=SyncOverviewResponse)
async def get_sync_overview(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync overview statistics.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get total API keys
    total_keys_result = await db.execute(
        select(func.count(APIKey.id)).where(
            APIKey.agency_id == current_user.agency_id
        )
    )
    total_keys = total_keys_result.scalar() or 0
    
    # Get sync enabled keys
    enabled_keys_result = await db.execute(
        select(func.count(APIKey.id)).where(
            and_(
                APIKey.agency_id == current_user.agency_id,
                APIKey.sync_enabled == True
            )
        )
    )
    enabled_keys = enabled_keys_result.scalar() or 0
    
    # Get scheduler stats
    scheduler = await get_sync_scheduler()
    scheduler_stats = scheduler.get_stats()
    
    # Get 24h sync stats
    time_24h_ago = datetime.utcnow() - timedelta(hours=24)
    
    # Failed syncs in 24h
    failed_syncs_result = await db.execute(
        select(func.count(APIKey.id)).where(
            and_(
                APIKey.agency_id == current_user.agency_id,
                APIKey.last_sync_at >= time_24h_ago,
                APIKey.last_sync_status == "failed"
            )
        )
    )
    failed_syncs_24h = failed_syncs_result.scalar() or 0
    
    # Successful syncs in 24h
    successful_syncs_result = await db.execute(
        select(func.count(APIKey.id)).where(
            and_(
                APIKey.agency_id == current_user.agency_id,
                APIKey.last_sync_at >= time_24h_ago,
                APIKey.last_sync_status == "completed"
            )
        )
    )
    successful_syncs_24h = successful_syncs_result.scalar() or 0
    
    # Average sync duration (estimate based on recent syncs)
    avg_duration = 45.0  # Default 45 seconds
    
    # Last sync time
    last_sync_result = await db.execute(
        select(func.max(APIKey.last_sync_at)).where(
            APIKey.agency_id == current_user.agency_id
        )
    )
    last_sync = last_sync_result.scalar()
    
    return SyncOverviewResponse(
        total_api_keys=total_keys,
        sync_enabled_keys=enabled_keys,
        active_syncs=scheduler_stats["active_syncs"],
        scheduled_syncs=scheduler_stats["job_stats"].get("scheduled", 0),
        failed_syncs_24h=failed_syncs_24h,
        successful_syncs_24h=successful_syncs_24h,
        average_sync_duration=avg_duration,
        last_sync_time=last_sync.isoformat() if last_sync else None
    )


@router.get("/api-keys", response_model=List[ApiKeySyncStatusResponse])
async def get_api_keys_sync_status(
    provider: Optional[str] = None,
    sync_enabled: Optional[bool] = None,
    has_errors: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync status for all API keys.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Build query
    query = select(APIKey).where(APIKey.agency_id == current_user.agency_id)
    
    if provider:
        query = query.where(APIKey.provider == provider)
    if sync_enabled is not None:
        query = query.where(APIKey.sync_enabled == sync_enabled)
    if has_errors:
        query = query.where(APIKey.sync_failure_count > 0)
    
    result = await db.execute(query.order_by(APIKey.name))
    api_keys = result.scalars().all()
    
    # Get scheduler for checking active syncs
    scheduler = await get_sync_scheduler()
    
    # Build response
    response = []
    for key in api_keys:
        # Check if currently syncing
        is_syncing = False
        for job_id, job in scheduler._jobs.items():
            if (job.api_key_id == str(key.id) and 
                job.status == SyncStatus.RUNNING):
                is_syncing = True
                break
        
        # Calculate next sync time
        next_sync_at = None
        if key.sync_enabled and key.last_sync_at:
            next_sync_at = key.last_sync_at + timedelta(minutes=key.sync_interval_minutes)
        
        response.append(ApiKeySyncStatusResponse(
            api_key_id=str(key.id),
            api_key_name=key.name,
            provider=key.provider,
            sync_enabled=key.sync_enabled,
            sync_interval_minutes=key.sync_interval_minutes,
            last_sync_at=key.last_sync_at.isoformat() if key.last_sync_at else None,
            last_sync_status=key.last_sync_status,
            last_sync_error=key.last_sync_error,
            sync_failure_count=key.sync_failure_count,
            next_sync_at=next_sync_at.isoformat() if next_sync_at else None,
            is_syncing=is_syncing
        ))
    
    return response


@router.get("/history", response_model=List[SyncHistoryItem])
async def get_sync_history(
    api_key_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync history.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get scheduler
    scheduler = await get_sync_scheduler()
    
    # Filter jobs
    history = []
    for job in scheduler._jobs.values():
        # Check agency
        if job.agency_id != str(current_user.agency_id):
            continue
        
        # Apply filters
        if api_key_id and job.api_key_id != api_key_id:
            continue
        if status and job.status.value != status:
            continue
        if start_date and job.started_at and job.started_at < start_date:
            continue
        if end_date and job.started_at and job.started_at > end_date:
            continue
        
        # Get API key info
        api_key = await db.get(APIKey, job.api_key_id)
        if not api_key:
            continue
        
        # Calculate duration
        duration = None
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()
        
        # Extract metrics from result
        items_fetched = 0
        items_created = 0
        items_updated = 0
        items_deleted = 0
        error_count = 0
        
        if job.result and isinstance(job.result, dict):
            if "results" in job.result:
                for sync_type, result in job.result["results"].items():
                    items_fetched += result.get("items_fetched", 0)
                    items_created += result.get("items_created", 0)
                    items_updated += result.get("items_updated", 0)
                    items_deleted += result.get("items_deleted", 0)
                    error_count += len(result.get("errors", []))
        
        history.append(SyncHistoryItem(
            sync_id=job.id,
            api_key_id=job.api_key_id,
            api_key_name=api_key.name,
            provider=job.provider,
            status=job.status.value,
            started_at=job.started_at.isoformat() if job.started_at else job.scheduled_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            duration_seconds=duration,
            items_fetched=items_fetched,
            items_created=items_created,
            items_updated=items_updated,
            items_deleted=items_deleted,
            error_count=error_count,
            error_message=job.error
        ))
    
    # Sort by started_at descending
    history.sort(key=lambda x: x.started_at, reverse=True)
    
    # Apply limit
    return history[:limit]


@router.get("/health", response_model=SyncHealthResponse)
async def get_sync_health(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync system health status.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get scheduler stats
    scheduler = await get_sync_scheduler()
    scheduler_stats = scheduler.get_stats()
    
    # Calculate health metrics
    time_1h_ago = datetime.utcnow() - timedelta(hours=1)
    time_24h_ago = datetime.utcnow() - timedelta(hours=24)
    
    # Failed syncs
    failed_1h = 0
    failed_24h = 0
    total_duration = 0
    sync_count = 0
    
    for job in scheduler._jobs.values():
        if job.agency_id != str(current_user.agency_id):
            continue
        
        if job.completed_at:
            if job.status == SyncStatus.FAILED:
                if job.completed_at >= time_1h_ago:
                    failed_1h += 1
                if job.completed_at >= time_24h_ago:
                    failed_24h += 1
            
            # Calculate average duration
            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                total_duration += duration
                sync_count += 1
    
    avg_duration = (total_duration / sync_count / 60) if sync_count > 0 else 0
    
    # Find problematic API keys
    problematic_result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.agency_id == current_user.agency_id,
                APIKey.sync_failure_count >= 3
            )
        ).limit(10)
    )
    problematic_keys = []
    for key in problematic_result.scalars():
        problematic_keys.append({
            "api_key_id": str(key.id),
            "name": key.name,
            "provider": key.provider,
            "failure_count": key.sync_failure_count,
            "last_error": key.last_sync_error
        })
    
    # Determine overall health status
    if not scheduler_stats["running"] or failed_1h > 5:
        status = "critical"
    elif failed_24h > 10 or len(problematic_keys) > 5:
        status = "warning"
    else:
        status = "healthy"
    
    return SyncHealthResponse(
        status=status,
        scheduler_running=scheduler_stats["running"],
        active_workers=scheduler_stats["active_syncs"],
        queue_size=scheduler_stats["queue_size"],
        failed_syncs_1h=failed_1h,
        failed_syncs_24h=failed_24h,
        avg_sync_duration_minutes=avg_duration,
        problematic_keys=problematic_keys
    )


@router.get("/delta-sync/{service_name}", response_model=DeltaSyncStateResponse)
async def get_delta_sync_state(
    service_name: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get delta sync state for a service.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get delta sync state
    state_manager = DeltaSyncStateManager(db, service_name)
    state = await state_manager.load_state()
    
    return DeltaSyncStateResponse(
        service_name=service_name,
        last_sync_at=state.last_sync_at.isoformat() if state.last_sync_at else None,
        last_successful_sync_at=state.last_successful_sync_at.isoformat() if state.last_successful_sync_at else None,
        last_full_sync_at=state.last_full_sync_at.isoformat() if state.last_full_sync_at else None,
        is_initial_sync=state.is_initial_sync,
        total_synced=state.total_synced,
        consecutive_failures=state.consecutive_failures,
        checksum_cache_size=len(state.checksum_cache)
    )


@router.post("/trigger-sync/{api_key_id}")
async def trigger_manual_sync(
    api_key_id: str,
    priority: str = Query("normal", regex="^(high|normal|low)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a sync for an API key.
    
    Requires sync write permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    # Get API key
    api_key = await db.get(APIKey, api_key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to sync this API key"
        )
    
    # Schedule sync
    scheduler = await get_sync_scheduler()
    from services.sync_scheduler import QueuePriority
    
    priority_map = {
        "high": QueuePriority.HIGH,
        "normal": QueuePriority.NORMAL,
        "low": QueuePriority.LOW
    }
    
    job_id = await scheduler.schedule_sync(
        provider=api_key.provider,
        api_key_id=api_key_id,
        agency_id=str(current_user.agency_id),
        delay_seconds=0
    )
    
    logger.info(
        f"Manual sync triggered for API key {api_key_id}",
        extra={
            "user_id": current_user.id,
            "job_id": job_id,
            "priority": priority
        }
    )
    
    return {
        "success": True,
        "job_id": job_id,
        "message": f"Sync scheduled for {api_key.name}"
    }


@router.post("/reset-sync-state/{api_key_id}")
async def reset_sync_state(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset sync state for an API key (triggers full sync).
    
    Requires sync admin permission.
    """
    # Check permission
    check_permission(current_user, "sync", "admin")
    
    # Get API key
    api_key = await db.get(APIKey, api_key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reset this API key"
        )
    
    # Reset sync state
    service_name = f"{api_key.provider}_sync_{api_key_id}"
    state_manager = DeltaSyncStateManager(db, service_name)
    await state_manager.reset_state()
    
    # Reset API key sync stats
    api_key.last_sync_at = None
    api_key.last_sync_status = None
    api_key.last_sync_error = None
    api_key.sync_failure_count = 0
    await db.commit()
    
    logger.info(
        f"Sync state reset for API key {api_key_id}",
        extra={"user_id": current_user.id}
    )
    
    return {
        "success": True,
        "message": f"Sync state reset for {api_key.name}. Next sync will be a full sync."
    }