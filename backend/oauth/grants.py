"""
Custom OAuth2 grant implementations with agency-level validation.
Extends Authlib grants with multi-tenant support and enhanced security.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import secrets
import logging
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6749.errors import (
    OAuth2Error,
    InvalidClientError,
    InvalidRequestError,
    InvalidGrantError,
    UnauthorizedClientError,
    AccessDeniedError
)
from authlib.oauth2.rfc7636 import CodeChallenge
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import Request, Response

from .models import (
    OAuthClient,
    OAuthToken,
    OAuthAuthorizationCode,
    OAuthConsentRecord
)
from .config import oauth_config
from models.user import User
from models.agency import Agency
from core.security_v2.authentication.password_handler import PasswordHandler

logger = logging.getLogger(__name__)


class AgencyAuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    """
    Enhanced Authorization Code Grant with agency-level validation.
    Includes consent management and multi-tenant support.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = oauth_config.TOKEN_ENDPOINT_AUTH_METHODS
    GRANT_TYPE = 'authorization_code'
    
    def __init__(self, request: Request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db
        self.password_handler = PasswordHandler()
    
    async def validate_authorization_request(self):
        """
        Validate the authorization request with agency context.
        """
        # Get client
        client_id = self.request.data.get('client_id')
        if not client_id:
            raise InvalidRequestError('Missing client_id')
        
        result = await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            raise InvalidClientError('Invalid client')
        
        # Validate redirect URI
        redirect_uri = self.request.data.get('redirect_uri')
        if redirect_uri and not client.check_redirect_uri(redirect_uri):
            raise InvalidRequestError('Invalid redirect_uri')
        
        # Validate response type
        response_type = self.request.data.get('response_type')
        if not client.check_response_type(response_type):
            raise UnauthorizedClientError('Unsupported response_type')
        
        # Validate scope
        scope = self.request.data.get('scope', '')
        allowed_scope = client.get_allowed_scope(scope)
        
        # Check PKCE if required
        if oauth_config.REQUIRE_PKCE:
            code_challenge = self.request.data.get('code_challenge')
            if not code_challenge:
                raise InvalidRequestError('PKCE required: missing code_challenge')
            
            code_challenge_method = self.request.data.get('code_challenge_method', 'S256')
            if code_challenge_method not in oauth_config.PKCE_METHODS_SUPPORTED:
                raise InvalidRequestError(f'Unsupported code_challenge_method: {code_challenge_method}')
        
        # Store client in request
        self.request.client = client
        self.request.redirect_uri = redirect_uri or client.redirect_uris[0]
        self.request.scope = allowed_scope
        
        return client
    
    async def create_authorization_response(self, grant_user: User):
        """
        Create authorization response with consent check.
        """
        client = self.request.client
        
        # Check for existing consent
        if oauth_config.REQUIRE_CONSENT:
            consent = await self._check_user_consent(grant_user, client)
            if not consent:
                # Need to show consent screen
                return await self._prepare_consent_data(grant_user, client)
        
        # Verify agency membership
        if not await self._verify_agency_access(grant_user, client):
            raise AccessDeniedError('User does not have access to this agency')
        
        # Generate authorization code
        code = OAuthAuthorizationCode.generate_code()
        
        # Save authorization code
        auth_code = OAuthAuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=self.request.redirect_uri,
            scope=self.request.scope,
            user_id=grant_user.id,
            agency_id=client.agency_id,
            code_challenge=self.request.data.get('code_challenge'),
            code_challenge_method=self.request.data.get('code_challenge_method', 'S256'),
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=oauth_config.AUTHORIZATION_CODE_LIFETIME
            )
        )
        
        self.db.add(auth_code)
        await self.db.commit()
        
        # Build redirect URI with code
        params = {'code': code}
        if self.request.data.get('state'):
            params['state'] = self.request.data.get('state')
        
        return {
            'status': 'redirect',
            'redirect_uri': self._build_redirect_uri(self.request.redirect_uri, params)
        }
    
    async def _check_user_consent(self, user: User, client: OAuthClient) -> Optional[OAuthConsentRecord]:
        """Check if user has valid consent for this client."""
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user.id,
                    OAuthConsentRecord.client_id == client.client_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consent = result.scalar_one_or_none()
        
        if consent and consent.is_valid:
            # Check if requested scopes are covered
            consented_scopes = set(consent.scope.split())
            requested_scopes = set(self.request.scope.split())
            if requested_scopes.issubset(consented_scopes):
                return consent
        
        return None
    
    async def _prepare_consent_data(self, user: User, client: OAuthClient) -> Dict[str, Any]:
        """Prepare data for consent screen."""
        scopes = self.request.scope.split()
        scope_descriptions = [
            {
                'name': scope,
                'description': oauth_config.get_scope_description(scope)
            }
            for scope in scopes
        ]
        
        return {
            'status': 'consent_required',
            'client': {
                'name': client.client_name or client.client_id,
                'id': client.client_id
            },
            'user': {
                'email': user.email,
                'name': getattr(user, 'name', user.email)
            },
            'scopes': scope_descriptions,
            'request_id': secrets.token_urlsafe(32)  # For CSRF protection
        }
    
    async def _verify_agency_access(self, user: User, client: OAuthClient) -> bool:
        """Verify user has access to the client's agency."""
        # Check if user belongs to the same agency
        if hasattr(user, 'agency_id') and user.agency_id == client.agency_id:
            return True
        
        # Check if cross-agency access is allowed
        if oauth_config.ENABLE_CROSS_AGENCY_ACCESS and client.allowed_agencies:
            if hasattr(user, 'agency_id') and user.agency_id in client.allowed_agencies:
                return True
        
        return False
    
    def _build_redirect_uri(self, base_uri: str, params: Dict[str, str]) -> str:
        """Build redirect URI with parameters."""
        from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
        
        parsed = urlparse(base_uri)
        query_params = parse_qs(parsed.query)
        query_params.update(params)
        
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))


class AgencyPasswordGrant(grants.ResourceOwnerPasswordCredentialsGrant):
    """
    Password Grant for legacy support during migration.
    Should be deprecated once OAuth migration is complete.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post']
    GRANT_TYPE = 'password'
    
    def __init__(self, request: Request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db
        self.password_handler = PasswordHandler()
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username/password."""
        # Find user by email
        result = await self.db.execute(
            select(User).where(User.email == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Password grant: User not found: {username}")
            return None
        
        # Verify password
        if not await self.password_handler.verify_password(password, user.password_hash):
            logger.warning(f"Password grant: Invalid password for user: {username}")
            return None
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Password grant: Inactive user attempted login: {username}")
            return None
        
        return user
    
    async def authenticate_client(self, client_id: str, client_secret: Optional[str]) -> Optional[OAuthClient]:
        """Authenticate the client."""
        result = await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return None
        
        # Check client secret if provided
        if client_secret and not client.check_client_secret(client_secret):
            return None
        
        # Verify password grant is allowed for this client
        if 'password' not in client.grant_types:
            logger.warning(f"Password grant not allowed for client: {client_id}")
            return None
        
        return client
    
    async def create_token_response(self):
        """Create token response for password grant."""
        client = await self.authenticate_client(
            self.request.data.get('client_id'),
            self.request.data.get('client_secret')
        )
        
        if not client:
            raise InvalidClientError('Invalid client credentials')
        
        user = await self.authenticate_user(
            self.request.data.get('username'),
            self.request.data.get('password')
        )
        
        if not user:
            raise InvalidGrantError('Invalid username or password')
        
        # Verify agency access
        if hasattr(user, 'agency_id') and user.agency_id != client.agency_id:
            if not oauth_config.ENABLE_CROSS_AGENCY_ACCESS:
                raise AccessDeniedError('User does not belong to client agency')
        
        # Generate tokens
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        # Create token record
        token = OAuthToken(
            agency_id=client.agency_id,
            user_id=user.id,
            client_id=client.client_id,
            token_type='Bearer',
            access_token=access_token,
            refresh_token=refresh_token,
            scope=self.request.data.get('scope', ''),
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=oauth_config.ACCESS_TOKEN_LIFETIME
            ),
            extra_data={
                'grant_type': 'password',
                'user_email': user.email
            }
        )
        
        self.db.add(token)
        await self.db.commit()
        
        return token.to_dict()


class AgencyClientCredentialsGrant(grants.ClientCredentialsGrant):
    """
    Client Credentials Grant for machine-to-machine authentication.
    Used for server-to-server API calls within the same agency.
    """
    
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post', 'client_secret_jwt']
    GRANT_TYPE = 'client_credentials'
    
    def __init__(self, request: Request, server):
        super().__init__(request, server)
        self.db: AsyncSession = request.state.db
    
    async def authenticate_client(self, client_id: str, client_secret: str) -> Optional[OAuthClient]:
        """Authenticate the client for client credentials grant."""
        result = await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return None
        
        # Verify client secret
        if not client.check_client_secret(client_secret):
            return None
        
        # Verify client credentials grant is allowed
        if 'client_credentials' not in client.grant_types:
            logger.warning(f"Client credentials grant not allowed for client: {client_id}")
            return None
        
        return client
    
    async def create_token_response(self):
        """Create token response for client credentials grant."""
        client = await self.authenticate_client(
            self.request.data.get('client_id'),
            self.request.data.get('client_secret')
        )
        
        if not client:
            raise InvalidClientError('Invalid client credentials')
        
        # Generate access token (no refresh token for client credentials)
        access_token = secrets.token_urlsafe(32)
        
        # Create token record (no user_id for M2M tokens)
        token = OAuthToken(
            agency_id=client.agency_id,
            user_id=None,  # No user for M2M
            client_id=client.client_id,
            token_type='Bearer',
            access_token=access_token,
            refresh_token=None,  # No refresh token for client credentials
            scope=client.get_allowed_scope(self.request.data.get('scope', '')),
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=oauth_config.ACCESS_TOKEN_LIFETIME
            ),
            extra_data={
                'grant_type': 'client_credentials',
                'client_name': client.client_name
            }
        )
        
        self.db.add(token)
        await self.db.commit()
        
        return token.to_dict()


class ConsentGrant:
    """
    Handle user consent for OAuth authorization.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def save_user_consent(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        remember: bool = False
    ) -> OAuthConsentRecord:
        """Save user consent for a client."""
        # Check for existing consent
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing consent
            existing.scope = scope
            existing.granted_at = datetime.now(timezone.utc)
            existing.revoked_at = None
            if remember:
                existing.expires_at = datetime.now(timezone.utc) + timedelta(
                    days=oauth_config.CONSENT_VALIDITY_DAYS
                )
            else:
                existing.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            await self.db.commit()
            return existing
        
        # Create new consent
        consent = OAuthConsentRecord(
            user_id=user_id,
            client_id=client_id,
            scope=scope,
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=oauth_config.CONSENT_VALIDITY_DAYS if remember else 0,
                hours=1 if not remember else 0
            )
        )
        
        self.db.add(consent)
        await self.db.commit()
        
        return consent
    
    async def revoke_user_consent(self, user_id: str, client_id: str) -> bool:
        """Revoke user consent for a client."""
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consent = result.scalar_one_or_none()
        
        if consent:
            consent.revoke()
            await self.db.commit()
            return True
        
        return False
    
    async def get_user_consents(self, user_id: str) -> List[OAuthConsentRecord]:
        """Get all consents for a user."""
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            ).order_by(OAuthConsentRecord.granted_at.desc())
        )
        return result.scalars().all()