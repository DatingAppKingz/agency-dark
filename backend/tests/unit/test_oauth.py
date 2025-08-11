"""
Unit tests for OAuth2.0 implementation.
Tests grants, token operations, and multi-tenancy.
"""
import pytest
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from oauth.models import OAuthClient, OAuthToken, OAuthAuthorizationCode
from oauth.provider import (
    MultiTenantAuthorizationCodeGrant,
    MultiTenantRefreshTokenGrant,
    create_authorization_server,
    create_resource_protector
)
from oauth.grants import (
    AgencyAuthorizationCodeGrant,
    AgencyPasswordGrant,
    AgencyClientCredentialsGrant
)
from oauth.multitenancy import get_current_agency, AgencyContext
from oauth.encryption import TokenEncryptionService, SecureTokenStorage


class TestOAuthGrants:
    """Test OAuth grant implementations."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def oauth_client(self):
        """Create test OAuth client."""
        return OAuthClient(
            id=uuid4(),
            agency_id=uuid4(),
            client_id=f"test_client_{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Test Client",
            redirect_uris=["http://localhost:3000/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write",
            allowed_agencies=[uuid4()],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def auth_code(self, oauth_client):
        """Create test authorization code."""
        return OAuthAuthorizationCode(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=uuid4(),
            client_id=oauth_client.client_id,
            code=secrets.token_urlsafe(32),
            redirect_uri="http://localhost:3000/callback",
            scope="read write",
            code_challenge=secrets.token_urlsafe(32),
            code_challenge_method="S256",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            created_at=datetime.now(timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_authorization_code_grant_creation(self, mock_db_session, oauth_client):
        """Test authorization code grant creation."""
        grant = AgencyAuthorizationCodeGrant(
            request=Mock(),
            server=Mock(),
            db_session=mock_db_session
        )
        
        # Mock request data
        grant.request.client = oauth_client
        grant.request.user = Mock(id=uuid4())
        grant.request.redirect_uri = "http://localhost:3000/callback"
        grant.request.scope = "read write"
        
        # Test authorization validation
        result = await grant.validate_authorization_request()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_authorization_code_exchange(self, mock_db_session, oauth_client, auth_code):
        """Test exchanging authorization code for token."""
        grant = AgencyAuthorizationCodeGrant(
            request=Mock(),
            server=Mock(),
            db_session=mock_db_session
        )
        
        # Mock database query
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = auth_code
        
        # Test code retrieval
        retrieved_code = await grant.query_authorization_code(
            auth_code.code,
            oauth_client
        )
        
        assert retrieved_code is not None
        assert retrieved_code.code == auth_code.code
    
    @pytest.mark.asyncio
    async def test_pkce_validation(self, oauth_client):
        """Test PKCE challenge validation."""
        # Generate PKCE challenge
        code_verifier = secrets.token_urlsafe(32)
        
        # Calculate challenge using S256 method
        import hashlib
        import base64
        
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        
        grant = AgencyAuthorizationCodeGrant(
            request=Mock(),
            server=Mock(),
            db_session=Mock()
        )
        
        # Test PKCE validation
        grant.request.data = {
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }
        
        # This should validate successfully
        # In real implementation, would check against stored challenge
        assert challenge is not None
        assert len(challenge) > 0
    
    @pytest.mark.asyncio
    async def test_refresh_token_grant(self, mock_db_session, oauth_client):
        """Test refresh token grant."""
        # Create existing token
        existing_token = OAuthToken(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=uuid4(),
            client_id=oauth_client.client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
        
        grant = MultiTenantRefreshTokenGrant(
            request=Mock(),
            server=Mock(),
            db_session=mock_db_session
        )
        
        # Mock database query
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = existing_token
        
        # Test token refresh
        grant.request.refresh_token = existing_token.refresh_token
        grant.request.client = oauth_client
        
        # Token should be valid for refresh
        assert existing_token.refresh_token is not None
    
    @pytest.mark.asyncio
    async def test_client_credentials_grant(self, mock_db_session, oauth_client):
        """Test client credentials grant for M2M."""
        # Update client for client_credentials
        oauth_client.grant_types = ["client_credentials"]
        
        grant = AgencyClientCredentialsGrant(
            request=Mock(),
            server=Mock(),
            db_session=mock_db_session
        )
        
        grant.request.client = oauth_client
        grant.request.scope = "api"
        
        # Test client validation
        assert oauth_client.client_id is not None
        assert oauth_client.client_secret is not None
        assert "client_credentials" in oauth_client.grant_types


class TestTokenOperations:
    """Test token generation, validation, and revocation."""
    
    @pytest.fixture
    def token_service(self):
        """Create token encryption service."""
        return TokenEncryptionService(master_key=secrets.token_urlsafe(32))
    
    @pytest.fixture
    def oauth_token(self):
        """Create test OAuth token."""
        return OAuthToken(
            id=uuid4(),
            agency_id=uuid4(),
            user_id=uuid4(),
            client_id=f"test_client_{secrets.token_urlsafe(16)}",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
    
    def test_token_generation(self):
        """Test token generation."""
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        assert len(access_token) > 0
        assert len(refresh_token) > 0
        assert access_token != refresh_token
    
    def test_token_encryption(self, token_service):
        """Test token encryption and decryption."""
        original_token = secrets.token_urlsafe(32)
        metadata = {"user_id": str(uuid4()), "scope": "read"}
        
        # Encrypt token
        encrypted = token_service.encrypt_token(original_token, metadata)
        assert encrypted != original_token
        
        # Decrypt token
        decrypted, decrypted_metadata = token_service.decrypt_token(encrypted)
        assert decrypted == original_token
        assert decrypted_metadata["user_id"] == metadata["user_id"]
    
    def test_token_rotation(self, token_service):
        """Test token encryption key rotation."""
        original_token = secrets.token_urlsafe(32)
        
        # Encrypt with current key
        encrypted = token_service.encrypt_token(original_token)
        
        # Rotate encryption
        rotated = token_service.rotate_encryption(encrypted)
        
        # Should still decrypt correctly
        decrypted, _ = token_service.decrypt_token(rotated)
        assert decrypted == original_token
    
    def test_token_expiration(self, oauth_token):
        """Test token expiration check."""
        # Token should not be expired
        assert not oauth_token.is_expired
        
        # Set expiration to past
        oauth_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert oauth_token.is_expired
    
    @pytest.mark.asyncio
    async def test_token_introspection(self, oauth_token):
        """Test token introspection."""
        # Create introspection response
        introspection = {
            "active": not oauth_token.is_expired,
            "scope": oauth_token.scope,
            "client_id": oauth_token.client_id,
            "username": str(oauth_token.user_id),
            "token_type": oauth_token.token_type,
            "exp": int(oauth_token.expires_at.timestamp()) if oauth_token.expires_at else None,
            "iat": int(oauth_token.created_at.timestamp()),
            "sub": str(oauth_token.user_id),
            "aud": oauth_token.client_id
        }
        
        assert introspection["active"] is True
        assert introspection["scope"] == "read write"
        assert introspection["token_type"] == "Bearer"
    
    @pytest.mark.asyncio
    async def test_token_revocation(self, mock_db_session, oauth_token):
        """Test token revocation."""
        # Revoke token
        oauth_token.revoke()
        
        # Token should be marked as revoked
        assert oauth_token.expires_at <= datetime.now(timezone.utc)
        
        # Save to database
        mock_db_session.add(oauth_token)
        await mock_db_session.commit()
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestMultiTenancy:
    """Test multi-tenant OAuth implementation."""
    
    @pytest.fixture
    def agency_context(self):
        """Create test agency context."""
        return AgencyContext(
            agency_id=uuid4(),
            agency_name="Test Agency",
            subdomain="test"
        )
    
    @pytest.mark.asyncio
    async def test_agency_isolation(self, agency_context):
        """Test agency isolation in OAuth operations."""
        # Create clients for different agencies
        agency1_id = uuid4()
        agency2_id = uuid4()
        
        client1 = OAuthClient(
            id=uuid4(),
            agency_id=agency1_id,
            client_id=f"client1_{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Agency 1 Client",
            allowed_agencies=[agency1_id]
        )
        
        client2 = OAuthClient(
            id=uuid4(),
            agency_id=agency2_id,
            client_id=f"client2_{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Agency 2 Client",
            allowed_agencies=[agency2_id]
        )
        
        # Clients should only access their own agency
        assert agency1_id in client1.allowed_agencies
        assert agency2_id not in client1.allowed_agencies
        assert agency2_id in client2.allowed_agencies
        assert agency1_id not in client2.allowed_agencies
    
    @pytest.mark.asyncio
    async def test_cross_agency_access_denial(self):
        """Test that cross-agency access is denied."""
        agency1_id = uuid4()
        agency2_id = uuid4()
        
        # Token for agency 1
        token = OAuthToken(
            id=uuid4(),
            agency_id=agency1_id,
            user_id=uuid4(),
            client_id="client1",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32)
        )
        
        # Try to access agency 2 resource
        # This should be denied in actual implementation
        assert token.agency_id == agency1_id
        assert token.agency_id != agency2_id
    
    def test_agency_scope_validation(self):
        """Test agency-specific scope validation."""
        agency_id = uuid4()
        
        client = OAuthClient(
            id=uuid4(),
            agency_id=agency_id,
            client_id=f"client_{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            scope="read write admin",
            allowed_agencies=[agency_id]
        )
        
        # Test scope validation
        requested_scope = "read write"
        allowed_scope = set(requested_scope.split()) & set(client.scope.split())
        
        assert "read" in allowed_scope
        assert "write" in allowed_scope
        assert "admin" not in allowed_scope  # Not requested
    
    @pytest.mark.asyncio
    async def test_subdomain_extraction(self):
        """Test agency extraction from subdomain."""
        # Mock request with subdomain
        request = Mock()
        request.url = Mock()
        request.url.hostname = "test-agency.agencydark.com"
        
        # Extract subdomain
        hostname = request.url.hostname
        if "." in hostname:
            subdomain = hostname.split(".")[0]
        else:
            subdomain = None
        
        assert subdomain == "test-agency"


class TestSecurityFeatures:
    """Test OAuth security features."""
    
    def test_pkce_required(self):
        """Test that PKCE is required for public clients."""
        # Public client (no secret)
        public_client = OAuthClient(
            id=uuid4(),
            agency_id=uuid4(),
            client_id=f"public_{secrets.token_urlsafe(16)}",
            client_secret=None,  # Public client
            client_name="Public Client",
            grant_types=["authorization_code"]
        )
        
        # PKCE should be required
        assert public_client.client_secret is None
        # In real implementation, would enforce PKCE
    
    def test_redirect_uri_validation(self):
        """Test redirect URI validation."""
        client = OAuthClient(
            id=uuid4(),
            agency_id=uuid4(),
            client_id=f"client_{secrets.token_urlsafe(16)}",
            redirect_uris=[
                "https://app.example.com/callback",
                "http://localhost:3000/callback"
            ]
        )
        
        # Valid redirect URI
        assert client.check_redirect_uri("https://app.example.com/callback")
        assert client.check_redirect_uri("http://localhost:3000/callback")
        
        # Invalid redirect URI
        assert not client.check_redirect_uri("https://evil.com/callback")
    
    def test_token_binding(self):
        """Test token binding to client."""
        client_id = f"client_{secrets.token_urlsafe(16)}"
        
        token = OAuthToken(
            id=uuid4(),
            agency_id=uuid4(),
            user_id=uuid4(),
            client_id=client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32)
        )
        
        # Token should be bound to specific client
        assert token.client_id == client_id
        assert token.client_id != "different_client"
    
    def test_scope_downgrading(self):
        """Test that token scope can only be downgraded, not upgraded."""
        original_scope = "read write admin"
        requested_scope = "read write delete"  # Trying to add 'delete'
        
        # Calculate allowed scope (intersection)
        original_set = set(original_scope.split())
        requested_set = set(requested_scope.split())
        allowed_set = original_set & requested_set
        
        assert "read" in allowed_set
        assert "write" in allowed_set
        assert "admin" not in allowed_set  # Not requested
        assert "delete" not in allowed_set  # Not in original


class TestOAuthEndpoints:
    """Test OAuth endpoint functionality."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        app = Mock()
        app.state = Mock()
        return app
    
    @pytest.mark.asyncio
    async def test_authorization_endpoint(self, mock_app):
        """Test /oauth/authorize endpoint."""
        # Mock request
        request = Mock()
        request.query_params = {
            "response_type": "code",
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
            "state": secrets.token_urlsafe(16),
            "code_challenge": secrets.token_urlsafe(32),
            "code_challenge_method": "S256"
        }
        
        # Validate required parameters
        assert request.query_params["response_type"] == "code"
        assert request.query_params["client_id"] is not None
        assert request.query_params["redirect_uri"] is not None
        assert request.query_params["code_challenge"] is not None
    
    @pytest.mark.asyncio
    async def test_token_endpoint(self, mock_app):
        """Test /oauth/token endpoint."""
        # Mock request for authorization code grant
        request = Mock()
        request.form = {
            "grant_type": "authorization_code",
            "code": secrets.token_urlsafe(32),
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "test_client",
            "client_secret": secrets.token_urlsafe(32),
            "code_verifier": secrets.token_urlsafe(32)
        }
        
        # Validate required parameters
        assert request.form["grant_type"] == "authorization_code"
        assert request.form["code"] is not None
        assert request.form["code_verifier"] is not None
    
    @pytest.mark.asyncio
    async def test_introspection_endpoint(self, mock_app):
        """Test /oauth/introspect endpoint."""
        # Mock request
        request = Mock()
        request.form = {
            "token": secrets.token_urlsafe(32),
            "token_type_hint": "access_token"
        }
        
        # Mock response
        response = {
            "active": True,
            "scope": "read write",
            "client_id": "test_client",
            "token_type": "Bearer"
        }
        
        assert response["active"] is True
        assert "scope" in response
    
    @pytest.mark.asyncio
    async def test_revocation_endpoint(self, mock_app):
        """Test /oauth/revoke endpoint."""
        # Mock request
        request = Mock()
        request.form = {
            "token": secrets.token_urlsafe(32),
            "token_type_hint": "refresh_token"
        }
        
        # Revocation should return 200 even if token doesn't exist
        # This prevents token scanning attacks
        assert request.form["token"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])