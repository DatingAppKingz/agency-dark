"""
Fraud detection models.
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from datetime import datetime
import enum

from core.database import Base


class RiskLevel(str, enum.Enum):
    """Risk level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudType(str, enum.Enum):
    """Types of fraud."""
    PAYMENT_FRAUD = "payment_fraud"
    ACCOUNT_TAKEOVER = "account_takeover"
    FAKE_ENGAGEMENT = "fake_engagement"
    CHARGEBACKS = "chargebacks"
    VELOCITY_ABUSE = "velocity_abuse"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    BOT_ACTIVITY = "bot_activity"
    CONTENT_THEFT = "content_theft"


class ActionType(str, enum.Enum):
    """Actions taken for fraud."""
    MONITOR = "monitor"
    FLAG = "flag"
    RESTRICT = "restrict"
    SUSPEND = "suspend"
    BLOCK = "block"
    REVIEW = "review"


class FraudRule(Base):
    """Fraud detection rules."""
    __tablename__ = "fraud_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    rule_type = Column(String(50), nullable=False)  # velocity, pattern, anomaly, etc.
    fraud_type = Column(SQLEnum(FraudType), nullable=False)
    
    # Rule configuration
    conditions = Column(JSON, nullable=False)  # Rule conditions in JSON format
    threshold_value = Column(Float)
    time_window_seconds = Column(Integer)
    
    # Actions
    risk_score = Column(Integer, nullable=False)  # Points to add to risk score
    auto_action = Column(SQLEnum(ActionType))
    notification_enabled = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher = more priority
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_fraud_rule_active", "is_active"),
        Index("idx_fraud_rule_type", "rule_type"),
        Index("idx_fraud_rule_fraud_type", "fraud_type"),
    )


class FraudScore(Base):
    """User/entity fraud risk scores."""
    __tablename__ = "fraud_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)  # user, ip, payment_method, etc.
    entity_id = Column(String(255), nullable=False)  # ID of the entity
    
    # Scores
    current_score = Column(Integer, default=0)
    max_score = Column(Integer, default=0)  # Highest score ever reached
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.LOW)
    
    # Score components
    velocity_score = Column(Integer, default=0)
    pattern_score = Column(Integer, default=0)
    anomaly_score = Column(Integer, default=0)
    history_score = Column(Integer, default=0)
    
    # Actions
    is_blocked = Column(Boolean, default=False)
    is_under_review = Column(Boolean, default=False)
    auto_action_taken = Column(SQLEnum(ActionType))
    
    # Metadata
    last_activity = Column(DateTime(timezone=True))
    score_updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_fraud_score_entity", "entity_type", "entity_id", unique=True),
        Index("idx_fraud_score_risk_level", "risk_level"),
        Index("idx_fraud_score_blocked", "is_blocked"),
        Index("idx_fraud_score_review", "is_under_review"),
    )


class FraudEvent(Base):
    """Fraud detection events."""
    __tablename__ = "fraud_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # transaction, login, message, etc.
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    
    # Event details
    fraud_type = Column(SQLEnum(FraudType))
    risk_score = Column(Integer, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    
    # Detection details
    triggered_rules = Column(ARRAY(UUID(as_uuid=True)))  # IDs of rules that triggered
    anomaly_factors = Column(JSON)  # Factors that contributed to anomaly detection
    velocity_metrics = Column(JSON)  # Velocity check results
    pattern_matches = Column(JSON)  # Pattern matching results
    
    # Context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_fingerprint = Column(String(255))
    location_data = Column(JSON)  # Country, city, coordinates, etc.
    
    # Transaction specific (if applicable)
    amount = Column(Float)
    currency = Column(String(3))
    payment_method = Column(String(50))
    
    # Action taken
    action_taken = Column(SQLEnum(ActionType))
    blocked = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)
    false_positive = Column(Boolean)
    
    # Metadata
    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    notes = Column(Text)
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    agency = relationship("Agency")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_fraud_event_entity", "entity_type", "entity_id"),
        Index("idx_fraud_event_user", "user_id"),
        Index("idx_fraud_event_detected", "detected_at"),
        Index("idx_fraud_event_risk_level", "risk_level"),
        Index("idx_fraud_event_review", "reviewed", "false_positive"),
    )


class FraudPattern(Base):
    """Known fraud patterns for pattern matching."""
    __tablename__ = "fraud_patterns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    pattern_type = Column(String(50), nullable=False)  # behavioral, transactional, etc.
    fraud_type = Column(SQLEnum(FraudType), nullable=False)
    
    # Pattern definition
    pattern_data = Column(JSON, nullable=False)  # Pattern matching rules
    confidence_threshold = Column(Float, default=0.8)  # 0-1 confidence needed
    
    # Impact
    risk_score = Column(Integer, nullable=False)
    auto_block = Column(Boolean, default=False)
    
    # Statistics
    match_count = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    last_matched = Column(DateTime(timezone=True))
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_fraud_pattern_active", "is_active"),
        Index("idx_fraud_pattern_type", "pattern_type", "fraud_type"),
    )


class VelocityCheck(Base):
    """Velocity check configurations."""
    __tablename__ = "velocity_checks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    check_type = Column(String(50), nullable=False)  # transaction_count, amount_sum, etc.
    entity_type = Column(String(50), nullable=False)  # user, ip, card, etc.
    
    # Limits
    time_window_seconds = Column(Integer, nullable=False)
    max_count = Column(Integer)
    max_amount = Column(Float)
    unique_constraint = Column(String(50))  # e.g., unique IPs, unique cards
    
    # Actions
    risk_score = Column(Integer, nullable=False)
    auto_action = Column(SQLEnum(ActionType))
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_velocity_check_active", "is_active"),
        Index("idx_velocity_check_type", "check_type", "entity_type"),
    )


class ReviewQueue(Base):
    """Manual review queue for suspicious activities."""
    __tablename__ = "review_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    priority = Column(Integer, default=0)  # Higher = more urgent
    status = Column(String(20), default="pending")  # pending, in_review, resolved
    
    # What to review
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    fraud_event_id = Column(UUID(as_uuid=True), ForeignKey("fraud_events.id"))
    
    # Review details
    reason = Column(Text, nullable=False)
    risk_score = Column(Integer)
    risk_level = Column(SQLEnum(RiskLevel))
    evidence = Column(JSON)  # Supporting evidence
    
    # Assignment
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_at = Column(DateTime(timezone=True))
    
    # Resolution
    resolution = Column(String(50))  # approved, blocked, false_positive
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    due_date = Column(DateTime(timezone=True))
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    
    # Relationships
    fraud_event = relationship("FraudEvent", backref="review_items")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    user = relationship("User", foreign_keys=[user_id])
    agency = relationship("Agency")
    
    # Indexes
    __table_args__ = (
        Index("idx_review_queue_status", "status"),
        Index("idx_review_queue_priority", "priority", "status"),
        Index("idx_review_queue_assigned", "assigned_to_id", "status"),
        Index("idx_review_queue_entity", "entity_type", "entity_id"),
    )


class FraudWhitelist(Base):
    """Whitelist for trusted entities."""
    __tablename__ = "fraud_whitelist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    
    # Whitelist details
    reason = Column(Text, nullable=False)
    whitelist_level = Column(String(20), default="full")  # full, partial
    skip_checks = Column(ARRAY(String))  # Which checks to skip
    
    # Validity
    valid_from = Column(DateTime(timezone=True), default=datetime.utcnow)
    valid_until = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_fraud_whitelist_entity", "entity_type", "entity_id", unique=True),
        Index("idx_fraud_whitelist_validity", "valid_from", "valid_until"),
    )