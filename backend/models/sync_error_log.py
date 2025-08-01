"""Model for sync error logging."""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class SyncErrorLog(Base):
    """Log of sync errors for analysis and monitoring."""
    
    __tablename__ = "sync_error_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Error details
    error_type = Column(String(50), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    error_code = Column(String(50), nullable=True, index=True)
    retry_count = Column(Integer, default=0)
    
    # Context
    sync_job_id = Column(String, nullable=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True, index=True)
    service_id = Column(String(100), nullable=True, index=True)
    
    # Error location
    item_id = Column(String, nullable=True)
    batch_number = Column(Integer, nullable=True)
    operation_type = Column(String(50), nullable=True)  # fetch, transform, save, etc.
    
    # Technical details
    stack_trace = Column(Text, nullable=True)
    context_data = Column(JSON, nullable=True)
    
    # Recovery information
    recovery_strategy = Column(String(50), nullable=True)
    recovery_successful = Column(Boolean, nullable=True)
    recovery_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    api_key = relationship("APIKey", back_populates="sync_errors")
    agency = relationship("Agency")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_sync_error_logs_occurred_at_desc', occurred_at.desc()),
        Index('ix_sync_error_logs_error_type_occurred_at', error_type, occurred_at),
        Index('ix_sync_error_logs_api_key_error_type', api_key_id, error_type),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "sync_job_id": self.sync_job_id,
            "api_key_id": self.api_key_id,
            "service_id": self.service_id,
            "item_id": self.item_id,
            "recovery_strategy": self.recovery_strategy,
            "recovery_successful": self.recovery_successful,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }