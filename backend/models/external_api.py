"""External API credential models."""

import enum
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, ForeignKey,
    Enum as SQLEnum, Text, Index, UniqueConstraint, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class APIProvider(str, enum.Enum):
    """External API providers."""
    ONLYFANS = "onlyfans"
    STRIPE = "stripe"
    INFLOW = "inflow"


class ExternalAPICredential(Base):
    """External API credentials for users."""
    __tablename__ = "external_api_credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    provider = Column(SQLEnum(APIProvider), nullable=False)
    
    # Encrypted credentials
    credentials = Column(JSON, nullable=False)  # Should be encrypted in production
    
    # Validation status
    is_active = Column(Boolean, default=True, nullable=False)
    is_valid = Column(Boolean, default=None)  # None = not validated, True/False = validation result
    last_validated = Column(DateTime)
    validation_error = Column(Text)
    
    # Metadata from provider
    extra_metadata = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="external_credentials")
    agency = relationship("Agency", back_populates="external_credentials")
    
    # Indexes
    __table_args__ = (
        Index("idx_external_api_user_provider", "user_id", "provider"),
        Index("idx_external_api_agency_provider", "agency_id", "provider"),
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )
    
    def __repr__(self):
        return f"<ExternalAPICredential(provider={self.provider}, user_id={self.user_id})>"
    
    @property
    def masked_credentials(self) -> Dict[str, Any]:
        """Return credentials with sensitive values masked."""
        if not self.credentials:
            return {}
        
        masked = {}
        for key, value in self.credentials.items():
            if isinstance(value, str) and len(value) > 8:
                if key in ['api_key', 'secret_key', 'password', 'token', 'webhook_secret']:
                    masked[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    masked[key] = value
            else:
                masked[key] = value
        
        return masked


class WebhookEndpoint(Base):
    """Webhook endpoints for external APIs."""
    __tablename__ = "webhook_endpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    provider = Column(SQLEnum(APIProvider), nullable=False)
    
    # Webhook configuration
    endpoint_url = Column(String(500), nullable=False)
    secret = Column(String(500))  # Should be encrypted
    events = Column(JSON)  # List of event types to listen for
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_received = Column(DateTime)
    failure_count = Column(Integer, default=0)
    
    # Metadata
    extra_metadata = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="webhook_endpoints")
    
    # Indexes
    __table_args__ = (
        Index("idx_webhook_agency_provider", "agency_id", "provider"),
        UniqueConstraint("agency_id", "provider", "endpoint_url", name="uq_agency_provider_url"),
    )
    
    def __repr__(self):
        return f"<WebhookEndpoint(provider={self.provider}, agency_id={self.agency_id})>"


class APICallLog(Base):
    """Log of external API calls for debugging and analytics."""
    __tablename__ = "api_call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id = Column(UUID(as_uuid=True), ForeignKey("external_api_credentials.id", ondelete="SET NULL"))
    provider = Column(SQLEnum(APIProvider), nullable=False)
    
    # Request details
    method = Column(String(10), nullable=False)
    endpoint = Column(String(500), nullable=False)
    request_headers = Column(JSON)
    request_body = Column(JSON)
    
    # Response details
    status_code = Column(Integer)
    response_headers = Column(JSON)
    response_body = Column(JSON)
    response_time_ms = Column(Integer)
    
    # Error tracking
    is_error = Column(Boolean, default=False)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    credential = relationship("ExternalAPICredential")
    
    # Indexes
    __table_args__ = (
        Index("idx_api_log_provider_created", "provider", "created_at"),
        Index("idx_api_log_credential", "credential_id"),
        Index("idx_api_log_error", "is_error", "created_at"),
    )
    
    def __repr__(self):
        return f"<APICallLog(provider={self.provider}, method={self.method}, endpoint={self.endpoint})>"