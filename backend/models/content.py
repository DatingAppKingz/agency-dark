from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, JSON, Numeric, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from models.base import Base, BaseModel


class ContentType(str, enum.Enum):
    """Content type enumeration."""
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    BUNDLE = "bundle"  # Multiple items


class ContentStatus(str, enum.Enum):
    """Content status enumeration."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ContentCategory(str, enum.Enum):
    """Content category."""
    GENERAL = "general"
    ADULT = "adult"
    PREMIUM = "premium"
    EXCLUSIVE = "exclusive"


class Content(BaseModel):
    """Content created by models."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "content"
    
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    
    # Content details
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    type = Column(SQLEnum(ContentType), nullable=False)
    status = Column(SQLEnum(ContentStatus), default=ContentStatus.DRAFT, nullable=False)
    
    # Media
    media_urls = Column(JSON, default=list, nullable=False)  # List of URLs
    thumbnail_url = Column(String(500), nullable=True)
    preview_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # For video/audio
    
    # Pricing
    is_free = Column(Boolean, default=True, nullable=False)
    price = Column(Numeric(10, 2), default=0.00, nullable=False)
    discount_price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Publishing
    published_at = Column(String(30), nullable=True)
    scheduled_for = Column(String(30), nullable=True)
    expires_at = Column(String(30), nullable=True)
    
    # Platform integration
    platform_content_id = Column(String(255), unique=True, nullable=True)
    platform_url = Column(String(500), nullable=True)
    
    # Engagement metrics
    views_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    comments_count = Column(Integer, default=0, nullable=False)
    purchases_count = Column(Integer, default=0, nullable=False)
    revenue_generated = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Categories and tags
    categories = Column(JSON, default=list, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    # Visibility
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_highlighted = Column(Boolean, default=False, nullable=False)
    is_exclusive = Column(Boolean, default=False, nullable=False)  # For VIP fans only
    
    # Relationships
    model = relationship("Model", back_populates="content")
    content_analytics = relationship("ContentAnalytics", back_populates="content", cascade="all, delete-orphan")
    vault_items = relationship("VaultItem", back_populates="content", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Content {self.type} - {self.title or 'Untitled'}>"
    
    @property
    def is_paid(self):
        """Check if content is paid."""
        return not self.is_free and self.price > 0
    
    @property
    def engagement_rate(self):
        """Calculate engagement rate."""
        if self.views_count == 0:
            return 0
        return round(((self.likes_count + self.comments_count) / self.views_count) * 100, 2)


class ContentTemplate(BaseModel):
    """Templates for content creation."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "content_templates"
    
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Template info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(SQLEnum(ContentType), nullable=False)
    
    # Template content
    title_template = Column(String(500), nullable=True)
    description_template = Column(Text, nullable=True)
    hashtags = Column(JSON, default=list, nullable=False)
    
    # Pricing template
    suggested_price = Column(Numeric(10, 2), nullable=True)
    pricing_strategy = Column(String(50), nullable=True)
    
    # Scheduling
    posting_schedule = Column(JSON, default=dict, nullable=False)  # Days and times
    
    # Usage
    usage_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="content_templates")
    
    def __repr__(self):
        return f"<ContentTemplate {self.name}>"


class ContentAnalytics(BaseModel):
    """Analytics for individual content pieces."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "content_analytics"
    
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)
    
    # Engagement
    views = Column(Integer, default=0, nullable=False)
    unique_views = Column(Integer, default=0, nullable=False)
    likes = Column(Integer, default=0, nullable=False)
    comments = Column(Integer, default=0, nullable=False)
    shares = Column(Integer, default=0, nullable=False)
    
    # Financial
    purchases = Column(Integer, default=0, nullable=False)
    revenue = Column(Numeric(10, 2), default=0.00, nullable=False)
    refunds = Column(Integer, default=0, nullable=False)
    
    # Audience
    viewer_demographics = Column(JSON, default=dict, nullable=False)  # Age, location, etc.
    peak_viewing_hour = Column(Integer, nullable=True)  # 0-23
    
    # Relationships
    content = relationship("Content", back_populates="content_analytics")
    
    def __repr__(self):
        return f"<ContentAnalytics Content:{self.content_id} Date:{self.date}>"


class Vault(BaseModel):
    """Content vault for PPV and exclusive content."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "vaults"
    
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Vault settings
    name = Column(String(255), default="Content Vault", nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Access settings
    default_price = Column(Numeric(10, 2), default=10.00, nullable=False)
    bundle_discount = Column(Numeric(5, 2), default=0.00, nullable=False)  # Percentage
    
    # Statistics
    total_items = Column(Integer, default=0, nullable=False)
    total_sales = Column(Integer, default=0, nullable=False)
    total_revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Relationships
    model = relationship("Model", back_populates="vault", uselist=False)
    items = relationship("VaultItem", back_populates="vault", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Vault Model:{self.model_id}>"


class VaultItem(BaseModel):
    """Individual items in content vault."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "vault_items"
    
    vault_id = Column(Integer, ForeignKey("vaults.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    
    # Item details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    position = Column(Integer, default=0, nullable=False)  # Display order
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    
    # Statistics
    views = Column(Integer, default=0, nullable=False)
    purchases = Column(Integer, default=0, nullable=False)
    revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Relationships
    vault = relationship("Vault", back_populates="items")
    content = relationship("Content", back_populates="vault_items")
    
    def __repr__(self):
        return f"<VaultItem {self.title}>"