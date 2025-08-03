"""
ML Analytics models for predictions and insights.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum, Index, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from datetime import datetime
import enum

from core.database import Base


class PredictionType(str, enum.Enum):
    """Types of ML predictions."""
    REVENUE_FORECAST = "revenue_forecast"
    CHURN_PREDICTION = "churn_prediction"
    CONTENT_OPTIMIZATION = "content_optimization"
    ANOMALY_DETECTION = "anomaly_detection"
    FAN_LTV = "fan_ltv"
    ENGAGEMENT_SCORE = "engagement_score"
    CONVERSION_RATE = "conversion_rate"


class ModelStatus(str, enum.Enum):
    """ML model training status."""
    PENDING = "pending"
    TRAINING = "training"
    TRAINED = "trained"
    EVALUATING = "evaluating"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ARCHIVED = "archived"


class MLModel(Base):
    """Machine learning model metadata."""
    __tablename__ = "ml_models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    prediction_type = Column(SQLEnum(PredictionType), nullable=False)
    
    # Model configuration
    algorithm = Column(String(100))  # e.g., 'prophet', 'random_forest', 'lstm'
    hyperparameters = Column(JSON)
    features = Column(JSON)  # List of features used
    target_variable = Column(String(100))
    
    # Training metadata
    training_data_start = Column(DateTime(timezone=True))
    training_data_end = Column(DateTime(timezone=True))
    training_samples = Column(Integer)
    
    # Model performance
    metrics = Column(JSON)  # e.g., {"mape": 0.15, "rmse": 1000, "r2": 0.85}
    accuracy_score = Column(Float)
    validation_score = Column(Float)
    
    # Model artifacts
    model_path = Column(String(500))  # Path to serialized model
    model_version = Column(String(50))
    model_size_mb = Column(Float)
    
    # Status and deployment
    status = Column(SQLEnum(ModelStatus), default=ModelStatus.PENDING)
    is_active = Column(Boolean, default=False)  # Currently deployed model
    deployment_date = Column(DateTime(timezone=True))
    
    # Metadata
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    last_trained_at = Column(DateTime(timezone=True))
    
    # Relationships
    agency = relationship("Agency")
    created_by = relationship("User")
    predictions = relationship("Prediction", back_populates="model")
    training_jobs = relationship("ModelTrainingJob", back_populates="model")
    
    # Indexes
    __table_args__ = (
        Index("idx_ml_model_agency", "agency_id"),
        Index("idx_ml_model_type", "prediction_type"),
        Index("idx_ml_model_status", "status"),
        Index("idx_ml_model_active", "is_active"),
    )


class Prediction(Base):
    """Individual predictions made by ML models."""
    __tablename__ = "predictions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False)
    
    # Prediction details
    prediction_type = Column(SQLEnum(PredictionType), nullable=False)
    target_date = Column(DateTime(timezone=True))  # Date being predicted for
    prediction_horizon = Column(Integer)  # Days/hours ahead
    
    # Prediction values
    predicted_value = Column(Float)
    confidence_interval_lower = Column(Float)
    confidence_interval_upper = Column(Float)
    probability = Column(Float)  # For classification predictions
    
    # Additional predictions (e.g., for multi-value forecasts)
    predictions_json = Column(JSON)
    
    # Context
    entity_type = Column(String(50))  # 'model', 'fan', 'agency', etc.
    entity_id = Column(UUID(as_uuid=True))
    
    # Input features used
    input_features = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    confidence_score = Column(Float)
    
    # Tracking
    actual_value = Column(Float)  # Filled when actual data becomes available
    error_percentage = Column(Float)  # Calculated error
    feedback_received_at = Column(DateTime(timezone=True))
    
    # Relationships
    model = relationship("MLModel", back_populates="predictions")
    
    # Indexes
    __table_args__ = (
        Index("idx_prediction_model", "model_id"),
        Index("idx_prediction_type", "prediction_type"),
        Index("idx_prediction_entity", "entity_type", "entity_id"),
        Index("idx_prediction_created", "created_at"),
        Index("idx_prediction_target_date", "target_date"),
    )


class ModelTrainingJob(Base):
    """Track ML model training jobs."""
    __tablename__ = "model_training_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False)
    
    # Job configuration
    job_type = Column(String(50))  # 'initial', 'retrain', 'fine_tune'
    parameters = Column(JSON)
    
    # Data used
    training_data_query = Column(Text)
    training_samples = Column(Integer)
    validation_samples = Column(Integer)
    test_samples = Column(Integer)
    
    # Execution
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    # Resources
    cpu_hours = Column(Float)
    memory_gb = Column(Float)
    cost_estimate = Column(Float)
    
    # Results
    metrics = Column(JSON)
    error_message = Column(Text)
    model_artifact_path = Column(String(500))
    
    # Metadata
    triggered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    model = relationship("MLModel", back_populates="training_jobs")
    triggered_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_training_job_model", "model_id"),
        Index("idx_training_job_status", "status"),
        Index("idx_training_job_created", "created_at"),
    )


class FeatureStore(Base):
    """Store computed features for ML models."""
    __tablename__ = "feature_store"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Feature identification
    feature_name = Column(String(100), nullable=False)
    feature_type = Column(String(50))  # 'numeric', 'categorical', 'embedding'
    description = Column(Text)
    
    # Entity association
    entity_type = Column(String(50), nullable=False)  # 'model', 'fan', 'content'
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Feature values
    numeric_value = Column(Float)
    categorical_value = Column(String(200))
    vector_value = Column(ARRAY(Float))  # For embeddings
    json_value = Column(JSON)  # For complex features
    
    # Time-based features
    timestamp = Column(DateTime(timezone=True), nullable=False)
    time_window = Column(String(50))  # 'daily', 'weekly', 'monthly'
    
    # Metadata
    computation_time_ms = Column(Integer)
    source_table = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    
    # Indexes
    __table_args__ = (
        Index("idx_feature_entity", "entity_type", "entity_id"),
        Index("idx_feature_name", "feature_name"),
        Index("idx_feature_timestamp", "timestamp"),
        Index("idx_feature_composite", "entity_type", "entity_id", "feature_name", "timestamp"),
    )


class PredictionFeedback(Base):
    """Track prediction accuracy and feedback."""
    __tablename__ = "prediction_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id = Column(UUID(as_uuid=True), ForeignKey("predictions.id"), nullable=False)
    
    # Actual outcomes
    actual_value = Column(Float)
    actual_date = Column(DateTime(timezone=True))
    
    # Error metrics
    absolute_error = Column(Float)
    percentage_error = Column(Float)
    squared_error = Column(Float)
    
    # Feedback
    user_feedback = Column(String(50))  # 'accurate', 'inaccurate', 'partially_accurate'
    feedback_notes = Column(Text)
    
    # Metadata
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    recorded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    prediction = relationship("Prediction")
    recorded_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_feedback_prediction", "prediction_id"),
        Index("idx_feedback_recorded", "recorded_at"),
    )


class InsightAlert(Base):
    """Automated insights and alerts from ML models."""
    __tablename__ = "insight_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Alert details
    alert_type = Column(String(50), nullable=False)  # 'anomaly', 'trend', 'threshold', 'prediction'
    severity = Column(String(20))  # 'low', 'medium', 'high', 'critical'
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Source
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id"))
    prediction_id = Column(UUID(as_uuid=True), ForeignKey("predictions.id"))
    
    # Context
    entity_type = Column(String(50))
    entity_id = Column(UUID(as_uuid=True))
    
    # Alert data
    metrics = Column(JSON)
    recommendations = Column(JSON)
    
    # Status
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Notification
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(ARRAY(String))  # ['email', 'sms', 'push']
    
    # Metadata
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    model = relationship("MLModel")
    prediction = relationship("Prediction")
    agency = relationship("Agency")
    resolved_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_alert_agency", "agency_id"),
        Index("idx_alert_type", "alert_type"),
        Index("idx_alert_severity", "severity"),
        Index("idx_alert_entity", "entity_type", "entity_id"),
        Index("idx_alert_created", "created_at"),
        Index("idx_alert_unread", "is_read", "agency_id"),
    )
