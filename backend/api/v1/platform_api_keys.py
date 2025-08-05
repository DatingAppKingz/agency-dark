"""
API key management endpoints.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field, validator
import re

from core.database import get_db
from core.auth import get_current_user
from core.security.api_keys.key_manager import api_key_manager
from core.security.api_keys.auth_middleware import (
    get_current_api_key, 
    require_api_key_scope,
    get_api_key_user
)
from models.platform_api_key import PlatformAPIKey, PlatformAPIKeyScope
from models.user import User, UserRole
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models

class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: List[str] = Field(..., min_items=1)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    allowed_ips: Optional[List[str]] = None
    allowed_origins: Optional[List[str]] = None
    allowed_user_agents: Optional[List[str]] = None
    rate_limits: Optional[Dict[str, int]] = None
    allowed_models: Optional[List[str]] = None
    allowed_conversations: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('scopes')
    def validate_scopes(cls, v):
        """Validate that all scopes are valid."""
        valid_scopes = [s.value for s in PlatformAPIKeyScope]
        invalid = [s for s in v if s not in valid_scopes]
        if invalid:
            raise ValueError(f"Invalid scopes: {', '.join(invalid)}")
        return v
    
    @validator('allowed_ips')
    def validate_ips(cls, v):
        """Basic IP validation."""
        if not v:
            return v
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$')
        for ip in v:
            if not ip_pattern.match(ip):
                raise ValueError(f"Invalid IP format: {ip}")
        return v


class APIKeyResponse(BaseModel):
    """API key response model."""
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    error_count: int
    created_at: datetime
    rate_limits: Dict[str, int]
    allowed_ips: Optional[List[str]]
    allowed_origins: Optional[List[str]]
    allowed_models: Optional[List[str]]
    metadata: Dict[str, Any]
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(APIKeyResponse):
    """Response when creating a new API key."""
    api_key: str  # Only returned on creation


class APIKeyRotateRequest(BaseModel):
    """Request to rotate an API key."""
    grace_period_hours: int = Field(24, ge=0, le=168)  # Max 1 week


class APIKeyRevokeRequest(BaseModel):
    """Request to revoke an API key."""
    reason: str = Field(..., min_length=1, max_length=500)


class APIKeyUsageStats(BaseModel):
    """API key usage statistics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    requests_by_endpoint: Dict[str, int]
    requests_by_status: Dict[str, int]
    monthly_usage: Dict[str, int]
    daily_usage_last_7_days: Dict[str, int]


# Endpoints

@router.post("/", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new API key.
    
    Permissions:
    - Super Admin: Can create any key with any scopes
    - Agency Owner/Admin: Can create agency-scoped keys
    - Model: Can create limited read-only keys
    - Others: Cannot create keys
    """
    try:
        # Create the API key
        api_key, plain_text_key = await api_key_manager.create_api_key(
            db=db,
            user=current_user,
            name=request.name,
            scopes=request.scopes,
            description=request.description,
            expires_in_days=request.expires_in_days,
            allowed_ips=request.allowed_ips,
            allowed_origins=request.allowed_origins,
            rate_limits=request.rate_limits,
            metadata=request.metadata or {}
        )
        
        # Prepare response
        response = APIKeyCreateResponse(
            id=str(api_key.id),
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            scopes=api_key.scopes,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            usage_count=api_key.usage_count,
            error_count=api_key.error_count,
            created_at=api_key.created_at,
            rate_limits={
                "per_minute": api_key.rate_limit_per_minute,
                "per_hour": api_key.rate_limit_per_hour,
                "per_day": api_key.rate_limit_per_day
            },
            allowed_ips=api_key.allowed_ips,
            allowed_origins=api_key.allowed_origins,
            allowed_models=api_key.allowed_models,
            metadata=api_key.metadata,
            api_key=plain_text_key  # Only included in creation response
        )
        
        logger.info(f"Created API key '{api_key.name}' for user {current_user.email}")
        
        return response
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[APIKeyResponse])
async def list_api_keys(
    include_revoked: bool = Query(False, description="Include revoked keys"),
    agency_id: Optional[str] = Query(None, description="Filter by agency (super admin only)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List API keys accessible to the current user.
    
    Permissions:
    - Super Admin: Can see all keys, optionally filtered by agency
    - Agency Owner/Admin: Can see all agency keys
    - Others: Can see only their own keys
    """
    keys = await api_key_manager.list_api_keys(
        db=db,
        user=current_user,
        include_revoked=include_revoked,
        agency_id=agency_id
    )
    
    return [
        APIKeyResponse(
            id=str(key.id),
            name=key.name,
            description=key.description,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            is_active=key.is_active,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            usage_count=key.usage_count,
            error_count=key.error_count,
            created_at=key.created_at,
            rate_limits={
                "per_minute": key.rate_limit_per_minute,
                "per_hour": key.rate_limit_per_hour,
                "per_day": key.rate_limit_per_day
            },
            allowed_ips=key.allowed_ips,
            allowed_origins=key.allowed_origins,
            allowed_models=key.allowed_models,
            metadata=key.metadata
        )
        for key in keys
    ]


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific API key."""
    # Get the key
    result = await db.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    can_view = (
        current_user.role == UserRole.SUPER_ADMIN or
        api_key.user_id == current_user.id or
        (current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN] and 
         api_key.agency_id == current_user.agency_id)
    )
    
    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this API key"
        )
    
    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count,
        error_count=api_key.error_count,
        created_at=api_key.created_at,
        rate_limits={
            "per_minute": api_key.rate_limit_per_minute,
            "per_hour": api_key.rate_limit_per_hour,
            "per_day": api_key.rate_limit_per_day
        },
        allowed_ips=api_key.allowed_ips,
        allowed_origins=api_key.allowed_origins,
        allowed_models=api_key.allowed_models,
        metadata=api_key.metadata
    )


@router.post("/{api_key_id}/rotate", response_model=APIKeyCreateResponse)
async def rotate_api_key(
    api_key_id: str,
    request: APIKeyRotateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rotate an API key with optional grace period.
    
    This creates a new key with the same settings and optionally
    keeps the old key active for a grace period.
    """
    try:
        new_key, plain_text_key = await api_key_manager.rotate_api_key(
            db=db,
            api_key_id=api_key_id,
            user=current_user,
            grace_period_hours=request.grace_period_hours
        )
        
        return APIKeyCreateResponse(
            id=str(new_key.id),
            name=new_key.name,
            description=new_key.description,
            key_prefix=new_key.key_prefix,
            scopes=new_key.scopes,
            is_active=new_key.is_active,
            expires_at=new_key.expires_at,
            last_used_at=new_key.last_used_at,
            usage_count=new_key.usage_count,
            error_count=new_key.error_count,
            created_at=new_key.created_at,
            rate_limits={
                "per_minute": new_key.rate_limit_per_minute,
                "per_hour": new_key.rate_limit_per_hour,
                "per_day": new_key.rate_limit_per_day
            },
            allowed_ips=new_key.allowed_ips,
            allowed_origins=new_key.allowed_origins,
            allowed_models=new_key.allowed_models,
            metadata=new_key.metadata,
            api_key=plain_text_key
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.post("/{api_key_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: str,
    request: APIKeyRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke an API key."""
    try:
        success = await api_key_manager.revoke_api_key(
            db=db,
            api_key_id=api_key_id,
            revoked_by=current_user,
            reason=request.reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
            
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{api_key_id}/usage", response_model=APIKeyUsageStats)
async def get_api_key_usage(
    api_key_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get usage statistics for an API key."""
    # Get the key
    result = await db.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    can_view = (
        current_user.role == UserRole.SUPER_ADMIN or
        api_key.user_id == current_user.id or
        (current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN] and 
         api_key.agency_id == current_user.agency_id)
    )
    
    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view usage for this API key"
        )
    
    # Get usage logs
    from sqlalchemy import func
    from models.platform_api_key import PlatformAPIKeyUsageLog
    
    # Calculate date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get aggregated stats
    stats_result = await db.execute(
        select(
            func.count(PlatformAPIKeyUsageLog.id).label('total'),
            func.count(PlatformAPIKeyUsageLog.id).filter(
                PlatformAPIKeyUsageLog.status_code < 400
            ).label('successful'),
            func.avg(PlatformAPIKeyUsageLog.response_time_ms).label('avg_response_time')
        ).where(
            and_(
                PlatformAPIKeyUsageLog.api_key_id == api_key_id,
                PlatformAPIKeyUsageLog.timestamp >= start_date
            )
        )
    )
    stats = stats_result.one()
    
    # Get requests by endpoint
    endpoint_result = await db.execute(
        select(
            PlatformAPIKeyUsageLog.endpoint,
            func.count(PlatformAPIKeyUsageLog.id)
        ).where(
            and_(
                PlatformAPIKeyUsageLog.api_key_id == api_key_id,
                PlatformAPIKeyUsageLog.timestamp >= start_date
            )
        ).group_by(PlatformAPIKeyUsageLog.endpoint)
    )
    requests_by_endpoint = dict(endpoint_result.all())
    
    # Get requests by status code
    status_result = await db.execute(
        select(
            PlatformAPIKeyUsageLog.status_code,
            func.count(PlatformAPIKeyUsageLog.id)
        ).where(
            and_(
                PlatformAPIKeyUsageLog.api_key_id == api_key_id,
                PlatformAPIKeyUsageLog.timestamp >= start_date
            )
        ).group_by(PlatformAPIKeyUsageLog.status_code)
    )
    requests_by_status = {
        str(status): count for status, count in status_result.all()
    }
    
    # Get daily usage for last 7 days
    daily_usage = {}
    for i in range(7):
        day = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        day_result = await db.execute(
            select(func.count(PlatformAPIKeyUsageLog.id)).where(
                and_(
                    PlatformAPIKeyUsageLog.api_key_id == api_key_id,
                    PlatformAPIKeyUsageLog.timestamp >= day_start,
                    PlatformAPIKeyUsageLog.timestamp < day_end
                )
            )
        )
        daily_usage[day.isoformat()] = day_result.scalar() or 0
    
    return APIKeyUsageStats(
        total_requests=stats.total or 0,
        successful_requests=stats.successful or 0,
        failed_requests=(stats.total or 0) - (stats.successful or 0),
        average_response_time_ms=float(stats.avg_response_time or 0),
        requests_by_endpoint=requests_by_endpoint,
        requests_by_status=requests_by_status,
        monthly_usage=api_key.monthly_usage or {},
        daily_usage_last_7_days=daily_usage
    )


# API key authenticated endpoints

@router.get("/test/auth", dependencies=[Depends(get_current_api_key)])
async def test_api_key_auth(
    api_key: PlatformAPIKey = Depends(get_current_api_key)
):
    """Test endpoint for API key authentication."""
    return {
        "message": "API key authentication successful",
        "key_name": api_key.name,
        "scopes": api_key.scopes
    }


@router.get("/test/scope", dependencies=[Depends(require_api_key_scope("read:users"))])
async def test_api_key_scope(
    api_key: PlatformAPIKey = Depends(get_current_api_key)
):
    """Test endpoint for API key scope validation."""
    return {
        "message": "API key has required scope",
        "key_name": api_key.name,
        "required_scope": "read:users"
    }