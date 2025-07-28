"""
API Key Audit Log Model
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class APIKeyAudit(Base):
    """Audit log for API key operations"""
    __tablename__ = "api_key_audits"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Audit information
    action = Column(String(50), nullable=False)  # created, used, rotated, revoked, failed_verification
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    api_key = relationship("APIKey", back_populates="audit_logs")
    user = relationship("User", backref="api_key_audits")