"""
Mobile Session Model

Tracks active sessions for mobile devices
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from core.database import Base


class MobileSession(Base):
    """Mobile session tracking"""
    __tablename__ = "mobile_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mobile_devices.id", ondelete="CASCADE"), nullable=False)
    
    # Session tokens
    refresh_token = Column(Text, unique=True)
    
    # Session info
    ip_address = Column(String(45))
    location_country = Column(String(2))
    location_city = Column(String(100))
    
    # Session lifecycle
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    
    # Status
    is_active = Column(Boolean, default=True)
    ended_reason = Column(String(50))  # logout, expired, revoked, device_change
    
    # Relationships
    user = relationship("User")
    device = relationship("MobileDevice", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index("idx_mobile_session_user", "user_id", "is_active"),
        Index("idx_mobile_session_device", "device_id", "is_active"),
        Index("idx_mobile_session_token", "refresh_token"),
        Index("idx_mobile_session_active", "is_active", "expires_at"),
    )