"""
API key management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.domain.api_key_schemas import (
    APIKeyCreate, APIKeyResponse, APIKeyCreateResponse,
    APIKeyRotate, APIKeyRotateResponse, APIKeyRevoke,
    APIKeyUpdate, APIKeyAuditLogResponse, APIKeyValidation,
    APIKeyValidationResponse
)
from core.application.api_key_service import APIKeyService
from core.exceptions import NotFoundError, ValidationError, PermissionError

router = APIRouter()


@router.post("", response_model=APIKeyCreateResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIKeyCreateResponse:
    """
    Create a new API key.
    
    The API key and secret are only shown once. Store them securely.
    """
    try:
        result = await APIKeyService.create_api_key(
            db=db,
            user_id=str(current_user.id),
            agency_id=str(current_user.agency_id),
            name=key_data.name,
            description=key_data.description,
            scopes=key_data.scopes,
            expires_in_days=key_data.expires_in_days,
            ip_whitelist=key_data.ip_whitelist,
            metadata=key_data.metadata if hasattr(key_data, 'metadata') else key_data.key_metadata if hasattr(key_data, 'key_metadata') else None
        )
        
        return APIKeyCreateResponse(**result)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[APIKeyResponse]:
    """
    List API keys.
    
    Admins see all agency keys, others see only their own.
    """
    keys = await APIKeyService.list_api_keys(
        db=db,
        user_id=str(current_user.id),
        agency_id=str(current_user.agency_id) if current_user.agency_id else None
    )
    
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIKeyResponse:
    """Get details of a specific API key."""
    try:
        key = await APIKeyService.get_api_key(
            db=db,
            key_id=str(key_id),
            user_id=str(current_user.id),
            agency_id=str(current_user.agency_id)
        )
        
        return APIKeyResponse.model_validate(key)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="API key not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/{key_id}/rotate", response_model=APIKeyRotateResponse)
async def rotate_api_key(
    key_id: int,
    rotation_data: APIKeyRotate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIKeyRotateResponse:
    """
    Rotate an API key.
    
    Generates new credentials while keeping the same key ID.
    The old key remains valid for the grace period.
    """
    try:
        result = await APIKeyService.rotate_api_key(
            db=db,
            key_id=str(key_id),
            user_id=str(current_user.id),
            agency_id=str(current_user.agency_id),
            reason=rotation_data.reason,
            grace_period_hours=rotation_data.grace_period_hours
        )
        
        return APIKeyRotateResponse(**result)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="API key not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: int,
    revoke_data: APIKeyRevoke,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Revoke an API key.
    
    The key becomes immediately invalid and cannot be reactivated.
    """
    try:
        await APIKeyService.revoke_api_key(
            db=db,
            key_id=str(key_id),
            user_id=str(current_user.id),
            agency_id=str(current_user.agency_id),
            reason=revoke_data.reason
        )
        
        return {"status": "success", "message": "API key revoked"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="API key not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{key_id}/audit-logs", response_model=List[APIKeyAuditLogResponse])
async def get_api_key_audit_logs(
    key_id: int,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[APIKeyAuditLogResponse]:
    """Get audit logs for an API key."""
    try:
        logs = await APIKeyService.get_api_key_audit_logs(
            db=db,
            key_id=str(key_id),
            user_id=str(current_user.id),
            agency_id=str(current_user.agency_id),
            limit=limit
        )
        
        return [APIKeyAuditLogResponse.model_validate(log) for log in logs]
    except NotFoundError:
        raise HTTPException(status_code=404, detail="API key not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/validate", response_model=APIKeyValidationResponse)
async def validate_api_key(
    validation_data: APIKeyValidation,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> APIKeyValidationResponse:
    """
    Validate an API key.
    
    This endpoint is public and can be used to verify API credentials.
    """
    # Get client IP
    client_ip = request.client.host if request.client else None
    
    api_key_record = await APIKeyService.validate_api_key(
        db=db,
        api_key=validation_data.api_key,
        api_secret=validation_data.api_secret,
        required_scopes=validation_data.required_scopes,
        ip_address=client_ip
    )
    
    if api_key_record:
        return APIKeyValidationResponse(
            valid=True,
            agency_id=str(api_key_record.agency_id),
            user_id=str(api_key_record.user_id),
            scopes=api_key_record.scopes,
            expires_at=api_key_record.expires_at.isoformat() if api_key_record.expires_at else None
        )
    else:
        return APIKeyValidationResponse(valid=False)


# Admin endpoints

@router.post("/admin/cleanup-expired")
async def cleanup_expired_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Clean up expired API keys.
    
    Requires super admin role.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    count = await APIKeyService.cleanup_expired_keys(db)
    
    return {
        "status": "success",
        "expired_keys_cleaned": count
    }


# Middleware for API key authentication

async def get_api_key_from_header(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_api_secret: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    Extract and validate API key from headers.
    
    Supports two formats:
    1. Authorization: Bearer <api_key>:<api_secret>
    2. X-API-Key: <api_key> and X-API-Secret: <api_secret>
    """
    api_key = None
    api_secret = None
    
    if authorization and authorization.startswith("Bearer "):
        # Extract from Authorization header
        token = authorization.replace("Bearer ", "")
        if ":" in token:
            api_key, api_secret = token.split(":", 1)
    elif x_api_key and x_api_secret:
        # Extract from custom headers
        api_key = x_api_key
        api_secret = x_api_secret
    
    if not api_key or not api_secret:
        return None
    
    # Validate the key
    api_key_record = await APIKeyService.validate_api_key(
        db=db,
        api_key=api_key,
        api_secret=api_secret
    )
    
    if api_key_record:
        return {
            "api_key_id": str(api_key_record.id),
            "agency_id": str(api_key_record.agency_id),
            "user_id": str(api_key_record.user_id),
            "scopes": api_key_record.scopes
        }
    
    return None