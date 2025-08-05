"""Email queue models for reliable email delivery."""

from sqlalchemy import Column, String, Integer, JSON, Boolean, Text, Index
from sqlalchemy.orm import relationship
from core.database import Base
from models.base import BaseModel
import enum


class EmailStatus(str, enum.Enum):
    """Email queue status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailPriority(str, enum.Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EmailQueue(BaseModel):
    """Email queue for reliable delivery."""
    __tablename__ = "email_queue"
    
    # Recipient information
    to_emails = Column(JSON, nullable=False)  # List of email addresses
    cc_emails = Column(JSON, nullable=True)
    bcc_emails = Column(JSON, nullable=True)
    
    # Email content
    subject = Column(String(500), nullable=False)
    html_content = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)
    
    # Template information
    template_id = Column(String(100), nullable=True)
    template_data = Column(JSON, nullable=True)
    
    # Metadata
    from_email = Column(String(255), nullable=True)
    from_name = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)
    
    # Queue management
    status = Column(String(20), default=EmailStatus.PENDING, nullable=False, index=True)
    priority = Column(String(20), default=EmailPriority.NORMAL, nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    
    # Scheduling
    scheduled_at = Column(String(30), nullable=True, index=True)
    sent_at = Column(String(30), nullable=True)
    next_retry_at = Column(String(30), nullable=True, index=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    
    # Provider information
    provider = Column(String(50), nullable=True)  # sendgrid, smtp, etc.
    provider_message_id = Column(String(255), nullable=True)
    provider_response = Column(JSON, nullable=True)
    
    # Tracking
    user_id = Column(Integer, nullable=True, index=True)
    related_object_type = Column(String(50), nullable=True, index=True)  # payout, invoice, etc.
    related_object_id = Column(Integer, nullable=True, index=True)
    
    # Settings
    track_opens = Column(Boolean, default=False, nullable=False)
    track_clicks = Column(Boolean, default=False, nullable=False)
    
    # Additional data
    attachments = Column(JSON, nullable=True)  # List of attachment info
    headers = Column(JSON, nullable=True)  # Custom headers
    email_metadata = Column(JSON, nullable=True)  # Additional metadata
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_email_queue_status_priority', 'status', 'priority'),
        Index('idx_email_queue_scheduled', 'status', 'scheduled_at'),
        Index('idx_email_queue_retry', 'status', 'next_retry_at'),
        Index('idx_email_queue_user', 'user_id', 'status'),
        Index('idx_email_queue_related', 'related_object_type', 'related_object_id'),
    )
    
    def __repr__(self):
        return f"<EmailQueue {self.id} - {self.subject} - {self.status}>"


class EmailLog(BaseModel):
    """Log of all email activities."""
    __tablename__ = "email_logs"
    
    # Reference to queue
    email_queue_id = Column(Integer, nullable=True, index=True)
    
    # Email details
    to_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    
    # Event information
    event_type = Column(String(50), nullable=False, index=True)  # sent, opened, clicked, bounced, etc.
    event_data = Column(JSON, nullable=True)
    event_timestamp = Column(String(30), nullable=False, index=True)
    
    # Provider data
    provider = Column(String(50), nullable=True)
    provider_event_id = Column(String(255), nullable=True)
    
    # User tracking
    user_id = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_email_log_email_event', 'to_email', 'event_type'),
        Index('idx_email_log_timestamp', 'event_timestamp'),
    )