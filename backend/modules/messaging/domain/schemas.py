"""
Pydantic schemas for messaging module.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from .models import MessageStatus, MessagePriority, TemplateCategory


# Template Schemas
class MessageTemplateBase(BaseModel):
    """Base schema for message templates."""
    name: str = Field(..., min_length=1, max_length=255)
    category: TemplateCategory = TemplateCategory.CUSTOM
    subject: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    variables: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_global: bool = False


class MessageTemplateCreate(MessageTemplateBase):
    """Schema for creating a message template."""
    pass


class MessageTemplateUpdate(BaseModel):
    """Schema for updating a message template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[TemplateCategory] = None
    subject: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    variables: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_global: Optional[bool] = None
    is_active: Optional[bool] = None


class MessageTemplateResponse(MessageTemplateBase):
    """Schema for message template responses."""
    id: UUID
    agency_id: UUID
    created_by_id: Optional[UUID]
    usage_count: int
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Bulk Message Schemas
class RecipientFilter(BaseModel):
    """Schema for recipient filtering."""
    subscription_status: Optional[List[str]] = None
    spent_min: Optional[float] = None
    spent_max: Optional[float] = None
    last_active_days: Optional[int] = None
    tags: Optional[List[str]] = None
    custom_filters: Optional[Dict[str, Any]] = None


class BulkMessageBase(BaseModel):
    """Base schema for bulk messages."""
    campaign_name: str = Field(..., min_length=1, max_length=255)
    model_id: UUID
    template_id: Optional[UUID] = None
    subject: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    scheduled_at: Optional[datetime] = None
    time_zone: str = "UTC"
    priority: MessagePriority = MessagePriority.NORMAL
    recipient_filters: RecipientFilter = Field(default_factory=RecipientFilter)
    personalize: bool = True
    track_opens: bool = True
    track_clicks: bool = True
    messages_per_minute: int = Field(60, ge=1, le=120)


class BulkMessageCreate(BulkMessageBase):
    """Schema for creating a bulk message."""
    send_test: bool = False  # Send test to creator first
    test_recipient_ids: Optional[List[UUID]] = None


class BulkMessageUpdate(BaseModel):
    """Schema for updating a bulk message."""
    campaign_name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    scheduled_at: Optional[datetime] = None
    time_zone: Optional[str] = None
    priority: Optional[MessagePriority] = None
    messages_per_minute: Optional[int] = Field(None, ge=1, le=120)


class BulkMessageResponse(BulkMessageBase):
    """Schema for bulk message responses."""
    id: UUID
    agency_id: UUID
    created_by_id: Optional[UUID]
    status: MessageStatus
    total_recipients: int
    sent_count: int
    failed_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BulkMessageStats(BaseModel):
    """Statistics for a bulk message campaign."""
    total_recipients: int
    sent_count: int
    failed_count: int
    pending_count: int
    open_rate: float
    click_rate: float
    avg_send_time_seconds: Optional[float]
    estimated_completion_time: Optional[datetime]


# Recipient Schemas
class RecipientStatus(BaseModel):
    """Status of a bulk message recipient."""
    fan_id: UUID
    fan_name: str
    status: MessageStatus
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    error_message: Optional[str]


class RecipientListResponse(BaseModel):
    """Response for listing bulk message recipients."""
    recipients: List[RecipientStatus]
    total: int
    sent: int
    failed: int
    pending: int


# Canned Response Schemas
class CannedResponseBase(BaseModel):
    """Base schema for canned responses."""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    shortcut: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    tags: List[str] = Field(default_factory=list)
    auto_personalize: bool = True
    
    @validator('shortcut')
    def validate_shortcut(cls, v):
        if v and not v.startswith('/'):
            v = f'/{v}'
        return v


class CannedResponseCreate(CannedResponseBase):
    """Schema for creating a canned response."""
    is_agency_wide: bool = False  # If True, available to all agency users


class CannedResponseUpdate(BaseModel):
    """Schema for updating a canned response."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    shortcut: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    auto_personalize: Optional[bool] = None
    is_active: Optional[bool] = None


class CannedResponseResponse(CannedResponseBase):
    """Schema for canned response responses."""
    id: UUID
    agency_id: UUID
    user_id: Optional[UUID]
    usage_count: int
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Message Schedule Schemas
class MessageScheduleBase(BaseModel):
    """Base schema for scheduled messages."""
    model_id: UUID
    fan_id: UUID
    content: str = Field(..., min_length=1)
    media_urls: List[str] = Field(default_factory=list)
    scheduled_for: datetime
    time_zone: str = "UTC"
    platform: str = "onlyfans"
    is_recurring: bool = False
    recurrence_pattern: Optional[Dict[str, Any]] = None
    recurrence_end_date: Optional[datetime] = None
    
    @validator('scheduled_for')
    def validate_future_date(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Scheduled time must be in the future')
        return v
    
    @validator('recurrence_pattern')
    def validate_recurrence(cls, v, values):
        if values.get('is_recurring') and not v:
            raise ValueError('Recurrence pattern required for recurring messages')
        return v


class MessageScheduleCreate(MessageScheduleBase):
    """Schema for creating a scheduled message."""
    pass


class MessageScheduleUpdate(BaseModel):
    """Schema for updating a scheduled message."""
    content: Optional[str] = Field(None, min_length=1)
    media_urls: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None
    time_zone: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[Dict[str, Any]] = None
    recurrence_end_date: Optional[datetime] = None


class MessageScheduleResponse(MessageScheduleBase):
    """Schema for scheduled message responses."""
    id: UUID
    agency_id: UUID
    created_by_id: Optional[UUID]
    status: MessageStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    platform_message_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Analytics Schemas
class MessageAnalytics(BaseModel):
    """Analytics for messaging performance."""
    total_messages_sent: int
    total_bulk_campaigns: int
    avg_open_rate: float
    avg_click_rate: float
    total_scheduled: int
    total_templates: int
    most_used_templates: List[Dict[str, Any]]
    peak_sending_hours: List[Dict[str, Any]]
    platform_breakdown: Dict[str, int]