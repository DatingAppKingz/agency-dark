"""API Key model for external service integrations."""

from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, Enum as SQLEnum, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid
from core.database import Base
from models.base import BaseModel


class APIKeyProvider(str, enum.Enum):
    """Supported API providers."""
    ONLYFANS = "onlyfans"
    STRIPE = "stripe"
    INFLOW = "inflow"
    CUSTOM = "custom"


class APIKeyStatus(str, enum.Enum):
    """API key status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class APIKey(BaseModel):
    """Encrypted API key storage."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "api_keys"
    
    # Relationships
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Key information
    provider = Column(SQLEnum(APIKeyProvider), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # Display name
    key_prefix = Column(String(16), nullable=False)  # First few chars for identification
    encrypted_value = Column(Text, nullable=False)  # AES-256 encrypted
    
    # Status and validation
    status = Column(SQLEnum(APIKeyStatus), default=APIKeyStatus.ACTIVE, nullable=False)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security
    last_rotated_at = Column(DateTime(timezone=True), nullable=True)
    allowed_ips = Column(JSON, nullable=True)  # IP whitelist
    permissions = Column(JSON, default=dict, nullable=False)  # Scope/permissions
    
    # Key metadata
    key_metadata = Column("metadata", JSON, default=dict, nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Sync configuration
    sync_enabled = Column(Boolean, default=False, nullable=False)
    sync_interval_minutes = Column(Integer, default=30, nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_error = Column(Text, nullable=True)
    sync_failure_count = Column(Integer, default=0, nullable=False)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    agency = relationship("Agency", back_populates="api_keys")
    user = relationship("User", foreign_keys=[user_id], back_populates="api_keys")
    sync_conflicts = relationship("SyncConflictLog", back_populates="api_key")
    sync_errors = relationship("SyncErrorLog", back_populates="api_key")
    
    def __repr__(self):
        return f"<APIKey {self.provider.value}:{self.key_prefix}***>"
    
    @property
    def is_expired(self):
        """Check if key is expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @property
    def display_value(self):
        """Get masked display value."""
        return f"{self.key_prefix}{'*' * 24}"