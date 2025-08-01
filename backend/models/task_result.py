"""Task result model for tracking background tasks."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum

from core.database import Base


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class TaskResult(Base):
    """Task result tracking model."""
    
    __tablename__ = "task_results"
    
    # Use task_id as primary key (from Celery)
    task_id = Column(String(255), primary_key=True)
    
    # Task information
    task_name = Column(String(255), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    
    # User and agency tracking
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    
    # Task parameters and results
    params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    traceback = Column(String, nullable=True)
    
    # Retry information
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    agency = relationship("Agency", back_populates="tasks")
    
    def __repr__(self):
        return f"<TaskResult {self.task_id} ({self.task_name}) - {self.status.value}>"
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if task is complete (success or failure)."""
        return self.status in [TaskStatus.SUCCESS, TaskStatus.FAILURE]
    
    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status in [TaskStatus.PENDING, TaskStatus.STARTED, TaskStatus.RETRY]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "user_id": str(self.user_id),
            "agency_id": str(self.agency_id) if self.agency_id else None,
            "params": self.params,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration
        }