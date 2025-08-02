"""
Notification Models
"""
from sqlalchemy import Column, String, Boolean, JSON, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from core.database import Base


class PushSubscription(Base):
    """Push notification subscription"""
    __tablename__ = "push_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Device info
    token = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False)  # ios, android, web
    device_info = Column(JSON, default={})
    
    # Status
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="push_subscriptions")


class NotificationPreferences(Base):
    """User notification preferences"""
    __tablename__ = "notification_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # Channel preferences
    push_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)
    in_app_enabled = Column(Boolean, default=True)
    
    # Type preferences
    notification_types = Column(JSON, default={
        "messages": True,
        "tips": True,
        "subscriptions": True,
        "content": True,
        "promotions": True,
        "system": True
    })
    
    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String)  # HH:MM format
    quiet_hours_end = Column(String)    # HH:MM format
    timezone = Column(String, default="UTC")
    
    # Frequency limits
    max_daily_notifications = Column(Integer, default=50)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")


class NotificationLog(Base):
    """Log of sent notifications"""
    __tablename__ = "notification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Notification details
    type = Column(String, nullable=False)  # message, tip, subscription, etc
    channel = Column(String, nullable=False)  # push, email, sms, in_app
    title = Column(String)
    body = Column(Text)
    data = Column(JSON, default={})
    
    # Status
    status = Column(String, default="pending")  # pending, sent, failed, delivered, read
    error_message = Column(Text)
    
    # Tracking
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    
    # Metadata
    message_id = Column(String)  # External message ID (FCM, etc)
    extra_metadata = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")