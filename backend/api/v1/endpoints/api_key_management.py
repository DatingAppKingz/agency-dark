"""
API Key Management Endpoints
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from core.database import get_db
from core.security_v2 import get_current_user
from core.domain.models import User, UserRole
from models.api_key import APIKey, APIKeyService
from core.pagination import PaginatedResponse, get_pagination_params, paginate

router = APIRouter(prefix="/api-keys", tags=["api-key-management"])


class APIKeyCreate(BaseModel):
    """API Key creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    allowed_ips: Optional[List[str]] = Field(default_factory=list)
    rate_limit: int = Field(1000, ge=1, le=10000)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API Key response"""
    id: UUID
    name: str
    key_prefix: str
    permissions: Dict[str, Any]
    allowed_ips: List[str]
    rate_limit: int
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyCreateResponse(APIKeyResponse):
    """API Key creation response with raw key"""
    key: str  # Only returned on creation


@router.post("/", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key"""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions to create API keys")
    
    service = APIKeyService(db)
    
    # Create API key
    api_key, raw_key = await service.create_api_key(
        agency_id=current_user.agency_id,
        user_id=current_user.id,
        name=request.name,
        permissions=request.permissions,
        allowed_ips=request.allowed_ips,
        rate_limit=request.rate_limit,
        expires_in_days=request.expires_in_days
    )
    
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,  # Raw key shown only once
        permissions=api_key.permissions,
        allowed_ips=api_key.allowed_ips,
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at
    )


@router.get("/", response_model=PaginatedResponse[APIKeyResponse])
async def list_api_keys(
    active_only: bool = Query(True),
    pagination = Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List API keys for the current user's agency with pagination"""
    # Build base query
    query = select(APIKey)
    
    # Apply filters based on role
    if current_user.role == UserRole.SUPER_ADMIN:
        # Super admin can see all keys
        pass
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        # Agency admins can see agency keys
        query = query.where(APIKey.agency_id == current_user.agency_id)
    else:
        # Regular users can only see their own keys
        query = query.where(APIKey.user_id == current_user.id)
    
    # Apply active filter
    if active_only:
        query = query.where(APIKey.is_active == True)
    
    # Order by creation date
    query = query.order_by(APIKey.created_at.desc())
    
    # Apply pagination
    return await paginate(db, query, pagination, APIKeyResponse)


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get API key details"""
    api_key = await db.get(APIKey, key_id)
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass  # Super admin can see any key
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if api_key.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if api_key.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions,
        allowed_ips=api_key.allowed_ips,
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at
    )


@router.put("/{key_id}")
async def update_api_key(
    key_id: UUID,
    name: Optional[str] = None,
    permissions: Optional[Dict[str, Any]] = None,
    allowed_ips: Optional[List[str]] = None,
    rate_limit: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update API key settings"""
    api_key = await db.get(APIKey, key_id)
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if api_key.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if api_key.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields
    if name is not None:
        api_key.name = name
    if permissions is not None:
        api_key.permissions = permissions
    if allowed_ips is not None:
        api_key.allowed_ips = allowed_ips
    if rate_limit is not None:
        api_key.rate_limit = rate_limit
    
    api_key.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(api_key)
    
    return {
        "message": "API key updated successfully",
        "key": APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            permissions=api_key.permissions,
            allowed_ips=api_key.allowed_ips,
            rate_limit=api_key.rate_limit,
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            usage_count=api_key.usage_count,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at
        )
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke (deactivate) an API key"""
    api_key = await db.get(APIKey, key_id)
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if api_key.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if api_key.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    service = APIKeyService(db)
    success = await service.revoke_api_key(key_id)
    
    if success:
        return {"message": "API key revoked successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: UUID,
    expires_in_days: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rotate an API key (revoke old, create new)"""
    # Get existing key
    old_key = await db.get(APIKey, key_id)
    
    if not old_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN:
        pass
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if old_key.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if old_key.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    service = APIKeyService(db)
    
    # Create new key with same settings
    new_key, raw_key = await service.create_api_key(
        agency_id=old_key.agency_id,
        user_id=old_key.user_id,
        name=f"{old_key.name} (rotated)",
        permissions=old_key.permissions,
        allowed_ips=old_key.allowed_ips,
        rate_limit=old_key.rate_limit,
        expires_in_days=expires_in_days
    )
    
    # Revoke old key
    await service.revoke_api_key(old_key.id)
    
    return APIKeyCreateResponse(
        id=new_key.id,
        name=new_key.name,
        key_prefix=new_key.key_prefix,
        key=raw_key,
        permissions=new_key.permissions,
        allowed_ips=new_key.allowed_ips,
        rate_limit=new_key.rate_limit,
        is_active=new_key.is_active,
        last_used_at=new_key.last_used_at,
        usage_count=new_key.usage_count,
        expires_at=new_key.expires_at,
        created_at=new_key.created_at
    )