"""
Tests for OnlyFans API client v2 using External API Framework
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from decimal import Decimal
from pydantic import SecretStr

from modules.onlyfans_wrapper.domain.schemas import OnlyFansConfig, OnlyFansProfile, OnlyFansFan
from modules.onlyfans_wrapper.infrastructure.client_v2 import OnlyFansClient
from modules.onlyfans_wrapper.infrastructure.webhooks import OnlyFansWebhookHandler
from core.external_api import APIRateLimitError, APIAuthenticationError


@pytest.fixture
def onlyfans_config():
    """Create test OnlyFans configuration"""
    return OnlyFansConfig(
        base_url="https://onlyfansapi.com/api/v1",
        api_key="test-api-key",
        timeout=30,
        max_retries=3,
        cookie="test-cookie",
        x_bc="test-x-bc"
    )


@pytest.fixture
def onlyfans_client(onlyfans_config):
    """Create test OnlyFans client"""
    return OnlyFansClient(onlyfans_config)


class TestOnlyFansClient:
    """Test OnlyFansClient functionality"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, onlyfans_client, onlyfans_config):
        """Test client initialization"""
        assert onlyfans_client.config.name == "onlyfans"
        assert onlyfans_client.config.base_url == onlyfans_config.base_url
        assert onlyfans_client.config.timeout == onlyfans_config.timeout
        assert onlyfans_client.config.credentials.api_key.get_secret_value() == onlyfans_config.api_key
        assert onlyfans_client.config.custom_headers['Cookie'] == onlyfans_config.cookie
        assert onlyfans_client.config.custom_headers['X-BC'] == onlyfans_config.x_bc
        
    @pytest.mark.asyncio
    async def test_default_headers(self, onlyfans_client):
        """Test default headers include all required fields"""
        headers = onlyfans_client.get_default_headers()
        
        assert headers['User-Agent'] == 'AgencyDark/2.0'
        assert headers['Accept'] == 'application/json'
        assert headers['Content-Type'] == 'application/json'
        assert headers['X-API-Key'] == 'test-api-key'
        assert headers['Cookie'] == 'test-cookie'
        assert headers['X-BC'] == 'test-x-bc'
        
    @pytest.mark.asyncio
    async def test_authenticate_success(self, onlyfans_client):
        """Test successful authentication"""
        with patch.object(onlyfans_client, 'get_profile') as mock_get_profile:
            mock_get_profile.return_value = OnlyFansProfile(
                id="user123",
                username="testmodel",
                name="Test Model",
                about="Test bio",
                avatar_url="https://example.com/avatar.jpg"
            )
            
            result = await onlyfans_client.authenticate()
            
            assert result is True
            assert onlyfans_client._authenticated is True
            mock_get_profile.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, onlyfans_client):
        """Test failed authentication"""
        with patch.object(onlyfans_client, 'get_profile') as mock_get_profile:
            mock_get_profile.side_effect = APIAuthenticationError("Invalid API key")
            
            result = await onlyfans_client.authenticate()
            
            assert result is False
            assert onlyfans_client._authenticated is False
            
    @pytest.mark.asyncio
    async def test_rate_limiting(self, onlyfans_client):
        """Test rate limiting is applied"""
        with patch.object(onlyfans_client.rate_limiter, 'acquire') as mock_acquire:
            mock_acquire.return_value = 0.5  # Simulated wait time
            
            with patch.object(onlyfans_client, 'get') as mock_get:
                mock_get.return_value = {"id": "user123"}
                
                await onlyfans_client.get_profile()
                
                mock_acquire.assert_called_once()
                
    @pytest.mark.asyncio
    async def test_get_fans(self, onlyfans_client):
        """Test getting list of fans"""
        response_data = {
            "list": [
                {
                    "id": "fan1",
                    "username": "testfan",
                    "name": "Test Fan",
                    "avatar_url": "https://example.com/fan.jpg",
                    "is_subscriber": True,
                    "subscription_price": 9.99,
                    "total_spent": 99.99
                }
            ],
            "hasMore": False,
            "total": 1
        }
        
        with patch.object(onlyfans_client, 'get') as mock_get:
            mock_get.return_value = response_data
            
            fans = await onlyfans_client.get_fans()
            
            assert len(fans) == 1
            assert isinstance(fans[0], OnlyFansFan)
            assert fans[0].id == "fan1"
            assert fans[0].username == "testfan"
            
            mock_get.assert_called_with(
                "/fans",
                params={"limit": 100, "offset": 0}
            )
            
    @pytest.mark.asyncio
    async def test_send_message(self, onlyfans_client):
        """Test sending a message"""
        message_data = {
            "id": "msg123",
            "text": "Hello fan!",
            "createdAt": datetime.utcnow().isoformat(),
            "price": 0,
            "isPaid": False,
            "fromUser": {"id": "model1"},
            "toUser": {"id": "fan1"}
        }
        
        with patch.object(onlyfans_client, 'post') as mock_post:
            mock_post.return_value = message_data
            
            message = await onlyfans_client.send_message(
                user_id="fan1",
                text="Hello fan!"
            )
            
            assert message.id == "msg123"
            assert message.text == "Hello fan!"
            
            mock_post.assert_called_with(
                "/messages",
                data={
                    "userId": "fan1",
                    "text": "Hello fan!",
                    "isPaid": False
                }
            )
            
    @pytest.mark.asyncio
    async def test_send_ppv_message(self, onlyfans_client):
        """Test sending a PPV message"""
        message_data = {
            "id": "msg123",
            "text": "Exclusive content!",
            "createdAt": datetime.utcnow().isoformat(),
            "price": 10.00,
            "isPaid": True,
            "fromUser": {"id": "model1"},
            "toUser": {"id": "fan1"}
        }
        
        with patch.object(onlyfans_client, 'post') as mock_post:
            mock_post.return_value = message_data
            
            message = await onlyfans_client.send_message(
                user_id="fan1",
                text="Exclusive content!",
                price=Decimal("10.00")
            )
            
            assert message.id == "msg123"
            assert message.price == 10.00
            assert message.isPaid is True
            
    @pytest.mark.asyncio
    async def test_mass_message_rate_limit(self, onlyfans_client):
        """Test mass message applies higher rate limit"""
        user_ids = ["fan1", "fan2", "fan3", "fan4", "fan5"]
        
        with patch.object(onlyfans_client.rate_limiter, 'acquire') as mock_acquire:
            with patch.object(onlyfans_client, 'post') as mock_post:
                mock_post.return_value = {"success": True}
                
                await onlyfans_client.send_mass_message(
                    user_ids=user_ids,
                    text="Mass message"
                )
                
                # Should acquire tokens equal to number of users
                mock_acquire.assert_called_once_with(tokens=5)


class TestOnlyFansWebhookHandler:
    """Test OnlyFans webhook handler"""
    
    def test_initialization(self):
        """Test webhook handler initialization"""
        handler = OnlyFansWebhookHandler("test-secret")
        
        assert handler.api_name == "onlyfans"
        assert handler.signature_header == "x-onlyfans-signature"
        assert handler.hash_algorithm == "sha256"
        assert handler.webhook_secret == "test-secret"
        
    def test_parse_event(self):
        """Test parsing webhook event"""
        handler = OnlyFansWebhookHandler("test-secret")
        
        payload = {
            "id": "evt123",
            "type": "subscription.create",
            "created_at": "2024-01-01T00:00:00Z",
            "data": {
                "user_id": "fan123",
                "creator_id": "model123",
                "price": 9.99
            }
        }
        
        event = handler.parse_event(payload)
        
        assert event.id == "evt123"
        assert event.type == "subscription.create"
        assert event.data == payload["data"]
        
    @pytest.mark.asyncio
    async def test_verify_signature(self):
        """Test webhook signature verification"""
        handler = OnlyFansWebhookHandler("test-secret")
        
        # Create test payload and signature
        import hmac
        import hashlib
        
        payload = b'{"test": "data"}'
        
        expected_sig = hmac.new(
            "test-secret".encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature = f"sha256={expected_sig}"
        
        # Test valid signature
        assert await handler.verify_signature(payload, signature, "test-secret") is True
        
        # Test invalid signature
        assert await handler.verify_signature(payload, "sha256=invalid", "test-secret") is False