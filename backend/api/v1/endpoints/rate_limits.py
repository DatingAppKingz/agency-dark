"""Rate limiting endpoints for API usage control."""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.rate_limit_service import RateLimitService
from core.exceptions import ValidationError, NotFoundError

router = APIRouter()


# Request/Response schemas
class CustomLimitRequest(BaseModel):
    """Request to set custom rate limit."""
    user_id: int
    endpoint: str
    max_requests: int = Field(..., ge=0)
    window_seconds: Optional[int] = Field(None, ge=1)
    expires_at: Optional[datetime] = None


class RateLimitStatusResponse(BaseModel):
    """Rate limit status response."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: str
    window_seconds: int
    retry_after: Optional[int] = None


class EndpointStatusResponse(BaseModel):
    """Endpoint rate limit status."""
    current: int
    limit: int
    remaining: int
    reset_at: str
    window_seconds: int


class UserRateLimitStatus(BaseModel):
    """User rate limit status response."""
    user_id: int
    endpoints: Dict[str, EndpointStatusResponse]
    timestamp: str


@router.get("/status", response_model=UserRateLimitStatus)
async def get_rate_limit_status(
    endpoints: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user)
) -> UserRateLimitStatus:
    """
    Get current rate limit status for the authenticated user.
    
    Returns usage counts and limits for specified endpoints.
    If no endpoints specified, returns status for all default endpoints.
    """
    status = await RateLimitService.get_rate_limit_status(
        user_id=current_user.id,
        endpoints=endpoints
    )
    
    return UserRateLimitStatus(**status)


@router.get("/check/{endpoint:path}", response_model=RateLimitStatusResponse)
async def check_endpoint_limit(
    endpoint: str,
    current_user: User = Depends(get_current_user)
) -> RateLimitStatusResponse:
    """
    Check rate limit for a specific endpoint without incrementing counter.
    
    Useful for pre-flight checks before making actual requests.
    """
    allowed, result = await RateLimitService.check_rate_limit(
        user_id=current_user.id,
        endpoint=endpoint,
        user_role=current_user.role,
        agency_id=current_user.agency_id
    )
    
    return RateLimitStatusResponse(**result)


@router.post("/custom", response_model=Dict[str, Any])
async def set_custom_limit(
    request: CustomLimitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Set custom rate limit for a specific user and endpoint.
    
    - Requires admin or owner role
    - Can set temporary limits with expiration
    - Overrides default limits for the user
    """
    # Check permissions
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If setting limit for another user, verify they're in same agency
    if request.user_id != current_user.id:
        target_user = await db.get(User, request.user_id)
        if not target_user or target_user.agency_id != current_user.agency_id:
            raise HTTPException(status_code=404, detail="User not found or not in your agency")
    
    try:
        result = await RateLimitService.set_custom_limit(
            db=db,
            user_id=request.user_id,
            endpoint=request.endpoint,
            max_requests=request.max_requests,
            window_seconds=request.window_seconds,
            expires_at=request.expires_at
        )
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset", response_model=Dict[str, Any])
async def reset_rate_limits(
    user_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reset rate limit counters.
    
    - Users can reset their own limits
    - Admins can reset any user's limits
    - Can reset specific endpoint or all endpoints
    """
    # Default to current user if not specified
    if user_id is None:
        user_id = current_user.id
    
    # Check permissions for resetting other users
    if user_id != current_user.id and current_user.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Cannot reset limits for other users")
    
    # Verify user exists and is in same agency
    if user_id != current_user.id:
        target_user = await db.get(User, user_id)
        if not target_user or target_user.agency_id != current_user.agency_id:
            raise HTTPException(status_code=404, detail="User not found or not in your agency")
    
    result = await RateLimitService.reset_rate_limit(
        user_id=user_id,
        endpoint=endpoint
    )
    
    return result


@router.get("/agency/{agency_id}", response_model=Dict[str, Any])
async def get_agency_limits(
    agency_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get rate limits for an agency based on their plan.
    
    - Shows limits for all endpoints
    - Includes plan multipliers
    - Requires admin access
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify agency access
    if agency_id != current_user.agency_id and current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Cannot view other agency limits")
    
    try:
        limits = await RateLimitService.get_agency_limits(
            db=db,
            agency_id=agency_id
        )
        return limits
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/violations")
async def get_rate_limit_violations(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get rate limit violations for monitoring.
    
    - Shows users who hit rate limits
    - Requires admin access
    - Useful for identifying abusive patterns
    """
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # This would typically query a violations log
    # For now, return placeholder
    return {
        "violations": [],
        "total": 0,
        "start_date": start_date,
        "end_date": end_date
    }


@router.post("/api-key/check")
async def check_api_key_limit(
    endpoint: str,
    api_key: str = Header(..., alias="X-API-Key")
) -> RateLimitStatusResponse:
    """
    Check rate limit for API key access.
    
    API keys have stricter limits than user tokens.
    """
    allowed, result = await RateLimitService.check_api_key_rate_limit(
        api_key=api_key,
        endpoint=endpoint
    )
    
    return RateLimitStatusResponse(**result)


# Utility endpoints

@router.get("/rules")
async def get_rate_limit_rules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get default rate limit rules for all endpoints."""
    rules = {}
    
    for name, rule in RateLimitService.DEFAULT_RULES.items():
        rules[name] = {
            "endpoint": rule.endpoint,
            "max_requests": rule.max_requests,
            "window_seconds": rule.window_seconds,
            "burst_size": rule.burst_size
        }
    
    # Add role multipliers
    role_multiplier = RateLimitService.ROLE_MULTIPLIERS.get(current_user.role, 1.0)
    
    return {
        "rules": rules,
        "user_role": current_user.role,
        "role_multiplier": role_multiplier,
        "effective_limits": {
            name: {
                "max_requests": int(rule["max_requests"] * role_multiplier),
                "window_seconds": rule["window_seconds"]
            }
            for name, rule in rules.items()
        }
    }