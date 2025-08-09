"""Sync scheduler management endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from models.user import User
from services.sync_scheduler import get_sync_scheduler, SyncJob
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sync/scheduler")


class ScheduleSyncRequest(BaseModel):
    """Request to schedule a sync."""
    provider: str
    api_key_id: str
    delay_seconds: int = 0


class ScheduleSyncResponse(BaseModel):
    """Response from scheduling a sync."""
    job_id: str
    scheduled_at: str


class SyncJobResponse(BaseModel):
    """Sync job details."""
    id: str
    provider: str
    api_key_id: str
    agency_id: str
    status: str
    scheduled_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retry_count: int
    
    @classmethod
    def from_job(cls, job: SyncJob) -> "SyncJobResponse":
        """Create response from sync job."""
        return cls(
            id=job.id,
            provider=job.provider,
            api_key_id=job.api_key_id,
            agency_id=job.agency_id,
            status=job.status.value,
            scheduled_at=job.scheduled_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error=job.error,
            retry_count=job.retry_count
        )


class SchedulerStatsResponse(BaseModel):
    """Scheduler statistics."""
    running: bool
    active_syncs: int
    max_concurrent: int
    total_jobs: int
    job_stats: dict
    queue_size: int


@router.post("/schedule", response_model=ScheduleSyncResponse)
async def schedule_sync(
    request: ScheduleSyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Schedule a sync job.
    
    Requires sync management permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    try:
        scheduler = await get_sync_scheduler()
        
        # Schedule sync
        job_id = await scheduler.schedule_sync(
            provider=request.provider,
            api_key_id=request.api_key_id,
            agency_id=str(current_user.agency_id),
            delay_seconds=request.delay_seconds
        )
        
        # Get job details
        job = await scheduler.get_job_status(job_id)
        
        return ScheduleSyncResponse(
            job_id=job_id,
            scheduled_at=job.scheduled_at.isoformat() if job else ""
        )
    
    except Exception as e:
        logger.error(f"Failed to schedule sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/jobs/{job_id}")
async def cancel_sync(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a scheduled sync job.
    
    Requires sync management permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    try:
        scheduler = await get_sync_scheduler()
        
        # Verify job belongs to user's agency
        job = await scheduler.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sync job not found"
            )
        
        if job.agency_id != str(current_user.agency_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this job"
            )
        
        # Cancel job
        success = await scheduler.cancel_sync(job_id)
        
        return {"success": success}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/jobs/{job_id}", response_model=SyncJobResponse)
async def get_sync_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get sync job details.
    
    Requires authentication.
    """
    try:
        scheduler = await get_sync_scheduler()
        
        # Get job
        job = await scheduler.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sync job not found"
            )
        
        # Verify job belongs to user's agency
        if job.agency_id != str(current_user.agency_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this job"
            )
        
        return SyncJobResponse.from_job(job)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats", response_model=SchedulerStatsResponse)
async def get_scheduler_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get sync scheduler statistics.
    
    Requires admin role.
    """
    # Check permission
    check_permission(current_user, "system", "admin")
    
    try:
        scheduler = await get_sync_scheduler()
        stats = scheduler.get_stats()
        
        return SchedulerStatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Failed to get scheduler stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/api-keys/{api_key_id}/enable-sync")
async def enable_api_key_sync(
    api_key_id: str,
    sync_interval_minutes: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable automated sync for an API key.
    
    Requires API key management permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "write")
    
    try:
        from services.api_key_service import APIKeyService
        
        # Get and update API key
        api_key_service = APIKeyService(db)
        api_key = await api_key_service.get_by_id(api_key_id)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Verify ownership
        if api_key.agency_id != current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this API key"
            )
        
        # Enable sync
        api_key.sync_enabled = True
        api_key.sync_interval_minutes = sync_interval_minutes
        await db.commit()
        
        # Schedule immediate sync
        scheduler = await get_sync_scheduler()
        job_id = await scheduler.schedule_sync(
            provider=api_key.provider,
            api_key_id=api_key_id,
            agency_id=str(current_user.agency_id)
        )
        
        return {
            "success": True,
            "sync_enabled": True,
            "sync_interval_minutes": sync_interval_minutes,
            "initial_sync_job_id": job_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable API key sync: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/api-keys/{api_key_id}/disable-sync")
async def disable_api_key_sync(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable automated sync for an API key.
    
    Requires API key management permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "write")
    
    try:
        from services.api_key_service import APIKeyService
        
        # Get and update API key
        api_key_service = APIKeyService(db)
        api_key = await api_key_service.get_by_id(api_key_id)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Verify ownership
        if api_key.agency_id != current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this API key"
            )
        
        # Disable sync
        api_key.sync_enabled = False
        await db.commit()
        
        return {
            "success": True,
            "sync_enabled": False
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable API key sync: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )