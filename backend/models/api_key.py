"""
Enhanced API Key Model with Encryption Support
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class APIKey(Base):
    """API Key model with enhanced security features"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Key identification
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(8), nullable=False, index=True)  # First 8 chars for lookup
    key_hash = Column(String(128), nullable=False)  # SHA256 hash of the actual key
    
    # Encrypted data (contains full key info)
    encrypted_data = Column(Text, nullable=False)
    
    # Permissions
    scopes = Column(JSON, nullable=False, default=list)
    
    # Key properties
    environment = Column(String(20), default="live")  # live, test
    expires_at = Column(DateTime, nullable=True, index=True)
    
    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(100), nullable=True)
    
    # Rotation tracking
    rotated_at = Column(DateTime, nullable=True)
    rotation_count = Column(Integer, default=0)
    
    # Metadata
    key_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    audit_logs = relationship("APIKeyAudit", back_populates="api_key", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_api_key_lookup', 'key_prefix', 'is_active'),
        Index('idx_api_key_user_active', 'user_id', 'is_active'),
        Index('idx_api_key_expiry', 'expires_at', 'is_active'),
    )