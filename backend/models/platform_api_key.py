"""
Platform API Key model for secure programmatic access to the platform.
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Index, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from models.base import Base


class PlatformAPIKeyScope(str, enum.Enum):
    """Platform API key permission scopes."""
    # Read scopes
    READ_CONVERSATIONS = "read:conversations"
    READ_MODELS = "read:models"
    READ_ANALYTICS = "read:analytics"
    READ_USERS = "read:users"
    READ_FINANCIAL = "read:financial"
    
    # Write scopes
    WRITE_CONVERSATIONS = "write:conversations"
    WRITE_MODELS = "write:models"
    WRITE_USERS = "write:users"
    WRITE_FINANCIAL = "write:financial"
    
    # Admin scopes
    ADMIN_USERS = "admin:users"
    ADMIN_AGENCY = "admin:agency"
    ADMIN_SYSTEM = "admin:system"
    
    # Special scopes
    WEBHOOKS = "webhooks"
    ANALYTICS_EXPORT = "analytics:export"
    BULK_OPERATIONS = "bulk:operations"
    WEBSOCKET_ACCESS = "websocket:access"


class PlatformAPIKey(Base):
    """Platform API Key for programmatic access."""
    __tablename__ = "platform_api_keys"
    __table_args__ = (
        Index('idx_platform_api_keys_prefix', 'key_prefix'),
        Index('idx_platform_api_keys_user_agency', 'user_id', 'agency_id'),
        Index('idx_platform_api_keys_expires', 'expires_at'),
        {"extend_existing": True}
    )
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User and agency relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=True)
    
    # Key information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    key_prefix = Column(String(8), nullable=False, index=True)  # First 8 chars for identification
    key_hash = Column(String(255), nullable=False, unique=True)  # Hashed key
    
    # Permissions
    scopes = Column(JSON, nullable=False, default=list)  # List of PlatformAPIKeyScope values
    role_restrictions = Column(JSON, nullable=True)  # Restrict to specific user roles
    
    # Security restrictions
    allowed_ips = Column(JSON, nullable=True)  # List of allowed IP addresses/ranges
    allowed_origins = Column(JSON, nullable=True)  # List of allowed origins for CORS
    allowed_user_agents = Column(JSON, nullable=True)  # Restrict to specific user agents
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    
    # Status and expiration
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    monthly_usage = Column(JSON, default=dict)  # {"2024-01": 1000, "2024-02": 2000}
    error_count = Column(Integer, default=0, nullable=False)
    
    # Advanced features
    key_metadata = Column(JSON, default=dict)  # Custom metadata
    webhook_url = Column(String(500), nullable=True)  # For webhook-enabled keys
    webhook_secret = Column(String(255), nullable=True)  # For webhook signature
    allowed_models = Column(JSON, nullable=True)  # Restrict to specific model IDs
    allowed_conversations = Column(JSON, nullable=True)  # Restrict to specific conversations
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoke_reason = Column(Text, nullable=True)
    
    # Rotation tracking
    rotated_from_id = Column(UUID(as_uuid=True), ForeignKey("platform_api_keys.id"), nullable=True)
    rotation_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    agency = relationship("Agency")
    created_by = relationship("User", foreign_keys=[created_by_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_id])
    rotated_from = relationship("PlatformAPIKey", remote_side=[id])
    usage_logs = relationship("PlatformAPIKeyUsageLog", back_populates="api_key", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PlatformAPIKey {self.name} ({self.key_prefix}...)>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid for use."""
        return self.is_active and not self.is_expired and not self.revoked_at
    
    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope."""
        return scope in self.scopes
    
    def has_any_scope(self, scopes: list) -> bool:
        """Check if the API key has any of the specified scopes."""
        return any(self.has_scope(scope) for scope in scopes)
    
    def has_all_scopes(self, scopes: list) -> bool:
        """Check if the API key has all of the specified scopes."""
        return all(self.has_scope(scope) for scope in scopes)
    
    def increment_usage(self):
        """Increment usage count and update monthly usage."""
        self.usage_count += 1
        
        # Update monthly usage
        current_month = datetime.utcnow().strftime("%Y-%m")
        if self.monthly_usage is None:
            self.monthly_usage = {}
        
        if current_month not in self.monthly_usage:
            self.monthly_usage[current_month] = 0
        
        self.monthly_usage[current_month] += 1
    
    def increment_errors(self):
        """Increment error count."""
        self.error_count += 1
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """Check if an IP address is allowed to use this key."""
        if not self.allowed_ips:
            return True  # No restriction
        
        # Check exact match and CIDR ranges
        import ipaddress
        try:
            ip = ipaddress.ip_address(ip_address)
            for allowed in self.allowed_ips:
                try:
                    # Check if it's a network range
                    if '/' in allowed:
                        network = ipaddress.ip_network(allowed)
                        if ip in network:
                            return True
                    # Check exact match
                    elif ip_address == allowed:
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        
        return False
    
    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed for CORS."""
        if not self.allowed_origins:
            return True  # No restriction
        
        # Support wildcards
        for allowed in self.allowed_origins:
            if allowed == "*":
                return True
            if allowed.startswith("*.") and origin.endswith(allowed[1:]):
                return True
            if origin == allowed:
                return True
        
        return False
    
    def is_user_agent_allowed(self, user_agent: str) -> bool:
        """Check if a user agent is allowed."""
        if not self.allowed_user_agents:
            return True  # No restriction
        
        # Check if user agent contains any allowed pattern
        for allowed in self.allowed_user_agents:
            if allowed in user_agent:
                return True
        
        return False
    
    def can_access_model(self, model_id: str) -> bool:
        """Check if the key can access a specific model."""
        if not self.allowed_models:
            return True  # No restriction
        
        return str(model_id) in [str(m) for m in self.allowed_models]
    
    def can_access_conversation(self, conversation_id: str) -> bool:
        """Check if the key can access a specific conversation."""
        if not self.allowed_conversations:
            return True  # No restriction
        
        return str(conversation_id) in [str(c) for c in self.allowed_conversations]


class PlatformAPIKeyUsageLog(Base):
    """Log of platform API key usage for analytics and rate limiting."""
    __tablename__ = "platform_api_key_usage_logs"
    __table_args__ = (
        Index('idx_platform_key_usage_key_time', 'api_key_id', 'timestamp'),
        Index('idx_platform_key_usage_time', 'timestamp'),
        {"extend_existing": True}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("platform_api_keys.id", ondelete="CASCADE"), nullable=False)
    
    # Request information
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Client information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    origin = Column(String(255), nullable=True)
    
    # Usage details
    request_size = Column(Integer, nullable=True)  # In bytes
    response_size = Column(Integer, nullable=True)  # In bytes
    scope_used = Column(String(100), nullable=True)  # Which scope was used
    resource_accessed = Column(String(255), nullable=True)  # Resource ID accessed
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    
    # Rate limiting
    rate_limit_remaining = Column(Integer, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    api_key = relationship("PlatformAPIKey", back_populates="usage_logs")
    
    def __repr__(self):
        return f"<PlatformAPIKeyUsageLog {self.api_key_id} - {self.endpoint}>"