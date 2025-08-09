"""
Secure API Key Management Endpoints
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.database import get_db
from core.security_v2 import get_current_user
from core.security_v2.authorization import check_permission
from core.security.api_key_manager import secure_api_key_manager
from core.security.encryption import data_masking
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys-secure"])


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(..., min_items=1)
    expires_in_days: Optional[int] = Field(365, ge=1, le=365)
    metadata: Optional[Dict[str, Any]] = None


class CreateAPIKeyResponse(BaseModel):
    id: int
    name: str
    public_key: str
    secret_key: str
    scopes: List[str]
    expires_at: datetime
    message: str = "Save the secret key securely. It won't be shown again."


class APIKeyInfo(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: List[str]
    environment: str
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    is_active: bool
    needs_rotation: bool
    metadata: Dict[str, Any]


class RotateKeyResponse(BaseModel):
    public_key: str
    secret_key: str
    message: str = "Key rotated successfully. Save the new secret key."


class RevokeKeyRequest(BaseModel):
    reason: str = Field("user_requested", max_length=100)


class APIKeyAuditEntry(BaseModel):
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


@router.post("/", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None)
):
    """Create a new API key with encryption"""
    try:
        # Add request metadata
        metadata = request.metadata or {}
        metadata["created_by_ip"] = x_forwarded_for or "unknown"
        metadata["created_by_agent"] = user_agent or "unknown"
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        # Create the API key
        public_key, secret_key, api_key = await secure_api_key_manager.create_api_key(
            db=db,
            user_id=current_user["id"],
            name=request.name,
            scopes=request.scopes,
            expires_at=expires_at,
            metadata=metadata
        )
        
        logger.info(f"Created API key '{request.name}' for user {current_user['id']}")
        
        return CreateAPIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            public_key=public_key,
            secret_key=secret_key,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/", response_model=List[APIKeyInfo])
async def list_api_keys(
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for the current user"""
    try:
        keys_data = await secure_api_key_manager.list_user_keys(
            db=db,
            user_id=current_user["id"],
            include_inactive=include_inactive
        )
        
        return [APIKeyInfo(**key_data) for key_data in keys_data]
        
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.get("/{key_id}", response_model=APIKeyInfo)
async def get_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific API key"""
    try:
        keys_data = await secure_api_key_manager.list_user_keys(
            db=db,
            user_id=current_user["id"],
            include_inactive=True
        )
        
        for key_data in keys_data:
            if key_data["id"] == key_id:
                return APIKeyInfo(**key_data)
        
        raise HTTPException(status_code=404, detail="API key not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API key")


@router.post("/{key_id}/rotate", response_model=RotateKeyResponse)
async def rotate_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rotate an API key to generate new credentials"""
    try:
        public_key, secret_key = await secure_api_key_manager.rotate_api_key(
            db=db,
            api_key_id=key_id,
            user_id=current_user["id"]
        )
        
        logger.info(f"Rotated API key {key_id} for user {current_user['id']}")
        
        return RotateKeyResponse(
            public_key=public_key,
            secret_key=secret_key
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rotate API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate API key")


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: int,
    request: RevokeKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke an API key"""
    try:
        success = await secure_api_key_manager.revoke_api_key(
            db=db,
            api_key_id=key_id,
            user_id=current_user["id"],
            reason=request.reason
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        
        logger.info(f"Revoked API key {key_id} for user {current_user['id']}: {request.reason}")
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.get("/{key_id}/audit", response_model=List[APIKeyAuditEntry])
async def get_api_key_audit_log(
    key_id: int,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get audit log for an API key"""
    try:
        audit_logs = await secure_api_key_manager.get_key_audit_log(
            db=db,
            api_key_id=key_id,
            user_id=current_user["id"],
            limit=limit
        )
        
        # Mask sensitive data in audit logs
        masked_logs = []
        for log in audit_logs:
            log_copy = log.copy()
            if log_copy.get("details"):
                log_copy["details"] = data_masking.mask_dict(log_copy["details"])
            masked_logs.append(APIKeyAuditEntry(**log_copy))
        
        return masked_logs
        
    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(status_code=500, detail="Failed to get audit log")


@router.post("/verify")
async def verify_api_key(
    api_key: str = Body(..., embed=True),
    required_scopes: Optional[List[str]] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Verify an API key (for testing purposes)"""
    try:
        api_key_record = await secure_api_key_manager.verify_api_key(
            db=db,
            api_key=api_key,
            required_scopes=required_scopes
        )
        
        if not api_key_record:
            return {"valid": False, "reason": "Invalid or expired API key"}
        
        return {
            "valid": True,
            "key_id": api_key_record.id,
            "scopes": api_key_record.scopes,
            "environment": api_key_record.environment,
            "expires_at": api_key_record.expires_at
        }
        
    except Exception as e:
        logger.error(f"Failed to verify API key: {e}")
        return {"valid": False, "reason": "Verification failed"}


@router.get("/stats/summary")
async def get_api_key_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get API key usage statistics for the current user"""
    await check_permission(current_user["role"], "user.read")
    
    try:
        keys_data = await secure_api_key_manager.list_user_keys(
            db=db,
            user_id=current_user["id"],
            include_inactive=True
        )
        
        active_keys = [k for k in keys_data if k["is_active"]]
        expired_keys = [k for k in keys_data if k["expires_at"] < datetime.utcnow()]
        needs_rotation = [k for k in active_keys if k["needs_rotation"]]
        
        total_usage = sum(k["usage_count"] for k in keys_data)
        
        return {
            "total_keys": len(keys_data),
            "active_keys": len(active_keys),
            "expired_keys": len(expired_keys),
            "needs_rotation": len(needs_rotation),
            "total_api_calls": total_usage,
            "most_used_key": max(keys_data, key=lambda k: k["usage_count"])["name"] if keys_data else None,
            "recommendations": []
        }
        
        # Add recommendations
        recommendations = []
        if len(needs_rotation) > 0:
            recommendations.append({
                "type": "security",
                "message": f"{len(needs_rotation)} key(s) need rotation for security"
            })
        
        if len(expired_keys) > 3:
            recommendations.append({
                "type": "cleanup",
                "message": f"Consider removing {len(expired_keys)} expired keys"
            })
        
        return {
            "total_keys": len(keys_data),
            "active_keys": len(active_keys),
            "expired_keys": len(expired_keys),
            "needs_rotation": len(needs_rotation),
            "total_api_calls": total_usage,
            "most_used_key": max(keys_data, key=lambda k: k["usage_count"])["name"] if keys_data else None,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"Failed to get API key stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")