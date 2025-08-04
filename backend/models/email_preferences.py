"""Email preferences model for managing user notification settings."""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from core.database import Base
from models.base import BaseModel


class EmailPreferences(BaseModel):
    """User email notification preferences."""
    __tablename__ = "email_preferences"
    
    # User reference
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Global settings
    email_enabled = Column(Boolean, default=True, nullable=False)
    email_address = Column(String(255), nullable=True)  # Override email if different from user email
    
    # Notification categories
    # Account notifications
    account_updates = Column(Boolean, default=True, nullable=False)
    security_alerts = Column(Boolean, default=True, nullable=False)
    
    # Model notifications
    model_approval = Column(Boolean, default=True, nullable=False)
    model_updates = Column(Boolean, default=True, nullable=False)
    
    # Financial notifications
    payout_created = Column(Boolean, default=True, nullable=False)
    payout_approved = Column(Boolean, default=True, nullable=False)
    payout_completed = Column(Boolean, default=True, nullable=False)
    invoice_created = Column(Boolean, default=True, nullable=False)
    payment_received = Column(Boolean, default=True, nullable=False)
    
    # Activity notifications
    daily_summary = Column(Boolean, default=True, nullable=False)
    weekly_report = Column(Boolean, default=True, nullable=False)
    monthly_statement = Column(Boolean, default=True, nullable=False)
    
    # Marketing notifications
    product_updates = Column(Boolean, default=True, nullable=False)
    tips_and_tricks = Column(Boolean, default=True, nullable=False)
    promotional_offers = Column(Boolean, default=False, nullable=False)
    
    # Communication preferences
    chat_notifications = Column(Boolean, default=True, nullable=False)
    mention_notifications = Column(Boolean, default=True, nullable=False)
    
    # Frequency settings
    notification_frequency = Column(String(20), default="realtime", nullable=False)  # realtime, hourly, daily
    quiet_hours_enabled = Column(Boolean, default=False, nullable=False)
    quiet_hours_start = Column(String(5), nullable=True)  # HH:MM format
    quiet_hours_end = Column(String(5), nullable=True)  # HH:MM format
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Language preference
    language = Column(String(10), default="en", nullable=False)
    
    # Unsubscribe
    unsubscribe_token = Column(String(255), unique=True, nullable=True)
    unsubscribed_at = Column(String(30), nullable=True)
    unsubscribe_reason = Column(String(500), nullable=True)
    
    # Custom preferences (JSON for flexibility)
    custom_preferences = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    user = relationship("User", backref="email_preferences")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_email_preferences_user'),
    )
    
    def __repr__(self):
        return f"<EmailPreferences user_id={self.user_id} enabled={self.email_enabled}>"
    
    def should_send_notification(self, notification_type: str) -> bool:
        """Check if user should receive a specific notification type."""
        if not self.email_enabled:
            return False
        
        if self.unsubscribed_at:
            return False
        
        # Map notification types to preference fields
        preference_map = {
            'account_update': self.account_updates,
            'security_alert': self.security_alerts,
            'model_approval': self.model_approval,
            'model_update': self.model_updates,
            'payout_created': self.payout_created,
            'payout_approved': self.payout_approved,
            'payout_completed': self.payout_completed,
            'invoice_created': self.invoice_created,
            'payment_received': self.payment_received,
            'daily_summary': self.daily_summary,
            'weekly_report': self.weekly_report,
            'monthly_statement': self.monthly_statement,
            'product_update': self.product_updates,
            'tips_and_tricks': self.tips_and_tricks,
            'promotional_offer': self.promotional_offers,
            'chat_notification': self.chat_notifications,
            'mention_notification': self.mention_notifications,
        }
        
        return preference_map.get(notification_type, True)
    
    def get_email_address(self) -> str:
        """Get the preferred email address."""
        return self.email_address or self.user.email if self.user else None