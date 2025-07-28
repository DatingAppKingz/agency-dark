"""
Domain models for messaging module.

Handles bulk messaging, templates, and message scheduling.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, JSON, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class MessageStatus(str, enum.Enum):
    """Message delivery status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    PARTIALLY_SENT = "partially_sent"
    CANCELLED = "cancelled"


class MessagePriority(str, enum.Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TemplateCategory(str, enum.Enum):
    """Template categories."""
    GREETING = "greeting"
    PROMOTIONAL = "promotional"
    ENGAGEMENT = "engagement"
    RETENTION = "retention"
    CUSTOM = "custom"


class MessageTemplate(Base):
    """Message templates for reusable content."""
    __tablename__ = "message_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    name = Column(String(255), nullable=False)
    category = Column(SQLEnum(TemplateCategory), default=TemplateCategory.CUSTOM)
    subject = Column(String(255))  # For messages with subjects
    content = Column(Text, nullable=False)
    
    # Variable placeholders in template (e.g., {{fan_name}}, {{model_name}})
    variables = Column(JSON, default=list)  # List of variable names
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # Metadata
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=False)  # Available to all users in agency
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    created_by = relationship("User")
    bulk_messages = relationship("BulkMessage", back_populates="template")
    
    __table_args__ = (
        Index('idx_message_templates_agency', 'agency_id'),
        Index('idx_message_templates_category', 'category'),
        UniqueConstraint('agency_id', 'name', name='uq_agency_template_name'),
    )


class BulkMessage(Base):
    """Bulk message campaigns."""
    __tablename__ = "bulk_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("message_templates.id", ondelete="SET NULL"))
    
    # Campaign details
    campaign_name = Column(String(255), nullable=False)
    subject = Column(String(255))
    content = Column(Text, nullable=False)
    
    # Scheduling
    scheduled_at = Column(DateTime)  # None means send immediately
    time_zone = Column(String(50), default="UTC")
    
    # Status tracking
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.DRAFT)
    priority = Column(SQLEnum(MessagePriority), default=MessagePriority.NORMAL)
    
    # Recipients
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # Filters for recipient selection
    recipient_filters = Column(JSON, default=dict)  # e.g., {"subscription_status": "active", "spent_min": 100}
    
    # Performance
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Settings
    personalize = Column(Boolean, default=True)  # Use template variables
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)
    
    # Rate limiting
    messages_per_minute = Column(Integer, default=60)  # Platform limits
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    model = relationship("ModelProfile")
    created_by = relationship("User")
    template = relationship("MessageTemplate", back_populates="bulk_messages")
    recipients = relationship("BulkMessageRecipient", back_populates="bulk_message", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_bulk_messages_agency', 'agency_id'),
        Index('idx_bulk_messages_model', 'model_id'),
        Index('idx_bulk_messages_status', 'status'),
        Index('idx_bulk_messages_scheduled', 'scheduled_at'),
    )


class BulkMessageRecipient(Base):
    """Individual recipients of bulk messages."""
    __tablename__ = "bulk_message_recipients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bulk_message_id = Column(UUID(as_uuid=True), ForeignKey("bulk_messages.id", ondelete="CASCADE"), nullable=False)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id", ondelete="CASCADE"), nullable=False)
    
    # Delivery status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SCHEDULED)
    sent_at = Column(DateTime)
    failed_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Personalized content (after variable substitution)
    personalized_content = Column(Text)
    
    # Tracking
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    platform_message_id = Column(String(255))  # ID from OnlyFans/platform
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bulk_message = relationship("BulkMessage", back_populates="recipients")
    fan = relationship("Fan")
    
    __table_args__ = (
        Index('idx_bulk_recipients_message', 'bulk_message_id'),
        Index('idx_bulk_recipients_fan', 'fan_id'),
        Index('idx_bulk_recipients_status', 'status'),
        UniqueConstraint('bulk_message_id', 'fan_id', name='uq_bulk_message_fan'),
    )


class CannedResponse(Base):
    """Pre-written responses for quick replies."""
    __tablename__ = "canned_responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))  # NULL = agency-wide
    
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    shortcut = Column(String(50))  # e.g., "/thanks" triggers this response
    
    category = Column(String(100))
    tags = Column(JSON, default=list)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # Settings
    is_active = Column(Boolean, default=True)
    auto_personalize = Column(Boolean, default=True)  # Replace {{variables}}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_canned_responses_agency', 'agency_id'),
        Index('idx_canned_responses_user', 'user_id'),
        Index('idx_canned_responses_shortcut', 'shortcut'),
        UniqueConstraint('agency_id', 'shortcut', name='uq_agency_shortcut'),
    )


class MessageSchedule(Base):
    """Scheduled messages for future delivery."""
    __tablename__ = "message_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    # Message content
    content = Column(Text, nullable=False)
    media_urls = Column(JSON, default=list)  # Attached media
    
    # Scheduling
    scheduled_for = Column(DateTime, nullable=False)
    time_zone = Column(String(50), default="UTC")
    
    # Status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SCHEDULED)
    sent_at = Column(DateTime)
    error_message = Column(Text)
    
    # Platform details
    platform = Column(String(50), default="onlyfans")
    platform_message_id = Column(String(255))
    
    # Settings
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(JSON)  # e.g., {"type": "daily", "interval": 1}
    recurrence_end_date = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    model = relationship("ModelProfile")
    fan = relationship("Fan")
    created_by = relationship("User")
    
    __table_args__ = (
        Index('idx_message_schedules_agency', 'agency_id'),
        Index('idx_message_schedules_model', 'model_id'),
        Index('idx_message_schedules_scheduled', 'scheduled_for'),
        Index('idx_message_schedules_status', 'status'),
    )