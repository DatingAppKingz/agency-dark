"""Model settings and schedule."""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, Numeric, JSON, Time
from sqlalchemy.orm import relationship
from datetime import time
from decimal import Decimal
from models.base import BaseModel


class ModelSettings(BaseModel):
    """Settings for a model profile."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "model_settings"
    
    # Foreign key
    model_id = Column(Integer, ForeignKey("models.id"), unique=True, nullable=False)
    
    # Auto-welcome settings
    auto_welcome_enabled = Column(Boolean, default=True, nullable=False)
    welcome_message = Column(Text, nullable=True)
    welcome_delay_seconds = Column(Integer, default=30, nullable=False)
    
    # Auto-response settings
    auto_response_enabled = Column(Boolean, default=False, nullable=False)
    response_delay_min = Column(Integer, default=1, nullable=False)  # minutes
    response_delay_max = Column(Integer, default=3, nullable=False)  # minutes
    
    # PPV settings
    ppv_enabled = Column(Boolean, default=True, nullable=False)
    ppv_min_price = Column(Numeric(10, 2), default=5.00, nullable=False)
    ppv_max_price = Column(Numeric(10, 2), default=100.00, nullable=False)
    ppv_watermark_enabled = Column(Boolean, default=True, nullable=False)
    
    # Tip menu settings
    tip_menu_enabled = Column(Boolean, default=True, nullable=False)
    tip_menu = Column(JSON, nullable=True)  # JSON structure for tip menu items
    
    # Chat settings
    chat_price_per_minute = Column(Numeric(10, 2), default=0, nullable=False)
    mass_message_enabled = Column(Boolean, default=False, nullable=False)
    voice_message_enabled = Column(Boolean, default=True, nullable=False)
    
    # Content settings
    content_categories = Column(JSON, nullable=True)  # List of content categories
    blocked_words = Column(JSON, nullable=True)  # List of blocked words
    
    # AI settings
    ai_enabled = Column(Boolean, default=False, nullable=False)
    ai_personality = Column(Text, nullable=True)
    ai_tone = Column(String(50), default="friendly", nullable=False)
    
    # Commission settings
    commission_rate = Column(Numeric(5, 2), default=20.00, nullable=False)
    
    # Notification settings
    notification_new_subscriber = Column(Boolean, default=True, nullable=False)
    notification_new_message = Column(Boolean, default=True, nullable=False)
    notification_new_tip = Column(Boolean, default=True, nullable=False)
    notification_expiring_fans = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    model = relationship("Model", uselist=False)


class ModelSchedule(BaseModel):
    """Working schedule for a model."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "model_schedules"
    
    # Foreign key
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    
    # Schedule details
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    model = relationship("Model")