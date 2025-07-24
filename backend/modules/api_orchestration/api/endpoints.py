"""
API Orchestration endpoints.

Provides unified access to data and functionality from multiple sources.
"""
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.database import get_db
from core.dependencies import get_current_user, RoleChecker
from core.domain.models import User, UserRole, ModelProfile
from modules.api_orchestration.application.orchestrator import APIOrchestrator
from modules.api_orchestration.domain.schemas import (
    UnifiedFan,
    UnifiedMessage,
    UnifiedAnalytics,
    SyncStatus,
    MessageRequest,
    MassMessageRequest,
    ContentPost,
    DataSource
)


router = APIRouter(prefix="/orchestration", tags=["orchestration"])


async def get_model_profile(
    model_id: str,
    user: User,
    db: AsyncSession
) -> ModelProfile:
    """Get model profile with permission check."""
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model profile not found")
    
    # Check permissions
    if user.role == UserRole.SUPER_ADMIN:
        # Super admin can access any model
        pass
    elif user.role == UserRole.AGENCY_OWNER:
        # Agency owner can access models in their agency
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    elif user.role == UserRole.MODEL:
        # Model can only access their own profile
        if model_profile.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your model profile")
    elif user.role in [UserRole.AGENCY_MEMBER, UserRole.CHATTER, UserRole.AGENCY_MEMBER]:
        # Staff can access models in their agency
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return model_profile


@router.get("/fans/{model_id}", response_model=List[UnifiedFan])
async def get_unified_fans(
    model_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_unclaimed: bool = Query(True),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.CHATTER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unified list of fans from all sources.
    
    - **model_id**: Model profile ID
    - **limit**: Maximum number of fans to return
    - **offset**: Number of fans to skip
    - **include_unclaimed**: Include fans not claimed by any chatter
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    orchestrator = APIOrchestrator(db)
    fans = await orchestrator.get_unified_fans(
        model_profile=model_profile,
        limit=limit,
        offset=offset,
        include_unclaimed=include_unclaimed
    )
    
    return fans


@router.post("/sync/{model_id}")
async def trigger_sync(
    model_id: str,
    background_tasks: BackgroundTasks,
    sync_inflow: bool = Query(True),
    sync_onlyfans: bool = Query(True),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger data synchronization from all configured sources.
    
    - **model_id**: Model profile ID
    - **sync_inflow**: Sync data from Inflow API
    - **sync_onlyfans**: Sync data from OnlyFans API
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Check if APIs are configured
    if sync_inflow and not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=400,
            detail="Inflow API key not configured for this model"
        )
    
    if sync_onlyfans and not model_profile.onlyfans_api_key:
        raise HTTPException(
            status_code=400,
            detail="OnlyFans API key not configured for this model"
        )
    
    orchestrator = APIOrchestrator(db)
    
    # Check if sync is already running
    current_status = await orchestrator.get_sync_status(str(model_profile.id))
    if current_status and current_status.is_syncing:
        raise HTTPException(
            status_code=409,
            detail="Sync is already in progress"
        )
    
    # Trigger sync in background
    background_tasks.add_task(
        orchestrator.sync_all_data,
        model_profile,
        sync_inflow,
        sync_onlyfans
    )
    
    return {
        "status": "sync_started",
        "model_id": str(model_profile.id),
        "sync_inflow": sync_inflow,
        "sync_onlyfans": sync_onlyfans
    }


@router.get("/sync/{model_id}/status", response_model=SyncStatus)
async def get_sync_status(
    model_id: str,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.CHATTER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current synchronization status.
    
    - **model_id**: Model profile ID
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    orchestrator = APIOrchestrator(db)
    status = await orchestrator.get_sync_status(str(model_profile.id))
    
    if not status:
        # Return default status if no sync has been run
        status = SyncStatus(
            model_id=str(model_profile.id),
            inflow_enabled=bool(model_profile.inflow_api_key),
            onlyfans_enabled=bool(model_profile.onlyfans_api_key)
        )
    
    return status


@router.post("/messages/send")
async def send_message(
    request: MessageRequest,
    model_id: str = Query(..., description="Model profile ID"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.CHATTER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message through the best available channel.
    
    - **model_id**: Model profile ID
    - **request**: Message details including fan ID, text, media, and price
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    orchestrator = APIOrchestrator(db)
    
    try:
        result = await orchestrator.send_message(
            model_profile=model_profile,
            request=request,
            user=current_user
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post("/messages/mass-send")
async def send_mass_message(
    request: MassMessageRequest,
    background_tasks: BackgroundTasks,
    model_id: str = Query(..., description="Model profile ID"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Send mass messages to multiple fans.
    
    - **model_id**: Model profile ID
    - **request**: Mass message details including fan IDs, content, and filters
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Validate fan count
    if len(request.fan_ids) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Cannot send to more than 1000 fans at once"
        )
    
    # TODO: Implement mass message sending in background
    # For now, return a placeholder response
    return {
        "status": "scheduled",
        "campaign_name": request.campaign_name,
        "fan_count": len(request.fan_ids),
        "scheduled_at": request.scheduled_at or datetime.utcnow()
    }


@router.get("/analytics/{model_id}", response_model=UnifiedAnalytics)
async def get_unified_analytics(
    model_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get combined analytics from all sources.
    
    - **model_id**: Model profile ID
    - **start_date**: Start date for analytics period
    - **end_date**: End date for analytics period
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Convert dates to datetime
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    orchestrator = APIOrchestrator(db)
    analytics = await orchestrator.get_unified_analytics(
        model_profile=model_profile,
        start_date=start_datetime,
        end_date=end_datetime
    )
    
    return analytics


@router.post("/content/post")
async def create_content_post(
    request: ContentPost,
    model_id: str = Query(..., description="Model profile ID"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Create content post across multiple platforms.
    
    - **model_id**: Model profile ID
    - **request**: Content details including text, media, and platform targeting
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Validate platform configuration
    if request.post_to_onlyfans and not model_profile.onlyfans_api_key:
        raise HTTPException(
            status_code=400,
            detail="OnlyFans API key not configured"
        )
    
    if request.post_to_inflow and not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=400,
            detail="Inflow API key not configured"
        )
    
    # TODO: Implement content posting across platforms
    # For now, return a placeholder response
    return {
        "status": "scheduled" if not request.publish_immediately else "published",
        "platforms": [],
        "scheduled_at": request.scheduled_at
    }


@router.get("/messages/{model_id}", response_model=List[UnifiedMessage])
async def get_unified_messages(
    model_id: str,
    fan_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.CHATTER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unified messages from all sources.
    
    - **model_id**: Model profile ID
    - **fan_id**: Filter by specific fan (optional)
    - **limit**: Maximum number of messages to return
    - **offset**: Number of messages to skip
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # TODO: Implement unified message retrieval
    # For now, return an empty list
    return []