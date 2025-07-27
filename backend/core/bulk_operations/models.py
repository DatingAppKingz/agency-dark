"""
Bulk operations models.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from datetime import datetime
import enum

from core.database import Base


class BulkOperationType(str, enum.Enum):
    """Types of bulk operations."""
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_ACTIVATE = "user_activate"
    USER_DEACTIVATE = "user_deactivate"
    MODEL_UPDATE = "model_update"
    MODEL_ASSIGN = "model_assign"
    TRANSACTION_EXPORT = "transaction_export"
    TRANSACTION_RECONCILE = "transaction_reconcile"
    PAYOUT_SCHEDULE = "payout_schedule"
    PAYOUT_CANCEL = "payout_cancel"
    MESSAGE_SEND = "message_send"
    MESSAGE_DELETE = "message_delete"
    ANALYTICS_EXPORT = "analytics_export"
    DATA_IMPORT = "data_import"
    DATA_EXPORT = "data_export"


class BulkOperationStatus(str, enum.Enum):
    """Status of bulk operations."""
    PENDING = "pending"
    VALIDATING = "validating"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class BulkOperation(Base):
    """Bulk operation record."""
    __tablename__ = "bulk_operations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_type = Column(SQLEnum(BulkOperationType), nullable=False)
    status = Column(SQLEnum(BulkOperationStatus), default=BulkOperationStatus.PENDING)
    
    # Operation details
    entity_type = Column(String(50), nullable=False)  # users, models, transactions, etc.
    entity_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)  # IDs of entities to operate on
    total_count = Column(Integer, nullable=False)
    processed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # Operation parameters
    operation_params = Column(JSON)  # Parameters specific to operation type
    validation_rules = Column(JSON)  # Validation rules to apply
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Progress tracking
    progress_percentage = Column(Integer, default=0)
    current_batch = Column(Integer, default=0)
    total_batches = Column(Integer, default=1)
    batch_size = Column(Integer, default=100)
    
    # Error handling
    error_summary = Column(Text)
    errors = Column(JSON)  # Detailed errors per entity
    can_rollback = Column(Boolean, default=True)
    rollback_data = Column(JSON)  # Data needed for rollback
    
    # Limits
    max_entities = Column(Integer)  # Maximum entities allowed
    max_duration_seconds = Column(Integer)  # Maximum operation duration
    priority = Column(Integer, default=0)  # Higher = more priority
    
    # User info
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    notes = Column(Text)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    agency = relationship("Agency")
    items = relationship("BulkOperationItem", back_populates="operation", cascade="all, delete-orphan")
    logs = relationship("BulkOperationLog", back_populates="operation", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_operation_status", "status"),
        Index("idx_bulk_operation_type", "operation_type"),
        Index("idx_bulk_operation_agency", "agency_id"),
        Index("idx_bulk_operation_scheduled", "scheduled_at"),
        Index("idx_bulk_operation_created", "created_at"),
    )


class BulkOperationItem(Base):
    """Individual item in a bulk operation."""
    __tablename__ = "bulk_operation_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id = Column(UUID(as_uuid=True), ForeignKey("bulk_operations.id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, success, failed, skipped
    processed_at = Column(DateTime(timezone=True))
    
    # Data
    original_data = Column(JSON)  # Data before operation (for rollback)
    new_data = Column(JSON)  # Data after operation
    changes = Column(JSON)  # What changed
    
    # Error info
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Validation
    validation_passed = Column(Boolean)
    validation_errors = Column(JSON)
    
    # Relationships
    operation = relationship("BulkOperation", back_populates="items")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_item_operation", "operation_id"),
        Index("idx_bulk_item_entity", "entity_id"),
        Index("idx_bulk_item_status", "status"),
    )


class BulkOperationLog(Base):
    """Log entries for bulk operations."""
    __tablename__ = "bulk_operation_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id = Column(UUID(as_uuid=True), ForeignKey("bulk_operations.id"), nullable=False)
    
    # Log details
    log_level = Column(String(20), nullable=False)  # info, warning, error, debug
    message = Column(Text, nullable=False)
    details = Column(JSON)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Context
    batch_number = Column(Integer)
    entity_id = Column(UUID(as_uuid=True))
    
    # Relationships
    operation = relationship("BulkOperation", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_log_operation", "operation_id"),
        Index("idx_bulk_log_timestamp", "timestamp"),
        Index("idx_bulk_log_level", "log_level"),
    )


class BulkOperationTemplate(Base):
    """Templates for common bulk operations."""
    __tablename__ = "bulk_operation_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    operation_type = Column(SQLEnum(BulkOperationType), nullable=False)
    
    # Template configuration
    default_params = Column(JSON, nullable=False)
    validation_rules = Column(JSON)
    selection_criteria = Column(JSON)  # Criteria for auto-selecting entities
    
    # Permissions
    required_role = Column(String(50))  # Minimum role required
    is_system = Column(Boolean, default=False)  # System templates can't be edited
    is_active = Column(Boolean, default=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    
    # Relationships
    created_by = relationship("User")
    agency = relationship("Agency")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_template_name", "name"),
        Index("idx_bulk_template_type", "operation_type"),
        Index("idx_bulk_template_agency", "agency_id"),
    )


class BulkOperationSchedule(Base):
    """Scheduled recurring bulk operations."""
    __tablename__ = "bulk_operation_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("bulk_operation_templates.id"))
    
    # Schedule configuration
    cron_expression = Column(String(100))  # Cron expression for scheduling
    timezone = Column(String(50), default="UTC")
    is_active = Column(Boolean, default=True)
    
    # Execution details
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    
    # Selection
    entity_selection = Column(JSON)  # Dynamic selection criteria
    max_entities_per_run = Column(Integer)
    
    # Notification
    notify_on_completion = Column(Boolean, default=True)
    notify_on_failure = Column(Boolean, default=True)
    notification_emails = Column(ARRAY(String))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Relationships
    template = relationship("BulkOperationTemplate")
    created_by = relationship("User")
    agency = relationship("Agency")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_schedule_active", "is_active"),
        Index("idx_bulk_schedule_next_run", "next_run_at"),
        Index("idx_bulk_schedule_agency", "agency_id"),
    )


class BulkOperationLimit(Base):
    """Limits for bulk operations per agency/user."""
    __tablename__ = "bulk_operation_limits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Scope
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    operation_type = Column(SQLEnum(BulkOperationType))
    
    # Limits
    max_entities_per_operation = Column(Integer, default=1000)
    max_operations_per_day = Column(Integer, default=100)
    max_operations_per_hour = Column(Integer, default=20)
    max_concurrent_operations = Column(Integer, default=3)
    
    # Rate limiting
    operations_today = Column(Integer, default=0)
    operations_this_hour = Column(Integer, default=0)
    last_reset_date = Column(DateTime(timezone=True))
    last_reset_hour = Column(DateTime(timezone=True))
    
    # Override
    is_unlimited = Column(Boolean, default=False)
    valid_until = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_bulk_limit_agency", "agency_id"),
        Index("idx_bulk_limit_user", "user_id"),
        Index("idx_bulk_limit_type", "operation_type"),
    )