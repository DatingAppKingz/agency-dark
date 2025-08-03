"""Fan claim models."""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
from models.base import BaseModel


class FanClaim(BaseModel):
    """Represents a claim or request made by a fan."""
    
    __tablename__ = "fan_claims"
    
    # Fan who made the claim
    fan_id = Column(Integer, ForeignKey("subscribers.id"), nullable=False)
    fan = relationship("Subscriber", back_populates="claims")
    
    # Claim details
    claim_type = Column(String(50), nullable=False)  # refund, dispute, etc.
    status = Column(String(50), default="pending", nullable=False)
    description = Column(Text, nullable=False)
    resolution = Column(Text, nullable=True)
    
    # Tracking
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by = relationship("User")
    
    def __repr__(self):
        return f"<FanClaim {self.id} - {self.claim_type} ({self.status})>"