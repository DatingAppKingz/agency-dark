"""
A/B Testing domain models
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, String, JSON, DateTime, Boolean, Integer, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExperimentType(str, Enum):
    """Types of experiments supported"""
    MESSAGE_CONTENT = "message_content"
    MESSAGE_TIMING = "message_timing"
    PRICING = "pricing"
    UI_ELEMENT = "ui_element"
    CONTENT_RECOMMENDATION = "content_recommendation"
    ENGAGEMENT_STRATEGY = "engagement_strategy"
    EMAIL_CAMPAIGN = "email_campaign"


class AllocationMethod(str, Enum):
    """Traffic allocation methods"""
    RANDOM = "random"
    DETERMINISTIC = "deterministic"
    WEIGHTED = "weighted"
    SEQUENTIAL = "sequential"


class StatisticalTest(str, Enum):
    """Statistical tests for analysis"""
    T_TEST = "t_test"
    CHI_SQUARED = "chi_squared"
    MANN_WHITNEY_U = "mann_whitney_u"
    ANOVA = "anova"
    BAYESIAN = "bayesian"


class Experiment(Base):
    """Main experiment configuration"""
    __tablename__ = "ab_experiments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Basic info
    name = Column(String, nullable=False)
    description = Column(Text)
    hypothesis = Column(Text)  # What we expect to happen
    
    # Experiment configuration
    experiment_type = Column(String, nullable=False)
    status = Column(String, default=ExperimentStatus.DRAFT.value)
    
    # Targeting
    target_audience = Column(JSON)  # Criteria for participant selection
    model_ids = Column(JSON)  # Specific models to include
    
    # Duration
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Traffic allocation
    allocation_method = Column(String, default=AllocationMethod.RANDOM.value)
    allocation_config = Column(JSON)  # Method-specific configuration
    
    # Success metrics
    primary_metric = Column(String, nullable=False)
    secondary_metrics = Column(JSON)
    minimum_sample_size = Column(Integer)
    
    # Statistical configuration
    statistical_test = Column(String, default=StatisticalTest.T_TEST.value)
    confidence_level = Column(Float, default=0.95)
    minimum_detectable_effect = Column(Float, default=0.05)
    
    # Results
    winner_variant_id = Column(UUID(as_uuid=True))
    results_summary = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    variants = relationship("ExperimentVariant", back_populates="experiment", cascade="all, delete-orphan")
    participants = relationship("ExperimentParticipant", back_populates="experiment", cascade="all, delete-orphan")
    events = relationship("ExperimentEvent", back_populates="experiment", cascade="all, delete-orphan")


class ExperimentVariant(Base):
    """Variants within an experiment"""
    __tablename__ = "ab_experiment_variants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False)
    
    # Variant info
    name = Column(String, nullable=False)  # e.g., "Control", "Variant A"
    description = Column(Text)
    is_control = Column(Boolean, default=False)
    
    # Configuration
    config = Column(JSON, nullable=False)  # Variant-specific settings
    
    # Allocation
    allocation_percentage = Column(Float, default=50.0)
    
    # Performance tracking
    participant_count = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    average_value = Column(Float, default=0.0)
    
    # Statistical results
    statistical_significance = Column(Float)
    confidence_interval_lower = Column(Float)
    confidence_interval_upper = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="variants")
    participants = relationship("ExperimentParticipant", back_populates="variant")


class ExperimentParticipant(Base):
    """Track experiment participants"""
    __tablename__ = "ab_experiment_participants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiment_variants.id"), nullable=False)
    
    # Participant identification
    participant_type = Column(String, nullable=False)  # "fan", "model", "user"
    participant_id = Column(String, nullable=False)  # ID of the participant
    
    # Assignment details
    assignment_timestamp = Column(DateTime, default=datetime.utcnow)
    assignment_reason = Column(String)  # How they were assigned
    
    # Conversion tracking
    has_converted = Column(Boolean, default=False)
    conversion_timestamp = Column(DateTime)
    conversion_value = Column(Float)
    
    # Engagement metrics
    interaction_count = Column(Integer, default=0)
    last_interaction = Column(DateTime)
    
    # Metadata
    metadata = Column(JSON)  # Additional participant info
    
    # Relationships
    experiment = relationship("Experiment", back_populates="participants")
    variant = relationship("ExperimentVariant", back_populates="participants")
    events = relationship("ExperimentEvent", back_populates="participant")


class ExperimentEvent(Base):
    """Track events within experiments"""
    __tablename__ = "ab_experiment_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiment_participants.id"), nullable=False)
    
    # Event info
    event_type = Column(String, nullable=False)  # e.g., "view", "click", "purchase"
    event_value = Column(Float)  # Monetary or numeric value
    event_data = Column(JSON)  # Additional event details
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="events")
    participant = relationship("ExperimentParticipant", back_populates="events")


class ExperimentTemplate(Base):
    """Reusable experiment templates"""
    __tablename__ = "ab_experiment_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agency_id = Column(String, ForeignKey("agencies.id"))
    
    # Template info
    name = Column(String, nullable=False)
    description = Column(Text)
    experiment_type = Column(String, nullable=False)
    
    # Template configuration
    default_config = Column(JSON, nullable=False)
    variant_templates = Column(JSON)  # Pre-defined variants
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    
    # Metadata
    tags = Column(JSON)
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExperimentResult(Base):
    """Detailed experiment results and analysis"""
    __tablename__ = "ab_experiment_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ab_experiments.id"), nullable=False, unique=True)
    
    # Overall results
    total_participants = Column(Integer)
    total_conversions = Column(Integer)
    overall_conversion_rate = Column(Float)
    
    # Statistical analysis
    p_value = Column(Float)
    effect_size = Column(Float)
    power = Column(Float)
    
    # Variant comparisons
    variant_results = Column(JSON)  # Detailed results per variant
    pairwise_comparisons = Column(JSON)  # Statistical comparisons between variants
    
    # Segmentation analysis
    segment_results = Column(JSON)  # Results broken down by segments
    
    # Time series data
    daily_results = Column(JSON)  # Results over time
    cumulative_results = Column(JSON)  # Cumulative metrics
    
    # Recommendations
    recommendation = Column(Text)
    confidence_in_results = Column(Float)
    
    # Metadata
    analysis_timestamp = Column(DateTime, default=datetime.utcnow)
    analysis_version = Column(String)  # Version of analysis algorithm
    
    # Relationships
    experiment = relationship("Experiment", backref="results", uselist=False)
