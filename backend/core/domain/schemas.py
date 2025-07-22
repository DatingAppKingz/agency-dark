from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from core.domain.models import UserRole, SubscriptionStatus, NotificationType


class AgencyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class AgencyCreate(AgencyBase):
    slug: str = Field(..., min_length=1, max_length=255)
    
    @validator('slug')
    def validate_slug(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()


class AgencyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class Agency(AgencyBase):
    id: UUID
    slug: str
    subscription_status: SubscriptionStatus
    subscription_ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    role: UserRole = UserRole.AGENCY_MEMBER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    agency_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    id: UUID
    agency_id: Optional[UUID]
    is_active: bool
    email_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class User(UserInDB):
    agency: Optional[Agency] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: UUID
    agency_id: Optional[UUID] = None
    role: UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class NotificationBase(BaseModel):
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=255)
    message: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class NotificationCreate(NotificationBase):
    user_id: Optional[UUID] = None


class Notification(NotificationBase):
    id: UUID
    agency_id: UUID
    user_id: Optional[UUID]
    read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogBase(BaseModel):
    action: str = Field(..., min_length=1, max_length=255)
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class AuditLog(AuditLogBase):
    id: UUID
    agency_id: UUID
    user_id: Optional[UUID]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class HealthCheck(BaseModel):
    status: str
    services: Dict[str, str]


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    request_id: Optional[str] = None