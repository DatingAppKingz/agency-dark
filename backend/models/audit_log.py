"""
Comprehensive audit log models for tracking all system activities.
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Index, Text, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from models.base import Base


class AuditAction(str, enum.Enum):
    """Types of auditable actions."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_PERMISSIONS_CHANGED = "user_permissions_changed"
    
    # Model Management
    MODEL_CREATED = "model_created"
    MODEL_UPDATED = "model_updated"
    MODEL_DELETED = "model_deleted"
    MODEL_ASSIGNED = "model_assigned"
    MODEL_UNASSIGNED = "model_unassigned"
    
    # Financial
    TRANSACTION_CREATED = "transaction_created"
    TRANSACTION_UPDATED = "transaction_updated"
    TRANSACTION_DELETED = "transaction_deleted"
    PAYOUT_INITIATED = "payout_initiated"
    PAYOUT_APPROVED = "payout_approved"
    PAYOUT_REJECTED = "payout_rejected"
    COMMISSION_CALCULATED = "commission_calculated"
    
    # Chat/Communication
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELETED = "message_deleted"
    CONVERSATION_CREATED = "conversation_created"
    CONVERSATION_ARCHIVED = "conversation_archived"
    BULK_MESSAGE_SENT = "bulk_message_sent"
    
    # API Keys
    API_KEY_CREATED = "api_key_created"
    API_KEY_ROTATED = "api_key_rotated"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"
    
    # Data Access
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    REPORT_GENERATED = "report_generated"
    ANALYTICS_VIEWED = "analytics_viewed"
    
    # System
    SETTINGS_CHANGED = "settings_changed"
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    WEBHOOK_CONFIGURED = "webhook_configured"
    SYNC_INITIATED = "sync_initiated"
    
    # Security
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    IP_BLOCKED = "ip_blocked"
    
    # Compliance
    DATA_RETENTION_APPLIED = "data_retention_applied"
    USER_DATA_REQUESTED = "user_data_requested"
    USER_DATA_DELETED = "user_data_deleted"
    AUDIT_EXPORTED = "audit_exported"


class AuditSeverity(str, enum.Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Comprehensive audit log for all system activities."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index('idx_audit_logs_timestamp', 'timestamp'),
        Index('idx_audit_logs_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_logs_agency_timestamp', 'agency_id', 'timestamp'),
        Index('idx_audit_logs_action_timestamp', 'action', 'timestamp'),
        Index('idx_audit_logs_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_logs_ip', 'ip_address'),
        {"extend_existing": True}
    )
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # When
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Who
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True)
    impersonator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("platform_api_keys.id", ondelete="SET NULL"), nullable=True)
    
    # What
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True, index=True)  # e.g., "user", "model", "transaction"
    resource_id = Column(String(255), nullable=True)  # ID of the affected resource
    resource_name = Column(String(255), nullable=True)  # Human-readable name
    
    # Details
    description = Column(Text, nullable=True)  # Human-readable description
    changes = Column(JSONB, nullable=True)  # Before/after values for updates
    audit_metadata = Column(JSONB, nullable=True)  # Additional context
    
    # Where
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)  # Geo-location if available
    
    # Context
    session_id = Column(String(255), nullable=True)  # For tracking user sessions
    request_id = Column(String(255), nullable=True)  # For correlating with logs
    correlation_id = Column(String(255), nullable=True)  # For tracking across services
    
    # Security
    severity = Column(SQLEnum(AuditSeverity), default=AuditSeverity.INFO, nullable=False)
    risk_score = Column(Integer, nullable=True)  # 0-100 risk assessment
    flagged = Column(Boolean, default=False, nullable=False)  # For security review
    
    # Compliance
    retention_days = Column(Integer, nullable=True)  # Override default retention
    compliance_tags = Column(JSONB, nullable=True)  # e.g., ["gdpr", "financial"]
    exported = Column(Boolean, default=False, nullable=False)
    export_date = Column(DateTime(timezone=True), nullable=True)
    
    # Performance
    duration_ms = Column(Integer, nullable=True)  # For performance tracking
    
    # Relationships - Comment out for now to avoid mapper issues
    # We'll use lazy loading and direct queries instead of relationships
    # until we can properly fix the circular dependency issues
    
    # user = relationship("User", 
    #                    foreign_keys=[user_id], 
    #                    backref="audit_logs_as_user")
    # impersonator = relationship("User", 
    #                            foreign_keys=[impersonator_id],
    #                            backref="audit_logs_as_impersonator")
    # agency = relationship("Agency", 
    #                      foreign_keys=[agency_id],
    #                      backref="audit_logs")
    # api_key = relationship("PlatformAPIKey", 
    #                       foreign_keys=[api_key_id],
    #                       backref="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"
    
    def to_dict(self):
        """Convert to dictionary for export."""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "user_id": str(self.user_id) if self.user_id else None,
            "agency_id": str(self.agency_id) if self.agency_id else None,
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "changes": self.changes,
            "metadata": self.audit_metadata,
            "ip_address": self.ip_address,
            "severity": self.severity.value,
            "risk_score": self.risk_score
        }


class AuditLogRetentionPolicy(Base):
    """Data retention policies for audit logs."""
    __tablename__ = "audit_log_retention_policies"
    __table_args__ = {"extend_existing": True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Policy details
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Retention rules
    action_pattern = Column(String(255), nullable=True)  # Regex pattern for actions
    resource_type_pattern = Column(String(255), nullable=True)  # Regex pattern
    severity = Column(SQLEnum(AuditSeverity), nullable=True)
    
    # Retention period
    retention_days = Column(Integer, nullable=False)  # How long to keep
    delete_after_export = Column(Boolean, default=False)  # Delete after archiving
    
    # Policy metadata
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher = higher priority
    compliance_requirement = Column(String(100), nullable=True)  # e.g., "GDPR", "SOX"
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    def __repr__(self):
        return f"<AuditLogRetentionPolicy {self.name} - {self.retention_days} days>"


class AuditLogExport(Base):
    """Track audit log exports for compliance."""
    __tablename__ = "audit_log_exports"
    __table_args__ = {"extend_existing": True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Export details
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    exported_at = Column(DateTime(timezone=True), server_default=func.now())
    exported_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Filters applied
    filters = Column(JSONB, nullable=True)  # What filters were used
    record_count = Column(Integer, nullable=False)
    
    # Export location
    storage_location = Column(String(500), nullable=True)  # S3 URL, file path, etc.
    file_hash = Column(String(255), nullable=True)  # SHA-256 of export
    file_size_bytes = Column(Integer, nullable=True)
    
    # Compliance
    purpose = Column(String(255), nullable=True)  # Why exported
    authorized_by = Column(String(255), nullable=True)  # Who authorized
    compliance_tags = Column(JSONB, nullable=True)
    
    # Security
    encrypted = Column(Boolean, default=True, nullable=False)
    encryption_key_id = Column(String(255), nullable=True)
    
    # Relationships
    exported_by = relationship("User", foreign_keys=[exported_by_id])
    
    def __repr__(self):
        return f"<AuditLogExport {self.start_date} to {self.end_date}>"


class AuditLogAlert(Base):
    """Alerts triggered by audit log patterns."""
    __tablename__ = "audit_log_alerts"
    __table_args__ = {"extend_existing": True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Alert configuration
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Trigger conditions
    action_pattern = Column(String(255), nullable=True)  # Regex for actions
    threshold_count = Column(Integer, nullable=True)  # Number of events
    threshold_minutes = Column(Integer, nullable=True)  # Time window
    severity_threshold = Column(SQLEnum(AuditSeverity), nullable=True)
    risk_score_threshold = Column(Integer, nullable=True)
    
    # Alert details
    is_active = Column(Boolean, default=True, nullable=False)
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)
    
    # Notification
    notify_emails = Column(JSONB, nullable=True)  # List of emails
    notify_webhook = Column(String(500), nullable=True)
    notify_in_app = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    def __repr__(self):
        return f"<AuditLogAlert {self.name}>"