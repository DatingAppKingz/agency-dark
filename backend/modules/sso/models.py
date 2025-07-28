"""
SSO Database Models
"""
from sqlalchemy import Column, String, Boolean, JSON, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class SSOProviderType(str, enum.Enum):
    SAML = "saml"
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class SSOProvider(Base):
    """SSO Provider Configuration"""
    __tablename__ = "sso_providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    name = Column(String(255), nullable=False)
    provider_type = Column(SQLEnum(SSOProviderType), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # SAML Configuration
    entity_id = Column(String(500))
    sso_url = Column(String(500))
    slo_url = Column(String(500))
    x509_cert = Column(Text)
    metadata_url = Column(String(500))
    
    # OAuth/OIDC Configuration
    client_id = Column(String(255))
    client_secret = Column(String(255))
    authorization_url = Column(String(500))
    token_url = Column(String(500))
    userinfo_url = Column(String(500))
    scopes = Column(JSON, default=list)
    
    # Common Configuration
    attribute_mapping = Column(JSON, default=dict)
    allowed_domains = Column(JSON, default=list)
    auto_provision_users = Column(Boolean, default=False)
    default_role = Column(String(50))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency", back_populates="sso_providers")
    sessions = relationship("SSOSession", back_populates="provider", cascade="all, delete-orphan")


class SSOSession(Base):
    """SSO Session Management"""
    __tablename__ = "sso_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("sso_providers.id"), nullable=False)
    
    # Session Data
    session_index = Column(String(255))  # SAML session index
    name_id = Column(String(255))  # SAML NameID
    access_token = Column(Text)  # OAuth access token
    refresh_token = Column(Text)  # OAuth refresh token
    id_token = Column(Text)  # OIDC ID token
    
    # Session Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_activity = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Relationships
    user = relationship("User", back_populates="sso_sessions")
    provider = relationship("SSOProvider", back_populates="sessions")


class SCIMUser(Base):
    """SCIM User Provisioning"""
    __tablename__ = "scim_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("sso_providers.id"), nullable=False)
    
    # SCIM Data
    external_id = Column(String(255), unique=True)
    scim_id = Column(String(255), unique=True)
    resource_type = Column(String(50), default="User")
    schemas = Column(JSON, default=list)
    
    # Sync Status
    last_synced = Column(DateTime)
    sync_status = Column(String(50))
    sync_error = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    provider = relationship("SSOProvider")