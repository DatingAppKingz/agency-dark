"""
API Orchestration domain schemas.

Unified schemas that combine data from multiple sources.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DataSource(str, Enum):
    """Source of the data."""
    INFLOW = "inflow"
    ONLYFANS = "onlyfans"
    BOTH = "both"
    LOCAL = "local"


class ConflictResolution(str, Enum):
    """How to resolve conflicts between data sources."""
    PREFER_ONLYFANS = "prefer_onlyfans"
    PREFER_INFLOW = "prefer_inflow"
    MERGE = "merge"
    LATEST = "latest"


class UnifiedFan(BaseModel):
    """Unified fan/subscriber data from multiple sources."""
    # Local database ID
    id: str
    
    # Common identifiers
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Subscription info (merged)
    is_subscriber: bool = False
    is_paying: bool = False
    subscription_price: Optional[Decimal] = None
    subscribed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Spending stats (summed from both sources)
    total_spent: Decimal = Decimal("0.00")
    tip_count: int = 0
    message_count: int = 0
    ppv_purchased_count: int = 0
    
    # Activity
    last_active_at: Optional[datetime] = None
    
    # Claiming info (local)
    is_claimed: bool = False
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    claim_expires_at: Optional[datetime] = None
    
    # Source tracking
    data_sources: List[DataSource] = Field(default_factory=list)
    inflow_id: Optional[str] = None
    onlyfans_id: Optional[str] = None
    
    # Sync status
    last_synced_at: Optional[datetime] = None
    sync_errors: List[str] = Field(default_factory=list)


class UnifiedMessage(BaseModel):
    """Unified message data from multiple sources."""
    id: str
    
    # Message content
    text: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    
    # Participants
    from_user_id: str
    from_username: str
    to_user_id: str
    to_username: str
    
    # Monetization
    is_ppv: bool = False
    price: Optional[Decimal] = None
    is_paid: bool = False
    is_tip: bool = False
    tip_amount: Optional[Decimal] = None
    
    # Status
    is_read: bool = False
    is_opened: bool = False
    
    # Timestamps
    created_at: datetime
    read_at: Optional[datetime] = None
    
    # Source tracking
    source: DataSource
    external_id: str


class UnifiedAnalytics(BaseModel):
    """Combined analytics from all sources."""
    period_start: datetime
    period_end: datetime
    
    # Revenue (combined)
    total_revenue: Decimal
    subscription_revenue: Decimal
    tip_revenue: Decimal
    ppv_revenue: Decimal
    
    # Revenue by source
    inflow_revenue: Decimal = Decimal("0.00")
    onlyfans_revenue: Decimal = Decimal("0.00")
    
    # Subscribers (deduplicated)
    total_subscribers: int
    new_subscribers: int
    lost_subscribers: int
    paying_subscribers: int
    
    # Content metrics
    posts_created: int = 0
    content_views: int = 0
    
    # Engagement
    messages_sent: int = 0
    messages_received: int = 0
    
    # Source breakdown
    data_sources: List[DataSource] = Field(default_factory=list)


class SyncStatus(BaseModel):
    """Status of data synchronization."""
    model_id: str
    
    # Inflow sync
    inflow_enabled: bool = False
    inflow_last_sync: Optional[datetime] = None
    inflow_sync_errors: List[str] = Field(default_factory=list)
    inflow_subscribers_synced: int = 0
    inflow_messages_synced: int = 0
    
    # OnlyFans sync
    onlyfans_enabled: bool = False
    onlyfans_last_sync: Optional[datetime] = None
    onlyfans_sync_errors: List[str] = Field(default_factory=list)
    onlyfans_fans_synced: int = 0
    onlyfans_messages_synced: int = 0
    
    # Overall status
    is_syncing: bool = False
    last_full_sync: Optional[datetime] = None
    next_sync_scheduled: Optional[datetime] = None


class MessageRequest(BaseModel):
    """Request to send a message through the best available channel."""
    fan_id: str
    text: Optional[str] = None
    media_ids: Optional[List[str]] = None
    price: Optional[Decimal] = None
    
    # Routing preferences
    preferred_source: Optional[DataSource] = None
    fallback_enabled: bool = True
    
    # Metadata
    campaign_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class MassMessageRequest(BaseModel):
    """Request to send mass messages."""
    text: Optional[str] = None
    media_ids: Optional[List[str]] = None
    price: Optional[Decimal] = None
    
    # Targeting - use either fan_ids or criteria
    fan_ids: Optional[List[str]] = None  # Specific fans
    recipient_criteria: Optional[Dict[str, Any]] = None  # Filter criteria
    
    # Additional fields
    model_id: Optional[str] = None  # Required for agency users
    limit: Optional[int] = None  # Maximum number of recipients
    fallback_enabled: bool = True
    
    # Metadata
    campaign_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ContentPost(BaseModel):
    """Request to create content across platforms."""
    text: Optional[str] = None
    media_ids: List[str] = Field(default_factory=list)
    
    # Monetization
    price: Optional[Decimal] = None
    is_ppv: bool = False
    
    # Platform targeting
    post_to_onlyfans: bool = True
    post_to_inflow: bool = False
    
    # Scheduling
    publish_immediately: bool = True
    scheduled_at: Optional[datetime] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)


class MassMessageStatus(BaseModel):
    """Status of a mass messaging campaign."""
    campaign_id: str
    total_recipients: int
    sent: int = 0
    failed: int = 0
    pending: int = 0
    status: str  # running, completed, cancelled, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class MassMessageResult(BaseModel):
    """Result of a mass message send to individual recipient."""
    fan_id: str
    success: bool
    source: Optional[DataSource] = None
    message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: Optional[datetime] = None