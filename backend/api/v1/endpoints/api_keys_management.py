"""API Key management endpoints with encryption."""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from core.database import get_db
from core.dependencies import CurrentUser, get_current_active_user
from core.errors import NotFoundError, AuthorizationError
from models.api_key import APIKeyProvider, APIKeyStatus
from services.api_key_service import APIKeyService
from models.user import UserRole

router = APIRouter()


# Request/Response Models
class APIKeyCreate(BaseModel):
    provider: APIKeyProvider
    name: str = Field(..., min_length=1, max_length=255)
    key_value: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class APIKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    key_value: Optional[str] = Field(None, min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class APIKeyResponse(BaseModel):
    id: int
    provider: APIKeyProvider
    name: str
    key_prefix: str
    status: APIKeyStatus
    last_validated_at: Optional[datetime]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    last_rotated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyDetailResponse(APIKeyResponse):
    decrypted_value: Optional[str] = None
    allowed_ips: Optional[List[str]]
    permissions: Dict[str, Any]
    key_metadata: Dict[str, Any]


class APIKeyValidationResponse(BaseModel):
    valid: bool
    message: str
    provider: str
    validated_at: datetime
    details: Optional[Dict[str, Any]] = None


# Endpoints
@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: CurrentUser,
    provider: Optional[APIKeyProvider] = None,
    status: Optional[APIKeyStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """List API keys for the agency."""
    service = APIKeyService(db)
    keys = await service.list_api_keys(current_user, provider, status)
    return keys


@router.get("/api-keys/{key_id}", response_model=APIKeyDetailResponse)
async def get_api_key(
    key_id: int,
    current_user: CurrentUser,
    decrypt: bool = Query(False, description="Decrypt the key value (requires admin permissions)"),
    db: AsyncSession = Depends(get_db)
):
    """Get API key details."""
    service = APIKeyService(db)
    key = await service.get_api_key(key_id, current_user, decrypt)
    return key


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    data: APIKeyCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Create a new encrypted API key."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise AuthorizationError("Insufficient permissions to create API keys")
    
    service = APIKeyService(db)
    key = await service.create_api_key(
        user=current_user,
        provider=data.provider,
        name=data.name,
        key_value=data.key_value,
        metadata=data.metadata
    )
    return key


@router.put("/api-keys/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    data: APIKeyUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update an API key."""
    service = APIKeyService(db)
    key = await service.update_api_key(
        key_id=key_id,
        user=current_user,
        name=data.name,
        key_value=data.key_value,
        metadata=data.metadata
    )
    return key


@router.post("/api-keys/{key_id}/rotate", response_model=APIKeyResponse)
async def rotate_api_key(
    key_id: int,
    current_user: CurrentUser,
    new_key_value: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Rotate an API key with a new value."""
    service = APIKeyService(db)
    key = await service.rotate_api_key(key_id, current_user, new_key_value)
    return key


@router.post("/api-keys/{key_id}/validate", response_model=APIKeyValidationResponse)
async def validate_api_key(
    key_id: int,
    current_user: CurrentUser,
    test_endpoint: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Validate an API key against its provider."""
    service = APIKeyService(db)
    result = await service.validate_api_key(key_id, current_user, test_endpoint)
    
    return APIKeyValidationResponse(
        valid=result["valid"],
        message=result["message"],
        provider=result["provider"],
        validated_at=datetime.utcnow(),
        details=result.get("details")
    )


@router.delete("/api-keys/{key_id}")
async def deactivate_api_key(
    key_id: int,
    current_user: CurrentUser,
    reason: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate an API key."""
    service = APIKeyService(db)
    await service.deactivate_api_key(key_id, current_user, reason)
    return {"status": "deactivated", "key_id": key_id}


@router.get("/api-keys/{key_id}/usage")
async def get_api_key_usage(
    key_id: int,
    current_user: CurrentUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get usage statistics for an API key."""
    # TODO: Implement usage statistics query
    return {
        "key_id": key_id,
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "average_response_time_ms": 0,
        "period": {
            "start": start_date,
            "end": end_date
        }
    }


@router.get("/api-keys/{key_id}/audit-logs")
async def get_api_key_audit_logs(
    key_id: int,
    current_user: CurrentUser,
    action: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs for an API key."""
    # TODO: Implement audit log query
    return {
        "key_id": key_id,
        "logs": [],
        "total": 0
    }