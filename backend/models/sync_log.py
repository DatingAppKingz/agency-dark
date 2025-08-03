"""Sync log model."""

from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
from models.base import BaseModel


class SyncLog(BaseModel):
    """Log of sync operations."""
    
    __tablename__ = "sync_logs"
    
    # Sync details
    sync_type = Column(String(50), nullable=False)  # messages, media, subscribers, etc.
    platform = Column(String(50), nullable=False)  # onlyfans, fansly, etc.
    status = Column(String(50), nullable=False)  # pending, running, completed, failed
    
    # Model being synced
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    model = relationship("Model")
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    items_processed = Column(Integer, default=0)
    items_created = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, default=dict)
    
    def __repr__(self):
        return f"<SyncLog {self.sync_type} for model {self.model_id} - {self.status}>"