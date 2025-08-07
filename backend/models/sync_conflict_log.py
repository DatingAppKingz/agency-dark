"""Model for sync conflict logging."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base
from services.sync.conflict_resolver import ConflictType, ResolutionAction


class SyncConflictLog(Base):
    """Log of sync conflicts and their resolutions."""
    
    __tablename__ = "sync_conflict_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Sync context
    sync_job_id = Column(String, nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, index=True)
    
    # Conflict details
    conflict_type = Column(SQLEnum(ConflictType), nullable=False)
    entity_type = Column(String, nullable=False)  # e.g., "model", "transaction", "subscriber"
    local_id = Column(String, nullable=False)
    remote_id = Column(String, nullable=False)
    
    # Conflict data
    field_conflicts = Column(JSON, nullable=True)  # List of field-level conflicts
    local_data_snapshot = Column(JSON, nullable=True)  # Snapshot of local data
    remote_data_snapshot = Column(JSON, nullable=True)  # Snapshot of remote data
    
    # Resolution details
    resolution_action = Column(SQLEnum(ResolutionAction), nullable=False)
    resolved_data = Column(JSON, nullable=True)  # Final resolved data
    merge_conflicts = Column(JSON, nullable=True)  # Conflicts that couldn't be auto-merged
    manual_review_required = Column(Boolean, default=False)
    
    # Resolution metadata
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    auto_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    api_key = relationship("APIKey", back_populates="sync_conflicts")
    agency = relationship("Agency")
    resolver = relationship("User", foreign_keys=[resolved_by])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "sync_job_id": self.sync_job_id,
            "api_key_id": str(self.api_key_id) if self.api_key_id else None,
            "conflict_type": self.conflict_type.value if self.conflict_type else None,
            "entity_type": self.entity_type,
            "local_id": self.local_id,
            "remote_id": self.remote_id,
            "field_conflicts": self.field_conflicts,
            "resolution_action": self.resolution_action.value if self.resolution_action else None,
            "manual_review_required": self.manual_review_required,
            "resolved_by": str(self.resolved_by) if self.resolved_by else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "auto_resolved": self.auto_resolved,
            "created_at": self.created_at.isoformat()
        }