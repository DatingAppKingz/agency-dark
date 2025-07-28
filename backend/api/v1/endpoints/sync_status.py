"""
Sync Status API endpoints.

Provides endpoints for monitoring and managing data synchronization
across external platforms (Inflow, OnlyFans).
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from core.database import get_db
from core.dependencies import get_current_active_user
from core.domain.models import User, ModelProfile
from core.tasks.sync_orchestrator import (
    SyncOrchestrator,
    SyncPlatform,
    SyncStatus
)
from pydantic import BaseModel, Field


router = APIRouter(prefix="/sync", tags=["sync"])


class SyncRequest(BaseModel):
    """Request to sync data for a model."""
    model_id: uuid.UUID
    platform: SyncPlatform = SyncPlatform.ALL
    force_full_sync: bool = False


class SyncResponse(BaseModel):
    """Response from sync operation."""
    sync_id: str
    model_id: str
    status: SyncStatus
    started_at: str
    completed_at: Optional[str] = None
    platforms: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []


class SyncStatusResponse(BaseModel):
    """Current sync status for a model."""
    model_id: str
    status: SyncStatus
    last_sync: Optional[Dict[str, Any]] = None
    next_sync: Optional[str] = None
    platforms: Dict[str, Dict[str, Any]] = {}


class SyncHistoryItem(BaseModel):
    """Sync history entry."""
    sync_id: str
    started_at: str
    completed_at: Optional[str]
    status: SyncStatus
    platforms: Dict[str, Any]
    errors: List[Dict[str, str]]


class SyncScheduleRequest(BaseModel):
    """Request to schedule a sync."""
    model_id: uuid.UUID
    platform: SyncPlatform = SyncPlatform.ALL
    delay_minutes: int = Field(0, ge=0, le=1440)  # Max 24 hours


class SyncScheduleResponse(BaseModel):
    """Response from scheduling a sync."""
    job_id: str
    model_id: str
    scheduled_for: str
    platform: SyncPlatform


class SyncStatsResponse(BaseModel):
    """Sync statistics for dashboard."""
    total_syncs_today: int
    successful_syncs: int
    failed_syncs: int
    average_sync_duration: float
    last_sync_time: Optional[str]
    models_synced_today: int
    total_records_synced: Dict[str, int]


@router.post("/sync-now", response_model=SyncResponse)
async def sync_model_now(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Trigger immediate sync for a model."""
    # Check permissions
    if current_user.role not in ['super_admin', 'agency_owner', 'agency_admin', 'model']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get model and verify access
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == request.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check user has access to this model
    if current_user.role == 'model' and model.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in ['agency_owner', 'agency_admin'] and model.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if model has API keys
    if request.platform == SyncPlatform.ALL:
        if not model.inflow_api_key and not model.onlyfans_api_key:
            raise HTTPException(
                status_code=400,
                detail="No API keys configured for this model"
            )
    elif request.platform == SyncPlatform.INFLOW and not model.inflow_api_key:
        raise HTTPException(status_code=400, detail="No Inflow API key configured")
    elif request.platform == SyncPlatform.ONLYFANS and not model.onlyfans_api_key:
        raise HTTPException(status_code=400, detail="No OnlyFans API key configured")
    
    # Create orchestrator
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    # Check if sync is already running
    status = await orchestrator.get_sync_status(str(model.id))
    if status.get('status') == SyncStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Sync is already running for this model"
        )
    
    # Start sync in background
    sync_id = f"sync_{model.id}_{datetime.utcnow().timestamp()}"
    
    async def run_sync():
        async with get_db() as sync_db:
            sync_orchestrator = SyncOrchestrator(sync_db)
            await sync_orchestrator.initialize()
            await sync_orchestrator.sync_model(
                model,
                platform=request.platform,
                force_full_sync=request.force_full_sync
            )
    
    background_tasks.add_task(run_sync)
    
    return SyncResponse(
        sync_id=sync_id,
        model_id=str(model.id),
        status=SyncStatus.RUNNING,
        started_at=datetime.utcnow().isoformat(),
        platforms={}
    )


@router.get("/status/{model_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    model_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current sync status for a model."""
    # Verify access
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check permissions
    if current_user.role == 'model' and model.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in ['agency_owner', 'agency_admin'] and model.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get sync status
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    status = await orchestrator.get_sync_status(str(model.id))
    
    # Get platform-specific status
    platform_status = {}
    
    if model.inflow_api_key:
        platform_status['inflow'] = {
            'configured': True,
            'last_sync': model.last_sync_at.isoformat() if model.last_sync_at else None,
            'status': 'active'
        }
    
    if model.onlyfans_api_key:
        platform_status['onlyfans'] = {
            'configured': True,
            'last_sync': model.last_sync_at.isoformat() if model.last_sync_at else None,
            'status': 'active'
        }
    
    return SyncStatusResponse(
        model_id=str(model.id),
        status=status.get('status', SyncStatus.PENDING),
        last_sync=status.get('last_sync'),
        next_sync=status.get('next_sync'),
        platforms=platform_status
    )


@router.get("/history/{model_id}", response_model=List[SyncHistoryItem])
async def get_sync_history(
    model_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sync history for a model."""
    # Verify access
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check permissions
    if current_user.role == 'model' and model.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in ['agency_owner', 'agency_admin'] and model.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get sync history
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    history = await orchestrator.get_sync_history(str(model.id), limit=limit)
    
    return [
        SyncHistoryItem(
            sync_id=item.get('sync_id', ''),
            started_at=item.get('started_at', ''),
            completed_at=item.get('completed_at'),
            status=item.get('status', SyncStatus.PENDING),
            platforms=item.get('platforms', {}),
            errors=item.get('errors', [])
        )
        for item in history
    ]


@router.post("/schedule", response_model=SyncScheduleResponse)
async def schedule_sync(
    request: SyncScheduleRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Schedule a sync for later."""
    # Verify access
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == request.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check permissions
    if current_user.role == 'model' and model.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in ['agency_owner', 'agency_admin'] and model.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Schedule sync
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    job_id = await orchestrator.schedule_sync(
        str(model.id),
        platform=request.platform,
        delay_minutes=request.delay_minutes
    )
    
    scheduled_time = datetime.utcnow() + timedelta(minutes=request.delay_minutes)
    
    return SyncScheduleResponse(
        job_id=job_id,
        model_id=str(model.id),
        scheduled_for=scheduled_time.isoformat(),
        platform=request.platform
    )


@router.delete("/schedule/{job_id}")
async def cancel_scheduled_sync(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a scheduled sync."""
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    success = await orchestrator.cancel_sync(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Scheduled sync not found")
    
    return {"message": "Sync cancelled successfully"}


@router.get("/stats", response_model=SyncStatsResponse)
async def get_sync_statistics(
    agency_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sync statistics for dashboard."""
    # Check permissions
    if current_user.role not in ['super_admin', 'agency_owner', 'agency_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if agency_id and current_user.role != 'super_admin':
        if current_user.agency_id != agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != 'super_admin':
        agency_id = current_user.agency_id
    
    # Get models for the agency
    query = select(ModelProfile)
    if agency_id:
        query = query.where(ModelProfile.agency_id == agency_id)
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    # Aggregate statistics
    orchestrator = SyncOrchestrator(db)
    await orchestrator.initialize()
    
    stats = {
        'total_syncs_today': 0,
        'successful_syncs': 0,
        'failed_syncs': 0,
        'average_sync_duration': 0.0,
        'last_sync_time': None,
        'models_synced_today': 0,
        'total_records_synced': {
            'subscribers': 0,
            'transactions': 0,
            'content': 0,
            'messages': 0
        }
    }
    
    total_duration = 0.0
    sync_count = 0
    
    for model in models:
        # Get sync history for today
        history = await orchestrator.get_sync_history(str(model.id), limit=50)
        
        for sync in history:
            sync_date = datetime.fromisoformat(sync.get('started_at', ''))
            if sync_date.date() == datetime.utcnow().date():
                stats['total_syncs_today'] += 1
                
                if sync.get('status') == SyncStatus.COMPLETED:
                    stats['successful_syncs'] += 1
                elif sync.get('status') == SyncStatus.FAILED:
                    stats['failed_syncs'] += 1
                
                # Calculate duration
                if sync.get('completed_at') and sync.get('started_at'):
                    start = datetime.fromisoformat(sync['started_at'])
                    end = datetime.fromisoformat(sync['completed_at'])
                    duration = (end - start).total_seconds()
                    total_duration += duration
                    sync_count += 1
                
                # Count records
                for platform, platform_data in sync.get('platforms', {}).items():
                    if isinstance(platform_data, dict):
                        stats['total_records_synced']['subscribers'] += \
                            platform_data.get('subscribers', {}).get('added', 0)
                        stats['total_records_synced']['transactions'] += \
                            platform_data.get('transactions', {}).get('added', 0)
                        stats['total_records_synced']['content'] += \
                            platform_data.get('content', {}).get('added', 0)
                        stats['total_records_synced']['messages'] += \
                            platform_data.get('messages', {}).get('processed', 0)
        
        if model.last_sync_at and model.last_sync_at.date() == datetime.utcnow().date():
            stats['models_synced_today'] += 1
        
        if model.last_sync_at:
            if not stats['last_sync_time'] or model.last_sync_at > datetime.fromisoformat(stats['last_sync_time']):
                stats['last_sync_time'] = model.last_sync_at.isoformat()
    
    if sync_count > 0:
        stats['average_sync_duration'] = total_duration / sync_count
    
    return SyncStatsResponse(**stats)


@router.post("/sync-all")
async def sync_all_models(
    platform: SyncPlatform = SyncPlatform.ALL,
    agency_id: Optional[uuid.UUID] = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Sync all models for an agency."""
    # Check permissions
    if current_user.role not in ['super_admin', 'agency_owner', 'agency_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if agency_id and current_user.role != 'super_admin':
        if current_user.agency_id != agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != 'super_admin':
        agency_id = current_user.agency_id
    
    # Run sync in background
    async def run_bulk_sync():
        async with get_db() as sync_db:
            orchestrator = SyncOrchestrator(sync_db)
            await orchestrator.initialize()
            await orchestrator.sync_all_models(
                agency_id=str(agency_id) if agency_id else None,
                platform=platform
            )
    
    background_tasks.add_task(run_bulk_sync)
    
    return {
        "message": "Bulk sync started",
        "agency_id": str(agency_id) if agency_id else None,
        "platform": platform
    }