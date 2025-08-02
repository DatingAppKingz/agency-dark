"""
Inflow API wrapper endpoints.

These endpoints provide access to Inflow functionality through our wrapper.
"""
import logging
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.dependencies import CurrentUser, Model, require_model
from core.domain.models import ModelProfile, User
from .application.service import InflowService
from .application.sync_service import InflowSyncService
from .domain.schemas import (
    InflowUser,
    InflowContent,
    InflowMessage,
    InflowAnalytics,
    InflowSubscription
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inflow", tags=["inflow"])

# Import webhook router
# TODO: Fix this import - api.py is a module, not a package
# from modules.inflow_wrapper.api.webhooks import router as webhook_router
# router.include_router(webhook_router)


async def get_model_profile(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> ModelProfile:
    """Get model profile with permission checks."""
    # Query model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model profile not found"
        )
    
    # Check permissions
    if current_user.role == "model" and model_profile.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this model"
        )
    
    if current_user.role in ["chatter", "agency_member"] and current_user.agency_id != model_profile.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access models from other agencies"
        )
    
    return model_profile


@router.post("/models/{model_id}/sync/subscribers")
async def sync_subscribers(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Sync subscribers from Inflow for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    if not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inflow API key not configured for this model"
        )
    
    service = InflowService(db)
    try:
        synced_count = await service.sync_subscribers(model_profile)
        return {
            "status": "success",
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} subscribers"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync subscribers: {str(e)}"
        )


@router.post("/models/{model_id}/sync/messages")
async def sync_messages(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    since: Optional[datetime] = Query(None, description="Sync messages since this timestamp")
):
    """Sync messages from Inflow for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    service = InflowService(db)
    try:
        message_count = await service.sync_messages(model_profile, since)
        return {
            "status": "success",
            "message_count": message_count,
            "message": f"Successfully synced {message_count} messages"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync messages: {str(e)}"
        )


@router.get("/models/{model_id}/content", response_model=List[InflowContent])
async def list_content(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    content_type: Optional[str] = Query(None, description="Filter by content type")
):
    """List content from Inflow for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    service = InflowService(db)
    try:
        content = await service.list_content(model_profile, content_type)
        return content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch content: {str(e)}"
        )


@router.post("/models/{model_id}/messages")
async def send_message(
    model_id: UUID,
    fan_id: UUID,
    content: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    price: Optional[float] = None
):
    """Send a message through Inflow."""
    # Only models and chatters can send messages
    if current_user.role not in ["model", "chatter", "super_admin", "agency_owner", "agency_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages"
        )
    
    model_profile = await get_model_profile(model_id, current_user, db)
    
    service = InflowService(db)
    try:
        message = await service.send_message(
            model_profile=model_profile,
            fan_id=str(fan_id),
            content=content,
            price=price
        )
        return {
            "status": "success",
            "message_id": message.id,
            "created_at": message.created_at
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/models/{model_id}/analytics", response_model=InflowAnalytics)
async def get_analytics(
    model_id: UUID,
    start_date: date,
    end_date: date,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get analytics from Inflow for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Convert dates to datetime
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    service = InflowService(db)
    try:
        analytics = await service.get_analytics(
            model_profile=model_profile,
            start_date=start_datetime,
            end_date=end_datetime
        )
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )


@router.post("/test-connection/{model_id}")
async def test_connection(
    model_id: UUID,
    current_user: Model,  # Only models can test their own connection
    db: AsyncSession = Depends(get_db)
):
    """Test Inflow API connection for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    if model_profile.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only test your own API connection"
        )
    
    if not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inflow API key not configured"
        )
    
    service = InflowService(db)
    try:
        client = await service.get_client(model_profile)
        user = await client.get_current_user()
        return {
            "status": "success",
            "connected": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }


@router.post("/models/{model_id}/sync/all")
async def sync_all_data(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    start_date: Optional[date] = Query(None, description="Start date for transaction sync"),
    end_date: Optional[date] = Query(None, description="End date for transaction sync"),
    force: bool = Query(False, description="Force resync even if recently synced")
):
    """
    Sync all data from Inflow for a model.
    
    This includes:
    - Subscribers/fans
    - Content
    - Financial transactions
    - Messages (for PPV tracking)
    - Analytics
    
    Only models, agency owners, and admins can trigger sync.
    """
    if current_user.role not in ["model", "super_admin", "agency_owner", "agency_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to sync data"
        )
    
    model_profile = await get_model_profile(model_id, current_user, db)
    
    if not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inflow API key not configured for this model"
        )
    
    # Check if recently synced (unless force=True)
    if not force and model_profile.last_sync_at:
        time_since_sync = datetime.utcnow() - model_profile.last_sync_at
        if time_since_sync.total_seconds() < 300:  # 5 minutes
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Model was synced {int(time_since_sync.total_seconds())} seconds ago. Wait 5 minutes or use force=true"
            )
    
    sync_service = InflowSyncService(db)
    
    try:
        # Convert dates if provided
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
        
        # Perform sync
        sync_results = await sync_service.sync_all_data(
            model_profile=model_profile,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        return {
            "status": "success",
            "model_id": str(model_id),
            "sync_results": sync_results,
            "last_sync": model_profile.last_sync_at
        }
        
    except Exception as e:
        logger.error(f"Failed to sync Inflow data for model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync data: {str(e)}"
        )


@router.post("/models/{model_id}/sync/transactions")
async def sync_transactions(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    start_date: date = Query(..., description="Start date for transaction sync"),
    end_date: date = Query(..., description="End date for transaction sync")
):
    """
    Sync only financial transactions from Inflow.
    
    This creates proper FinancialTransaction records with commission calculations.
    """
    model_profile = await get_model_profile(model_id, current_user, db)
    
    if not model_profile.inflow_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inflow API key not configured for this model"
        )
    
    sync_service = InflowSyncService(db)
    
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync transactions: {str(e)}"
        )


@router.get("/models/{model_id}/sync/status")
async def get_sync_status(
    model_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get the sync status for a model."""
    model_profile = await get_model_profile(model_id, current_user, db)
    
    # Calculate sync freshness
    sync_age = None
    is_fresh = False
    if model_profile.last_sync_at:
        sync_age = (datetime.utcnow() - model_profile.last_sync_at).total_seconds()
        is_fresh = sync_age < 3600  # Fresh if synced within last hour
    
    return {
        "model_id": str(model_id),
        "has_api_key": bool(model_profile.inflow_api_key),
        "last_sync": model_profile.last_sync_at,
        "sync_age_seconds": sync_age,
        "is_fresh": is_fresh,
        "subscriber_count": model_profile.subscriber_count,
        "analytics": None  # TODO: Implement analytics storage
    }