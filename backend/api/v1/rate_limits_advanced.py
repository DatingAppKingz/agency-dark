"""
Rate limit management endpoints.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from core.database import get_db
from core.security_v2 import get_current_user
from core.rate_limit.service import rate_limit_service
from models.rate_limit import (
    RateLimitConfig, RateLimitType, RateLimitTier, RateLimitAlgorithm,
    RateLimitViolation, EndpointCost, RateLimitOverride
)
from models.user import User, UserRole
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])


# Pydantic models

class RateLimitConfigRequest(BaseModel):
    """Request to create/update rate limit configuration."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    limit_type: str = Field(..., description="Type of rate limit")
    identifier: Optional[str] = Field(None, description="Specific identifier (user_id, api_key_id, etc.)")
    
    # Request-based limits
    requests_per_minute: Optional[int] = Field(None, ge=1)
    requests_per_hour: Optional[int] = Field(None, ge=1)
    requests_per_day: Optional[int] = Field(None, ge=1)
    
    # Cost-based limits
    cost_per_minute: Optional[float] = Field(None, ge=0.1)
    cost_per_hour: Optional[float] = Field(None, ge=0.1)
    cost_per_day: Optional[float] = Field(None, ge=0.1)
    
    # Algorithm settings
    algorithm: str = Field("token_bucket", description="Rate limiting algorithm")
    burst_size: Optional[int] = Field(None, ge=1)
    refill_rate: Optional[float] = Field(None, ge=0.1)
    
    # Advanced settings
    tier: Optional[str] = None
    priority: int = Field(0, ge=0, le=100)
    expires_in_days: Optional[int] = Field(None, ge=1)
    
    # Geographic settings
    allowed_countries: Optional[List[str]] = None
    blocked_countries: Optional[List[str]] = None
    geographic_multiplier: Optional[Dict[str, float]] = None


class RateLimitConfigResponse(BaseModel):
    """Rate limit configuration response."""
    id: str
    name: str
    description: Optional[str]
    limit_type: str
    identifier: Optional[str]
    requests_per_minute: Optional[int]
    requests_per_hour: Optional[int]
    requests_per_day: Optional[int]
    cost_per_minute: Optional[float]
    cost_per_hour: Optional[float]
    cost_per_day: Optional[float]
    algorithm: str
    is_active: bool
    priority: int
    created_at: datetime
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class EndpointCostRequest(BaseModel):
    """Request to set endpoint cost."""
    endpoint_pattern: str = Field(..., description="Endpoint pattern (supports wildcards)")
    method: Optional[str] = Field(None, description="HTTP method")
    base_cost: float = Field(1.0, ge=0.1, description="Base cost per request")
    request_size_factor: float = Field(0.0, ge=0, description="Cost per KB of request")
    response_size_factor: float = Field(0.0, ge=0, description="Cost per KB of response")
    compute_time_factor: float = Field(0.0, ge=0, description="Cost per ms of compute")
    description: Optional[str] = None
    priority: int = Field(0, ge=0)


class EndpointCostResponse(BaseModel):
    """Endpoint cost response."""
    id: str
    endpoint_pattern: str
    method: Optional[str]
    base_cost: float
    request_size_factor: float
    response_size_factor: float
    compute_time_factor: float
    is_active: bool
    priority: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class RateLimitOverrideRequest(BaseModel):
    """Request to create rate limit override."""
    target_type: str = Field(..., description="Type of target (user, api_key, ip)")
    target_identifier: str = Field(..., description="Target identifier")
    reason: str = Field(..., min_length=10, max_length=500)
    expires_in_hours: int = Field(..., ge=1, le=720)  # Max 30 days
    
    # Override values (null = no override)
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    cost_per_minute: Optional[float] = None
    cost_per_hour: Optional[float] = None
    cost_per_day: Optional[float] = None


class RateLimitOverrideResponse(BaseModel):
    """Rate limit override response."""
    id: str
    target_type: str
    target_identifier: str
    reason: str
    requests_per_minute: Optional[int]
    requests_per_hour: Optional[int]
    requests_per_day: Optional[int]
    starts_at: datetime
    expires_at: datetime
    is_active: bool
    approved_by: Optional[str]
    
    class Config:
        from_attributes = True


class CurrentUsageResponse(BaseModel):
    """Current rate limit usage response."""
    identifier: str
    type: str
    configs: List[Dict[str, Any]]


class ViolationResponse(BaseModel):
    """Rate limit violation response."""
    id: str
    timestamp: datetime
    identifier: str
    identifier_type: str
    endpoint: str
    method: str
    limit_type: str
    limit_value: float
    actual_value: float
    severity_score: int
    is_repeated: bool
    retry_after_seconds: Optional[int]
    
    class Config:
        from_attributes = True


class ViolationAnalysisResponse(BaseModel):
    """Violation analysis response."""
    period_days: int
    total_violations: int
    unique_violators: int
    top_violators: List[Dict[str, Any]]
    endpoint_violations: List[Dict[str, Any]]
    hourly_pattern: List[Dict[str, Any]]


# Endpoints

@router.get("/configs", response_model=List[RateLimitConfigResponse])
async def list_rate_limit_configs(
    limit_type: Optional[str] = Query(None, description="Filter by limit type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List rate limit configurations."""
    # Only admins can view configs
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view rate limit configurations"
        )
    
    query = select(RateLimitConfig)
    
    if limit_type:
        try:
            limit_type_enum = RateLimitType(limit_type)
            query = query.where(RateLimitConfig.limit_type == limit_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid limit type: {limit_type}"
            )
    
    if is_active is not None:
        query = query.where(RateLimitConfig.is_active == is_active)
    
    # Non-super admins can only see their agency's configs
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(
            or_(
                RateLimitConfig.agency_id == current_user.agency_id,
                RateLimitConfig.limit_type == RateLimitType.GLOBAL
            )
        )
    
    query = query.order_by(RateLimitConfig.priority.desc())
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    return [
        RateLimitConfigResponse(
            id=str(config.id),
            name=config.name,
            description=config.description,
            limit_type=config.limit_type.value,
            identifier=config.identifier,
            requests_per_minute=config.requests_per_minute,
            requests_per_hour=config.requests_per_hour,
            requests_per_day=config.requests_per_day,
            cost_per_minute=config.cost_per_minute,
            cost_per_hour=config.cost_per_hour,
            cost_per_day=config.cost_per_day,
            algorithm=config.algorithm.value,
            is_active=config.is_active,
            priority=config.priority,
            created_at=config.created_at,
            expires_at=config.expires_at
        )
        for config in configs
    ]


@router.post("/configs", response_model=RateLimitConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_rate_limit_config(
    request: RateLimitConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new rate limit configuration."""
    # Validate enums
    try:
        limit_type = RateLimitType(request.limit_type)
        algorithm = RateLimitAlgorithm(request.algorithm)
        tier = RateLimitTier(request.tier) if request.tier else None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create config
    config = await rate_limit_service.create_rate_limit_config(
        db=db,
        name=request.name,
        limit_type=limit_type,
        user=current_user,
        description=request.description,
        identifier=request.identifier,
        requests_per_minute=request.requests_per_minute,
        requests_per_hour=request.requests_per_hour,
        requests_per_day=request.requests_per_day,
        cost_per_minute=request.cost_per_minute,
        cost_per_hour=request.cost_per_hour,
        cost_per_day=request.cost_per_day,
        algorithm=algorithm,
        burst_size=request.burst_size,
        refill_rate=request.refill_rate,
        tier=tier,
        priority=request.priority,
        expires_at=expires_at,
        allowed_countries=request.allowed_countries,
        blocked_countries=request.blocked_countries,
        geographic_multiplier=request.geographic_multiplier
    )
    
    return RateLimitConfigResponse(
        id=str(config.id),
        name=config.name,
        description=config.description,
        limit_type=config.limit_type.value,
        identifier=config.identifier,
        requests_per_minute=config.requests_per_minute,
        requests_per_hour=config.requests_per_hour,
        requests_per_day=config.requests_per_day,
        cost_per_minute=config.cost_per_minute,
        cost_per_hour=config.cost_per_hour,
        cost_per_day=config.cost_per_day,
        algorithm=config.algorithm.value,
        is_active=config.is_active,
        priority=config.priority,
        created_at=config.created_at,
        expires_at=config.expires_at
    )


@router.get("/usage/current", response_model=CurrentUsageResponse)
async def get_current_usage(
    identifier: Optional[str] = Query(None, description="Specific identifier to check"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current rate limit usage for the authenticated user or specified identifier."""
    # Determine what to check
    if identifier and current_user.role == UserRole.SUPER_ADMIN:
        # Super admin can check any identifier
        check_identifier = identifier
        check_type = RateLimitType.USER  # Assume user, could be enhanced
    else:
        # Regular users can only check their own usage
        check_identifier = str(current_user.id)
        check_type = RateLimitType.USER
    
    usage = await rate_limit_service.get_current_usage(
        db=db,
        identifier=check_identifier,
        identifier_type=check_type,
        user=current_user
    )
    
    return CurrentUsageResponse(**usage)


@router.get("/endpoint-costs", response_model=List[EndpointCostResponse])
async def list_endpoint_costs(
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List endpoint cost configurations."""
    # Only admins can view endpoint costs
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view endpoint costs"
        )
    
    query = select(EndpointCost)
    
    if is_active is not None:
        query = query.where(EndpointCost.is_active == is_active)
    
    query = query.order_by(EndpointCost.priority.desc())
    
    result = await db.execute(query)
    costs = result.scalars().all()
    
    return [
        EndpointCostResponse(
            id=str(cost.id),
            endpoint_pattern=cost.endpoint_pattern,
            method=cost.method,
            base_cost=cost.base_cost,
            request_size_factor=cost.request_size_factor,
            response_size_factor=cost.response_size_factor,
            compute_time_factor=cost.compute_time_factor,
            is_active=cost.is_active,
            priority=cost.priority,
            created_at=cost.created_at
        )
        for cost in costs
    ]


@router.post("/endpoint-costs", response_model=EndpointCostResponse, status_code=status.HTTP_201_CREATED)
async def set_endpoint_cost(
    request: EndpointCostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Set or update endpoint cost configuration."""
    # Only super admins can set endpoint costs
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can set endpoint costs"
        )
    
    cost = await rate_limit_service.update_endpoint_cost(
        db=db,
        endpoint_pattern=request.endpoint_pattern,
        base_cost=request.base_cost,
        user=current_user,
        method=request.method,
        request_size_factor=request.request_size_factor,
        response_size_factor=request.response_size_factor,
        compute_time_factor=request.compute_time_factor,
        description=request.description,
        priority=request.priority
    )
    
    return EndpointCostResponse(
        id=str(cost.id),
        endpoint_pattern=cost.endpoint_pattern,
        method=cost.method,
        base_cost=cost.base_cost,
        request_size_factor=cost.request_size_factor,
        response_size_factor=cost.response_size_factor,
        compute_time_factor=cost.compute_time_factor,
        is_active=cost.is_active,
        priority=cost.priority,
        created_at=cost.created_at
    )


@router.post("/overrides", response_model=RateLimitOverrideResponse, status_code=status.HTTP_201_CREATED)
async def create_rate_limit_override(
    request: RateLimitOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a temporary rate limit override."""
    # Only admins can create overrides
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create rate limit overrides"
        )
    
    # Validate target type
    try:
        target_type = RateLimitType(request.target_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target type: {request.target_type}"
        )
    
    # Create override
    override = await rate_limit_service.create_override(
        db=db,
        target_type=target_type,
        target_identifier=request.target_identifier,
        reason=request.reason,
        expires_in_hours=request.expires_in_hours,
        created_by=current_user,
        requests_per_minute=request.requests_per_minute,
        requests_per_hour=request.requests_per_hour,
        requests_per_day=request.requests_per_day,
        cost_per_minute=request.cost_per_minute,
        cost_per_hour=request.cost_per_hour,
        cost_per_day=request.cost_per_day
    )
    
    return RateLimitOverrideResponse(
        id=str(override.id),
        target_type=override.target_type.value,
        target_identifier=override.target_identifier,
        reason=override.reason,
        requests_per_minute=override.requests_per_minute,
        requests_per_hour=override.requests_per_hour,
        requests_per_day=override.requests_per_day,
        starts_at=override.starts_at,
        expires_at=override.expires_at,
        is_active=override.is_active,
        approved_by=override.approved_by
    )


@router.get("/violations", response_model=List[ViolationResponse])
async def get_rate_limit_violations(
    identifier: Optional[str] = Query(None, description="Filter by identifier"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get rate limit violations."""
    # Regular users can only see their own violations
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        identifier = str(current_user.id)
    
    violations = await rate_limit_service.get_violations(
        db=db,
        identifier=identifier,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return [
        ViolationResponse(
            id=str(v.id),
            timestamp=v.timestamp,
            identifier=v.identifier,
            identifier_type=v.identifier_type.value,
            endpoint=v.endpoint,
            method=v.method,
            limit_type=v.limit_type,
            limit_value=v.limit_value,
            actual_value=v.actual_value,
            severity_score=v.severity_score,
            is_repeated=v.is_repeated,
            retry_after_seconds=v.retry_after_seconds
        )
        for v in violations
    ]


@router.get("/violations/analysis", response_model=ViolationAnalysisResponse)
async def analyze_violations(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze rate limit violations for patterns."""
    # Only admins can analyze violations
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can analyze violations"
        )
    
    analysis = await rate_limit_service.analyze_violations(db=db, days=days)
    
    return ViolationAnalysisResponse(**analysis)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rate_limit_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a rate limit configuration."""
    # Only super admins can delete configs
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete rate limit configurations"
        )
    
    # Get config
    result = await db.execute(
        select(RateLimitConfig).where(RateLimitConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rate limit configuration not found"
        )
    
    # Soft delete
    config.is_active = False
    await db.commit()


@router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_override(
    override_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a rate limit override."""
    # Only admins can cancel overrides
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can cancel overrides"
        )
    
    # Get override
    result = await db.execute(
        select(RateLimitOverride).where(RateLimitOverride.id == override_id)
    )
    override = result.scalar_one_or_none()
    
    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Override not found"
        )
    
    # Deactivate
    override.is_active = False
    await db.commit()