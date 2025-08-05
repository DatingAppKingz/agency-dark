"""
Advanced rate limiting models for dynamic throttling.
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Index, Integer, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from models.base import Base


class RateLimitType(str, enum.Enum):
    """Types of rate limits."""
    USER = "user"
    API_KEY = "api_key"
    IP = "ip"
    ENDPOINT = "endpoint"
    GLOBAL = "global"
    GEOGRAPHIC = "geographic"
    TIER = "tier"
    CUSTOM = "custom"


class RateLimitAlgorithm(str, enum.Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"


class RateLimitTier(str, enum.Enum):
    """Service tiers for rate limiting."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


class RateLimitConfig(Base):
    """Dynamic rate limit configurations."""
    __tablename__ = "rate_limit_configs"
    __table_args__ = (
        Index('idx_rate_limit_configs_type_identifier', 'limit_type', 'identifier'),
        Index('idx_rate_limit_configs_active', 'is_active'),
        {"extend_existing": True}
    )
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Configuration identity
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    limit_type = Column(SQLEnum(RateLimitType), nullable=False, index=True)
    identifier = Column(String(255), nullable=True)  # user_id, api_key_id, IP, etc.
    
    # Rate limit settings
    requests_per_minute = Column(Integer, nullable=True)
    requests_per_hour = Column(Integer, nullable=True)
    requests_per_day = Column(Integer, nullable=True)
    burst_size = Column(Integer, nullable=True)  # Max burst for token bucket
    
    # Cost-based limiting
    cost_per_minute = Column(Float, nullable=True)  # Total cost units per minute
    cost_per_hour = Column(Float, nullable=True)
    cost_per_day = Column(Float, nullable=True)
    
    # Advanced settings
    algorithm = Column(SQLEnum(RateLimitAlgorithm), default=RateLimitAlgorithm.TOKEN_BUCKET)
    refill_rate = Column(Float, nullable=True)  # Tokens per second for token bucket
    window_size_seconds = Column(Integer, nullable=True)  # For sliding window
    
    # Geographic restrictions
    allowed_countries = Column(JSONB, nullable=True)  # List of country codes
    blocked_countries = Column(JSONB, nullable=True)
    geographic_multiplier = Column(JSONB, nullable=True)  # {"US": 1.0, "CN": 0.5}
    
    # Time-based variations
    time_based_limits = Column(JSONB, nullable=True)  # {"peak_hours": 0.5, "off_hours": 2.0}
    
    # Tier settings
    tier = Column(SQLEnum(RateLimitTier), nullable=True)
    tier_multiplier = Column(Float, default=1.0)  # Multiplier for tier benefits
    
    # Endpoint-specific settings
    endpoint_costs = Column(JSONB, nullable=True)  # {"/api/v1/expensive": 10, "/api/v1/cheap": 1}
    endpoint_limits = Column(JSONB, nullable=True)  # Specific limits per endpoint
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0)  # Higher priority configs override lower
    
    # Override settings
    override_global = Column(Boolean, default=False)  # Override global limits
    stackable = Column(Boolean, default=True)  # Can stack with other limits
    
    # Negotiated limits (for enterprise)
    is_negotiated = Column(Boolean, default=False)
    negotiated_by = Column(String(255), nullable=True)
    negotiation_notes = Column(String(1000), nullable=True)
    
    # Metadata
    metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    
    created_by = relationship("User")
    agency = relationship("Agency")
    
    def __repr__(self):
        return f"<RateLimitConfig {self.name} ({self.limit_type.value})>"
    
    def get_effective_limit(self, endpoint: str = None, cost_based: bool = False) -> dict:
        """Get effective limits considering all factors."""
        base_limits = {
            "per_minute": self.requests_per_minute,
            "per_hour": self.requests_per_hour,
            "per_day": self.requests_per_day
        }
        
        if cost_based:
            base_limits = {
                "per_minute": self.cost_per_minute,
                "per_hour": self.cost_per_hour,
                "per_day": self.cost_per_day
            }
        
        # Apply endpoint-specific limits
        if endpoint and self.endpoint_limits and endpoint in self.endpoint_limits:
            endpoint_config = self.endpoint_limits[endpoint]
            for key in base_limits:
                if key in endpoint_config:
                    base_limits[key] = endpoint_config[key]
        
        # Apply tier multiplier
        if self.tier_multiplier != 1.0:
            for key in base_limits:
                if base_limits[key]:
                    base_limits[key] = int(base_limits[key] * self.tier_multiplier)
        
        return base_limits


class RateLimitBucket(Base):
    """Token bucket state for rate limiting."""
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        Index('idx_rate_limit_buckets_identifier', 'bucket_key'),
        Index('idx_rate_limit_buckets_updated', 'last_updated'),
        {"extend_existing": True}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Bucket identity
    bucket_key = Column(String(500), nullable=False, unique=True)  # e.g., "user:123:endpoint:/api/v1/users"
    config_id = Column(UUID(as_uuid=True), ForeignKey("rate_limit_configs.id"))
    
    # Token bucket state
    tokens = Column(Float, nullable=False, default=0)
    last_refill = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Usage tracking
    request_count = Column(Integer, default=0)
    total_cost = Column(Float, default=0)
    
    # Sliding window data
    window_counters = Column(JSONB, default=dict)  # {"timestamp": count} for sliding window
    
    # Burst tracking
    burst_used = Column(Integer, default=0)
    last_burst_reset = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    config = relationship("RateLimitConfig")
    
    def __repr__(self):
        return f"<RateLimitBucket {self.bucket_key} (tokens: {self.tokens})>"


class RateLimitViolation(Base):
    """Track rate limit violations for analysis."""
    __tablename__ = "rate_limit_violations"
    __table_args__ = (
        Index('idx_rate_limit_violations_timestamp', 'timestamp'),
        Index('idx_rate_limit_violations_identifier', 'identifier'),
        {"extend_existing": True}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Violation details
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    identifier = Column(String(255), nullable=False)  # User ID, IP, etc.
    identifier_type = Column(SQLEnum(RateLimitType), nullable=False)
    
    # Request details
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Limit details
    limit_type = Column(String(50), nullable=False)  # "per_minute", "cost_per_hour", etc.
    limit_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    
    # Response
    response_code = Column(Integer, default=429)
    retry_after_seconds = Column(Integer, nullable=True)
    
    # Geographic info
    country_code = Column(String(2), nullable=True)
    region = Column(String(100), nullable=True)
    
    # Analysis
    is_repeated = Column(Boolean, default=False)  # Multiple violations in short time
    severity_score = Column(Integer, default=1)  # 1-10 severity
    
    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("platform_api_keys.id"))
    config_id = Column(UUID(as_uuid=True), ForeignKey("rate_limit_configs.id"))
    
    user = relationship("User")
    api_key = relationship("PlatformAPIKey")
    config = relationship("RateLimitConfig")
    
    def __repr__(self):
        return f"<RateLimitViolation {self.identifier} at {self.timestamp}>"


class EndpointCost(Base):
    """Define costs for different endpoints."""
    __tablename__ = "endpoint_costs"
    __table_args__ = (
        Index('idx_endpoint_costs_pattern', 'endpoint_pattern'),
        {"extend_existing": True}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Endpoint definition
    endpoint_pattern = Column(String(500), nullable=False)  # Regex pattern
    method = Column(String(10), nullable=True)  # HTTP method (null = all)
    
    # Cost configuration
    base_cost = Column(Float, default=1.0, nullable=False)
    
    # Dynamic cost factors
    request_size_factor = Column(Float, default=0.0)  # Cost per KB of request
    response_size_factor = Column(Float, default=0.0)  # Cost per KB of response
    compute_time_factor = Column(Float, default=0.0)  # Cost per ms of compute
    
    # Resource-specific costs
    database_read_cost = Column(Float, default=0.1)
    database_write_cost = Column(Float, default=1.0)
    cache_miss_cost = Column(Float, default=0.5)
    external_api_cost = Column(Float, default=2.0)
    
    # ML/AI costs
    ml_inference_cost = Column(Float, default=5.0)
    ml_training_cost = Column(Float, default=50.0)
    
    # Time-based multipliers
    peak_hours_multiplier = Column(Float, default=1.5)
    off_hours_multiplier = Column(Float, default=0.8)
    
    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # For pattern matching order
    
    # Metadata
    description = Column(String(500), nullable=True)
    tags = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<EndpointCost {self.endpoint_pattern} (base: {self.base_cost})>"


class RateLimitOverride(Base):
    """Temporary rate limit overrides for specific users/situations."""
    __tablename__ = "rate_limit_overrides"
    __table_args__ = {"extend_existing": True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Override target
    target_type = Column(SQLEnum(RateLimitType), nullable=False)
    target_identifier = Column(String(255), nullable=False)
    
    # Override values (null = no override for that limit)
    requests_per_minute = Column(Integer, nullable=True)
    requests_per_hour = Column(Integer, nullable=True)
    requests_per_day = Column(Integer, nullable=True)
    cost_per_minute = Column(Float, nullable=True)
    cost_per_hour = Column(Float, nullable=True)
    cost_per_day = Column(Float, nullable=True)
    
    # Override details
    reason = Column(String(500), nullable=False)
    approved_by = Column(String(255), nullable=True)
    
    # Time bounds
    starts_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<RateLimitOverride {self.target_type.value}:{self.target_identifier}>"
    
    @property
    def is_expired(self):
        """Check if override has expired."""
        return datetime.utcnow() > self.expires_at