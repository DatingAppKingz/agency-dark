"""
API Key management schemas.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from core.domain.api_key_models import APIKeyStatus, APIKeyScope


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scopes: List[str] = Field(..., min_items=1)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    ip_whitelist: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('scopes')
    def validate_scopes(cls, v):
        valid_scopes = [s.value for s in APIKeyScope]
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f"Invalid scope: {scope}")
        return v
    
    @validator('ip_whitelist')
    def validate_ip_whitelist(cls, v):
        if v:
            import ipaddress
            for ip in v:
                try:
                    # Validate IP address format
                    ipaddress.ip_address(ip)
                except ValueError:
                    raise ValueError(f"Invalid IP address: {ip}")
        return v


class APIKeyRotate(BaseModel):
    """Request to rotate an API key."""
    reason: str = Field(..., min_length=1, max_length=500)
    grace_period_hours: int = Field(24, ge=0, le=168)  # Max 1 week


class APIKeyRevoke(BaseModel):
    """Request to revoke an API key."""
    reason: str = Field(..., min_length=1, max_length=500)


class APIKeyUpdate(BaseModel):
    """Request to update an API key."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('scopes')
    def validate_scopes(cls, v):
        if v is not None:
            valid_scopes = [s.value for s in APIKeyScope]
            for scope in v:
                if scope not in valid_scopes:
                    raise ValueError(f"Invalid scope: {scope}")
        return v


class APIKeyResponse(BaseModel):
    """API key response (without secrets)."""
    id: UUID
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    ip_whitelist: List[str]
    status: str
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    last_rotated_at: Optional[datetime]
    rotation_count: int
    usage_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Response after creating an API key (includes secrets)."""
    id: str
    name: str
    key_prefix: str
    api_key: str
    api_secret: str
    scopes: List[str]
    expires_at: Optional[str]
    created_at: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Production API Key",
                "key_prefix": "ak_1234abcd...",
                "api_key": "ak_1234abcd5678efgh",
                "api_secret": "sk_abcdef123456789",
                "scopes": ["read:analytics", "read:financial"],
                "expires_at": "2024-12-31T23:59:59Z",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class APIKeyRotateResponse(BaseModel):
    """Response after rotating an API key."""
    id: str
    name: str
    key_prefix: str
    api_key: str
    api_secret: str
    old_key_expires_at: str
    rotated_at: str


class APIKeyAuditLogResponse(BaseModel):
    """API key audit log entry."""
    id: UUID
    action: str
    performed_by_id: Optional[UUID]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_path: Optional[str]
    request_method: Optional[str]
    response_status: Optional[int]
    metadata: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyValidation(BaseModel):
    """Request to validate an API key."""
    api_key: str
    api_secret: str
    required_scopes: Optional[List[str]] = Field(default_factory=list)


class APIKeyValidationResponse(BaseModel):
    """Response from API key validation."""
    valid: bool
    agency_id: Optional[str] = None
    user_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "agency_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "987fcdeb-51a2-43c1-9876-543210fedcba",
                "scopes": ["read:analytics", "read:financial"],
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }