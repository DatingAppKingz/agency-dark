"""
Feature-specific permission models for granular access control.

This module defines permissions for specific features like reports, exports,
analytics, and messaging, providing fine-grained control over feature access.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, ForeignKey, JSON,
    UniqueConstraint, Index, CheckConstraint, Enum as SQLEnum, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class FeatureType(str, Enum):
    """Types of features that can have permissions."""
    REPORTS = "reports"
    EXPORTS = "exports"
    ANALYTICS = "analytics"
    MESSAGING = "messaging"
    FINANCIAL = "financial"
    MODELS = "models"
    CHAT = "chat"
    SYNC = "sync"
    WEBHOOKS = "webhooks"
    API = "api"
    ADMIN = "admin"
    SETTINGS = "settings"
    AUDIT = "audit"
    ML = "ml"
    INTEGRATIONS = "integrations"


class ReportType(str, Enum):
    """Types of reports with specific permissions."""
    EARNINGS = "earnings"
    PERFORMANCE = "performance"
    USER_ACTIVITY = "user_activity"
    MODEL_METRICS = "model_metrics"
    CHAT_ANALYTICS = "chat_analytics"
    REVENUE_BREAKDOWN = "revenue_breakdown"
    COMMISSION_REPORT = "commission_report"
    TAX_REPORT = "tax_report"
    COMPLIANCE_REPORT = "compliance_report"
    CUSTOM = "custom"


class ExportFormat(str, Enum):
    """Allowed export formats."""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"
    XML = "xml"
    HTML = "html"
    PARQUET = "parquet"


class AnalyticsScope(str, Enum):
    """Scopes of analytics access."""
    OWN = "own"  # Only own data
    TEAM = "team"  # Team members' data
    AGENCY = "agency"  # All agency data
    GLOBAL = "global"  # Cross-agency data (admin only)


class MessagePermission(str, Enum):
    """Specific messaging permissions."""
    SEND_INDIVIDUAL = "send_individual"
    SEND_BULK = "send_bulk"
    VIEW_HISTORY = "view_history"
    DELETE_MESSAGES = "delete_messages"
    EDIT_TEMPLATES = "edit_templates"
    APPROVE_SCHEDULED = "approve_scheduled"
    MANAGE_AUTOMATION = "manage_automation"
    ACCESS_ALL_CHATS = "access_all_chats"
    EXPORT_CHATS = "export_chats"


class DataSensitivity(str, Enum):
    """Data sensitivity levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class FeaturePermission(Base):
    """Feature-specific permission configuration."""
    
    __tablename__ = "feature_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    feature_type = Column(SQLEnum(FeatureType), nullable=False, index=True)
    
    # Permission scope
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    
    # Feature-specific permissions
    allowed_actions = Column(JSONB, default=list)  # List of allowed actions
    denied_actions = Column(JSONB, default=list)  # Explicitly denied actions
    
    # Report permissions
    allowed_report_types = Column(JSONB, default=list)
    max_report_range_days = Column(Integer, nullable=True)  # Max date range for reports
    can_access_financial_data = Column(Boolean, default=False)
    can_access_pii_data = Column(Boolean, default=False)
    data_sensitivity_level = Column(SQLEnum(DataSensitivity), default=DataSensitivity.INTERNAL)
    
    # Export permissions
    allowed_export_formats = Column(JSONB, default=list)
    max_export_rows = Column(Integer, nullable=True)
    max_export_size_mb = Column(Integer, nullable=True)
    export_rate_limit_per_hour = Column(Integer, default=10)
    can_export_all_data = Column(Boolean, default=False)
    requires_export_approval = Column(Boolean, default=False)
    
    # Analytics permissions
    analytics_scope = Column(SQLEnum(AnalyticsScope), default=AnalyticsScope.OWN)
    allowed_metrics = Column(JSONB, default=list)
    can_view_revenue_data = Column(Boolean, default=False)
    can_view_cost_data = Column(Boolean, default=False)
    can_create_custom_metrics = Column(Boolean, default=False)
    
    # Messaging permissions
    message_permissions = Column(JSONB, default=list)
    max_bulk_recipients = Column(Integer, nullable=True)
    max_messages_per_hour = Column(Integer, nullable=True)
    can_use_automation = Column(Boolean, default=False)
    can_access_all_conversations = Column(Boolean, default=False)
    
    # Time restrictions
    access_start_time = Column(String(5), nullable=True)  # HH:MM format
    access_end_time = Column(String(5), nullable=True)  # HH:MM format
    access_days_of_week = Column(JSONB, default=list)  # [0-6] where 0 is Monday
    access_timezone = Column(String(50), default="UTC")
    
    # Conditional access
    requires_mfa = Column(Boolean, default=False)
    requires_vpn = Column(Boolean, default=False)
    allowed_ip_ranges = Column(JSONB, nullable=True)
    allowed_countries = Column(JSONB, nullable=True)
    
    # Approval workflow
    requires_approval = Column(Boolean, default=False)
    approval_chain = Column(JSONB, default=list)  # List of role IDs in approval order
    auto_expire_hours = Column(Integer, nullable=True)  # Auto-expire after approval
    
    # Usage tracking
    usage_quota_daily = Column(Integer, nullable=True)
    usage_quota_monthly = Column(Integer, nullable=True)
    cost_per_use = Column(Float, nullable=True)
    
    # Metadata
    priority = Column(Integer, default=0)  # Higher priority overrides lower
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # System permissions can't be modified
    permission_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default='now()')
    updated_at = Column(DateTime(timezone=True), server_default='now()', onupdate='now()')
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    role = relationship("Role", back_populates="feature_permissions")
    user = relationship("User", back_populates="feature_permissions")
    usage_logs = relationship("FeatureUsageLog", back_populates="permission", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "(role_id IS NOT NULL) OR (user_id IS NOT NULL)",
            name="check_permission_target"
        ),
        Index("idx_feature_permissions_active", "is_active"),
        Index("idx_feature_permissions_feature_type", "feature_type"),
        Index("idx_feature_permissions_role_user", "role_id", "user_id"),
    )


class FeatureUsageLog(Base):
    """Log of feature permission usage."""
    
    __tablename__ = "feature_usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default='now()', index=True)
    
    # What was accessed
    permission_id = Column(UUID(as_uuid=True), ForeignKey("feature_permissions.id"), nullable=False)
    feature_type = Column(SQLEnum(FeatureType), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    resource_type = Column(String(100), nullable=True)
    
    # Who accessed it
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Access details
    was_allowed = Column(Boolean, nullable=False)
    denial_reason = Column(String(255), nullable=True)
    
    # Usage details
    data_accessed = Column(JSONB, nullable=True)  # What data was accessed/exported
    rows_affected = Column(Integer, nullable=True)
    export_format = Column(String(20), nullable=True)
    export_size_mb = Column(Float, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    # Cost tracking
    usage_cost = Column(Float, nullable=True)
    quota_used = Column(Integer, default=1)
    
    # Metadata
    request_id = Column(String(255), nullable=True)
    session_id = Column(String(255), nullable=True)
    permission_metadata = Column(JSONB, default=dict)
    
    # Relationships
    permission = relationship("FeaturePermission", back_populates="usage_logs")
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_feature_usage_logs_user_timestamp", "user_id", "timestamp"),
        Index("idx_feature_usage_logs_permission_timestamp", "permission_id", "timestamp"),
    )


class ReportTemplate(Base):
    """Predefined report templates with specific permissions."""
    
    __tablename__ = "report_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Template information
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    
    # Template configuration
    query_template = Column(Text, nullable=False)  # SQL or query builder template
    parameters = Column(JSONB, default=dict)  # Available parameters
    default_filters = Column(JSONB, default=dict)
    available_columns = Column(JSONB, default=list)
    default_columns = Column(JSONB, default=list)
    
    # Visualization settings
    chart_types = Column(JSONB, default=list)  # Allowed chart types
    default_chart_type = Column(String(50), nullable=True)
    visualization_config = Column(JSONB, default=dict)
    
    # Access control
    required_permission_level = Column(SQLEnum(DataSensitivity), default=DataSensitivity.INTERNAL)
    required_roles = Column(JSONB, default=list)  # Role IDs that can access
    excluded_roles = Column(JSONB, default=list)  # Role IDs that cannot access
    requires_approval = Column(Boolean, default=False)
    
    # Data restrictions
    max_date_range_days = Column(Integer, nullable=True)
    data_retention_days = Column(Integer, nullable=True)
    cache_duration_minutes = Column(Integer, default=60)
    
    # Export settings
    allow_export = Column(Boolean, default=True)
    export_formats = Column(JSONB, default=["csv", "excel", "pdf"])
    include_pii = Column(Boolean, default=False)
    include_financial = Column(Boolean, default=False)
    
    # Scheduling
    allow_scheduling = Column(Boolean, default=True)
    min_schedule_interval_hours = Column(Integer, default=24)
    
    # Cost
    execution_cost = Column(Float, default=1.0)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    tags = Column(JSONB, default=list)
    permission_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default='now()')
    updated_at = Column(DateTime(timezone=True), server_default='now()', onupdate='now()')
    
    # Relationships
    schedules = relationship("ReportSchedule", back_populates="template", cascade="all, delete-orphan")
    executions = relationship("ReportExecution", back_populates="template", cascade="all, delete-orphan")


class ReportSchedule(Base):
    """Scheduled report configurations."""
    
    __tablename__ = "report_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Schedule information
    name = Column(String(255), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False)
    
    # Schedule configuration
    cron_expression = Column(String(100), nullable=True)  # Cron format
    interval_hours = Column(Integer, nullable=True)  # Alternative to cron
    timezone = Column(String(50), default="UTC")
    
    # Report parameters
    parameters = Column(JSONB, default=dict)
    filters = Column(JSONB, default=dict)
    
    # Distribution
    recipients = Column(JSONB, default=list)  # Email addresses
    export_format = Column(SQLEnum(ExportFormat), default=ExportFormat.PDF)
    delivery_method = Column(String(50), default="email")  # email, webhook, s3, etc.
    delivery_config = Column(JSONB, default=dict)
    
    # Access control
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    failure_count = Column(Integer, default=0)
    
    # Metadata
    permission_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default='now()')
    updated_at = Column(DateTime(timezone=True), server_default='now()', onupdate='now()')
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="schedules")
    executions = relationship("ReportExecution", back_populates="schedule", cascade="all, delete-orphan")


class ReportExecution(Base):
    """Log of report executions."""
    
    __tablename__ = "report_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Execution information
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("report_schedules.id"), nullable=True)
    executed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Execution details
    started_at = Column(DateTime(timezone=True), server_default='now()', index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Parameters used
    parameters = Column(JSONB, default=dict)
    filters = Column(JSONB, default=dict)
    
    # Results
    row_count = Column(Integer, nullable=True)
    file_size_mb = Column(Float, nullable=True)
    export_format = Column(String(20), nullable=True)
    file_path = Column(String(500), nullable=True)  # S3 or local path
    
    # Performance
    query_time_ms = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    memory_used_mb = Column(Float, nullable=True)
    
    # Cost
    execution_cost = Column(Float, nullable=True)
    
    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    permission_metadata = Column(JSONB, default=dict)
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="executions")
    schedule = relationship("ReportSchedule", back_populates="executions")
    executed_by = relationship("User")