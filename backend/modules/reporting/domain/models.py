"""
Domain models for reporting module.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, JSON, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class ReportStatus(str, enum.Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class DeliveryMethod(str, enum.Enum):
    """Report delivery methods."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    S3 = "s3"
    SFTP = "sftp"
    DOWNLOAD = "download"


class ReportTemplate(Base):
    """Custom report templates."""
    __tablename__ = "report_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    report_type = Column(String(50), nullable=False)  # revenue, engagement, comprehensive, etc.
    
    # Report configuration
    layout = Column(JSON, default=dict)  # Grid layout configuration
    filters = Column(JSON, default=dict)  # Default filters
    
    # Sharing
    is_public = Column(Boolean, default=False)  # Available to all agencies
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    created_by = relationship("User")
    widgets = relationship("ReportWidget", back_populates="template", cascade="all, delete-orphan")
    schedules = relationship("ReportSchedule", back_populates="template")
    
    __table_args__ = (
        Index('idx_report_templates_agency', 'agency_id'),
        Index('idx_report_templates_type', 'report_type'),
    )


class ReportWidget(Base):
    """Widgets within a report template."""
    __tablename__ = "report_widgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False)
    
    widget_type = Column(String(50), nullable=False)  # metric, chart, table, text, etc.
    title = Column(String(255))
    config = Column(JSON, default=dict)  # Widget-specific configuration
    position = Column(Integer, default=0)  # Order in report
    size = Column(String(20), default="medium")  # small, medium, large, full
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="widgets")
    
    __table_args__ = (
        Index('idx_report_widgets_template', 'template_id'),
    )


class ReportSchedule(Base):
    """Scheduled report generation."""
    __tablename__ = "report_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Schedule configuration
    schedule_type = Column(String(20), nullable=False)  # daily, weekly, monthly, cron
    cron_expression = Column(String(100))  # For advanced scheduling
    timezone = Column(String(50), default="UTC")
    
    # Report parameters
    parameters = Column(JSON, default=dict)  # Date ranges, filters, etc.
    
    # Delivery configuration
    delivery_method = Column(SQLEnum(DeliveryMethod), default=DeliveryMethod.EMAIL)
    delivery_config = Column(JSON, default=dict)  # Email addresses, webhook URLs, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency")
    template = relationship("ReportTemplate", back_populates="schedules")
    created_by = relationship("User")
    
    __table_args__ = (
        Index('idx_report_schedules_agency', 'agency_id'),
        Index('idx_report_schedules_next_run', 'next_run_at'),
        Index('idx_report_schedules_active', 'is_active'),
    )


class GeneratedReport(Base):
    """Generated report instances."""
    __tablename__ = "generated_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id", ondelete="SET NULL"))
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("report_schedules.id", ondelete="SET NULL"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    generated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    # Report data
    parameters = Column(JSON, default=dict)  # Parameters used for generation
    report_data = Column(JSON)  # The actual report data
    
    # Status
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    error_message = Column(Text)
    
    # File storage (if exported)
    file_url = Column(Text)
    file_format = Column(String(10))  # pdf, excel, csv
    file_size = Column(Integer)  # bytes
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)  # For cleanup
    
    # Relationships
    template = relationship("ReportTemplate")
    schedule = relationship("ReportSchedule")
    agency = relationship("Agency")
    generated_by = relationship("User")
    
    __table_args__ = (
        Index('idx_generated_reports_agency', 'agency_id'),
        Index('idx_generated_reports_created', 'created_at'),
        Index('idx_generated_reports_status', 'status'),
    )