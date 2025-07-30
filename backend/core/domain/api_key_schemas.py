"""API Key schemas for request/response models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    ip_whitelist: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class APIKeyResponse(BaseModel):
    """Schema for API key response (without sensitive data)."""
    id: int
    name: str
    description: Optional[str]
    prefix: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Response when creating an API key (includes the actual key once)."""
    id: int
    key: str  # Only shown once!
    name: str
    prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]


class APIKeyRotate(BaseModel):
    """Schema for rotating an API key."""
    key_id: int


class APIKeyRotateResponse(BaseModel):
    """Response when rotating an API key."""
    id: int
    key: str  # New key, only shown once!
    prefix: str


class APIKeyRevoke(BaseModel):
    """Schema for revoking an API key."""
    key_id: int
    reason: Optional[str] = None


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    name: Optional[str] = None
    description: Optional[str] = None
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    is_active: Optional[bool] = None


class APIKeyAuditLogResponse(BaseModel):
    """Schema for API key audit log entries."""
    id: int
    api_key_id: int
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    details: Optional[Dict[str, Any]]


class APIKeyValidation(BaseModel):
    """Schema for validating an API key."""
    key: str
    scope: Optional[str] = None


class APIKeyValidationResponse(BaseModel):
    """Response for API key validation."""
    valid: bool
    key_id: Optional[int]
    user_id: Optional[int]
    agency_id: Optional[int]
    scopes: Optional[List[str]]
    expires_at: Optional[datetime]