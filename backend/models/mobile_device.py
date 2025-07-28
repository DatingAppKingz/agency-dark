"""
Mobile Device Model

Tracks registered mobile devices for users
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from core.database import Base


class MobileDevice(Base):
    """Mobile device registration"""
    __tablename__ = "mobile_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Device identification
    device_id = Column(String(255), nullable=False)  # Unique device identifier
    device_name = Column(String(255))
    platform = Column(String(50), nullable=False)  # ios, android
    platform_version = Column(String(50))
    app_version = Column(String(50))
    
    # Push notifications
    push_token = Column(String(500))
    push_enabled = Column(Boolean, default=True)
    
    # Biometric authentication
    biometric_enabled = Column(Boolean, default=False)
    biometric_type = Column(String(50))  # face_id, touch_id, fingerprint
    
    # Status
    is_active = Column(Boolean, default=True)
    is_trusted = Column(Boolean, default=False)  # Trusted after verification period
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="mobile_devices")
    sessions = relationship("MobileSession", back_populates="device", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_mobile_device_user", "user_id"),
        Index("idx_mobile_device_unique", "user_id", "device_id", unique=True),
        Index("idx_mobile_device_active", "is_active", "user_id"),
    )