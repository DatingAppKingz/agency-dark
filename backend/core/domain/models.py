from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, JSON, Text, Integer, Numeric, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from backend.core.database import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    AGENCY_OWNER = "agency_owner"
    AGENCY_ADMIN = "agency_admin"
    AGENCY_MEMBER = "agency_member"
    MODEL = "model"
    CHATTER = "chatter"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"


class NotificationType(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class Agency(Base):
    __tablename__ = "agencies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    domain = Column(String(255))
    settings = Column(JSON, default=dict)
    subscription_status = Column(
        Enum(SubscriptionStatus), 
        default=SubscriptionStatus.TRIALING
    )
    subscription_ends_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    users = relationship("User", back_populates="agency", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="agency", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="agency", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), nullable=False, default=UserRole.AGENCY_MEMBER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255))
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    last_login = Column(DateTime)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    agency = relationship("Agency", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token = Column(String(500), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    user_agent = Column(Text)
    ip_address = Column(INET)
    refreshed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    data = Column(JSON, default=dict)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agency = relationship("Agency", back_populates="notifications")
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(255))
    resource_id = Column(UUID(as_uuid=True))
    data = Column(JSON, default=dict)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    agency = relationship("Agency", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")


class ModelProfile(Base):
    """OnlyFans model profile managed by the agency."""
    __tablename__ = "model_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    # OnlyFans account info
    onlyfans_username = Column(String(255), unique=True, nullable=False)
    onlyfans_user_id = Column(String(255), unique=True)
    display_name = Column(String(255))
    bio = Column(Text)
    profile_photo_url = Column(Text)
    cover_photo_url = Column(Text)
    
    # API credentials (encrypted in production)
    inflow_api_key = Column(Text)
    onlyfans_api_key = Column(Text)
    
    # Statistics
    subscriber_count = Column(Integer, default=0)
    paying_subscriber_count = Column(Integer, default=0)
    total_earnings = Column(Numeric(12, 2), default=0)
    
    # Commission settings
    commission_rate = Column(Numeric(5, 2))  # Override agency default if set
    
    # Status
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    agency = relationship("Agency")
    user = relationship("User")
    chatters = relationship("ModelChatter", back_populates="model", cascade="all, delete-orphan")
    fans = relationship("Fan", back_populates="model", cascade="all, delete-orphan")
    fan_claims = relationship("FanClaim", back_populates="model", cascade="all, delete-orphan")


class ModelChatter(Base):
    """Many-to-many relationship between models and chatters."""
    __tablename__ = "model_chatters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False)
    chatter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    
    model = relationship("ModelProfile", back_populates="chatters")
    chatter = relationship("User")
    
    __table_args__ = (
        UniqueConstraint('model_id', 'chatter_id', name='uq_model_chatter'),
    )


class Fan(Base):
    """OnlyFans subscriber/fan."""
    __tablename__ = "fans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # OnlyFans user info
    onlyfans_user_id = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    display_name = Column(String(255))
    avatar_url = Column(Text)
    
    # Subscription info
    is_subscriber = Column(Boolean, default=False)
    is_paying = Column(Boolean, default=False)
    subscription_price = Column(Numeric(10, 2))
    subscribed_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Engagement metrics
    total_spent = Column(Numeric(12, 2), default=0)
    message_count = Column(Integer, default=0)
    tip_count = Column(Integer, default=0)
    ppv_purchased_count = Column(Integer, default=0)
    last_active_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    model = relationship("ModelProfile", back_populates="fans")
    claims = relationship("FanClaim", back_populates="fan", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('model_id', 'onlyfans_user_id', name='uq_model_fan'),
    )


class FanClaim(Base):
    """Chatter claiming a fan for exclusive communication."""
    __tablename__ = "fan_claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("fans.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False)
    chatter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    claimed_by_model = Column(Boolean, default=False)  # True if model claimed, overrides chatter claims
    
    # Claim period
    claimed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # NULL means permanent claim
    is_active = Column(Boolean, default=True)
    
    # Who can override
    released_at = Column(DateTime)
    released_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    fan = relationship("Fan", back_populates="claims")
    model = relationship("ModelProfile", back_populates="fan_claims")
    chatter = relationship("User", foreign_keys=[chatter_id])
    released_by = relationship("User", foreign_keys=[released_by_id])
    
    __table_args__ = (
        # Only one active claim per fan
        Index('idx_active_fan_claim', 'fan_id', 'is_active', unique=True, postgresql_where='is_active = true'),
    )