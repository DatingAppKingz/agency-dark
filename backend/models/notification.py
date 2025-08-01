"""Notification models for email, SMS, and push notifications."""

from sqlalchemy import Column, String, Text, JSON, ForeignKey, DateTime, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from enum import Enum

from core.database import Base


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


class Notification(Base):
    """Main notification model."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SQLEnum(NotificationType), nullable=False)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL, nullable=False)
    
    # Recipients
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=True)  # For non-user recipients
    phone = Column(String(20), nullable=True)   # For SMS
    
    # Content
    subject = Column(String(500), nullable=True)  # For email
    content = Column(Text, nullable=False)
    html_content = Column(Text, nullable=True)    # For rich email
    
    # Template
    template_id = Column(UUID(as_uuid=True), ForeignKey("notification_templates.id"), nullable=True)
    template_data = Column(JSON, nullable=True)   # Variables for template
    
    # Metadata
    metadata = Column(JSON, nullable=True)         # Additional data
    tags = Column(JSON, nullable=True)            # For filtering/grouping
    
    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    
    # Error handling
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    
    # External references
    external_id = Column(String(255), nullable=True)  # Provider message ID
    callback_url = Column(String(500), nullable=True)  # Webhook URL
    
    # Agency relationship
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    agency = relationship("Agency", back_populates="notifications")
    template = relationship("NotificationTemplate", back_populates="notifications")
    events = relationship("NotificationEvent", back_populates="notification", cascade="all, delete-orphan")


class NotificationTemplate(Base):
    """Reusable notification templates."""
    __tablename__ = "notification_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(SQLEnum(NotificationType), nullable=False)
    
    # Template content
    subject_template = Column(String(500), nullable=True)  # For email
    content_template = Column(Text, nullable=False)
    html_template = Column(Text, nullable=True)           # For rich email
    
    # Variables schema
    variables_schema = Column(JSON, nullable=True)        # Expected variables
    
    # Settings
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)  # System templates can't be deleted
    
    # Agency relationship
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="notification_templates")
    notifications = relationship("Notification", back_populates="template")


class NotificationPreference(Base):
    """User notification preferences."""
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Channel preferences
    email_enabled = Column(Boolean, default=True, nullable=False)
    sms_enabled = Column(Boolean, default=True, nullable=False)
    push_enabled = Column(Boolean, default=True, nullable=False)
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    
    # Category preferences (JSON object with category: boolean pairs)
    categories = Column(JSON, default={
        "marketing": True,
        "transactions": True,
        "messages": True,
        "system": True,
        "security": True
    }, nullable=False)
    
    # Frequency settings
    digest_enabled = Column(Boolean, default=False, nullable=False)
    digest_frequency = Column(String(20), default="daily")  # daily, weekly, monthly
    quiet_hours_enabled = Column(Boolean, default=False, nullable=False)
    quiet_hours_start = Column(String(5), nullable=True)    # HH:MM format
    quiet_hours_end = Column(String(5), nullable=True)      # HH:MM format
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Contact preferences
    preferred_email = Column(String(255), nullable=True)
    preferred_phone = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences", uselist=False)


class NotificationEvent(Base):
    """Track notification events (opens, clicks, etc)."""
    __tablename__ = "notification_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # sent, delivered, opened, clicked, bounced, failed
    event_data = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    notification = relationship("Notification", back_populates="events")