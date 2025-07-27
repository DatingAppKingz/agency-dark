"""
Advanced reporting system models.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from datetime import datetime
import enum

from core.database import Base


# Association table for report sharing
report_shares = Table(
    'report_shares',
    Base.metadata,
    Column('report_id', UUID(as_uuid=True), ForeignKey('reports.id')),
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id')),
    Column('permission', String(20), default='view'),  # view, edit
    Column('shared_at', DateTime(timezone=True), default=datetime.utcnow)
)


class ReportType(str, enum.Enum):
    """Types of reports."""
    REVENUE = "revenue"
    USER_ACTIVITY = "user_activity"
    MODEL_PERFORMANCE = "model_performance"
    TRANSACTION = "transaction"
    PAYOUT = "payout"
    ENGAGEMENT = "engagement"
    CONVERSION = "conversion"
    CUSTOM = "custom"
    EXECUTIVE = "executive"


class ReportFormat(str, enum.Enum):
    """Report export formats."""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class ReportStatus(str, enum.Enum):
    """Report generation status."""
    DRAFT = "draft"
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class Report(Base):
    """Report definition and configuration."""
    __tablename__ = "reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    report_type = Column(SQLEnum(ReportType), nullable=False)
    
    # Report configuration
    query_config = Column(JSON, nullable=False)  # SQL query or data source config
    filters = Column(JSON)  # User-defined filters
    columns = Column(JSON)  # Selected columns and their configuration
    grouping = Column(JSON)  # Grouping configuration
    sorting = Column(JSON)  # Sorting configuration
    aggregations = Column(JSON)  # Aggregation functions
    
    # Visualization
    chart_config = Column(JSON)  # Chart type and configuration
    layout_config = Column(JSON)  # Layout and styling
    
    # Access control
    is_public = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    template_category = Column(String(50))  # For organizing templates
    
    # Performance
    cache_duration_minutes = Column(Integer, default=60)
    estimated_runtime_seconds = Column(Integer)
    
    # Metadata
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    last_run_at = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    agency = relationship("Agency")
    shared_with = relationship("User", secondary=report_shares, backref="shared_reports")
    executions = relationship("ReportExecution", back_populates="report", cascade="all, delete-orphan")
    schedules = relationship("ReportSchedule", back_populates="report", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_agency", "agency_id"),
        Index("idx_report_type", "report_type"),
        Index("idx_report_template", "is_template"),
        Index("idx_report_created", "created_at"),
    )


class ReportExecution(Base):
    """Individual report execution record."""
    __tablename__ = "report_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    
    # Execution details
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    format = Column(SQLEnum(ReportFormat), nullable=False)
    
    # Parameters used for this execution
    parameters = Column(JSON)  # Runtime parameters
    filters_applied = Column(JSON)  # Actual filters used
    
    # Results
    row_count = Column(Integer)
    file_path = Column(String(500))  # Path to generated file
    file_size_bytes = Column(Integer)
    preview_data = Column(JSON)  # Sample of results for preview
    
    # Performance metrics
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    execution_time_ms = Column(Integer)
    query_time_ms = Column(Integer)
    render_time_ms = Column(Integer)
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    
    # Cache info
    cached = Column(Boolean, default=False)
    cache_hit = Column(Boolean, default=False)
    cache_key = Column(String(255))
    
    # User info
    executed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))  # When the file will be deleted
    
    # Relationships
    report = relationship("Report", back_populates="executions")
    executed_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_execution_report", "report_id"),
        Index("idx_report_execution_status", "status"),
        Index("idx_report_execution_created", "created_at"),
        Index("idx_report_execution_cache", "cache_key"),
    )


class ReportSchedule(Base):
    """Scheduled report generation."""
    __tablename__ = "report_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    
    # Schedule configuration
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC")
    is_active = Column(Boolean, default=True)
    
    # Delivery configuration
    format = Column(SQLEnum(ReportFormat), nullable=False)
    delivery_method = Column(String(20), default="email")  # email, webhook, storage
    delivery_config = Column(JSON)  # Email addresses, webhook URL, etc.
    
    # Recipients
    recipient_users = Column(ARRAY(UUID(as_uuid=True)))  # User IDs
    recipient_emails = Column(ARRAY(String))  # External emails
    
    # Parameters
    parameters = Column(JSON)  # Parameters to use for scheduled runs
    
    # Execution tracking
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    
    # Metadata
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Relationships
    report = relationship("Report", back_populates="schedules")
    created_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_schedule_active", "is_active"),
        Index("idx_report_schedule_next_run", "next_run_at"),
    )


class ReportTemplate(Base):
    """Pre-built report templates."""
    __tablename__ = "report_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)
    
    # Template configuration
    report_type = Column(SQLEnum(ReportType), nullable=False)
    base_query = Column(Text)  # Base SQL query
    default_filters = Column(JSON)
    default_columns = Column(JSON)
    default_grouping = Column(JSON)
    default_sorting = Column(JSON)
    default_aggregations = Column(JSON)
    default_chart_config = Column(JSON)
    
    # Customization options
    customizable_fields = Column(JSON)  # Which fields users can customize
    required_parameters = Column(JSON)  # Parameters users must provide
    
    # Usage
    is_system = Column(Boolean, default=False)  # System templates can't be edited
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    
    # Preview
    preview_image_url = Column(String(500))
    sample_data = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    created_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_template_category", "category"),
        Index("idx_report_template_type", "report_type"),
        Index("idx_report_template_active", "is_active"),
    )


class ReportWidget(Base):
    """Widgets for report dashboards."""
    __tablename__ = "report_widgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    
    # Widget configuration
    widget_type = Column(String(50), nullable=False)  # chart, table, metric, text
    title = Column(String(200))
    configuration = Column(JSON, nullable=False)
    
    # Layout
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    width = Column(Integer, default=6)  # Grid units
    height = Column(Integer, default=4)  # Grid units
    
    # Data source
    data_source = Column(String(50), default="report")  # report, custom_query, api
    custom_query = Column(Text)
    refresh_interval_seconds = Column(Integer)
    
    # Styling
    style_config = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Relationships
    report = relationship("Report")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_widget_report", "report_id"),
    )


class ReportCache(Base):
    """Cache for report data and rendered outputs."""
    __tablename__ = "report_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(255), nullable=False, unique=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"))
    
    # Cache data
    data_type = Column(String(20), nullable=False)  # data, file, preview
    data = Column(JSON)  # For JSON data
    file_path = Column(String(500))  # For file outputs
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    hit_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True))
    size_bytes = Column(Integer)
    
    # Parameters used to generate
    parameters = Column(JSON)
    filters = Column(JSON)
    
    # Relationships
    report = relationship("Report")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_cache_key", "cache_key"),
        Index("idx_report_cache_expires", "expires_at"),
        Index("idx_report_cache_report", "report_id"),
    )


class ReportAuditLog(Base):
    """Audit log for report access and changes."""
    __tablename__ = "report_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    
    # Action details
    action = Column(String(50), nullable=False)  # created, updated, deleted, viewed, exported, shared
    action_details = Column(JSON)
    
    # User info
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Metadata
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    report = relationship("Report")
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_report_audit_report", "report_id"),
        Index("idx_report_audit_user", "user_id"),
        Index("idx_report_audit_timestamp", "timestamp"),
        Index("idx_report_audit_action", "action"),
    )