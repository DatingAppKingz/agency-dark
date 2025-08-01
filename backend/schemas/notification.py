"""Notification schemas for request/response validation."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum


class NotificationType(str, Enum):
    """Notification type enumeration."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    """Notification status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"


class NotificationPriority(str, Enum):
    """Notification priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationCategory(str, Enum):
    """Notification category enumeration."""
    MARKETING = "marketing"
    TRANSACTIONS = "transactions"
    MESSAGES = "messages"
    SYSTEM = "system"
    SECURITY = "security"


# Base Schemas
class NotificationBase(BaseModel):
    """Base notification schema."""
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: Optional[str] = Field(None, max_length=500, description="Email subject")
    content: str = Field(..., description="Notification content")
    html_content: Optional[str] = Field(None, description="HTML content for rich emails")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering/grouping")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule for later delivery")


class NotificationCreate(NotificationBase):
    """Create notification request."""
    user_id: Optional[str] = Field(None, description="Target user ID")
    email: Optional[EmailStr] = Field(None, description="Email for non-user recipients")
    phone: Optional[str] = Field(None, regex=r'^\+?[1-9]\d{1,14}$', description="Phone number for SMS")
    template_id: Optional[str] = Field(None, description="Template ID to use")
    template_data: Optional[Dict[str, Any]] = Field(None, description="Template variables")
    callback_url: Optional[str] = Field(None, description="Webhook URL for notifications")

    @validator('email')
    def validate_email_for_type(cls, v, values):
        if values.get('type') == NotificationType.EMAIL and not v and not values.get('user_id'):
            raise ValueError('Email is required for email notifications without user_id')
        return v

    @validator('phone')
    def validate_phone_for_type(cls, v, values):
        if values.get('type') == NotificationType.SMS and not v and not values.get('user_id'):
            raise ValueError('Phone is required for SMS notifications without user_id')
        return v


class NotificationUpdate(BaseModel):
    """Update notification request."""
    status: Optional[NotificationStatus] = None
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationResponse(NotificationBase):
    """Notification response."""
    id: str
    status: NotificationStatus
    user_id: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    template_id: Optional[str]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    retry_count: int
    error_message: Optional[str]
    external_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Bulk Notifications
class BulkNotificationCreate(BaseModel):
    """Create bulk notifications request."""
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: Optional[str] = Field(None, max_length=500)
    content: str
    html_content: Optional[str] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    
    # Recipients
    user_ids: Optional[List[str]] = Field(None, description="List of user IDs")
    emails: Optional[List[EmailStr]] = Field(None, description="List of emails")
    phones: Optional[List[str]] = Field(None, description="List of phone numbers")
    
    # Filters for dynamic recipients
    user_filters: Optional[Dict[str, Any]] = Field(None, description="Filters to select users")
    
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None


class BulkNotificationResponse(BaseModel):
    """Bulk notification response."""
    total_recipients: int
    notifications_created: int
    task_id: str
    estimated_time: Optional[int] = Field(None, description="Estimated time in seconds")


# Templates
class NotificationTemplateBase(BaseModel):
    """Base template schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    type: NotificationType
    subject_template: Optional[str] = Field(None, max_length=500)
    content_template: str
    html_template: Optional[str] = None
    variables_schema: Optional[Dict[str, Any]] = Field(None, description="Expected variables schema")
    is_active: bool = True


class NotificationTemplateCreate(NotificationTemplateBase):
    """Create template request."""
    pass


class NotificationTemplateUpdate(BaseModel):
    """Update template request."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    subject_template: Optional[str] = Field(None, max_length=500)
    content_template: Optional[str] = None
    html_template: Optional[str] = None
    variables_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class NotificationTemplateResponse(NotificationTemplateBase):
    """Template response."""
    id: str
    is_system: bool
    agency_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Preferences
class NotificationPreferenceUpdate(BaseModel):
    """Update notification preferences request."""
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    categories: Optional[Dict[str, bool]] = None
    digest_enabled: Optional[bool] = None
    digest_frequency: Optional[str] = Field(None, regex='^(daily|weekly|monthly)$')
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = Field(None, regex='^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    quiet_hours_end: Optional[str] = Field(None, regex='^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    timezone: Optional[str] = None
    preferred_email: Optional[EmailStr] = None
    preferred_phone: Optional[str] = Field(None, regex=r'^\+?[1-9]\d{1,14}$')


class NotificationPreferenceResponse(BaseModel):
    """Notification preferences response."""
    id: str
    user_id: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    categories: Dict[str, bool]
    digest_enabled: bool
    digest_frequency: str
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    timezone: str
    preferred_email: Optional[str]
    preferred_phone: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Events
class NotificationEventResponse(BaseModel):
    """Notification event response."""
    id: str
    notification_id: str
    event_type: str
    event_data: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Statistics
class NotificationStats(BaseModel):
    """Notification statistics."""
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_failed: int
    total_bounced: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    by_type: Dict[str, Dict[str, int]]
    by_priority: Dict[str, int]


# Test notification
class TestNotificationRequest(BaseModel):
    """Test notification request."""
    type: NotificationType
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    subject: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    html_content: Optional[str] = None