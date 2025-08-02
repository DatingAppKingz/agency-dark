"""
SSO Schemas
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from .models import SSOProviderType


class SSOProviderBase(BaseModel):
    """Base SSO Provider schema"""
    name: str = Field(..., max_length=255)
    provider_type: SSOProviderType
    is_active: bool = True
    
    # SAML Configuration
    entity_id: Optional[str] = Field(None, max_length=500)
    sso_url: Optional[str] = Field(None, max_length=500)
    slo_url: Optional[str] = Field(None, max_length=500)
    x509_cert: Optional[str] = None
    metadata_url: Optional[str] = Field(None, max_length=500)
    
    # OAuth/OIDC Configuration
    client_id: Optional[str] = Field(None, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=255)
    authorization_url: Optional[str] = Field(None, max_length=500)
    token_url: Optional[str] = Field(None, max_length=500)
    userinfo_url: Optional[str] = Field(None, max_length=500)
    scopes: Optional[List[str]] = Field(default_factory=list)
    
    # Common Configuration
    attribute_mapping: Optional[Dict[str, str]] = Field(default_factory=dict)
    allowed_domains: Optional[List[str]] = Field(default_factory=list)
    auto_provision_users: bool = False
    default_role: Optional[str] = Field(None, max_length=50)
    
    @field_validator('sso_url', 'entity_id')
    @classmethod
    def validate_saml_fields(cls, v, info):
        if info.data.get('provider_type') == SSOProviderType.SAML and not v:
            raise ValueError(f"Field is required for SAML providers")
        return v
    
    @field_validator('client_id', 'client_secret', 'authorization_url', 'token_url')
    @classmethod
    def validate_oauth_fields(cls, v, info):
        if info.data.get('provider_type') in [SSOProviderType.OAUTH2, SSOProviderType.OIDC] and not v:
            raise ValueError(f"Field is required for OAuth/OIDC providers")
        return v


class SSOProviderCreate(SSOProviderBase):
    """Create SSO Provider schema"""
    pass


class SSOProviderUpdate(BaseModel):
    """Update SSO Provider schema"""
    name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    
    # SAML Configuration
    entity_id: Optional[str] = Field(None, max_length=500)
    sso_url: Optional[str] = Field(None, max_length=500)
    slo_url: Optional[str] = Field(None, max_length=500)
    x509_cert: Optional[str] = None
    metadata_url: Optional[str] = Field(None, max_length=500)
    
    # OAuth/OIDC Configuration
    client_id: Optional[str] = Field(None, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=255)
    authorization_url: Optional[str] = Field(None, max_length=500)
    token_url: Optional[str] = Field(None, max_length=500)
    userinfo_url: Optional[str] = Field(None, max_length=500)
    scopes: Optional[List[str]] = None
    
    # Common Configuration
    attribute_mapping: Optional[Dict[str, str]] = None
    allowed_domains: Optional[List[str]] = None
    auto_provision_users: Optional[bool] = None
    default_role: Optional[str] = Field(None, max_length=50)


class SSOProviderResponse(SSOProviderBase):
    """SSO Provider response schema"""
    id: UUID
    agency_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class SSOSessionResponse(BaseModel):
    """SSO Session response schema"""
    id: UUID
    user_id: UUID
    provider_id: UUID
    provider_name: Optional[str] = None
    provider_type: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_activity: datetime
    ip_address: Optional[str] = None
    
    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
    
    @field_validator('provider_name', 'provider_type', mode='before')
    @classmethod
    def extract_provider_info(cls, v, info):
        # In Pydantic V2, we need to handle this differently
        # For now, just return the value as-is
        return v


class SAMLMetadataResponse(BaseModel):
    """SAML metadata response"""
    entity_id: str
    acs_url: str
    sls_url: str
    metadata_url: str


class SCIMUserRequest(BaseModel):
    """SCIM User request schema"""
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    externalId: Optional[str] = None
    userName: str
    name: Optional[Dict[str, str]] = None
    emails: Optional[List[Dict[str, Any]]] = None
    active: bool = True
    
    model_config = {
        "extra": "allow"
    }


class SCIMUserResponse(BaseModel):
    """SCIM User response schema"""
    schemas: List[str]
    id: str
    externalId: Optional[str] = None
    userName: str
    name: Optional[Dict[str, str]] = None
    emails: Optional[List[Dict[str, Any]]] = None
    active: bool
    meta: Dict[str, Any]


class SCIMListResponse(BaseModel):
    """SCIM List response schema"""
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: List[SCIMUserResponse]


class SCIMErrorResponse(BaseModel):
    """SCIM Error response schema"""
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:Error"]
    status: str
    scimType: Optional[str] = None
    detail: str