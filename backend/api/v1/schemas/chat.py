"""Pydantic schemas for chat API."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

from models.chat import ConversationStatus, MessageType, MessageStatus


# Base schemas
class ConversationBase(BaseModel):
    """Base conversation schema."""
    fan_id: str = Field(..., max_length=255)
    fan_username: str = Field(..., max_length=255)
    fan_display_name: Optional[str] = Field(None, max_length=255)
    fan_avatar_url: Optional[str] = Field(None, max_length=500)
    fan_location: Optional[str] = Field(None, max_length=255)
    fan_timezone: Optional[str] = Field(None, max_length=50)
    fan_language: str = Field("en", max_length=10)
    status: ConversationStatus = ConversationStatus.ACTIVE
    priority: int = Field(0, ge=0, le=10)
    tags: List[str] = []
    notes: Optional[str] = None


class MessageBase(BaseModel):
    """Base message schema."""
    type: MessageType = MessageType.TEXT
    content: Optional[str] = None
    media_url: Optional[str] = Field(None, max_length=500)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    amount: Optional[Decimal] = Field(None, ge=0)
    currency: str = Field("USD", max_length=3)
    platform_message_id: Optional[str] = Field(None, max_length=255)
    platform_data: Dict[str, Any] = {}


class ChatTemplateBase(BaseModel):
    """Base chat template schema."""
    name: str = Field(..., max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    content: str
    variables: List[str] = []
    tags: List[str] = []
    languages: List[str] = ["en"]


# Create schemas
class ConversationCreate(ConversationBase):
    """Schema for creating a conversation."""
    model_id: int
    assigned_chatter_id: Optional[int] = None


class MessageCreate(MessageBase):
    """Schema for creating a message."""
    pass


class ChatTemplateCreate(ChatTemplateBase):
    """Schema for creating a chat template."""
    pass


# Update schemas
class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    status: Optional[ConversationStatus] = None
    priority: Optional[int] = Field(None, ge=0, le=10)
    assigned_chatter_id: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    fan_display_name: Optional[str] = Field(None, max_length=255)
    fan_avatar_url: Optional[str] = Field(None, max_length=500)
    fan_location: Optional[str] = Field(None, max_length=255)
    fan_timezone: Optional[str] = Field(None, max_length=50)
    fan_language: Optional[str] = Field(None, max_length=10)


class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    status: Optional[MessageStatus] = None
    read_at: Optional[str] = None
    is_flagged: Optional[bool] = None
    flagged_reason: Optional[str] = Field(None, max_length=255)


class ChatTemplateUpdate(BaseModel):
    """Schema for updating a chat template."""
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    content: Optional[str] = None
    variables: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    is_active: Optional[bool] = None


# Response schemas
class UserInfo(BaseModel):
    """User info for responses."""
    id: int
    email: str
    full_name: Optional[str]
    role: str
    
    class Config:
        orm_mode = True


class ModelInfo(BaseModel):
    """Model info for responses."""
    id: int
    stage_name: str
    platform: str
    platform_username: str
    
    class Config:
        orm_mode = True


class ConversationResponse(ConversationBase):
    """Conversation response schema."""
    id: int
    model_id: int
    model: Optional[ModelInfo] = None
    assigned_chatter_id: Optional[int] = None
    assigned_chatter: Optional[UserInfo] = None
    assigned_at: Optional[str] = None
    total_spent: Decimal
    total_tips: Decimal
    ppv_purchased: int
    last_message_at: Optional[str] = None
    last_fan_message_at: Optional[str] = None
    unread_count: int
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class MessageResponse(MessageBase):
    """Message response schema."""
    id: int
    conversation_id: int
    sender_id: Optional[int] = None
    sender: Optional[UserInfo] = None
    sender_type: str
    status: MessageStatus
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None
    is_paid: bool
    is_flagged: bool
    flagged_reason: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class ChatTemplateResponse(ChatTemplateBase):
    """Chat template response schema."""
    id: int
    agency_id: int
    usage_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Paginated responses
class PaginatedConversations(BaseModel):
    """Paginated conversations response."""
    items: List[ConversationResponse]
    total: int
    page: int
    pages: int


class PaginatedMessages(BaseModel):
    """Paginated messages response."""
    items: List[MessageResponse]
    total: int
    page: int
    pages: int


# Statistics
class ConversationStats(BaseModel):
    """Conversation statistics."""
    conversation_id: int
    total_messages: int
    fan_messages: int
    our_messages: int
    avg_tip_amount: float
    total_tips_amount: float
    ppv_sent: int
    ppv_revenue: float
    total_revenue: Decimal