"""
OnlyFans API domain schemas.

These schemas define the data structures for OnlyFansAPI.com requests and responses.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OnlyFansMessageType(str, Enum):
    """Types of messages on OnlyFans."""
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    TIP = "tip"
    PPV = "ppv"


class OnlyFansContentType(str, Enum):
    """Types of content on OnlyFans."""
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    STREAM = "stream"
    TEXT = "text"


class OnlyFansConfig(BaseModel):
    """Configuration for OnlyFans API client."""
    base_url: HttpUrl = Field(default="https://onlyfansapi.com/api/v1")
    api_key: str
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=1, description="Initial retry delay in seconds")
    
    # OnlyFans specific auth (if needed)
    user_agent: Optional[str] = None
    cookie: Optional[str] = None
    x_bc: Optional[str] = None  # OnlyFans auth header


class OnlyFansProfile(BaseModel):
    """OnlyFans creator profile."""
    id: str
    username: str
    name: Optional[str] = None
    about: Optional[str] = None
    avatar: Optional[HttpUrl] = None
    header: Optional[HttpUrl] = None
    
    # Stats
    posts_count: int = 0
    photos_count: int = 0
    videos_count: int = 0
    subscribers_count: int = 0
    
    # Subscription info
    subscription_price: Decimal = Field(default=Decimal("0.00"))
    is_free: bool = False
    has_discount: bool = False
    discount_price: Optional[Decimal] = None
    
    # Profile settings
    show_posts_in_feed: bool = True
    can_receive_chat_message: bool = True
    has_stories: bool = False
    has_stream: bool = False
    
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansFan(BaseModel):
    """OnlyFans subscriber/fan."""
    id: str
    username: str
    name: Optional[str] = None
    avatar: Optional[HttpUrl] = None
    
    # Subscription info
    is_subscriber: bool = False
    is_expired_subscriber: bool = False
    subscription_price: Optional[Decimal] = None
    subscribed_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    renew_at: Optional[datetime] = None
    
    # Interaction stats
    total_spent: Decimal = Field(default=Decimal("0.00"))
    tips_sum: Decimal = Field(default=Decimal("0.00"))
    tips_count: int = 0
    messages_count: int = 0
    ppv_purchased: int = 0
    
    # Status
    is_restricted: bool = False
    is_blocked: bool = False
    can_send_chat_message: bool = True
    
    last_seen: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansPost(BaseModel):
    """OnlyFans post/content."""
    id: str
    text: Optional[str] = None
    preview: Optional[str] = None
    
    # Media
    media: List[Dict[str, Any]] = Field(default_factory=list)
    media_count: int = 0
    
    # Monetization
    price: Optional[Decimal] = None
    is_paid: bool = False
    can_purchase: bool = True
    
    # Engagement
    favorites_count: int = 0
    comments_count: int = 0
    
    # Metadata
    posted_at: datetime
    is_archived: bool = False
    is_pinned: bool = False
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansMessage(BaseModel):
    """OnlyFans chat message."""
    id: str
    text: Optional[str] = None
    
    # Participants
    from_user: Dict[str, Any]
    to_user: Optional[Dict[str, Any]] = None
    
    # Media
    media: List[Dict[str, Any]] = Field(default_factory=list)
    preview: Optional[str] = None
    
    # Message type and monetization
    message_type: OnlyFansMessageType = OnlyFansMessageType.TEXT
    price: Optional[Decimal] = None
    is_paid: bool = False
    is_opened: bool = False
    is_new: bool = True
    
    # Tip info
    tip_amount: Optional[Decimal] = None
    
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansTransaction(BaseModel):
    """OnlyFans financial transaction."""
    id: str
    type: str  # subscription, tip, post, message, stream
    amount: Decimal
    currency: str = "USD"
    
    # Participants
    user_id: str
    user_name: Optional[str] = None
    
    # Context
    description: Optional[str] = None
    post_id: Optional[str] = None
    message_id: Optional[str] = None
    
    status: str = "completed"  # completed, pending, failed
    created_at: datetime
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansStatistics(BaseModel):
    """OnlyFans account statistics."""
    period_start: datetime
    period_end: datetime
    
    # Revenue
    total_earnings: Decimal
    subscription_earnings: Decimal
    tip_earnings: Decimal
    post_earnings: Decimal
    message_earnings: Decimal
    stream_earnings: Decimal
    referral_earnings: Decimal
    
    # Subscribers
    new_subscribers: int
    lost_subscribers: int
    total_subscribers: int
    expired_subscribers: int
    
    # Content
    posts_count: int
    photos_count: int
    videos_count: int
    
    # Engagement
    messages_sent: int
    messages_received: int
    likes_received: int
    comments_received: int
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansMedia(BaseModel):
    """Media item (photo/video)."""
    id: str
    type: OnlyFansContentType
    src: Optional[HttpUrl] = None
    preview: Optional[HttpUrl] = None
    thumb: Optional[HttpUrl] = None
    
    duration: Optional[int] = None  # For videos, in seconds
    size: Optional[int] = None  # File size in bytes
    
    can_view: bool = True
    has_error: bool = False
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansVault(BaseModel):
    """Vault item (saved media)."""
    id: str
    type: str  # photo, video, etc.
    name: Optional[str] = None
    
    media: List[OnlyFansMedia] = Field(default_factory=list)
    
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansList(BaseModel):
    """Custom list of fans."""
    id: str
    name: str
    users_count: int = 0
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansNotification(BaseModel):
    """Notification from OnlyFans."""
    id: str
    type: str  # new_subscriber, tip, message, etc.
    text: str
    
    user: Optional[Dict[str, Any]] = None
    
    is_read: bool = False
    created_at: datetime
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OnlyFansAPIError(BaseModel):
    """Error response from OnlyFans API."""
    error: Union[str, Dict[str, Any]]
    message: Optional[str] = None
    code: Optional[int] = None


class MessageCreateRequest(BaseModel):
    """Request to create/send a message."""
    fan_id: str
    text: Optional[str] = None
    price: Optional[Decimal] = None
    media_ids: List[str] = Field(default_factory=list)
    preview: Optional[str] = None


class PostCreateRequest(BaseModel):
    """Request to create a post."""
    text: Optional[str] = None
    price: Optional[Decimal] = None
    media_ids: List[str] = Field(default_factory=list)
    preview: Optional[str] = None
    is_pinned: bool = False
    schedule_date: Optional[datetime] = None