"""
Enhanced API Orchestration endpoints.

Provides unified access to multiple APIs with intelligent routing,
conflict resolution, and automatic failover.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user
from core.domain.models import User, ModelProfile
from sqlalchemy import select

from ..application.orchestrator_v2 import EnhancedAPIOrchestrator
from ..application.routing_service import IntelligentRouter
from ..application.conflict_resolver import ConflictResolver
from ..application.login_sync_service import LoginSyncService
from ..domain.schemas import (
    DataSource,
    ConflictResolution,
    UnifiedFan,
    UnifiedMessage,
    UnifiedAnalytics,
    SyncStatus,
    MessageRequest,
    MassMessageRequest,
    ContentPost
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/orchestration", tags=["api-orchestration-v2"])


@router.post("/sync/on-login")
async def sync_on_login(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger data synchronization on user login.
    
    This endpoint automatically syncs data from configured APIs
    when a user logs in, based on their role and preferences.
    """
    sync_service = LoginSyncService(db)
    
    # Start sync (mostly in background)
    sync_statuses = await sync_service.sync_on_login(current_user)
    
    return {
        "message": f"Login sync initiated for {len(sync_statuses)} models",
        "sync_statuses": [
            {
                "model_id": status.model_id,
                "is_syncing": status.is_syncing,
                "sources": {
                    "inflow": status.inflow_enabled,
                    "onlyfans": status.onlyfans_enabled
                }
            }
            for status in sync_statuses
        ]
    }


@router.post("/sync/configure")
async def configure_sync_settings(
    enabled: bool,
    sync_on_login: bool = True,
    sync_interval_hours: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Configure automatic synchronization settings."""
    sync_service = LoginSyncService(db)
    
    await sync_service.configure_auto_sync(
        current_user,
        enabled=enabled,
        sync_on_login=sync_on_login,
        sync_interval_hours=sync_interval_hours
    )
    
    return {
        "message": "Sync settings updated",
        "settings": {
            "enabled": enabled,
            "sync_on_login": sync_on_login,
            "sync_interval_hours": sync_interval_hours or 24
        }
    }


@router.get("/sync/history")
async def get_sync_history(
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get synchronization history for the current user."""
    sync_service = LoginSyncService(db)
    history = await sync_service.get_sync_history(current_user, limit)
    
    return {
        "history": history,
        "count": len(history)
    }


@router.post("/models/{model_id}/sync")
async def sync_model_data(
    model_id: str,
    force: bool = False,
    sync_inflow: bool = True,
    sync_onlyfans: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SyncStatus:
    """
    Manually trigger data synchronization for a model.
    
    This endpoint syncs data from all configured APIs with
    intelligent conflict resolution and deduplication.
    """
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Check permissions
    if current_user.role == "model" and model_profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.role in ["chatter", "agency_member"] and current_user.agency_id != model_profile.agency_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    orchestrator = EnhancedAPIOrchestrator(db)
    
    sync_status = await orchestrator.sync_all_data(
        model_profile,
        sync_inflow=sync_inflow,
        sync_onlyfans=sync_onlyfans,
        force=force
    )
    
    return sync_status


@router.get("/models/{model_id}/sync/status")
async def get_sync_status(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Optional[SyncStatus]:
    """Get current synchronization status for a model."""
    orchestrator = EnhancedAPIOrchestrator(db)
    return await orchestrator.get_sync_status(model_id)


@router.post("/messages/send")
async def send_message_with_routing(
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message using intelligent routing.
    
    This endpoint automatically selects the best API to use based on
    availability, rate limits, cost, and performance history.
    """
    # Get fan's model
    from core.domain.models import Fan
    fan = await db.get(Fan, request.fan_id)
    if not fan:
        raise HTTPException(status_code=404, detail="Fan not found")
        
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == fan.model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Use intelligent routing if no preference specified
    if not request.preferred_source:
        router = IntelligentRouter(db)
        request.preferred_source = await router.determine_best_source(
            model_profile,
            operation_type="message",
            fan=fan,
            payload_size=len(request.text or "") + len(request.media_ids or []) * 1000,
            features_required=["ppv_messages"] if request.price else None
        )
        
    orchestrator = EnhancedAPIOrchestrator(db)
    
    # Record start time for metrics
    start_time = datetime.utcnow()
    
    try:
        result = await orchestrator.send_message_with_failover(
            model_profile,
            request,
            current_user
        )
        
        # Record success metrics
        if request.preferred_source:
            router = IntelligentRouter(db)
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            await router.record_api_call(
                model_profile,
                request.preferred_source,
                "message",
                response_time,
                success=True
            )
            
        return result
        
    except Exception as e:
        # Record failure metrics
        if request.preferred_source:
            router = IntelligentRouter(db)
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            await router.record_api_call(
                model_profile,
                request.preferred_source,
                "message",
                response_time,
                success=False,
                error=str(e)
            )
        raise


@router.post("/messages/mass-send")
async def send_mass_message(
    request: MassMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send mass messages with intelligent routing and rate limit management.
    
    This endpoint initiates a mass messaging campaign that runs in the background,
    automatically managing rate limits and using intelligent routing to maximize
    delivery success.
    """
    # Validate user has permission
    if current_user.role not in ["model", "super_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Not authorized for mass messaging")
        
    # Get model profile
    if current_user.role == "model":
        result = await db.execute(
            select(ModelProfile).where(ModelProfile.user_id == current_user.id)
        )
        model_profile = result.scalar_one_or_none()
        if not model_profile:
            raise HTTPException(status_code=404, detail="Model profile not found")
    else:
        # For agency owners/admins, require model_id in request
        if not request.model_id:
            raise HTTPException(status_code=400, detail="model_id required for agency users")
            
        result = await db.execute(
            select(ModelProfile).where(ModelProfile.id == request.model_id)
        )
        model_profile = result.scalar_one_or_none()
        
        if not model_profile:
            raise HTTPException(status_code=404, detail="Model not found")
            
        # Verify agency access
        if current_user.agency_id != model_profile.agency_id:
            raise HTTPException(status_code=403, detail="Not authorized for this model")
            
    # Import here to avoid circular imports
    from ..application.mass_message_service import MassMessageService
    
    service = MassMessageService(db)
    status = await service.send_mass_message(model_profile, request, current_user)
    
    return status


@router.get("/routing/recommendation")
async def get_routing_recommendation(
    model_id: str,
    operation_type: str,
    fan_id: Optional[str] = None,
    payload_size: Optional[int] = None,
    features: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get routing recommendation for an API operation.
    
    Returns the recommended API source and scoring breakdown.
    """
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Get fan if specified
    fan = None
    if fan_id:
        from core.domain.models import Fan
        fan = await db.get(Fan, fan_id)
        
    router = IntelligentRouter(db)
    
    # Get scores for all sources
    scores = []
    
    if model_profile.onlyfans_api_key:
        score = await router._calculate_source_score(
            model_profile,
            DataSource.ONLYFANS,
            operation_type,
            fan,
            payload_size,
            features
        )
        scores.append(score)
        
    if model_profile.inflow_api_key:
        score = await router._calculate_source_score(
            model_profile,
            DataSource.INFLOW,
            operation_type,
            fan,
            payload_size,
            features
        )
        scores.append(score)
        
    if not scores:
        raise HTTPException(status_code=400, detail="No API sources configured")
        
    # Sort by score
    scores.sort(key=lambda s: s.score, reverse=True)
    
    return {
        "recommendation": scores[0].source.value,
        "scores": [
            {
                "source": score.source.value,
                "total_score": round(score.score, 3),
                "factors": {
                    factor.value: round(value, 3)
                    for factor, value in score.factors.items()
                }
            }
            for score in scores
        ]
    }


@router.post("/conflicts/resolve")
async def resolve_data_conflicts(
    inflow_data: Dict[str, Any],
    onlyfans_data: Dict[str, Any],
    resolution_strategy: ConflictResolution = ConflictResolution.LATEST,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve conflicts between data from different sources.
    
    This endpoint demonstrates the conflict resolution logic
    that's automatically applied during synchronization.
    """
    resolver = ConflictResolver(db)
    
    resolved_data = resolver.resolve_fan_data(
        inflow_data,
        onlyfans_data,
        resolution_strategy
    )
    
    conflict_summary = resolver.get_conflict_summary()
    
    return {
        "resolved_data": resolved_data,
        "conflict_summary": conflict_summary
    }


@router.get("/messages/mass-send/{campaign_id}/status")
async def get_mass_message_status(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the status of a mass messaging campaign."""
    from ..application.mass_message_service import MassMessageService
    
    service = MassMessageService(db)
    status = await service.get_campaign_status(campaign_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    return status


@router.post("/messages/mass-send/{campaign_id}/cancel")
async def cancel_mass_message(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an active mass messaging campaign."""
    # Validate user has permission
    if current_user.role not in ["model", "super_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    from ..application.mass_message_service import MassMessageService
    
    service = MassMessageService(db)
    success = await service.cancel_campaign(campaign_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Campaign not found or already completed"
        )
        
    return {"message": "Campaign cancelled successfully"}


@router.get("/messages/mass-send/history")
async def get_mass_message_history(
    model_id: Optional[str] = None,
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get history of mass messaging campaigns."""
    # Get model profile
    if current_user.role == "model":
        result = await db.execute(
            select(ModelProfile).where(ModelProfile.user_id == current_user.id)
        )
        model_profile = result.scalar_one_or_none()
        if not model_profile:
            raise HTTPException(status_code=404, detail="Model profile not found")
    else:
        if not model_id:
            raise HTTPException(status_code=400, detail="model_id required")
            
        result = await db.execute(
            select(ModelProfile).where(ModelProfile.id == model_id)
        )
        model_profile = result.scalar_one_or_none()
        
        if not model_profile:
            raise HTTPException(status_code=404, detail="Model not found")
            
        # Verify access
        if current_user.agency_id != model_profile.agency_id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
    from ..application.mass_message_service import MassMessageService
    
    service = MassMessageService(db)
    history = await service.get_campaign_history(model_profile, limit)
    
    return {
        "campaigns": history,
        "count": len(history)
    }