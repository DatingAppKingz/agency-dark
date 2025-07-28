"""
Inflow API domain schemas.

These schemas define the data structures for Inflow API requests and responses.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class InflowAuthMethod(str, Enum):
    """Authentication methods supported by Inflow."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"


class InflowConfig(BaseModel):
    """Configuration for Inflow API client."""
    base_url: HttpUrl = Field(default="https://api.inflow.com")
    api_key: Optional[str] = None
    auth_method: InflowAuthMethod = InflowAuthMethod.API_KEY
    
    # OAuth2 configuration
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    scope: Optional[str] = None
    
    # JWT configuration
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = Field(default=3600, description="JWT expiration in seconds")
    
    # General configuration
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=1, description="Initial retry delay in seconds")
    verify_ssl: bool = True
    
    # Webhook configuration
    webhook_secret: Optional[str] = None
    
    # Token storage (runtime)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class InflowUser(BaseModel):
    """Inflow user representation."""
    id: str
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    is_creator: bool = False
    is_subscriber: bool = False
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowContent(BaseModel):
    """Content item from Inflow."""
    id: str
    creator_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    content_type: str  # image, video, text, etc.
    url: HttpUrl
    thumbnail_url: Optional[HttpUrl] = None
    price: Optional[float] = None
    is_ppv: bool = False
    is_locked: bool = False
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowMessage(BaseModel):
    """Chat message from Inflow."""
    id: str
    conversation_id: str
    sender_id: str
    recipient_id: str
    content: str
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    is_read: bool = False
    is_ppv: bool = False
    price: Optional[float] = None
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowSubscription(BaseModel):
    """Subscription information."""
    id: str
    subscriber_id: str
    creator_id: str
    price: float
    is_active: bool
    started_at: datetime
    expires_at: Optional[datetime] = None
    auto_renew: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowTransaction(BaseModel):
    """Financial transaction."""
    id: str
    type: str  # subscription, tip, ppv, etc.
    amount: float
    currency: str = "USD"
    from_user_id: str
    to_user_id: str
    status: str  # completed, pending, failed
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowAnalytics(BaseModel):
    """Analytics data from Inflow."""
    period_start: datetime
    period_end: datetime
    total_revenue: float
    subscription_revenue: float
    tip_revenue: float
    ppv_revenue: float
    new_subscribers: int
    lost_subscribers: int
    total_subscribers: int
    message_count: int
    content_views: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InflowWebhookEvent(BaseModel):
    """Webhook event from Inflow."""
    id: str
    event_type: str
    object_type: str
    object_id: str
    data: Dict[str, Any]
    created_at: datetime
    signature: Optional[str] = None


class InflowAPIError(BaseModel):
    """Error response from Inflow API."""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None