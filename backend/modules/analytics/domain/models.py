"""
Time-series data models for analytics.
"""
from sqlalchemy import Column, String, DateTime, Numeric, Integer, ForeignKey, Index, JSON, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

from core.database import Base


class AggregationPeriod(str, Enum):
    """Time periods for data aggregation."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


# class MetricSnapshot(Base):
#     """Stores point-in-time metrics for models."""
#     __tablename__ = "metric_snapshots"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=False)
    
#     # Timestamp for this snapshot
#     timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
#     # Subscriber metrics
#     total_subscribers = Column(Integer, default=0)
#     paying_subscribers = Column(Integer, default=0)
#     non_paying_fans = Column(Integer, default=0)
#     new_subscribers = Column(Integer, default=0)  # Since last snapshot
#     lost_subscribers = Column(Integer, default=0)  # Since last snapshot
    
#     # Revenue metrics (in USD)
#     total_revenue = Column(Numeric(12, 2), default=0)
#     subscription_revenue = Column(Numeric(12, 2), default=0)
#     tip_revenue = Column(Numeric(12, 2), default=0)
#     ppv_revenue = Column(Numeric(12, 2), default=0)
    
#     # Content metrics
#     total_posts = Column(Integer, default=0)
#     total_messages_sent = Column(Integer, default=0)
#     total_messages_received = Column(Integer, default=0)
    
#     # Engagement metrics
#     avg_fan_spend = Column(Numeric(10, 2), default=0)
#     conversion_rate = Column(Numeric(5, 2), default=0)  # Percentage
    
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
    
#     __table_args__ = (
#         Index('idx_metric_snapshot_model_timestamp', 'model_id', 'timestamp'),
#     )


class RevenueTransaction(Base):
    """Tracks individual revenue transactions."""
    __tablename__ = "revenue_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=False)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id"), nullable=False)
    
    # Transaction details
    transaction_type = Column(String(50), nullable=False)  # subscription, tip, ppv_message, ppv_post
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default='USD')
    
    # Source information
    source = Column(String(20), nullable=False)  # onlyfans, inflow
    external_transaction_id = Column(String(255))
    
    # Related content (if applicable)
    content_type = Column(String(50))  # post, message, stream
    content_id = Column(String(255))
    
    # Timestamps
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_revenue_transaction_model_date', 'model_id', 'transaction_date'),
        Index('idx_revenue_transaction_fan', 'fan_id', 'transaction_date'),
    )


class ContentPerformance(Base):
    """Tracks performance metrics for individual content pieces."""
    __tablename__ = "content_performance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=False)
    
    # Content identification
    content_type = Column(String(50), nullable=False)  # post, video, image, stream
    content_id = Column(String(255), nullable=False)  # External ID from OF/Inflow
    title = Column(String(500))
    
    # Categories/tags
    categories = Column(JSON, default=list)  # Array of category names
    tags = Column(JSON, default=list)  # Array of tags
    
    # Performance metrics
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    
    # Revenue metrics
    total_revenue = Column(Numeric(10, 2), default=0)
    purchase_count = Column(Integer, default=0)
    
    # Content metadata
    is_ppv = Column(Boolean, default=False)
    ppv_price = Column(Numeric(10, 2))
    duration_seconds = Column(Integer)  # For videos
    
    # Timestamps
    published_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_content_performance_model', 'model_id'),
        Index('idx_content_performance_type', 'content_type'),
        Index('idx_content_performance_published', 'published_at'),
    )


class FanSpendingHistory(Base):
    """Tracks spending patterns for individual fans."""
    __tablename__ = "fan_spending_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=False)
    
    # Period covered by this record
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Spending breakdown
    subscription_amount = Column(Numeric(10, 2), default=0)
    tip_amount = Column(Numeric(10, 2), default=0)
    ppv_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), default=0)
    
    # Transaction counts
    tip_count = Column(Integer, default=0)
    ppv_purchase_count = Column(Integer, default=0)
    
    # Engagement metrics
    messages_sent = Column(Integer, default=0)
    messages_received = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_fan_spending_history_fan', 'fan_id', 'period_start'),
        Index('idx_fan_spending_history_model', 'model_id', 'period_start'),
    )


class CategoryPerformance(Base):
    """Aggregated performance metrics by content category."""
    __tablename__ = "category_performance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=False)
    
    # Category information
    category_name = Column(String(100), nullable=False)
    
    # Period for aggregation
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Content metrics
    content_count = Column(Integer, default=0)
    total_views = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    
    # Revenue metrics
    total_revenue = Column(Numeric(10, 2), default=0)
    avg_revenue_per_content = Column(Numeric(10, 2), default=0)
    
    # Engagement rate
    avg_engagement_rate = Column(Numeric(5, 2), default=0)  # (likes + comments) / views * 100
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_category_performance_model', 'model_id', 'period_start'),
        Index('idx_category_performance_category', 'category_name'),
    )


class AnalyticsCache(Base):
    """Caches computed analytics for fast retrieval."""
    __tablename__ = "analytics_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Cache key components
    cache_type = Column(String(50), nullable=False)  # chart_data, summary, export
    entity_type = Column(String(50), nullable=False)  # model, agency, platform
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Time range
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Additional filters (JSON)
    filters = Column(JSON, default=dict)
    
    # Cached data
    data = Column(JSON, nullable=False)
    
    # Cache metadata
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (
        Index('idx_analytics_cache_lookup', 'cache_type', 'entity_type', 'entity_id', 'period_start', 'period_end'),
        Index('idx_analytics_cache_expires', 'expires_at'),
    )


class Analytics(Base):
    """Generic analytics event storage"""
    __tablename__ = "analytics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=True)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id"), nullable=True)
    
    # Event data
    metric_type = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    value = Column(Numeric(12, 2), default=0)
    data = Column(JSON, default=dict)
    
    # Timestamps
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_analytics_agency_date', 'agency_id', 'date'),
        Index('idx_analytics_model_date', 'model_id', 'date'),
        Index('idx_analytics_metric_type', 'metric_type'),
    )


# Pydantic models for real-time processing
class AnalyticsEvent(BaseModel):
    """Analytics event for real-time processing"""
    event_type: str
    agency_id: str
    model_id: Optional[str] = None
    fan_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }