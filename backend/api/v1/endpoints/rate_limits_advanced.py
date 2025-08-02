"""
Rate limit management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.rate_limiting.rate_limiter import rate_limiter
from core.middleware.rate_limit import DynamicRateLimiter, rate_limit
from core.domain.schemas import BaseResponse

router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])


# Schemas
from pydantic import BaseModel, Field


class RateLimitConfigRequest(BaseModel):
    """Request to configure rate limits."""
    tier: str = Field(..., description="Rate limit tier")
    endpoint_pattern: str = Field(..., description="Endpoint pattern (supports wildcards)")
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    burst_size: int = Field(10, ge=0)


class UserRateLimitRequest(BaseModel):
    """Request to set user-specific rate limit."""
    user_id: UUID
    limit_multiplier: float = Field(1.0, gt=0, le=10)
    custom_limits: Optional[dict] = None
    valid_days: int = Field(30, ge=1, le=365)
    reason: str = Field(..., min_length=1)


class IPBlockRequest(BaseModel):
    """Request to block an IP address."""
    ip_address: str
    duration_hours: int = Field(24, ge=1, le=168)  # Max 1 week
    reason: str = Field(..., min_length=1)


class WhitelistRequest(BaseModel):
    """Request to whitelist a user."""
    user_id: UUID
    endpoint_pattern: str = Field("*", description="Endpoint pattern or * for all")
    valid_days: int = Field(30, ge=1, le=365)
    reason: str = Field(..., min_length=1)


class UsageStatsResponse(BaseModel):
    """Response with usage statistics."""
    identifier: str
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    tier: str
    limits: dict


class ViolationResponse(BaseModel):
    """Rate limit violation details."""
    id: UUID
    user_id: Optional[UUID]
    ip_address: str
    endpoint: str
    method: str
    limit_type: str
    limit_value: int
    actual_value: int
    violated_at: datetime


# Endpoints

@router.get("/usage/me", response_model=UsageStatsResponse)
async def get_my_usage(
    current_user: User = Depends(get_current_user)
) -> UsageStatsResponse:
    """Get current user's rate limit usage statistics."""
    identifier = f"user:{current_user.id}"
    stats = await rate_limiter.get_usage_stats(identifier)
    
    # Determine tier
    if current_user.role == UserRole.SUPER_ADMIN:
        tier = "enterprise"
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        tier = "professional"
    elif current_user.role in [UserRole.MEMBER, UserRole.MODEL]:
        tier = "basic"
    else:
        tier = "free"
    
    # Get limits for tier
    from core.rate_limiting.models import RateLimitTier
    tier_enum = RateLimitTier(tier)
    limits = rate_limiter._get_default_config(tier_enum)
    
    return UsageStatsResponse(
        identifier=identifier,
        tier=tier,
        limits=limits,
        **stats
    )


@router.get("/usage/{user_id}", response_model=UsageStatsResponse)
async def get_user_usage(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UsageStatsResponse:
    """
    Get rate limit usage for a specific user.
    
    Requires admin permissions.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify user exists and belongs to same agency
    if current_user.role != UserRole.SUPER_ADMIN:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.agency_id == current_user.agency_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="User not found")
    
    identifier = f"user:{user_id}"
    stats = await rate_limiter.get_usage_stats(identifier)
    
    return UsageStatsResponse(
        identifier=identifier,
        tier="unknown",  # Would need to look up user to determine
        limits={},
        **stats
    )


@router.post("/user-limits")
async def set_user_rate_limit(
    request: UserRateLimitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """
    Set custom rate limit for a user.
    
    Requires admin permissions.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    await DynamicRateLimiter.set_user_limit(
        user_id=str(request.user_id),
        limit_multiplier=request.limit_multiplier,
        custom_limits=request.custom_limits,
        valid_days=request.valid_days,
        reason=request.reason
    )
    
    return BaseResponse(
        success=True,
        message="User rate limit updated successfully"
    )


@router.post("/block-ip")
async def block_ip_address(
    request: IPBlockRequest,
    current_user: User = Depends(get_current_user)
) -> BaseResponse:
    """
    Block an IP address.
    
    Requires admin permissions.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    await DynamicRateLimiter.block_ip(
        ip_address=request.ip_address,
        duration_hours=request.duration_hours,
        reason=request.reason
    )
    
    return BaseResponse(
        success=True,
        message=f"IP {request.ip_address} blocked for {request.duration_hours} hours"
    )


@router.post("/whitelist")
async def whitelist_user(
    request: WhitelistRequest,
    current_user: User = Depends(get_current_user)
) -> BaseResponse:
    """
    Add user to rate limit whitelist.
    
    Requires super admin permissions.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    await DynamicRateLimiter.whitelist_user(
        user_id=str(request.user_id),
        endpoint_pattern=request.endpoint_pattern,
        valid_days=request.valid_days,
        reason=request.reason,
        approved_by_id=str(current_user.id)
    )
    
    return BaseResponse(
        success=True,
        message="User added to whitelist"
    )


@router.get("/violations", response_model=List[ViolationResponse])
async def get_violations(
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
) -> List[ViolationResponse]:
    """
    Get recent rate limit violations.
    
    Requires admin permissions.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    violations = await DynamicRateLimiter.get_violations(
        user_id=str(user_id) if user_id else None,
        ip_address=ip_address,
        hours=hours
    )
    
    return [
        ViolationResponse(
            id=v.id,
            user_id=v.user_id,
            ip_address=v.ip_address,
            endpoint=v.endpoint,
            method=v.method,
            limit_type=v.limit_type,
            limit_value=v.limit_value,
            actual_value=v.actual_value,
            violated_at=v.violated_at
        )
        for v in violations
    ]


# Example endpoint with custom rate limit
@router.get("/expensive-operation")
@rate_limit(requests_per_minute=5, burst_size=2)
async def expensive_operation(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Example endpoint with strict rate limiting.
    
    Limited to 5 requests per minute with burst of 2.
    """
    # Simulate expensive operation
    import asyncio
    await asyncio.sleep(1)
    
    return {
        "message": "Expensive operation completed",
        "user_id": str(current_user.id)
    }


@router.get("/config")
async def get_rate_limit_config(
    tier: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get rate limit configuration.
    
    Requires admin permissions.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from sqlalchemy import select
    from core.rate_limiting.models import RateLimitConfig, RateLimitTier
    
    query = select(RateLimitConfig).where(RateLimitConfig.is_active == True)
    
    if tier:
        try:
            tier_enum = RateLimitTier(tier)
            query = query.where(RateLimitConfig.tier == tier_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tier")
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    return {
        "configs": [
            {
                "id": str(config.id),
                "tier": config.tier.value,
                "endpoint_pattern": config.endpoint_pattern,
                "requests_per_minute": config.requests_per_minute,
                "requests_per_hour": config.requests_per_hour,
                "requests_per_day": config.requests_per_day,
                "burst_size": config.burst_size
            }
            for config in configs
        ]
    }