"""
API Key management models.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from core.database import Base


class APIKeyStatus(str, enum.Enum):
    """API key status."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class APIKeyScope(str, enum.Enum):
    """API key permission scopes."""
    READ_ANALYTICS = "read:analytics"
    WRITE_ANALYTICS = "write:analytics"
    READ_FINANCIAL = "read:financial"
    WRITE_FINANCIAL = "write:financial"
    READ_MODELS = "read:models"
    WRITE_MODELS = "write:models"
    READ_FANS = "read:fans"
    WRITE_FANS = "write:fans"
    ADMIN = "admin"


class APIKey(Base):
    """API key for external integrations."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Owner information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Key information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    key_prefix = Column(String(50), nullable=False)  # First few chars for identification
    key_hash = Column(String(255), nullable=False, unique=True)  # Hashed version for lookup
    
    # Encrypted key data
    encrypted_data = Column(Text, nullable=False)  # Encrypted full key data
    encryption_version = Column(String(10), default="1.0")
    
    # Permissions
    scopes = Column(JSON, default=list)  # List of APIKeyScope values
    ip_whitelist = Column(JSON, default=list)  # List of allowed IPs
    
    # Status and lifecycle
    status = Column(String(20), default=APIKeyStatus.ACTIVE.value)
    expires_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))
    last_rotated_at = Column(DateTime(timezone=True))
    rotation_count = Column(Integer, default=0)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_ip = Column(String(45))  # IPv6 compatible
    last_user_agent = Column(Text)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    agency = relationship("Agency")
    audit_logs = relationship("APIKeyAuditLog", back_populates="api_key", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_api_key_user', 'user_id'),
        Index('idx_api_key_agency', 'agency_id'),
        Index('idx_api_key_status', 'status'),
        Index('idx_api_key_expires', 'expires_at'),
    )


class APIKeyAuditLog(Base):
    """Audit log for API key actions."""
    __tablename__ = "api_key_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    
    # Action details
    action = Column(String(50), nullable=False)  # created, rotated, revoked, used, etc.
    performed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    # Request details
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_path = Column(String(500))
    request_method = Column(String(10))
    response_status = Column(Integer)
    
    # Additional data
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    api_key = relationship("APIKey", back_populates="audit_logs")
    performed_by = relationship("User")
    
    __table_args__ = (
        Index('idx_api_key_audit_key', 'api_key_id'),
        Index('idx_api_key_audit_action', 'action'),
        Index('idx_api_key_audit_created', 'created_at'),
    )


class APIKeyRotationHistory(Base):
    """History of API key rotations."""
    __tablename__ = "api_key_rotation_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    
    # Rotation details
    old_key_prefix = Column(String(50), nullable=False)
    new_key_prefix = Column(String(50), nullable=False)
    rotated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    rotation_reason = Column(String(500))
    
    # Backup of old encrypted data (for recovery)
    old_encrypted_data = Column(Text)
    
    # Timing
    rotated_at = Column(DateTime(timezone=True), server_default=func.now())
    old_key_expires_at = Column(DateTime(timezone=True))  # Grace period for old key
    
    # Relationships
    api_key = relationship("APIKey")
    rotated_by = relationship("User")
    
    __table_args__ = (
        Index('idx_api_key_rotation_key', 'api_key_id'),
        Index('idx_api_key_rotation_date', 'rotated_at'),
    )