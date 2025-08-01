"""Schemas for external API credential management."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

from models.external_api import APIProvider


class ExternalAPICredentialBase(BaseModel):
    """Base schema for external API credentials."""
    provider: APIProvider
    credentials: Dict[str, Any]
    is_active: bool = True


class ExternalAPICredentialCreate(ExternalAPICredentialBase):
    """Schema for creating external API credentials."""
    pass


class ExternalAPICredentialUpdate(BaseModel):
    """Schema for updating external API credentials."""
    credentials: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ExternalAPICredentialResponse(BaseModel):
    """Response schema for external API credentials."""
    id: UUID
    user_id: UUID
    agency_id: UUID
    provider: APIProvider
    masked_credentials: Dict[str, Any]
    is_active: bool
    is_valid: Optional[bool]
    last_validated: Optional[datetime]
    validation_error: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to use masked credentials."""
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            agency_id=obj.agency_id,
            provider=obj.provider,
            masked_credentials=obj.masked_credentials,
            is_active=obj.is_active,
            is_valid=obj.is_valid,
            last_validated=obj.last_validated,
            validation_error=obj.validation_error,
            metadata=obj.metadata,
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )


class ValidationResult(BaseModel):
    """Result of credential validation."""
    provider: APIProvider
    is_valid: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TestAllCredentialsResponse(BaseModel):
    """Response for testing all credentials."""
    results: Dict[str, Dict[str, Any]]


class WebhookEndpointBase(BaseModel):
    """Base schema for webhook endpoints."""
    provider: APIProvider
    endpoint_url: str = Field(..., max_length=500)
    secret: Optional[str] = Field(None, max_length=500)
    events: Optional[List[str]] = None
    is_active: bool = True


class WebhookEndpointCreate(WebhookEndpointBase):
    """Schema for creating webhook endpoints."""
    pass


class WebhookEndpointUpdate(BaseModel):
    """Schema for updating webhook endpoints."""
    endpoint_url: Optional[str] = Field(None, max_length=500)
    secret: Optional[str] = Field(None, max_length=500)
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookEndpointResponse(BaseModel):
    """Response schema for webhook endpoints."""
    id: UUID
    agency_id: UUID
    provider: APIProvider
    endpoint_url: str
    events: Optional[List[str]]
    is_active: bool
    last_received: Optional[datetime]
    failure_count: int
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class APICallLogResponse(BaseModel):
    """Response schema for API call logs."""
    id: UUID
    provider: APIProvider
    method: str
    endpoint: str
    status_code: Optional[int]
    response_time_ms: Optional[int]
    is_error: bool
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True


class OnlyFansCredentials(BaseModel):
    """Schema for OnlyFans API credentials."""
    api_key: str = Field(..., description="OnlyFans API key")
    cookie: Optional[str] = Field(None, description="OnlyFans cookie for authentication")
    x_bc: Optional[str] = Field(None, description="OnlyFans X-BC header value")
    user_agent: Optional[str] = Field(None, description="Custom user agent")


class StripeCredentials(BaseModel):
    """Schema for Stripe API credentials."""
    secret_key: str = Field(..., description="Stripe secret key (sk_test_... or sk_live_...)")
    publishable_key: Optional[str] = Field(None, description="Stripe publishable key")
    webhook_secret: Optional[str] = Field(None, description="Stripe webhook endpoint secret")


class InflowCredentials(BaseModel):
    """Schema for Inflow API credentials."""
    api_key: str = Field(..., description="Inflow API key")
    agency_id: str = Field(..., description="Inflow agency ID")
    webhook_secret: Optional[str] = Field(None, description="Inflow webhook secret")