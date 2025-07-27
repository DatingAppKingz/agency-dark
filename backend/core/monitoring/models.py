"""
Monitoring system models.
"""
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, Boolean, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from core.database import Base


class MetricType(str, Enum):
    """Types of metrics collected."""
    SYSTEM_CPU = "system_cpu"
    SYSTEM_MEMORY = "system_memory"
    SYSTEM_DISK = "system_disk"
    SYSTEM_NETWORK = "system_network"
    API_REQUEST_COUNT = "api_request_count"
    API_REQUEST_DURATION = "api_request_duration"
    API_ERROR_RATE = "api_error_rate"
    API_THROUGHPUT = "api_throughput"
    DATABASE_CONNECTIONS = "database_connections"
    DATABASE_QUERY_TIME = "database_query_time"
    DATABASE_POOL_SIZE = "database_pool_size"
    CACHE_HIT_RATE = "cache_hit_rate"
    CACHE_MEMORY_USAGE = "cache_memory_usage"
    CACHE_OPERATIONS = "cache_operations"
    WEBSOCKET_CONNECTIONS = "websocket_connections"
    WEBSOCKET_MESSAGES = "websocket_messages"
    QUEUE_SIZE = "queue_size"
    QUEUE_PROCESSING_TIME = "queue_processing_time"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    MUTED = "muted"


class ServiceStatus(str, Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"


class Metric(Base):
    """System and application metrics."""
    __tablename__ = "metrics"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    metric_type = Column(String, nullable=False, index=True)
    metric_name = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String)  # e.g., "percent", "bytes", "milliseconds"
    
    # Dimensions/tags for filtering
    tags = Column(JSON, default=dict)  # e.g., {"endpoint": "/api/v1/users", "method": "GET"}
    
    # Optional reference to specific entity
    entity_type = Column(String)  # e.g., "api_endpoint", "database", "cache"
    entity_id = Column(String)
    
    # Metadata
    hostname = Column(String, index=True)
    service_name = Column(String, index=True)
    environment = Column(String, default="production")  # production, staging, development
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_metric_type_timestamp', 'metric_type', 'timestamp'),
        Index('idx_metric_name_timestamp', 'metric_name', 'timestamp'),
        Index('idx_service_timestamp', 'service_name', 'timestamp'),
    )


class ServiceHealth(Base):
    """Service health checks."""
    __tablename__ = "service_health"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default=ServiceStatus.UNKNOWN)
    
    # Health check details
    check_name = Column(String, nullable=False)  # e.g., "database_connectivity", "redis_ping"
    response_time_ms = Column(Float)
    
    # Additional context
    details = Column(JSON, default=dict)  # e.g., {"error": "Connection timeout", "latency": 150}
    dependencies = Column(JSON, default=list)  # List of dependent services
    
    # Timestamps
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_healthy_at = Column(DateTime)
    
    # For tracking state changes
    previous_status = Column(String)
    status_changed_at = Column(DateTime)
    consecutive_failures = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint('service_name', 'check_name', name='uq_service_check'),
        Index('idx_service_status', 'service_name', 'status'),
    )


class AlertRule(Base):
    """Alert rule definitions."""
    __tablename__ = "alert_rules"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    
    # Rule configuration
    metric_type = Column(String, nullable=False)
    condition = Column(String, nullable=False)  # e.g., "greater_than", "less_than", "equals"
    threshold = Column(Float, nullable=False)
    
    # Advanced conditions
    query = Column(Text)  # Custom query for complex conditions
    aggregation = Column(String)  # e.g., "avg", "sum", "max", "min"
    time_window_minutes = Column(Integer, default=5)
    
    # Alert properties
    severity = Column(String, nullable=False, default=AlertSeverity.WARNING)
    tags = Column(JSON, default=dict)
    
    # Notification settings
    notification_channels = Column(JSON, default=list)  # List of channel configs
    cooldown_minutes = Column(Integer, default=30)  # Prevent alert spam
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    alerts = relationship("Alert", back_populates="rule", cascade="all, delete-orphan")


class Alert(Base):
    """Alert instances."""
    __tablename__ = "alerts"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(PGUUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"))
    
    # Alert details
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False, default=AlertStatus.ACTIVE)
    
    # Triggering metric details
    metric_value = Column(Float)
    threshold_value = Column(Float)
    metric_details = Column(JSON, default=dict)
    
    # Timestamps
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    
    # User tracking
    acknowledged_by = Column(PGUUID(as_uuid=True))
    resolved_by = Column(PGUUID(as_uuid=True))
    
    # Additional context
    tags = Column(JSON, default=dict)
    notes = Column(Text)
    
    # Relationships
    rule = relationship("AlertRule", back_populates="alerts")
    notifications = relationship("AlertNotification", back_populates="alert", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_alert_status', 'status'),
        Index('idx_alert_triggered', 'triggered_at'),
    )


class AlertNotification(Base):
    """Alert notification history."""
    __tablename__ = "alert_notifications"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_id = Column(PGUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"))
    
    # Notification details
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=False)  # email, phone, webhook URL, etc.
    
    # Status
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered = Column(Boolean, default=False)
    error_message = Column(Text)
    
    # Response tracking
    response_code = Column(Integer)
    response_body = Column(Text)
    
    # Relationships
    alert = relationship("Alert", back_populates="notifications")


class PerformanceProfile(Base):
    """Performance profiling data."""
    __tablename__ = "performance_profiles"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Request identification
    request_id = Column(String, unique=True, index=True)
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    
    # Timing breakdown
    total_duration_ms = Column(Float, nullable=False)
    db_duration_ms = Column(Float)
    cache_duration_ms = Column(Float)
    external_api_duration_ms = Column(Float)
    processing_duration_ms = Column(Float)
    
    # Resource usage
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    
    # Query analysis
    query_count = Column(Integer, default=0)
    slow_queries = Column(JSON, default=list)  # List of slow query details
    
    # Cache performance
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)
    
    # Additional context
    user_id = Column(PGUUID(as_uuid=True))
    agency_id = Column(PGUUID(as_uuid=True))
    status_code = Column(Integer)
    error_details = Column(JSON)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_performance_endpoint_timestamp', 'endpoint', 'timestamp'),
    )


class MonitoringDashboard(Base):
    """Custom monitoring dashboards."""
    __tablename__ = "monitoring_dashboards"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Dashboard configuration
    layout = Column(JSON, nullable=False)  # Grid layout configuration
    widgets = Column(JSON, nullable=False)  # Widget definitions
    refresh_interval_seconds = Column(Integer, default=30)
    
    # Access control
    is_public = Column(Boolean, default=False)
    owner_id = Column(PGUUID(as_uuid=True))
    shared_with = Column(JSON, default=list)  # List of user IDs
    
    # Metadata
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)