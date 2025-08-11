"""
Integration tests for external OAuth providers.
Tests provider connections, token exchange, and webhook handling.
"""
import pytest
import secrets
import json
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from oauth.consumer import (
    ExternalOAuthProvider,
    GoogleOAuthProvider,
    InstagramOAuthProvider,
    MicrosoftOAuthProvider,
    ExternalOAuthManager
)
from oauth.models import ExternalOAuthToken
from oauth.encryption import TokenEncryptionService
from api.v1.oauth_webhooks import WebhookValidator


class TestExternalProviders:
    """Test external OAuth provider integrations."""
    
    @pytest.fixture
    def encryption_service(self):
        """Create encryption service."""
        return TokenEncryptionService(master_key=secrets.token_urlsafe(32))
    
    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = AsyncMock(spec=httpx.AsyncClient)
        return client
    
    @pytest.fixture
    def google_provider(self, mock_http_client):
        """Create Google OAuth provider."""
        provider = GoogleOAuthProvider()
        provider.http_client = mock_http_client
        return provider
    
    @pytest.fixture
    def instagram_provider(self, mock_http_client):
        """Create Instagram OAuth provider."""
        provider = InstagramOAuthProvider()
        provider.http_client = mock_http_client
        return provider
    
    @pytest.fixture
    def microsoft_provider(self, mock_http_client):
        """Create Microsoft OAuth provider."""
        provider = MicrosoftOAuthProvider()
        provider.http_client = mock_http_client
        return provider
    
    @pytest.mark.asyncio
    async def test_google_authorization_url(self, google_provider):
        """Test Google authorization URL generation."""
        state = secrets.token_urlsafe(16)
        auth_url, returned_state = await google_provider.get_authorization_url(state)
        
        assert "accounts.google.com" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert returned_state == state
        assert "scope=openid+email+profile" in auth_url
    
    @pytest.mark.asyncio
    async def test_google_token_exchange(self, google_provider, mock_http_client):
        """Test Google token exchange."""
        # Mock token response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "google_access_token",
            "refresh_token": "google_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid email profile",
            "id_token": "jwt_token_here"
        }
        mock_response.raise_for_status = Mock()
        mock_http_client.post.return_value = mock_response
        
        # Exchange code for token
        code = "test_authorization_code"
        token_data = await google_provider.exchange_code_for_token(code)
        
        assert token_data["access_token"] == "google_access_token"
        assert token_data["refresh_token"] == "google_refresh_token"
        assert token_data["expires_in"] == 3600
        assert "id_token" in token_data
    
    @pytest.mark.asyncio
    async def test_google_user_info(self, google_provider, mock_http_client):
        """Test Google user info retrieval."""
        # Mock user info response
        mock_response = Mock()
        mock_response.json.return_value = {
            "sub": "google_user_123",
            "name": "Test User",
            "email": "test@gmail.com",
            "email_verified": True,
            "picture": "https://example.com/photo.jpg"
        }
        mock_response.raise_for_status = Mock()
        mock_http_client.get.return_value = mock_response
        
        # Get user info
        access_token = "google_access_token"
        user_info = await google_provider.get_user_info(access_token)
        
        assert user_info["sub"] == "google_user_123"
        assert user_info["email"] == "test@gmail.com"
        assert user_info["email_verified"] is True
    
    @pytest.mark.asyncio
    async def test_instagram_authorization_url(self, instagram_provider):
        """Test Instagram authorization URL generation."""
        state = secrets.token_urlsafe(16)
        auth_url, returned_state = await instagram_provider.get_authorization_url(state)
        
        assert "api.instagram.com" in auth_url or "facebook.com" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert returned_state == state
    
    @pytest.mark.asyncio
    async def test_instagram_token_exchange(self, instagram_provider, mock_http_client):
        """Test Instagram token exchange."""
        # Mock token response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "instagram_access_token",
            "token_type": "Bearer",
            "expires_in": 5184000,  # 60 days
            "user_id": "instagram_user_123"
        }
        mock_response.raise_for_status = Mock()
        mock_http_client.post.return_value = mock_response
        
        # Exchange code for token
        code = "test_authorization_code"
        token_data = await instagram_provider.exchange_code_for_token(code)
        
        assert token_data["access_token"] == "instagram_access_token"
        assert token_data["user_id"] == "instagram_user_123"
    
    @pytest.mark.asyncio
    async def test_microsoft_authorization_url(self, microsoft_provider):
        """Test Microsoft authorization URL generation."""
        state = secrets.token_urlsafe(16)
        auth_url, returned_state = await microsoft_provider.get_authorization_url(state)
        
        assert "login.microsoftonline.com" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert returned_state == state
        assert "scope=openid+email+profile" in auth_url
    
    @pytest.mark.asyncio
    async def test_microsoft_token_exchange(self, microsoft_provider, mock_http_client):
        """Test Microsoft token exchange."""
        # Mock token response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "microsoft_access_token",
            "refresh_token": "microsoft_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid email profile",
            "id_token": "jwt_token_here"
        }
        mock_response.raise_for_status = Mock()
        mock_http_client.post.return_value = mock_response
        
        # Exchange code for token
        code = "test_authorization_code"
        token_data = await microsoft_provider.exchange_code_for_token(code)
        
        assert token_data["access_token"] == "microsoft_access_token"
        assert token_data["refresh_token"] == "microsoft_refresh_token"
    
    @pytest.mark.asyncio
    async def test_token_refresh(self, google_provider, mock_http_client):
        """Test token refresh flow."""
        # Mock refresh response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid email profile"
        }
        mock_response.raise_for_status = Mock()
        mock_http_client.post.return_value = mock_response
        
        # Refresh token
        refresh_token = "google_refresh_token"
        new_token = await google_provider.refresh_token(refresh_token)
        
        assert new_token["access_token"] == "new_access_token"
        assert new_token["expires_in"] == 3600


class TestTokenEncryption:
    """Test token encryption for external providers."""
    
    @pytest.fixture
    def encryption_service(self):
        """Create encryption service."""
        return TokenEncryptionService()
    
    @pytest.fixture
    def secure_storage(self, encryption_service):
        """Create secure token storage."""
        from oauth.encryption import SecureTokenStorage
        return SecureTokenStorage(encryption_service)
    
    @pytest.mark.asyncio
    async def test_token_encryption(self, secure_storage):
        """Test encrypting and storing external tokens."""
        # Store encrypted token
        result = secure_storage.store_token(
            provider="google",
            user_id="user_123",
            access_token="plain_access_token",
            refresh_token="plain_refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="openid email profile"
        )
        
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["access_token"] != "plain_access_token"  # Encrypted
        assert result["refresh_token"] != "plain_refresh_token"  # Encrypted
    
    @pytest.mark.asyncio
    async def test_token_decryption(self, secure_storage):
        """Test decrypting stored tokens."""
        # Store token
        result = secure_storage.store_token(
            provider="google",
            user_id="user_123",
            access_token="plain_access_token",
            refresh_token="plain_refresh_token"
        )
        
        # Retrieve and decrypt
        decrypted_access, metadata = secure_storage.retrieve_token(
            result["access_token"],
            expected_provider="google",
            expected_user_id="user_123"
        )
        
        assert decrypted_access == "plain_access_token"
        assert metadata["provider"] == "google"
        assert metadata["user_id"] == "user_123"
    
    @pytest.mark.asyncio
    async def test_token_rotation(self, encryption_service):
        """Test encryption key rotation."""
        original_token = "test_token"
        
        # Encrypt with current key
        encrypted = encryption_service.encrypt_token(original_token)
        
        # Rotate encryption
        rotated = encryption_service.rotate_encryption(encrypted)
        
        # Decrypt rotated token
        decrypted, _ = encryption_service.decrypt_token(rotated)
        
        assert decrypted == original_token


class TestWebhookHandling:
    """Test webhook handling from external providers."""
    
    @pytest.fixture
    def webhook_validator(self):
        """Create webhook validator."""
        return WebhookValidator()
    
    def test_google_webhook_signature(self, webhook_validator):
        """Test Google webhook signature validation."""
        secret = "google_webhook_secret"
        body = b'{"type": "token.revoked", "sub": "user_123"}'
        
        # Generate valid signature
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Validate
        is_valid = webhook_validator.validate_google_webhook(body, signature, secret)
        assert is_valid is True
        
        # Test invalid signature
        invalid_signature = "invalid_signature"
        is_invalid = webhook_validator.validate_google_webhook(body, invalid_signature, secret)
        assert is_invalid is False
    
    def test_instagram_webhook_signature(self, webhook_validator):
        """Test Instagram webhook signature validation."""
        app_secret = "instagram_app_secret"
        body = b'{"entry": [{"changes": [{"field": "permission"}]}]}'
        
        # Generate valid signature
        expected = hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={expected}"
        
        # Validate
        is_valid = webhook_validator.validate_instagram_webhook(body, signature, app_secret)
        assert is_valid is True
        
        # Test invalid signature
        invalid_signature = "sha256=invalid"
        is_invalid = webhook_validator.validate_instagram_webhook(body, invalid_signature, app_secret)
        assert is_invalid is False
    
    def test_microsoft_webhook_validation(self, webhook_validator):
        """Test Microsoft webhook validation."""
        # Test validation token (subscription confirmation)
        validation_token = "test_validation_token"
        is_valid = webhook_validator.validate_microsoft_webhook(
            b"",
            validation_token,
            None
        )
        assert is_valid is True
        
        # Test client state validation
        client_state = "expected_state"
        with patch("core.config.settings.MICROSOFT_WEBHOOK_STATE", "expected_state"):
            is_valid = webhook_validator.validate_microsoft_webhook(
                b"",
                None,
                client_state
            )
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_token_revocation_webhook(self):
        """Test handling token revocation webhook."""
        # Mock database session
        mock_db = AsyncMock()
        
        # Mock tokens to be revoked
        mock_tokens = [
            Mock(spec=ExternalOAuthToken, user_id=uuid4(), expires_at=None)
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_tokens
        
        # Handle revocation
        from api.v1.oauth_webhooks import handle_token_revocation
        await handle_token_revocation("google", "user_123", mock_db)
        
        # Verify token was marked as revoked
        for token in mock_tokens:
            assert token.expires_at is not None
    
    @pytest.mark.asyncio
    async def test_account_removal_webhook(self):
        """Test handling account removal webhook."""
        # Mock database session
        mock_db = AsyncMock()
        
        # Mock tokens to be removed
        mock_tokens = [
            Mock(spec=ExternalOAuthToken, user_id=uuid4())
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_tokens
        
        # Handle account removal
        from api.v1.oauth_webhooks import handle_account_removal
        await handle_account_removal("instagram", "user_123", mock_db)
        
        # Verify tokens were deleted
        assert mock_db.delete.called
        assert mock_db.commit.called


class TestExternalOAuthManager:
    """Test external OAuth manager operations."""
    
    @pytest.fixture
    async def oauth_manager(self):
        """Create OAuth manager."""
        mock_db = AsyncMock()
        return ExternalOAuthManager(mock_db)
    
    @pytest.mark.asyncio
    async def test_link_external_account(self, oauth_manager):
        """Test linking external account."""
        # Mock the database operations
        oauth_manager.db.add = Mock()
        oauth_manager.db.commit = AsyncMock()
        
        # Link account
        await oauth_manager.link_external_account(
            user_id="user_123",
            agency_id="agency_123",
            provider="google",
            access_token="encrypted_token",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="openid email profile"
        )
        
        # Verify account was linked
        assert oauth_manager.db.add.called
        assert oauth_manager.db.commit.called
    
    @pytest.mark.asyncio
    async def test_refresh_external_token(self, oauth_manager):
        """Test refreshing external token."""
        # Mock existing token
        mock_token = Mock(
            spec=ExternalOAuthToken,
            provider="google",
            refresh_token="encrypted_refresh",
            needs_refresh=Mock(return_value=True)
        )
        
        oauth_manager.db.execute.return_value.scalar_one_or_none.return_value = mock_token
        
        # Mock provider
        with patch("oauth.consumer.oauth_provider_registry.get_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.refresh_token.return_value = {
                "access_token": "new_token",
                "expires_in": 3600
            }
            mock_get_provider.return_value = mock_provider
            
            # Refresh token
            result = await oauth_manager.refresh_external_token("user_123", "google")
            
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])