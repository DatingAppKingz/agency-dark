"""
Model Assignment - Maps chatters to models they can manage.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from core.database import Base


class ModelAssignment(Base):
    """Represents the assignment of a chatter to a model."""
    
    __tablename__ = "model_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    chatter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Assignment details
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Optional fields
    notes = Column(String, nullable=True)
    priority = Column(String, default="normal")  # high, normal, low
    
    # Relationships
    chatter = relationship("User", foreign_keys=[chatter_id], backref="model_assignments")
    model = relationship("User", foreign_keys=[model_id], backref="chatter_assignments")
    agency = relationship("Agency", backref="model_assignments")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    
    # Ensure unique assignment per chatter-model pair
    __table_args__ = (
        UniqueConstraint('chatter_id', 'model_id', name='unique_chatter_model_assignment'),
    )
    
    def __repr__(self):
        return f"<ModelAssignment(chatter_id={self.chatter_id}, model_id={self.model_id}, active={self.is_active})>"