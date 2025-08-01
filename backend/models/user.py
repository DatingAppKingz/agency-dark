from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from models.base import Base, BaseModel


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "super_admin"  # Platform owner
    AGENCY_OWNER = "agency_owner"  # Agency owner
    AGENCY_ADMIN = "agency_admin"  # Agency administrator
    AGENCY_STAFF = "agency_staff"  # Agency staff member
    MODEL = "model"  # OnlyFans model
    CHATTER = "chatter"  # Chat operator
    MEMBER = "member"  # Basic member


class User(BaseModel):
    """User model for authentication and profile."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "users"
    
    # Authentication fields
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile fields
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(String(1000), nullable=True)
    
    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    # Role and permissions
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    permissions = Column(JSON, default=dict, nullable=False)
    
    # Verification and security
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)
    
    # Agency relationship
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    agency = relationship("Agency", back_populates="users", lazy="joined")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    
    # Model-specific relationships (when user is a model)
    model_profile = relationship("Model", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Chatter-specific relationships
    assigned_conversations = relationship("Conversation", back_populates="assigned_chatter", foreign_keys="Conversation.assigned_chatter_id")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    
    # Audit fields
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Performance metrics (for chatters)
    performance_metrics = relationship("ChatterPerformance", back_populates="chatter", cascade="all, delete-orphan")
    
    # Search
    saved_searches = relationship("SavedSearch", back_populates="user", cascade="all, delete-orphan")
    
    # Notifications
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Language
    language = Column(String(10), default="en", nullable=False)
    language_preference = relationship("LanguagePreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # External API credentials
    external_credentials = relationship("ExternalAPICredential", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    @property
    def full_name(self):
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_agency_member(self):
        """Check if user belongs to an agency."""
        return self.agency_id is not None
    
    @property
    def can_manage_agency(self):
        """Check if user can manage agency settings."""
        return self.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]
    
    @property
    def can_manage_models(self):
        """Check if user can manage models."""
        return self.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_STAFF, UserRole.SUPER_ADMIN]
    
    @property
    def can_chat(self):
        """Check if user can access chat features."""
        return self.role in [UserRole.CHATTER, UserRole.MODEL, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]


class Session(BaseModel):
    """User session model for managing active sessions."""
    __table_args__ = {"extend_existing": True}

    __tablename__ = "sessions"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    refresh_token = Column(String(500), unique=True, nullable=True)
    
    # Session info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_type = Column(String(50), nullable=True)
    device_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Activity tracking
    last_activity_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session {self.token[:20]}... for user {self.user_id}>"
    
    @property
    def is_expired(self):
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at