from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, JSON, Numeric, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from models.base import Base, BaseModel


class ModelStatus(str, enum.Enum):
    """Model status enumeration."""
    PENDING = "pending"  # Awaiting verification
    ACTIVE = "active"  # Active and working
    PAUSED = "paused"  # Temporarily paused
    INACTIVE = "inactive"  # No longer active
    BANNED = "banned"  # Banned from platform


class Platform(str, enum.Enum):
    """Supported platforms."""
    ONLYFANS = "onlyfans"
    FANSLY = "fansly"
    FANVUE = "fanvue"
    CUSTOM = "custom"


class Model(BaseModel):
    """Model representation for content creators."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "models"
    
    # User relationship (one-to-one)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Basic information
    stage_name = Column(String(255), nullable=False, index=True)
    real_name = Column(String(255), nullable=True)  # Encrypted in production
    bio = Column(Text, nullable=True)
    
    # Platform information
    platform = Column(SQLEnum(Platform), default=Platform.ONLYFANS, nullable=False)
    platform_username = Column(String(255), nullable=False)
    platform_user_id = Column(String(255), nullable=True)  # External platform ID
    platform_url = Column(String(500), nullable=True)
    
    # Status
    status = Column(SQLEnum(ModelStatus), default=ModelStatus.PENDING, nullable=False)
    verification_status = Column(String(50), default="unverified", nullable=False)
    verified_at = Column(String(30), nullable=True)  # ISO datetime
    
    # Media
    profile_photo_url = Column(String(500), nullable=True)
    cover_photo_url = Column(String(500), nullable=True)
    photo_galleries = Column(JSON, default=list, nullable=False)
    
    # Stats (cached from platform)
    followers_count = Column(Integer, default=0, nullable=False)
    posts_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    
    # Financial
    commission_rate = Column(Numeric(5, 2), nullable=True)  # Override agency default
    total_earnings = Column(Numeric(12, 2), default=0.00, nullable=False)
    pending_payout = Column(Numeric(12, 2), default=0.00, nullable=False)
    lifetime_earnings = Column(Numeric(12, 2), default=0.00, nullable=False)
    
    # Integration
    api_access_token = Column(Text, nullable=True)  # Encrypted
    api_refresh_token = Column(Text, nullable=True)  # Encrypted
    api_token_expires_at = Column(String(30), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    
    # Sync settings
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(String(30), nullable=True)
    sync_frequency_hours = Column(Integer, default=6, nullable=False)
    
    # Categories and tags
    categories = Column(JSON, default=list, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    content_types = Column(JSON, default=list, nullable=False)  # Types of content they create
    
    # Preferences
    languages = Column(JSON, default=["en"], nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    working_hours = Column(JSON, default=dict, nullable=False)  # Schedule
    
    # Chat settings
    chat_enabled = Column(Boolean, default=True, nullable=False)
    auto_reply_enabled = Column(Boolean, default=False, nullable=False)
    welcome_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="model_profile", uselist=False)
    agency = relationship("Agency", back_populates="models")
    conversations = relationship("Conversation", back_populates="model", cascade="all, delete-orphan")
    content = relationship("Content", back_populates="model", cascade="all, delete-orphan")
    earnings = relationship("Earning", back_populates="model", cascade="all, delete-orphan")
    payouts = relationship("Payout", back_populates="model", cascade="all, delete-orphan")
    analytics = relationship("ModelAnalytics", back_populates="model", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="model", cascade="all, delete-orphan")
    vault = relationship("Vault", back_populates="model", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Model {self.stage_name}>"
    
    @property
    def is_active(self):
        """Check if model is active."""
        return self.status == ModelStatus.ACTIVE
    
    @property
    def is_verified(self):
        """Check if model is verified."""
        return self.verification_status == "verified"
    
    @property
    def platform_icon(self):
        """Get platform icon/logo URL."""
        icons = {
            Platform.ONLYFANS: "/icons/onlyfans.svg",
            Platform.FANSLY: "/icons/fansly.svg",
            Platform.FANVUE: "/icons/fanvue.svg",
            Platform.CUSTOM: "/icons/custom.svg"
        }
        return icons.get(self.platform, "/icons/default.svg")
    
    @property
    def effective_commission_rate(self):
        """Get the effective commission rate for this model."""
        return self.commission_rate or self.agency.default_commission_rate
    
    def calculate_payout(self, gross_amount):
        """Calculate net payout after commission."""
        commission = gross_amount * (self.effective_commission_rate / 100)
        return gross_amount - commission
    
    # Relationships are defined in the related models to avoid circular imports