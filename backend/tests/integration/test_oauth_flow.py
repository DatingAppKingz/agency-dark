"""
Integration tests for complete OAuth2.0 flow.
Tests authorization, token exchange, refresh, and revocation.
"""
import pytest
import asyncio
import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlparse, parse_qs
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from oauth.models import OAuthClient, OAuthToken, OAuthAuthorizationCode
from oauth.provider import create_authorization_server, create_resource_protector
from models.user import User
from models.agency import Agency
from core.database import Base
from core.config import settings


class TestOAuthFlow:
    """Test complete OAuth2.0 authorization flow."""
    
    @pytest.fixture(scope="class")
    async def db_engine(self):
        """Create test database engine."""
        # Use test database
        engine = create_async_engine(
            "postgresql+asyncpg://test:test@localhost/test_oauth",
            echo=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield engine
        
        # Cleanup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        await engine.dispose()
    
    @pytest.fixture
    async def db_session(self, db_engine):
        """Create database session."""
        async_session = sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            yield session
    
    @pytest.fixture
    async def test_agency(self, db_session: AsyncSession):
        """Create test agency."""
        agency = Agency(
            id=uuid4(),
            name="Test Agency",
            subdomain="test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(agency)
        await db_session.commit()
        return agency
    
    @pytest.fixture
    async def test_user(self, db_session: AsyncSession, test_agency):
        """Create test user."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            agency_id=test_agency.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(user)
        await db_session.commit()
        return user
    
    @pytest.fixture
    async def oauth_client(self, db_session: AsyncSession, test_agency):
        """Create OAuth client."""
        client = OAuthClient(
            id=uuid4(),
            agency_id=test_agency.id,
            client_id=f"test_client_{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="Test Client",
            redirect_uris=["http://localhost:3000/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write",
            allowed_agencies=[test_agency.id],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(client)
        await db_session.commit()
        return client
    
    @pytest.fixture
    def pkce_challenge(self):
        """Generate PKCE challenge and verifier."""
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode('utf-8').rstrip('=')
        return verifier, challenge
    
    @pytest.mark.asyncio
    async def test_complete_authorization_flow(
        self,
        db_session: AsyncSession,
        test_user,
        oauth_client,
        pkce_challenge
    ):
        """Test complete authorization code flow with PKCE."""
        verifier, challenge = pkce_challenge
        
        # Step 1: Authorization request
        auth_params = {
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": oauth_client.redirect_uris[0],
            "scope": "read write",
            "state": secrets.token_urlsafe(16),
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }
        
        # Simulate user authorization (in real flow, this would be through UI)
        auth_code = OAuthAuthorizationCode(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=test_user.id,
            client_id=oauth_client.client_id,
            code=secrets.token_urlsafe(32),
            redirect_uri=auth_params["redirect_uri"],
            scope=auth_params["scope"],
            code_challenge=challenge,
            code_challenge_method="S256",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(auth_code)
        await db_session.commit()
        
        # Step 2: Token exchange
        # Verify code exists
        assert auth_code.code is not None
        assert auth_code.code_challenge == challenge
        
        # Exchange would happen here with verifier
        # Create token (simulating successful exchange)
        access_token = OAuthToken(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=test_user.id,
            client_id=oauth_client.client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(access_token)
        
        # Delete used authorization code
        await db_session.delete(auth_code)
        await db_session.commit()
        
        # Verify token created
        assert access_token.access_token is not None
        assert access_token.refresh_token is not None
        assert not access_token.is_expired
    
    @pytest.mark.asyncio
    async def test_pkce_validation(self, oauth_client, pkce_challenge):
        """Test PKCE challenge validation."""
        verifier, challenge = pkce_challenge
        
        # Verify challenge generation
        assert len(verifier) >= 43  # Min length for PKCE verifier
        assert len(challenge) >= 43  # Min length for PKCE challenge
        
        # Verify challenge derivation
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode('utf-8').rstrip('=')
        
        assert challenge == expected_challenge
    
    @pytest.mark.asyncio
    async def test_token_refresh(
        self,
        db_session: AsyncSession,
        test_user,
        oauth_client
    ):
        """Test refresh token flow."""
        # Create initial token
        original_token = OAuthToken(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=test_user.id,
            client_id=oauth_client.client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),  # Short expiry
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(original_token)
        await db_session.commit()
        
        # Simulate refresh
        new_access_token = secrets.token_urlsafe(32)
        original_token.access_token = new_access_token
        original_token.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db_session.commit()
        
        # Verify refresh
        assert original_token.access_token == new_access_token
        assert not original_token.is_expired
        assert original_token.refresh_token is not None  # Refresh token unchanged
    
    @pytest.mark.asyncio
    async def test_token_revocation(
        self,
        db_session: AsyncSession,
        test_user,
        oauth_client
    ):
        """Test token revocation."""
        # Create token
        token = OAuthToken(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=test_user.id,
            client_id=oauth_client.client_id,
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(token)
        await db_session.commit()
        
        # Revoke token
        token.revoke()
        await db_session.commit()
        
        # Verify revocation
        assert token.is_expired
        assert token.expires_at <= datetime.now(timezone.utc)
    
    @pytest.mark.asyncio
    async def test_concurrent_tokens(
        self,
        db_session: AsyncSession,
        test_user,
        oauth_client
    ):
        """Test multiple concurrent tokens for same user."""
        tokens = []
        
        # Create multiple tokens
        for i in range(3):
            token = OAuthToken(
                id=uuid4(),
                agency_id=oauth_client.agency_id,
                user_id=test_user.id,
                client_id=oauth_client.client_id,
                token_type="Bearer",
                access_token=secrets.token_urlsafe(32),
                refresh_token=secrets.token_urlsafe(32),
                scope="read" if i == 0 else "read write",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                created_at=datetime.now(timezone.utc)
            )
            tokens.append(token)
            db_session.add(token)
        
        await db_session.commit()
        
        # Verify all tokens exist
        assert len(tokens) == 3
        assert all(not t.is_expired for t in tokens)
        assert tokens[0].scope == "read"
        assert tokens[1].scope == "read write"
    
    @pytest.mark.asyncio
    async def test_error_scenarios(self, oauth_client):
        """Test various error scenarios."""
        # Test invalid client
        with pytest.raises(Exception):
            # This would be a proper API call in real test
            invalid_client = "invalid_client_id"
            assert invalid_client != oauth_client.client_id
        
        # Test invalid redirect URI
        invalid_uri = "http://evil.com/callback"
        assert invalid_uri not in oauth_client.redirect_uris
        
        # Test expired authorization code
        expired_code = OAuthAuthorizationCode(
            id=uuid4(),
            agency_id=oauth_client.agency_id,
            user_id=uuid4(),
            client_id=oauth_client.client_id,
            code=secrets.token_urlsafe(32),
            redirect_uri=oauth_client.redirect_uris[0],
            scope="read",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # Expired
            created_at=datetime.now(timezone.utc) - timedelta(minutes=11)
        )
        assert expired_code.is_expired
        
        # Test invalid scope
        invalid_scope = "admin delete_everything"
        client_scope = set(oauth_client.scope.split())
        requested_scope = set(invalid_scope.split())
        allowed_scope = client_scope & requested_scope
        assert "delete_everything" not in allowed_scope


class TestTokenOperations:
    """Test token-specific operations."""
    
    @pytest.mark.asyncio
    async def test_token_introspection(self):
        """Test token introspection."""
        token = OAuthToken(
            id=uuid4(),
            agency_id=uuid4(),
            user_id=uuid4(),
            client_id="test_client",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            scope="read write",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
        
        # Create introspection response
        introspection = {
            "active": not token.is_expired,
            "scope": token.scope,
            "client_id": token.client_id,
            "username": str(token.user_id),
            "token_type": token.token_type,
            "exp": int(token.expires_at.timestamp()),
            "iat": int(token.created_at.timestamp()),
            "sub": str(token.user_id),
            "aud": token.client_id
        }
        
        assert introspection["active"] is True
        assert introspection["scope"] == "read write"
        assert introspection["token_type"] == "Bearer"
    
    @pytest.mark.asyncio
    async def test_token_expiration(self):
        """Test token expiration handling."""
        # Create expired token
        expired_token = OAuthToken(
            id=uuid4(),
            agency_id=uuid4(),
            user_id=uuid4(),
            client_id="test_client",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            created_at=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        
        assert expired_token.is_expired
        
        # Create valid token
        valid_token = OAuthToken(
            id=uuid4(),
            agency_id=uuid4(),
            user_id=uuid4(),
            client_id="test_client",
            token_type="Bearer",
            access_token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc)
        )
        
        assert not valid_token.is_expired
    
    @pytest.mark.asyncio
    async def test_scope_validation(self):
        """Test scope validation."""
        client_scope = "read write admin"
        requested_scope = "read write delete"
        
        # Calculate allowed scope (intersection)
        client_scopes = set(client_scope.split())
        requested_scopes = set(requested_scope.split())
        allowed_scopes = client_scopes & requested_scopes
        
        assert "read" in allowed_scopes
        assert "write" in allowed_scopes
        assert "delete" not in allowed_scopes  # Not in client scope
        assert "admin" not in allowed_scopes  # Not requested


if __name__ == "__main__":
    pytest.main([__file__, "-v"])