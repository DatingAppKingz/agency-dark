from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from models.base import Base, BaseModel


class WebhookEvent(str, enum.Enum):
    """Webhook event types."""
    # Model events
    MODEL_CREATED = "model.created"
    MODEL_UPDATED = "model.updated"
    MODEL_DELETED = "model.deleted"
    MODEL_VERIFIED = "model.verified"
    
    # Transaction events
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_FAILED = "transaction.failed"
    
    # Message events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    
    # Content events
    CONTENT_PUBLISHED = "content.published"
    CONTENT_PURCHASED = "content.purchased"
    
    # Payout events
    PAYOUT_SCHEDULED = "payout.scheduled"
    PAYOUT_COMPLETED = "payout.completed"
    PAYOUT_FAILED = "payout.failed"


class WebhookStatus(str, enum.Enum):
    """Webhook status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class Webhook(BaseModel):
    """Webhook configuration."""
    __tablename__ = "webhooks"
    
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Webhook details
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)  # For signing payloads
    
    # Configuration
    events = Column(JSON, default=list, nullable=False)  # List of WebhookEvent values
    headers = Column(JSON, default=dict, nullable=False)  # Custom headers
    
    # Status
    status = Column(SQLEnum(WebhookStatus), default=WebhookStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Rate limiting
    max_retries = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    
    # Statistics
    total_calls = Column(Integer, default=0, nullable=False)
    successful_calls = Column(Integer, default=0, nullable=False)
    failed_calls = Column(Integer, default=0, nullable=False)
    last_called_at = Column(String(30), nullable=True)
    last_error = Column(String(500), nullable=True)
    
    # Relationships
    agency = relationship("Agency", back_populates="webhooks")
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Webhook {self.name} - {self.url}>"
    
    def is_subscribed_to(self, event):
        """Check if webhook is subscribed to an event."""
        return event in self.events or "*" in self.events


class WebhookDelivery(BaseModel):
    """Webhook delivery log."""
    __tablename__ = "webhook_deliveries"
    
    webhook_id = Column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    
    # Delivery details
    event = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    
    # Response
    status_code = Column(Integer, nullable=True)
    response_body = Column(String(2000), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Status
    is_successful = Column(Boolean, default=False, nullable=False)
    attempt_count = Column(Integer, default=1, nullable=False)
    
    # Error handling
    error_message = Column(String(500), nullable=True)
    next_retry_at = Column(String(30), nullable=True)
    
    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")
    
    def __repr__(self):
        return f"<WebhookDelivery {self.event} - {'Success' if self.is_successful else 'Failed'}>"


class APIKey(BaseModel):
    """API key for authentication."""
    __tablename__ = "api_keys"
    
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Key details
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)  # Hashed API key
    key_prefix = Column(String(20), nullable=False)  # First 8 chars for identification
    
    # Permissions
    scopes = Column(JSON, default=list, nullable=False)  # List of permission scopes
    ip_whitelist = Column(JSON, default=list, nullable=False)  # Allowed IPs
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(String(30), nullable=True)
    
    # Usage tracking
    last_used_at = Column(String(30), nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Rate limiting
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    rate_limit_per_day = Column(Integer, default=10000, nullable=False)
    
    # Metadata
    description = Column(String(500), nullable=True)
    key_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="api_keys")
    user = relationship("User", back_populates="api_keys")
    
    def __repr__(self):
        return f"<APIKey {self.name} - {self.key_prefix}...>"
    
    def has_scope(self, scope):
        """Check if API key has a specific scope."""
        return scope in self.scopes or "*" in self.scopes
    
    @property
    def is_expired(self):
        """Check if API key is expired."""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.fromisoformat(self.expires_at) < datetime.utcnow()