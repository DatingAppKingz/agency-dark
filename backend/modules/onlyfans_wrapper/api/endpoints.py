"""
OnlyFans API endpoints.
"""
import logging
from typing import List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.dependencies import get_current_user, RoleChecker
from core.domain.models import User, UserRole, ModelProfile
from modules.onlyfans_wrapper.application.service import OnlyFansService
from modules.onlyfans_wrapper.application.sync_service import OnlyFansSyncService
from modules.onlyfans_wrapper.domain.schemas import (
    OnlyFansProfile,
    OnlyFansFan,
    OnlyFansMessage,
    OnlyFansPost,
    OnlyFansStatistics,
    MessageCreateRequest,
    PostCreateRequest
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onlyfans", tags=["onlyfans"])


async def get_model_profile_with_of_key(
    model_id: str,
    user: User,
    db: AsyncSession
) -> ModelProfile:
    """Get model profile and verify OnlyFans API key is configured."""
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model profile not found")
    
    # Check permissions
    if user.role == UserRole.SUPER_ADMIN:
        pass
    elif user.role == UserRole.AGENCY_OWNER:
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    elif user.role == UserRole.MODEL:
        if model_profile.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your model profile")
    elif user.role in [UserRole.AGENCY_MEMBER, UserRole.CHATTER, UserRole.AGENCY_MEMBER]:
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check OnlyFans API key
    if not model_profile.onlyfans_api_key:
        raise HTTPException(
            status_code=400,
            detail="OnlyFans API key not configured for this model"
        )
    
    return model_profile


@router.get("/profile/{model_id}", response_model=OnlyFansProfile)
async def get_profile(
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
    """Get OnlyFans profile information."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    profile = await service.get_profile(model_profile)
    
    return profile


@router.post("/profile/{model_id}/sync")
async def sync_profile(
    model_id: str,
    background_tasks: BackgroundTasks,
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
    """Sync OnlyFans profile data."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    
    # Run sync in background
    background_tasks.add_task(service.sync_profile, model_profile)
    
    return {"status": "sync_started", "model_id": str(model_profile.id)}


@router.get("/fans/{model_id}", response_model=List[OnlyFansFan])
async def get_fans(
    model_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_subscribers: bool = Query(False),
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
    """Get list of OnlyFans fans."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    fans = await service.get_fans(
        model_profile,
        limit=limit,
        offset=offset,
        only_subscribers=only_subscribers
    )
    
    return fans


@router.post("/fans/{model_id}/sync")
async def sync_fans(
    model_id: str,
    background_tasks: BackgroundTasks,
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
    """Sync OnlyFans fans data."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    
    # Run sync in background
    background_tasks.add_task(service.sync_fans, model_profile)
    
    return {"status": "sync_started", "model_id": str(model_profile.id)}


@router.get("/fans/{model_id}/{fan_id}", response_model=OnlyFansFan)
async def get_fan_details(
    model_id: str,
    fan_id: str,
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
    """Get detailed OnlyFans fan information."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    fan = await service.get_fan_details(model_profile, fan_id)
    
    if not fan:
        raise HTTPException(status_code=404, detail="Fan not found")
    
    return fan


@router.get("/messages/{model_id}", response_model=List[OnlyFansMessage])
async def get_messages(
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
    """Get OnlyFans messages."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    messages = await service.get_messages(
        model_profile,
        fan_id=fan_id,
        limit=limit,
        offset=offset
    )
    
    return messages


@router.post("/messages/{model_id}/send", response_model=OnlyFansMessage)
async def send_message(
    model_id: str,
    request: MessageCreateRequest,
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
    """Send a message on OnlyFans."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    
    try:
        message = await service.send_message(
            model_profile=model_profile,
            fan_id=request.fan_id,
            text=request.text,
            media_ids=request.media_ids,
            price=request.price
        )
        return message
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/posts/{model_id}", response_model=List[OnlyFansPost])
async def get_posts(
    model_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
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
    """Get OnlyFans posts."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    posts = await service.get_posts(
        model_profile,
        limit=limit,
        offset=offset
    )
    
    return posts


@router.post("/posts/{model_id}/create", response_model=OnlyFansPost)
async def create_post(
    model_id: str,
    request: PostCreateRequest,
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
    """Create a new OnlyFans post."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    service = OnlyFansService(db)
    
    try:
        post = await service.create_post(
            model_profile=model_profile,
            text=request.text,
            media_ids=request.media_ids,
            price=request.price
        )
        return post
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/statistics/{model_id}", response_model=OnlyFansStatistics)
async def get_statistics(
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
    """Get OnlyFans statistics for a date range."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    # Convert dates to datetime
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    service = OnlyFansService(db)
    stats = await service.get_statistics(
        model_profile,
        start_date=start_datetime,
        end_date=end_datetime
    )
    
    return stats


@router.post("/sync/{model_id}/all")
async def sync_all_data(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[date] = Query(None, description="Start date for transaction sync"),
    end_date: Optional[date] = Query(None, description="End date for transaction sync"),
    sync_messages: bool = Query(True, description="Whether to sync messages (can be slow)"),
    force: bool = Query(False, description="Force resync even if recently synced")
):
    """
    Sync all data from OnlyFans for a model.
    
    This includes:
    - Profile information
    - Fans/subscribers
    - Financial transactions
    - Posts/content
    - Messages (optional - can be slow)
    - Statistics
    
    Only models, agency owners, and admins can trigger sync.
    """
    if current_user.role not in [UserRole.MODEL, UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_MEMBER]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to sync data"
        )
    
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    # Check if recently synced (unless force=True)
    if not force and model_profile.last_sync_at:
        time_since_sync = datetime.utcnow() - model_profile.last_sync_at
        if time_since_sync.total_seconds() < 300:  # 5 minutes
            raise HTTPException(
                status_code=429,
                detail=f"Model was synced {int(time_since_sync.total_seconds())} seconds ago. Wait 5 minutes or use force=true"
            )
    
    sync_service = OnlyFansSyncService(db)
    
    try:
        # Convert dates if provided
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
        
        # Perform sync
        sync_results = await sync_service.sync_all_data(
            model_profile=model_profile,
            start_date=start_datetime,
            end_date=end_datetime,
            sync_messages=sync_messages
        )
        
        return {
            "status": "success",
            "model_id": str(model_id),
            "sync_results": sync_results,
            "last_sync": model_profile.last_sync_at
        }
        
    except Exception as e:
        logger.error(f"Failed to sync OnlyFans data for model {model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync data: {str(e)}"
        )


@router.post("/sync/{model_id}/transactions")
async def sync_transactions(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: date = Query(..., description="Start date for transaction sync"),
    end_date: date = Query(..., description="End date for transaction sync")
):
    """
    Sync only financial transactions from OnlyFans.
    
    This creates proper FinancialTransaction records with commission calculations.
    """
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    sync_service = OnlyFansSyncService(db)
    
    try:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        synced_count = await sync_service.sync_transactions(
            model_profile=model_profile,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        return {
            "status": "success",
            "synced_count": synced_count,
            "period": {
                "start": start_date,
                "end": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to sync transactions for model {model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync transactions: {str(e)}"
        )


@router.get("/sync/{model_id}/status")
async def get_sync_status(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the sync status for a model."""
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    # Calculate sync freshness
    sync_age = None
    is_fresh = False
    if model_profile.last_sync_at:
        sync_age = (datetime.utcnow() - model_profile.last_sync_at).total_seconds()
        is_fresh = sync_age < 3600  # Fresh if synced within last hour
    
    # Get recent stats if available
    stats = None
    try:
        service = OnlyFansService(db)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        stats = await service.get_statistics(model_profile, start_date, end_date)
    except:
        pass
    
    return {
        "model_id": str(model_id),
        "has_api_key": bool(model_profile.onlyfans_api_key),
        "last_sync": model_profile.last_sync_at,
        "sync_age_seconds": sync_age,
        "is_fresh": is_fresh,
        "subscriber_count": model_profile.subscriber_count,
        "total_earnings": float(model_profile.total_earnings) if model_profile.total_earnings else 0,
        "recent_stats": {
            "total_earnings": float(stats.total_earnings) if stats else None,
            "new_subscribers": stats.new_subscribers if stats else None,
            "expired_subscribers": stats.expired_subscribers if stats else None
        } if stats else None
    }


@router.post("/sync/{model_id}/fans")
async def sync_fans_detailed(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Sync fans with detailed subscription information.
    
    This not only syncs fan data but also creates/updates subscription records.
    """
    model_profile = await get_model_profile_with_of_key(model_id, current_user, db)
    
    sync_service = OnlyFansSyncService(db)
    
    try:
        # Run sync
        fan_count = await sync_service.sync_fans(model_profile)
        
        return {
            "status": "success",
            "synced_fans": fan_count,
            "subscriber_count": model_profile.subscriber_count,
            "paying_subscriber_count": model_profile.paying_subscriber_count
        }
        
    except Exception as e:
        logger.error(f"Failed to sync fans for model {model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync fans: {str(e)}"
        )