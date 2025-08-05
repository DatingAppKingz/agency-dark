"""Subscriber models for platform users."""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Numeric, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from models.base import BaseModel


class SubscriptionTier(str, enum.Enum):
    """Subscription tier levels."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    VIP = "vip"
    CUSTOM = "custom"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class Subscriber(BaseModel):
    """Represents a subscriber to a model."""
    __tablename__ = "subscribers"
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    
    # Platform info
    platform_user_id = Column(String(255), nullable=True)  # Platform-specific user ID
    username = Column(String(100), nullable=True)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Subscription details
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    subscription_price = Column(Numeric(10, 2), default=0, nullable=False)
    
    # Dates
    subscribed_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    expires_at = Column(String(50), nullable=True)
    last_seen_at = Column(String(50), nullable=True)
    
    # Preferences
    auto_renew = Column(Boolean, default=True, nullable=False)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    
    # Status flags
    is_vip = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    is_restricted = Column(Boolean, default=False, nullable=False)
    
    # Analytics
    total_spent = Column(Numeric(10, 2), default=0, nullable=False)
    total_tips = Column(Numeric(10, 2), default=0, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user = relationship("User", backref="subscriptions", foreign_keys=[user_id])
    model = relationship("Model", backref="subscribers", foreign_keys=[model_id])
    claims = relationship("FanClaim", back_populates="fan", cascade="all, delete-orphan")
    
    # Unique constraint - one subscription per user per model
    __table_args__ = (
        UniqueConstraint('user_id', 'model_id', name='_user_model_uc'),
    )