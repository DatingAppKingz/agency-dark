"""API usage tracking and statistics endpoints."""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import get_current_active_user
from core.rbac import check_permission
from models.user import User
from services.api_usage_tracker import get_usage_tracker, UsageMetric, RateLimitConfig
from services.api_key_service import APIKeyService
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/api-keys/{api_key_id}/usage")


class UsageStatsResponse(BaseModel):
    """Usage statistics response."""
    api_key_id: str
    period_start: str
    period_end: str
    metrics: dict


class RateLimitsResponse(BaseModel):
    """Rate limits configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    sync_operations_per_day: int
    data_fetch_mb_per_day: int
    webhooks_per_hour: int


class CurrentUsageResponse(BaseModel):
    """Current usage status."""
    requests: dict
    sync_operations: dict
    data_fetched: dict
    webhooks_sent: dict
    errors: dict
    limits: RateLimitsResponse


@router.get("/stats", response_model=List[UsageStatsResponse])
async def get_usage_stats(
    api_key_id: str,
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    lookback_days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get usage statistics for an API key.
    
    Requires API key read permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "read")
    
    # Verify API key ownership
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this API key"
        )
    
    # Get usage stats
    tracker = get_usage_tracker()
    stats = await tracker.get_usage_stats(api_key_id, period, lookback_days)
    
    return [
        UsageStatsResponse(
            api_key_id=stat.api_key_id,
            period_start=stat.period_start.isoformat(),
            period_end=stat.period_end.isoformat(),
            metrics=stat.metrics
        )
        for stat in stats
    ]


@router.get("/current", response_model=CurrentUsageResponse)
async def get_current_usage(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current usage and limits for an API key.
    
    Requires API key read permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "read")
    
    # Verify API key ownership
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this API key"
        )
    
    # Get current usage
    tracker = get_usage_tracker()
    now = datetime.utcnow()
    
    # Build usage response
    usage = {
        "requests": {
            "minute": await tracker._get_period_total(
                api_key_id,
                UsageMetric.REQUESTS,
                now - timedelta(minutes=1),
                now
            ),
            "hour": await tracker._get_period_total(
                api_key_id,
                UsageMetric.REQUESTS,
                now - timedelta(hours=1),
                now
            ),
            "day": await tracker._get_period_total(
                api_key_id,
                UsageMetric.REQUESTS,
                now - timedelta(days=1),
                now
            )
        },
        "sync_operations": {
            "day": await tracker._get_period_total(
                api_key_id,
                UsageMetric.SYNC_OPERATIONS,
                now - timedelta(days=1),
                now
            )
        },
        "data_fetched": {
            "day": await tracker._get_period_total(
                api_key_id,
                UsageMetric.DATA_FETCHED,
                now - timedelta(days=1),
                now
            )
        },
        "webhooks_sent": {
            "hour": await tracker._get_period_total(
                api_key_id,
                UsageMetric.WEBHOOKS_SENT,
                now - timedelta(hours=1),
                now
            )
        },
        "errors": {
            "day": await tracker._get_period_total(
                api_key_id,
                UsageMetric.ERRORS,
                now - timedelta(days=1),
                now
            )
        }
    }
    
    # Get limits
    limits = await tracker._get_rate_limits(api_key_id)
    
    return CurrentUsageResponse(
        **usage,
        limits=RateLimitsResponse(
            requests_per_minute=limits.requests_per_minute,
            requests_per_hour=limits.requests_per_hour,
            requests_per_day=limits.requests_per_day,
            sync_operations_per_day=limits.sync_operations_per_day,
            data_fetch_mb_per_day=limits.data_fetch_mb_per_day,
            webhooks_per_hour=limits.webhooks_per_hour
        )
    )


@router.put("/limits", response_model=RateLimitsResponse)
async def update_rate_limits(
    api_key_id: str,
    limits: RateLimitsResponse,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update rate limits for an API key.
    
    Requires API key admin permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "admin")
    
    # Verify API key ownership
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this API key"
        )
    
    # Update rate limits in metadata
    if not api_key.key_metadata:
        api_key.key_metadata = {}
    
    api_key.key_metadata["rate_limits"] = limits.dict()
    await db.commit()
    
    # Clear cache
    tracker = get_usage_tracker()
    limits_key = f"limits:{api_key_id}"
    await tracker.redis.delete(limits_key)
    
    logger.info(
        f"Updated rate limits for API key {api_key_id}",
        extra={"user_id": current_user.id, "limits": limits.dict()}
    )
    
    return limits


@router.post("/reset")
async def reset_usage(
    api_key_id: str,
    metric: Optional[UsageMetric] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset usage counters for an API key.
    
    Requires API key admin permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "admin")
    
    # Verify API key ownership
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this API key"
        )
    
    # Reset usage
    tracker = get_usage_tracker()
    await tracker.reset_usage(api_key_id, metric)
    
    logger.info(
        f"Reset usage counters for API key {api_key_id}",
        extra={"user_id": current_user.id, "metric": metric}
    )
    
    return {"success": True, "message": "Usage counters reset successfully"}