"""
OAuth database models for multi-tenant authentication.
Implements OAuth2.0 clients, tokens, and authorization codes with agency isolation.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import secrets
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from core.database import Base

class OAuthClient(Base):
    """OAuth2 client registration for multi-tenant support."""
    __tablename__ = 'oauth_clients'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id', ondelete='CASCADE'), nullable=False)
    client_id = Column(String(48), unique=True, nullable=False, index=True)
    client_secret = Column(String(120), nullable=True)  # None for public clients
    client_name = Column(String(100), nullable=True)
    
    # OAuth2 metadata
    redirect_uris = Column(ARRAY(Text), nullable=False, default=list)
    grant_types = Column(ARRAY(Text), nullable=False, default=['authorization_code'])
    response_types = Column(ARRAY(Text), nullable=False, default=['code'])
    scope = Column(Text, default='')
    
    # Multi-tenant support
    allowed_agencies = Column(ARRAY(UUID), nullable=True)  # For cross-agency access
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    agency = relationship("Agency", back_populates="oauth_clients")
    tokens = relationship("OAuthToken", back_populates="client", cascade="all, delete-orphan")
    authorization_codes = relationship("OAuthAuthorizationCode", back_populates="client", cascade="all, delete-orphan")
    consent_records = relationship("OAuthConsentRecord", back_populates="client", cascade="all, delete-orphan")
    
    def check_client_secret(self, client_secret: str) -> bool:
        """Verify client secret."""
        if self.client_secret is None:
            return False
        return secrets.compare_digest(self.client_secret, client_secret)
    
    def get_allowed_scope(self, scope: str) -> str:
        """Return allowed scope for this client."""
        if not self.scope:
            return scope
        allowed = set(self.scope.split())
        requested = set(scope.split())
        return ' '.join(allowed & requested)
    
    def check_redirect_uri(self, redirect_uri: str) -> bool:
        """Validate redirect URI."""
        if not self.redirect_uris:
            return False
        return redirect_uri in self.redirect_uris
    
    def check_response_type(self, response_type: str) -> bool:
        """Check if response type is allowed."""
        return response_type in self.response_types
    
    def check_grant_type(self, grant_type: str) -> bool:
        """Check if grant type is allowed."""
        return grant_type in self.grant_types
    
    @property
    def client_metadata(self) -> Dict[str, Any]:
        """Return client metadata for OAuth2 operations."""
        return {
            'client_id': self.client_id,
            'client_name': self.client_name,
            'redirect_uris': self.redirect_uris,
            'grant_types': self.grant_types,
            'response_types': self.response_types,
            'scope': self.scope,
            'token_endpoint_auth_method': 'client_secret_post' if self.client_secret else 'none'
        }


class OAuthToken(Base):
    """OAuth2 access and refresh tokens with multi-tenant support."""
    __tablename__ = 'oauth_tokens'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(String(48), ForeignKey('oauth_clients.client_id', ondelete='CASCADE'), nullable=True)
    
    # Token data
    token_type = Column(String(40), default='Bearer')
    access_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, index=True)
    scope = Column(Text, default='')
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional claims for multi-tenancy
    extra_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    agency = relationship("Agency")
    user = relationship("User", back_populates="oauth_tokens")
    client = relationship("OAuthClient", back_populates="tokens")
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_refresh_token_active(self) -> bool:
        """Check if refresh token is still valid."""
        if not self.refresh_token:
            return False
        # Refresh tokens typically last longer (30 days)
        created_dt = self.created_at
        if not isinstance(created_dt, datetime):
            return False
        return datetime.now(timezone.utc) < created_dt + timedelta(days=30)
    
    def revoke(self):
        """Revoke this token."""
        self.expires_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token to dictionary for responses."""
        data = {
            'access_token': self.access_token,
            'token_type': self.token_type,
            'scope': self.scope
        }
        
        if self.expires_at:
            expires_in = int((self.expires_at - datetime.now(timezone.utc)).total_seconds())
            data['expires_in'] = max(0, expires_in)
        
        if self.refresh_token:
            data['refresh_token'] = self.refresh_token
        
        # Add custom claims
        if self.extra_data:
            data.update(self.extra_data)
        
        return data


class OAuthAuthorizationCode(Base):
    """OAuth2 authorization codes with PKCE support."""
    __tablename__ = 'oauth_authorization_codes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(String(48), ForeignKey('oauth_clients.client_id', ondelete='CASCADE'), nullable=True)
    
    code = Column(String(120), unique=True, nullable=False, index=True)
    redirect_uri = Column(Text, nullable=True)
    scope = Column(Text, default='')
    
    # PKCE support
    code_challenge = Column(String(128), nullable=True)
    code_challenge_method = Column(String(10), nullable=True)  # 'S256' or 'plain'
    
    # Expiration (codes are short-lived, typically 10 minutes)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    agency = relationship("Agency")
    user = relationship("User")
    client = relationship("OAuthClient", back_populates="authorization_codes")
    
    @property
    def is_expired(self) -> bool:
        """Check if authorization code is expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def get_redirect_uri(self) -> str:
        """Get redirect URI for this code."""
        return self.redirect_uri or ''
    
    @classmethod
    def generate_code(cls) -> str:
        """Generate a secure authorization code."""
        return secrets.token_urlsafe(32)


class ExternalOAuthToken(Base):
    """Tokens from external OAuth providers (Instagram, OnlyFans, etc.)."""
    __tablename__ = 'external_oauth_tokens'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    provider = Column(String(50), nullable=False)  # 'instagram', 'onlyfans', etc.
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(Text, nullable=True)
    raw_data = Column(Text, nullable=True)  # Encrypted JSON
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    agency = relationship("Agency")
    user = relationship("User", back_populates="external_oauth_tokens")
    
    @property
    def is_expired(self) -> bool:
        """Check if external token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def needs_refresh(self) -> bool:
        """Check if token needs refreshing (5 minutes before expiry)."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at - timedelta(minutes=5)


class OAuthConsentRecord(Base):
    """Track user consent for OAuth clients."""
    __tablename__ = 'oauth_consent_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_id = Column(String(48), ForeignKey('oauth_clients.client_id', ondelete='CASCADE'), nullable=False)
    
    scope = Column(Text, nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="oauth_consent_records")
    client = relationship("OAuthClient", back_populates="consent_records")
    
    @property
    def is_valid(self) -> bool:
        """Check if consent is still valid."""
        if self.revoked_at:
            return False
        if self.expires_at:
            return datetime.now(timezone.utc) < self.expires_at
        return True
    
    def revoke(self):
        """Revoke this consent."""
        self.revoked_at = datetime.now(timezone.utc)