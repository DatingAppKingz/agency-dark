"""
OAuth2 Provider implementation using Authlib.
Handles authorization server, token generation, and multi-tenant support.
"""
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import base64
from authlib.integrations.sqla_oauth2 import (
    create_query_client_func,
    create_save_token_func,
    create_bearer_token_validator,
)
from authlib.integrations.fastapi_oauth2 import AuthorizationServer, ResourceProtector
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oauth2.rfc6749.errors import OAuth2Error, InvalidClientError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request, Depends
import logging

from .models import OAuthClient, OAuthToken, OAuthAuthorizationCode, OAuthConsentRecord
from models.user import User
from core.database import get_db

logger = logging.getLogger(__name__)


class MultiTenantAuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    """
    Authorization Code Grant with multi-tenant support and PKCE.
    Handles the OAuth2 authorization code flow with agency isolation.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post', 'none']
    GRANT_TYPE = 'authorization_code'
    
    def __init__(self, request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db
    
    async def save_authorization_code(self, code: str, request: Request) -> OAuthAuthorizationCode:
        """Save authorization code with agency context."""
        client = request.client
        user = request.user
        
        # Extract agency_id from user
        agency_id = getattr(user, 'agency_id', None)
        if not agency_id:
            raise InvalidRequestError('User must belong to an agency')
        
        # Verify client belongs to the same agency
        if client.agency_id != agency_id:
            raise InvalidClientError('Client does not belong to user agency')
        
        auth_code = OAuthAuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=user.id,
            agency_id=agency_id,
            code_challenge=request.data.get('code_challenge'),
            code_challenge_method=request.data.get('code_challenge_method', 'S256'),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        
        self.db.add(auth_code)
        await self.db.commit()
        return auth_code
    
    async def query_authorization_code(self, code: str, client: OAuthClient) -> Optional[OAuthAuthorizationCode]:
        """Query authorization code with agency validation."""
        result = await self.db.execute(
            select(OAuthAuthorizationCode).where(
                OAuthAuthorizationCode.code == code,
                OAuthAuthorizationCode.client_id == client.client_id
            )
        )
        auth_code = result.scalar_one_or_none()
        
        if auth_code and not auth_code.is_expired:
            # Verify agency match
            if auth_code.agency_id != client.agency_id:
                return None
            return auth_code
        return None
    
    async def delete_authorization_code(self, authorization_code: OAuthAuthorizationCode):
        """Delete used authorization code."""
        await self.db.delete(authorization_code)
        await self.db.commit()
    
    async def authenticate_user(self, authorization_code: OAuthAuthorizationCode) -> Optional[User]:
        """Load user with agency context."""
        result = await self.db.execute(
            select(User).where(User.id == authorization_code.user_id)
        )
        return result.scalar_one_or_none()
    
    def validate_code_challenge(self, authorization_code: OAuthAuthorizationCode, verifier: str) -> bool:
        """Validate PKCE code challenge."""
        if not authorization_code.code_challenge:
            return True  # PKCE not required for this code
        
        if authorization_code.code_challenge_method == 'plain':
            return secrets.compare_digest(authorization_code.code_challenge, verifier)
        
        # S256 method (recommended)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip('=')
        
        return secrets.compare_digest(authorization_code.code_challenge, challenge)


class MultiTenantRefreshTokenGrant(grants.RefreshTokenGrant):
    """
    Refresh Token Grant with multi-tenant support.
    Handles token refresh with agency isolation.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post', 'none']
    GRANT_TYPE = 'refresh_token'
    
    def __init__(self, request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db
    
    async def authenticate_refresh_token(self, refresh_token: str) -> Optional[OAuthToken]:
        """Authenticate refresh token with agency validation."""
        result = await self.db.execute(
            select(OAuthToken).where(OAuthToken.refresh_token == refresh_token)
        )
        token = result.scalar_one_or_none()
        
        if token and token.is_refresh_token_active:
            # Verify client and agency match
            client = request.client
            if token.client_id != client.client_id or token.agency_id != client.agency_id:
                return None
            return token
        return None
    
    async def authenticate_user(self, token: OAuthToken) -> Optional[User]:
        """Load user from refresh token."""
        result = await self.db.execute(
            select(User).where(User.id == token.user_id)
        )
        return result.scalar_one_or_none()
    
    async def revoke_old_credential(self, token: OAuthToken):
        """Revoke old token when issuing new one."""
        token.revoke()
        await self.db.commit()


class MultiTenantClientCredentialsGrant(grants.ClientCredentialsGrant):
    """
    Client Credentials Grant for machine-to-machine authentication.
    Used for server-to-server API calls within the same agency.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post']
    GRANT_TYPE = 'client_credentials'
    
    def __init__(self, request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db


class OAuthProvider:
    """
    Main OAuth2 provider class that manages the authorization server.
    Handles all OAuth2 flows with multi-tenant support.
    """
    
    def __init__(self, app=None):
        self.authorization_server = None
        self.resource_protector = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize OAuth provider with FastAPI app."""
        # Create authorization server
        self.authorization_server = AuthorizationServer()
        
        # Register grants
        self.authorization_server.register_grant(
            MultiTenantAuthorizationCodeGrant,
            [CodeChallenge(required=True)]  # Require PKCE
        )
        self.authorization_server.register_grant(MultiTenantRefreshTokenGrant)
        self.authorization_server.register_grant(MultiTenantClientCredentialsGrant)
        
        # Create resource protector for validating tokens
        self.resource_protector = ResourceProtector()
        
        logger.info("OAuth2 provider initialized with multi-tenant support")
    
    async def create_authorization_response(
        self,
        request: Request,
        grant_user: User,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Create authorization response (authorization code)."""
        request.state.db = db
        request.state.user = grant_user
        
        try:
            grant = self.authorization_server.get_consent_grant(request)
            return await grant.create_authorization_response(request)
        except OAuth2Error as error:
            return error.get_body()
    
    async def create_token_response(
        self,
        request: Request,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Create token response for various grant types."""
        request.state.db = db
        
        try:
            grant = self.authorization_server.get_token_grant(request)
            return await grant.create_token_response(request)
        except OAuth2Error as error:
            return error.get_body()
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: Optional[str],
        client: OAuthClient,
        db: AsyncSession
    ) -> bool:
        """Revoke an access or refresh token."""
        # Try to find as access token first
        result = await db.execute(
            select(OAuthToken).where(
                OAuthToken.access_token == token,
                OAuthToken.client_id == client.client_id,
                OAuthToken.agency_id == client.agency_id
            )
        )
        token_obj = result.scalar_one_or_none()
        
        if not token_obj and token_type_hint != 'access_token':
            # Try as refresh token
            result = await db.execute(
                select(OAuthToken).where(
                    OAuthToken.refresh_token == token,
                    OAuthToken.client_id == client.client_id,
                    OAuthToken.agency_id == client.agency_id
                )
            )
            token_obj = result.scalar_one_or_none()
        
        if token_obj:
            token_obj.revoke()
            await db.commit()
            return True
        
        return False
    
    async def introspect_token(
        self,
        token: str,
        token_type_hint: Optional[str],
        client: OAuthClient,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Introspect token to get metadata."""
        # Try to find the token
        result = await db.execute(
            select(OAuthToken).where(
                OAuthToken.access_token == token,
                OAuthToken.agency_id == client.agency_id
            )
        )
        token_obj = result.scalar_one_or_none()
        
        if not token_obj or token_obj.is_expired:
            return {"active": False}
        
        # Load user
        result = await db.execute(
            select(User).where(User.id == token_obj.user_id)
        )
        user = result.scalar_one_or_none()
        
        return {
            "active": True,
            "scope": token_obj.scope,
            "client_id": token_obj.client_id,
            "username": user.email if user else None,
            "exp": int(token_obj.expires_at.timestamp()) if token_obj.expires_at else None,
            "iat": int(token_obj.created_at.timestamp()),
            "sub": str(token_obj.user_id) if token_obj.user_id else None,
            "aud": str(token_obj.agency_id),
            "token_type": token_obj.token_type
        }


# Global OAuth provider instance
oauth_provider = OAuthProvider()


def create_authorization_server(app, get_db_func) -> AuthorizationServer:
    """
    Create and configure the authorization server.
    Used during app initialization.
    """
    oauth_provider.init_app(app)
    return oauth_provider.authorization_server


def create_resource_protector(get_db_func) -> ResourceProtector:
    """
    Create and configure the resource protector.
    Used for protecting API endpoints with OAuth tokens.
    """
    if not oauth_provider.resource_protector:
        oauth_provider.resource_protector = ResourceProtector()
    
    # Configure bearer token validator
    async def bearer_token_validator(token_string: str, scope: str, request: Request) -> Optional[OAuthToken]:
        """Validate bearer token."""
        db = request.state.db
        
        result = await db.execute(
            select(OAuthToken).where(
                OAuthToken.access_token == token_string
            )
        )
        token = result.scalar_one_or_none()
        
        if token and not token.is_expired:
            # Check scope if required
            if scope:
                token_scopes = set(token.scope.split())
                required_scopes = set(scope.split())
                if not required_scopes.issubset(token_scopes):
                    return None
            
            # Add token to request state
            request.state.token = token
            return token
        
        return None
    
    oauth_provider.resource_protector.register_token_validator(bearer_token_validator)
    return oauth_provider.resource_protector


def get_current_oauth_token(request: Request) -> Optional[OAuthToken]:
    """Get current OAuth token from request."""
    return getattr(request.state, 'token', None)


async def get_current_oauth_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from OAuth token."""
    token = get_current_oauth_token(request)
    if not token:
        return None
    
    result = await db.execute(
        select(User).where(User.id == token.user_id)
    )
    return result.scalar_one_or_none()