"""
Rate limiting models for tracking and configuration.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Index, Enum, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from core.database import Base


class RateLimitTier(str, enum.Enum):
    """Rate limit tiers."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class RateLimitType(str, enum.Enum):
    """Types of rate limits."""
    API_CALLS = "api_calls"
    DATA_EXPORT = "data_export"
    FILE_UPLOAD = "file_upload"
    WEBHOOK_CALLS = "webhook_calls"
    WEBSOCKET_MESSAGES = "websocket_messages"


class RateLimitConfig(Base):
    """Rate limit configuration for different tiers and endpoints."""
    __tablename__ = "rate_limit_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Configuration scope
    tier = Column(Enum(RateLimitTier), nullable=False)
    endpoint_pattern = Column(String(255), nullable=False)  # e.g., "/api/v1/analytics/*"
    limit_type = Column(Enum(RateLimitType), nullable=False)
    
    # Rate limit settings
    requests_per_minute = Column(Integer, nullable=True)
    requests_per_hour = Column(Integer, nullable=True)
    requests_per_day = Column(Integer, nullable=True)
    
    # Burst settings
    burst_size = Column(Integer, default=10)  # Allow burst up to this many requests
    burst_window_seconds = Column(Integer, default=10)  # Within this time window
    
    # Additional constraints
    max_concurrent_requests = Column(Integer, nullable=True)
    max_request_size_mb = Column(Integer, nullable=True)
    
    # Flags
    is_active = Column(Boolean, default=True)
    bypass_for_internal = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_rate_limit_config_tier', 'tier'),
        Index('idx_rate_limit_config_endpoint', 'endpoint_pattern'),
        Index('idx_rate_limit_config_active', 'is_active'),
    )


class UserRateLimit(Base):
    """Custom rate limits for specific users."""
    __tablename__ = "user_rate_limits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Override settings
    tier_override = Column(Enum(RateLimitTier), nullable=True)
    custom_limits = Column(JSON, default=dict)  # Endpoint-specific limits
    
    # Multipliers (e.g., 2.0 = double the limit)
    limit_multiplier = Column(Float, default=1.0)
    
    # Validity
    valid_from = Column(DateTime(timezone=True), default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Reason for custom limit
    reason = Column(String(500))
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_user_rate_limit_user', 'user_id'),
        Index('idx_user_rate_limit_validity', 'valid_from', 'valid_until'),
    )


class IPRateLimit(Base):
    """Rate limits based on IP addresses."""
    __tablename__ = "ip_rate_limits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # IP configuration
    ip_address = Column(String(45), nullable=False)  # Supports IPv6
    ip_range = Column(String(50), nullable=True)  # CIDR notation
    
    # Action
    action = Column(String(20), nullable=False)  # 'allow', 'block', 'throttle'
    
    # Custom limits (if action is 'throttle')
    requests_per_minute = Column(Integer, nullable=True)
    
    # Metadata
    reason = Column(String(500))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_ip_rate_limit_address', 'ip_address'),
        Index('idx_ip_rate_limit_action', 'action'),
        Index('idx_ip_rate_limit_expires', 'expires_at'),
    )


class RateLimitViolation(Base):
    """Log of rate limit violations for analysis."""
    __tablename__ = "rate_limit_violations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Violator information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    ip_address = Column(String(45), nullable=False)
    
    # Violation details
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    limit_type = Column(String(50), nullable=False)
    limit_value = Column(Integer, nullable=False)
    actual_value = Column(Integer, nullable=False)
    
    # Response
    response_code = Column(Integer, default=429)
    blocked_until = Column(DateTime(timezone=True))
    
    # Additional context
    user_agent = Column(String(500))
    request_headers = Column(JSON)
    
    # Timestamp
    violated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_rate_limit_violation_user', 'user_id'),
        Index('idx_rate_limit_violation_ip', 'ip_address'),
        Index('idx_rate_limit_violation_time', 'violated_at'),
        Index('idx_rate_limit_violation_endpoint', 'endpoint'),
    )


class RateLimitWhitelist(Base):
    """Whitelist entries that bypass rate limiting."""
    __tablename__ = "rate_limit_whitelist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Whitelist target
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    ip_range = Column(String(50), nullable=True)
    
    # Scope
    endpoint_pattern = Column(String(255), nullable=True)  # Specific endpoints or * for all
    
    # Validity
    valid_from = Column(DateTime(timezone=True), default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    reason = Column(String(500), nullable=False)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_rate_limit_whitelist_user', 'user_id'),
        Index('idx_rate_limit_whitelist_api_key', 'api_key_id'),
        Index('idx_rate_limit_whitelist_ip', 'ip_address'),
        Index('idx_rate_limit_whitelist_validity', 'valid_from', 'valid_until'),
    )