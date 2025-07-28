"""
Webhook data models
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from sqlalchemy import Column, String, JSON, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, HttpUrl

from core.database import Base


class WebhookEvent(str, Enum):
    """Supported webhook events"""
    # Message events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_READ = "message.read"
    
    # Fan events
    FAN_SUBSCRIBED = "fan.subscribed"
    FAN_UNSUBSCRIBED = "fan.unsubscribed"
    FAN_UPDATED = "fan.updated"
    
    # Payment events
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    
    # Model events
    MODEL_ONLINE = "model.online"
    MODEL_OFFLINE = "model.offline"
    MODEL_UPDATED = "model.updated"
    
    # Analytics events
    DAILY_SUMMARY = "analytics.daily_summary"
    MILESTONE_REACHED = "analytics.milestone"


class WebhookStatus(str, Enum):
    """Webhook status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class DeliveryStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(Base):
    """Webhook configuration model"""
    __tablename__ = "webhooks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=False)  # For signing payloads
    events = Column(JSON, nullable=False)  # List of subscribed events
    description = Column(String)
    
    # Configuration
    is_active = Column(Boolean, default=True)
    retry_enabled = Column(Boolean, default=True)
    max_retries = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)
    
    # Headers to include in requests
    custom_headers = Column(JSON, default={})
    
    # Statistics
    total_deliveries = Column(Integer, default=0)
    successful_deliveries = Column(Integer, default=0)
    failed_deliveries = Column(Integer, default=0)
    last_delivery_at = Column(DateTime)
    last_success_at = Column(DateTime)
    last_failure_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Webhook delivery attempt model"""
    __tablename__ = "webhook_deliveries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    webhook_id = Column(String, ForeignKey("webhooks.id"), nullable=False)
    event_type = Column(String, nullable=False)
    event_id = Column(String, nullable=False)  # ID of the event (message, payment, etc.)
    
    # Delivery details
    status = Column(String, default=DeliveryStatus.PENDING.value)
    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime)
    
    # Request/Response
    request_headers = Column(JSON)
    request_body = Column(JSON)
    response_status_code = Column(Integer)
    response_headers = Column(JSON)
    response_body = Column(Text)
    response_time_ms = Column(Integer)
    
    # Error details
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime)
    
    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")


# Pydantic schemas
class WebhookCreate(BaseModel):
    """Schema for creating a webhook"""
    url: HttpUrl
    events: List[WebhookEvent]
    description: Optional[str] = None
    is_active: bool = True
    retry_enabled: bool = True
    max_retries: int = Field(3, ge=0, le=10)
    timeout_seconds: int = Field(30, ge=5, le=60)
    custom_headers: Dict[str, str] = Field(default_factory=dict)


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook"""
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEvent]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    retry_enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=60)
    custom_headers: Optional[Dict[str, str]] = None


class WebhookResponse(BaseModel):
    """Schema for webhook response"""
    id: str
    url: str
    events: List[str]
    description: Optional[str]
    is_active: bool
    retry_enabled: bool
    max_retries: int
    timeout_seconds: int
    custom_headers: Dict[str, str]
    
    # Statistics
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float
    last_delivery_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        
    @property
    def success_rate(self) -> float:
        if self.total_deliveries == 0:
            return 0.0
        return (self.successful_deliveries / self.total_deliveries) * 100


class WebhookPayload(BaseModel):
    """Base webhook payload"""
    event: WebhookEvent
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    
    class Config:
        use_enum_values = True


class MessageWebhookPayload(WebhookPayload):
    """Message event payload"""
    data: Dict[str, Any] = Field(..., example={
        "message_id": "123e4567-e89b-12d3-a456-426614174000",
        "model_id": "123e4567-e89b-12d3-a456-426614174001",
        "fan_id": "123e4567-e89b-12d3-a456-426614174002",
        "content": "Hello!",
        "sender": "fan",
        "created_at": "2024-01-01T00:00:00Z"
    })


class PaymentWebhookPayload(WebhookPayload):
    """Payment event payload"""
    data: Dict[str, Any] = Field(..., example={
        "payment_id": "123e4567-e89b-12d3-a456-426614174000",
        "model_id": "123e4567-e89b-12d3-a456-426614174001",
        "fan_id": "123e4567-e89b-12d3-a456-426614174002",
        "amount": 50.00,
        "currency": "USD",
        "payment_type": "tip",
        "status": "completed",
        "created_at": "2024-01-01T00:00:00Z"
    })


class FanWebhookPayload(WebhookPayload):
    """Fan event payload"""
    data: Dict[str, Any] = Field(..., example={
        "fan_id": "123e4567-e89b-12d3-a456-426614174000",
        "model_id": "123e4567-e89b-12d3-a456-426614174001",
        "username": "fan123",
        "subscription_status": "active",
        "total_spent": 100.00,
        "created_at": "2024-01-01T00:00:00Z"
    })


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response"""
    id: str
    webhook_id: str
    event_type: str
    event_id: str
    status: str
    attempts: int
    response_status_code: Optional[int]
    response_time_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    delivered_at: Optional[datetime]
    
    class Config:
        orm_mode = True


class WebhookDeadLetter(Base):
    """Dead letter queue for failed webhook deliveries"""
    __tablename__ = "webhook_dead_letters"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    webhook_id = Column(String, ForeignKey("webhooks.id"), nullable=False)
    delivery_id = Column(String, ForeignKey("webhook_deliveries.id"), nullable=False)
    
    # Original event data
    event_type = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    
    # Failure information
    final_status_code = Column(Integer)
    total_attempts = Column(Integer, nullable=False)
    first_attempt_at = Column(DateTime, nullable=False)
    last_attempt_at = Column(DateTime, nullable=False)
    error_summary = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When to permanently delete
    is_reprocessed = Column(Boolean, default=False)
    reprocessed_at = Column(DateTime)
    
    # Relationships
    webhook = relationship("Webhook")
    delivery = relationship("WebhookDelivery")