"""Scheduled task model."""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Text, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class ScheduledTask(Base):
    """Scheduled task configuration."""
    __tablename__ = "scheduled_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Task configuration
    task_type = Column(String(50), nullable=False)  # report_generation, data_sync, etc.
    cron_expression = Column(String(100), nullable=False)
    parameters = Column(JSON, default=dict)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_run = Column(DateTime)
    last_run_status = Column(String(20))  # success, failed, partial
    last_run_result = Column(JSON)
    next_run = Column(DateTime)
    run_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    
    # Ownership
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="scheduled_tasks")
    created_by = relationship("User", back_populates="created_scheduled_tasks")
    executions = relationship("ScheduledTaskExecution", back_populates="task", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_scheduled_task_agency", "agency_id"),
        Index("idx_scheduled_task_type", "task_type"),
        Index("idx_scheduled_task_active", "is_active"),
        Index("idx_scheduled_task_next_run", "next_run"),
    )
    
    def __repr__(self):
        return f"<ScheduledTask(name={self.name}, type={self.task_type}, cron={self.cron_expression})>"


class ScheduledTaskExecution(Base):
    """Record of scheduled task executions."""
    __tablename__ = "scheduled_task_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False)
    
    # Execution details
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Status
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    result = Column(JSON)
    error_message = Column(Text)
    
    # Metrics
    records_processed = Column(Integer)
    records_failed = Column(Integer)
    
    # Relationships
    task = relationship("ScheduledTask", back_populates="executions")
    
    # Indexes
    __table_args__ = (
        Index("idx_execution_task", "task_id"),
        Index("idx_execution_started", "started_at"),
        Index("idx_execution_status", "status"),
    )
    
    def __repr__(self):
        return f"<ScheduledTaskExecution(task_id={self.task_id}, status={self.status})>"