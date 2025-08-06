"""
API Key model for authentication
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from core.database import Base
from models.base import BaseModel


class APIKeyProvider(str, enum.Enum):
    """API Key Provider types."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    PARTNER = "partner"


class APIKeyStatus(str, enum.Enum):
    """API Key status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class APIKey(BaseModel):
    """API Key for authentication."""
    __tablename__ = "api_keys"
    __table_args__ = {"extend_existing": True}
    
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    
    # Who owns this API key
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"))
    
    # Permissions and settings
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(SQLEnum(APIKeyStatus), default=APIKeyStatus.ACTIVE, nullable=False)
    provider = Column(SQLEnum(APIKeyProvider), default=APIKeyProvider.INTERNAL, nullable=False)
    permissions = Column(String(1000))  # Comma-separated list of permissions
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    
    # Tracking
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    agency = relationship("Agency", back_populates="api_keys")