"""Audit log models."""

from sqlalchemy import Column, String, JSON, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base, BaseModel


class AuditLog(BaseModel):
    """Audit log for tracking system events and user actions."""
    
    __tablename__ = "audit_logs"
    
    # User who performed the action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", foreign_keys=[user_id])
    
    # What action was performed
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    
    # Additional context
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Request tracking
    request_id = Column(String(255), nullable=True, index=True)
    
    # Result of the action
    status = Column(String(20), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<AuditLog {self.action} by user {self.user_id} at {self.created_at}>"