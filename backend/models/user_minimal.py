"""
Minimal User model that matches the actual database structure.
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid
from core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "super_admin"
    AGENCY_OWNER = "agency_owner"
    AGENCY_ADMIN = "agency_admin"
    AGENCY_STAFF = "agency_staff"
    MODEL = "model"
    CHATTER = "chatter"
    MEMBER = "member"


class User(Base):
    """Minimal User model matching actual database."""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    
    # Authentication
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column("hashed_password", String(255), nullable=False)
    
    # Profile
    full_name = Column(String(255), nullable=True)
    
    # Role and permissions
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Verification tokens
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Timestamps
    last_login = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency", back_populates="users", lazy="selectin")
    
    # Properties for compatibility
    @property
    def last_login_at(self):
        return self.last_login
    
    @last_login_at.setter
    def last_login_at(self, value):
        self.last_login = value
    
    @property
    def is_superuser(self):
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def permissions(self):
        return {}  # Return empty dict for now
    
    @property
    def email_verified_at(self):
        return self.verified_at
    
    # These fields don't exist in DB but are expected by some code
    phone_verified_at = None
    last_login_ip = None
    two_factor_enabled = False
    two_factor_secret = None
    created_by_id = None
    updated_by_id = None
    language = "en"


class Session(Base):
    """Session model for tracking user sessions."""
    __tablename__ = "sessions"
    __table_args__ = {"extend_existing": True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(500), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User")