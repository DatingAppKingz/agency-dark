"""
Simplified User model that matches the actual database schema.
"""
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid
from models.base import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "SUPER_ADMIN"  # Platform owner
    AGENCY_OWNER = "AGENCY_OWNER"  # Agency owner
    AGENCY_ADMIN = "AGENCY_ADMIN"  # Agency administrator
    AGENCY_STAFF = "AGENCY_STAFF"  # Agency staff member
    MODEL = "MODEL"  # OnlyFans model
    CHATTER = "CHATTER"  # Chat operator
    MEMBER = "MEMBER"  # Basic member


class User(Base):
    """Simplified User model that matches actual database schema."""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Agency relationship
    agency_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Authentication fields
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)  # Storing plain text for test environment
    
    # Profile fields
    full_name = Column(String(255), nullable=True)
    
    # Role and permissions
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.MEMBER)
    
    # Status fields
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Verification tokens
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Activity tracking
    last_login = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    @property
    def last_login_at(self):
        """Alias for last_login to match code expectations."""
        return self.last_login
    
    @property
    def username(self):
        """Virtual property - not in database."""
        return None
    
    @property
    def avatar_url(self):
        """Virtual property - not in database."""
        return None
    
    @property
    def stage_name(self):
        """Get stage name from model profile if available."""
        return self.full_name