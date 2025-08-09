"""
Rate Limit Management API endpoints
"""
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.database import get_db
from core.security_v2 import get_current_user
from core.domain.models import User, UserRole
from core.rate_limiting import (
    RateLimiter, 
    RateLimitTier, 
    RATE_LIMIT_CONFIGS,
    check_rate_limit
)
from core.redis import redis_manager

router = APIRouter(prefix="/rate-limits", tags=["rate-limit-management"])


class RateLimitStatus(BaseModel):
    """Rate limit status response"""
    identifier: str
    tier: RateLimitTier
    minute: Dict[str, int]
    hour: Dict[str, int]
    day: Dict[str, int]


class RateLimitUpdate(BaseModel):
    """Rate limit update request"""
    tier: RateLimitTier = Field(..., description="New rate limit tier")


class RateLimitConfigResponse(BaseModel):
    """Rate limit configuration response"""
    tier: RateLimitTier
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int
    api_limits: Dict[str, int]


@router.get("/configs", response_model=Dict[str, RateLimitConfigResponse])
async def get_rate_limit_configs(
    current_user: User = Depends(get_current_user)
):
    """Get all rate limit configurations"""
    # Only admins can view configurations
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    configs = {}
    for tier, config in RATE_LIMIT_CONFIGS.items():
        configs[tier] = RateLimitConfigResponse(
            tier=tier,
            requests_per_minute=config.requests_per_minute,
            requests_per_hour=config.requests_per_hour,
            requests_per_day=config.requests_per_day,
            burst_size=config.burst_size,
            api_limits=config.api_limits
        )
    
    return configs


@router.get("/status/user/{user_id}", response_model=RateLimitStatus)
async def get_user_rate_limit_status(
    user_id: UUID,
    path: str = Query("/", description="API path to check"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get rate limit status for a specific user"""
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass  # Can view any user
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        # Can only view users in their agency
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        target_user = result.scalar_one_or_none()
        
        if not target_user or target_user.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Can only view users in your agency")
    else:
        # Can only view own status
        if str(user_id) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Can only view your own rate limit status")
    
    # Get rate limiter
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    # Get user's tier
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get tier from role mapping
    from core.rate_limiting import ROLE_TIER_MAPPING
    tier = ROLE_TIER_MAPPING.get(user.role, RateLimitTier.FREE)
    
    # Get status
    identifier = f"user:{user_id}"
    status = await rate_limiter.get_rate_limit_status(identifier, tier, path)
    
    return RateLimitStatus(
        identifier=identifier,
        tier=tier,
        **status
    )


@router.get("/status/agency/{agency_id}", response_model=RateLimitStatus)
async def get_agency_rate_limit_status(
    agency_id: UUID,
    path: str = Query("/", description="API path to check"),
    tier: RateLimitTier = Query(RateLimitTier.PREMIUM, description="Agency tier"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get rate limit status for an agency"""
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass  # Can view any agency
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        # Can only view own agency
        if str(agency_id) != str(current_user.agency_id):
            raise HTTPException(status_code=403, detail="Can only view your own agency")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get rate limiter
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    # Get status
    identifier = f"agency:{agency_id}"
    status = await rate_limiter.get_rate_limit_status(identifier, tier, path)
    
    return RateLimitStatus(
        identifier=identifier,
        tier=tier,
        **status
    )


@router.post("/reset/user/{user_id}")
async def reset_user_rate_limit(
    user_id: UUID,
    path: Optional[str] = Query(None, description="Specific path to reset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset rate limits for a user"""
    # Only admins can reset rate limits
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if user exists and permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        target_user = result.scalar_one_or_none()
        
        if not target_user or target_user.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Can only reset users in your agency")
    
    # Reset rate limits
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    identifier = f"user:{user_id}"
    await rate_limiter.reset_rate_limit(identifier, path)
    
    return {"message": "Rate limits reset successfully"}


@router.post("/reset/agency/{agency_id}")
async def reset_agency_rate_limit(
    agency_id: UUID,
    path: Optional[str] = Query(None, description="Specific path to reset"),
    current_user: User = Depends(get_current_user)
):
    """Reset rate limits for an agency"""
    # Only super admin or agency owner can reset agency limits
    if current_user.role == UserRole.SUPER_ADMIN:
        pass
    elif current_user.role == UserRole.AGENCY_OWNER:
        if str(agency_id) != str(current_user.agency_id):
            raise HTTPException(status_code=403, detail="Can only reset your own agency")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Reset rate limits
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    identifier = f"agency:{agency_id}"
    await rate_limiter.reset_rate_limit(identifier, path)
    
    return {"message": "Agency rate limits reset successfully"}


@router.get("/stats")
async def get_rate_limit_stats(
    current_user: User = Depends(get_current_user)
):
    """Get rate limiter statistics"""
    # Only admins can view statistics
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    return await rate_limiter.get_stats()


@router.get("/my-status", response_model=RateLimitStatus)
async def get_my_rate_limit_status(
    path: str = Query("/", description="API path to check"),
    current_user: User = Depends(get_current_user)
):
    """Get your own rate limit status"""
    redis = await get_redis()
    rate_limiter = RateLimiter(redis)
    
    # Get user's tier
    from core.rate_limiting import ROLE_TIER_MAPPING
    tier = ROLE_TIER_MAPPING.get(current_user.role, RateLimitTier.FREE)
    
    # Get status
    identifier = f"user:{current_user.id}"
    status = await rate_limiter.get_rate_limit_status(identifier, tier, path)
    
    return RateLimitStatus(
        identifier=identifier,
        tier=tier,
        **status
    )


# Example of using rate limit dependency in an endpoint
@router.post("/test-rate-limit")
async def test_rate_limit(
    _: None = Depends(check_rate_limit),
    current_user: User = Depends(get_current_user)
):
    """Test endpoint to demonstrate rate limiting"""
    return {
        "message": "Request successful",
        "user_id": str(current_user.id),
        "tier": ROLE_TIER_MAPPING.get(current_user.role, RateLimitTier.FREE)
    }