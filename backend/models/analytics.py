from sqlalchemy import Column, String, Integer, ForeignKey, Numeric, JSON, Index, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from models.base import Base, BaseModel


class ModelAnalytics(BaseModel):
    """Daily analytics for models."""
    __tablename__ = "model_analytics"
    
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD format
    
    # Audience metrics
    followers_count = Column(Integer, default=0, nullable=False)
    followers_change = Column(Integer, default=0, nullable=False)  # Daily change
    subscribers_count = Column(Integer, default=0, nullable=False)
    subscribers_change = Column(Integer, default=0, nullable=False)
    
    # Engagement metrics
    messages_received = Column(Integer, default=0, nullable=False)
    messages_sent = Column(Integer, default=0, nullable=False)
    posts_created = Column(Integer, default=0, nullable=False)
    likes_received = Column(Integer, default=0, nullable=False)
    comments_received = Column(Integer, default=0, nullable=False)
    
    # Financial metrics
    revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    tips_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    ppv_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    subscription_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Conversion metrics
    profile_views = Column(Integer, default=0, nullable=False)
    conversion_rate = Column(Numeric(5, 2), default=0.00, nullable=False)  # Percentage
    
    # Content metrics
    photos_posted = Column(Integer, default=0, nullable=False)
    videos_posted = Column(Integer, default=0, nullable=False)
    avg_response_time = Column(Integer, default=0, nullable=False)  # In minutes
    
    # Top performers
    top_tipper_id = Column(String(255), nullable=True)
    top_tipper_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    top_spender_id = Column(String(255), nullable=True)
    top_spender_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    
    # Additional data
    hourly_breakdown = Column(JSON, default=dict, nullable=False)  # Revenue by hour
    fan_countries = Column(JSON, default=dict, nullable=False)  # Fan distribution
    
    # Relationships
    model = relationship("Model", back_populates="analytics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('model_id', 'date', name='uq_model_analytics_date'),
        Index('idx_model_analytics_date', 'date'),
        Index('idx_model_analytics_model_date', 'model_id', 'date'),
    )
    
    def __repr__(self):
        return f"<ModelAnalytics Model:{self.model_id} Date:{self.date}>"


class ConversationAnalytics(BaseModel):
    """Analytics for conversation performance."""
    __tablename__ = "conversation_analytics"
    
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)
    
    # Engagement
    messages_sent = Column(Integer, default=0, nullable=False)
    messages_received = Column(Integer, default=0, nullable=False)
    response_time_avg = Column(Integer, default=0, nullable=False)  # In minutes
    response_time_min = Column(Integer, default=0, nullable=False)
    response_time_max = Column(Integer, default=0, nullable=False)
    
    # Financial
    revenue = Column(Numeric(10, 2), default=0.00, nullable=False)
    tips_count = Column(Integer, default=0, nullable=False)
    tips_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    ppv_count = Column(Integer, default=0, nullable=False)
    ppv_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    
    # Quality metrics
    sentiment_score = Column(Numeric(3, 2), default=0.00, nullable=False)  # -1 to 1
    engagement_score = Column(Numeric(5, 2), default=0.00, nullable=False)  # 0 to 100
    
    # Relationships
    conversation = relationship("Conversation", back_populates="analytics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('conversation_id', 'date', name='uq_conversation_analytics_date'),
        Index('idx_conversation_analytics_date', 'date'),
    )
    
    def __repr__(self):
        return f"<ConversationAnalytics Conv:{self.conversation_id} Date:{self.date}>"


class ChatterPerformance(BaseModel):
    """Track chatter performance metrics."""
    __tablename__ = "chatter_performance"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)
    
    # Activity metrics
    conversations_handled = Column(Integer, default=0, nullable=False)
    messages_sent = Column(Integer, default=0, nullable=False)
    active_hours = Column(Numeric(4, 2), default=0.00, nullable=False)
    
    # Response metrics
    avg_response_time = Column(Integer, default=0, nullable=False)  # In seconds
    first_response_time = Column(Integer, default=0, nullable=False)
    
    # Financial performance
    revenue_generated = Column(Numeric(12, 2), default=0.00, nullable=False)
    tips_generated = Column(Numeric(12, 2), default=0.00, nullable=False)
    ppv_sold = Column(Integer, default=0, nullable=False)
    ppv_revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Quality metrics
    fan_satisfaction_score = Column(Numeric(3, 2), default=0.00, nullable=False)  # 0 to 5
    conversion_rate = Column(Numeric(5, 2), default=0.00, nullable=False)  # Percentage
    retention_rate = Column(Numeric(5, 2), default=0.00, nullable=False)  # Percentage
    
    # Goals and targets
    daily_target = Column(Numeric(10, 2), default=0.00, nullable=False)
    target_achieved = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    chatter = relationship("User", back_populates="performance_metrics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_chatter_performance_date'),
        Index('idx_chatter_performance_date', 'date'),
        Index('idx_chatter_performance_user_date', 'user_id', 'date'),
    )
    
    def __repr__(self):
        return f"<ChatterPerformance User:{self.user_id} Date:{self.date}>"
    
    @property
    def efficiency_score(self):
        """Calculate efficiency score."""
        if self.conversations_handled == 0:
            return 0
        return round((self.revenue_generated / self.conversations_handled) * 
                    (1 - min(self.avg_response_time / 300, 1)), 2)  # 5min response time baseline


class AgencyMetrics(BaseModel):
    """Agency-wide performance metrics."""
    __tablename__ = "agency_metrics"
    
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)
    
    # Model metrics
    active_models = Column(Integer, default=0, nullable=False)
    total_models = Column(Integer, default=0, nullable=False)
    
    # Chatter metrics
    active_chatters = Column(Integer, default=0, nullable=False)
    total_conversations = Column(Integer, default=0, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    
    # Financial metrics
    gross_revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    commission_earned = Column(Numeric(12, 2), default=0.00, nullable=False)
    payouts_made = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Growth metrics
    new_models = Column(Integer, default=0, nullable=False)
    churned_models = Column(Integer, default=0, nullable=False)
    growth_rate = Column(Numeric(5, 2), default=0.00, nullable=False)  # Percentage
    
    # Platform breakdown
    revenue_by_platform = Column(JSON, default=dict, nullable=False)
    models_by_platform = Column(JSON, default=dict, nullable=False)
    
    # Top performers
    top_model_id = Column(Integer, nullable=True)
    top_model_revenue = Column(Numeric(10, 2), default=0.00, nullable=False)
    top_chatter_id = Column(Integer, nullable=True)
    top_chatter_revenue = Column(Numeric(10, 2), default=0.00, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="metrics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('agency_id', 'date', name='uq_agency_metrics_date'),
        Index('idx_agency_metrics_date', 'date'),
    )
    
    def __repr__(self):
        return f"<AgencyMetrics Agency:{self.agency_id} Date:{self.date}>"