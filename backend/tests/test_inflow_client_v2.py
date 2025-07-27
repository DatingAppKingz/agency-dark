"""
Tests for Inflow API client v2 using External API Framework
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from pydantic import SecretStr

from modules.inflow_wrapper.domain.schemas import InflowConfig, InflowUser
from modules.inflow_wrapper.infrastructure.client_v2 import InflowClient, InflowWebhookHandler
from core.external_api import APIRateLimitError, APIAuthenticationError


@pytest.fixture
def inflow_config():
    """Create test Inflow configuration"""
    return InflowConfig(
        base_url="https://api.inflow.com",
        api_key="test-api-key",
        timeout=30,
        max_retries=3,
        auth_method="api_key"
    )


@pytest.fixture
def inflow_client(inflow_config):
    """Create test Inflow client"""
    return InflowClient(inflow_config)


class TestInflowClient:
    """Test InflowClient functionality"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, inflow_client, inflow_config):
        """Test client initialization"""
        assert inflow_client.config.name == "inflow"
        assert inflow_client.config.base_url == inflow_config.base_url
        assert inflow_client.config.timeout == inflow_config.timeout
        assert inflow_client.config.credentials.api_key.get_secret_value() == inflow_config.api_key
        
    @pytest.mark.asyncio
    async def test_default_headers(self, inflow_client):
        """Test default headers include API key"""
        headers = inflow_client.get_default_headers()
        
        assert headers['User-Agent'] == 'AgencyDark/2.0'
        assert headers['Accept'] == 'application/json'
        assert headers['Content-Type'] == 'application/json'
        assert headers['X-API-Key'] == 'test-api-key'
        
    @pytest.mark.asyncio
    async def test_authenticate_success(self, inflow_client):
        """Test successful authentication"""
        with patch.object(inflow_client, 'get_current_user') as mock_get_user:
            mock_get_user.return_value = InflowUser(
                id="user123",
                username="testuser",
                display_name="Test User",
                email="test@example.com"
            )
            
            result = await inflow_client.authenticate()
            
            assert result is True
            assert inflow_client._authenticated is True
            mock_get_user.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, inflow_client):
        """Test failed authentication"""
        with patch.object(inflow_client, 'get_current_user') as mock_get_user:
            mock_get_user.side_effect = APIAuthenticationError("Invalid API key")
            
            result = await inflow_client.authenticate()
            
            assert result is False
            assert inflow_client._authenticated is False
            
    @pytest.mark.asyncio
    async def test_rate_limiting(self, inflow_client):
        """Test rate limiting is applied"""
        with patch.object(inflow_client.rate_limiter, 'acquire') as mock_acquire:
            mock_acquire.return_value = 0.5  # Simulated wait time
            
            with patch.object(inflow_client, 'get') as mock_get:
                mock_get.return_value = {"id": "user123"}
                
                await inflow_client.get_current_user()
                
                mock_acquire.assert_called_once()
                
    @pytest.mark.asyncio
    async def test_get_user(self, inflow_client):
        """Test getting user by ID"""
        user_data = {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
            "email": "test@example.com"
        }
        
        with patch.object(inflow_client, 'get') as mock_get:
            mock_get.return_value = user_data
            
            user = await inflow_client.get_user("user123")
            
            assert isinstance(user, InflowUser)
            assert user.id == "user123"
            assert user.username == "testuser"
            mock_get.assert_called_with("/api/v1/users/user123")
            
    @pytest.mark.asyncio
    async def test_list_subscribers(self, inflow_client):
        """Test listing subscribers"""
        response_data = {
            "items": [
                {
                    "id": "sub1",
                    "subscriber_id": "fan1",
                    "creator_id": "creator1",
                    "tier": "premium",
                    "price": 9.99,
                    "is_active": True
                }
            ],
            "total": 1
        }
        
        with patch.object(inflow_client, 'get') as mock_get:
            mock_get.return_value = response_data
            
            subscribers = await inflow_client.list_subscribers("creator1")
            
            assert len(subscribers) == 1
            assert subscribers[0].id == "sub1"
            assert subscribers[0].price == 9.99
            
            mock_get.assert_called_with(
                "/api/v1/creators/creator1/subscribers",
                params={"limit": 100, "offset": 0, "active_only": True}
            )
            
    @pytest.mark.asyncio
    async def test_send_message(self, inflow_client):
        """Test sending a message"""
        message_data = {
            "id": "msg123",
            "sender_id": "creator1",
            "recipient_id": "fan1",
            "content": "Hello!",
            "created_at": datetime.utcnow().isoformat(),
            "is_ppv": False
        }
        
        with patch.object(inflow_client, 'post') as mock_post:
            mock_post.return_value = message_data
            
            message = await inflow_client.send_message(
                recipient_id="fan1",
                content="Hello!"
            )
            
            assert message.id == "msg123"
            assert message.content == "Hello!"
            
            mock_post.assert_called_with(
                "/api/v1/messages",
                data={
                    "recipient_id": "fan1",
                    "content": "Hello!",
                    "attachments": [],
                    "is_ppv": False,
                    "price": None
                }
            )


class TestInflowWebhookHandler:
    """Test Inflow webhook handler"""
    
    def test_initialization(self):
        """Test webhook handler initialization"""
        handler = InflowWebhookHandler("test-secret")
        
        assert handler.api_name == "inflow"
        assert handler.signature_header == "x-inflow-signature"
        assert handler.hash_algorithm == "sha256"
        assert handler.webhook_secret == "test-secret"
        
    def test_parse_event(self):
        """Test parsing webhook event"""
        handler = InflowWebhookHandler("test-secret")
        
        payload = {
            "event_id": "evt123",
            "event_type": "subscription.created",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "subscription_id": "sub123",
                "user_id": "user123"
            }
        }
        
        event = handler.parse_event(payload)
        
        assert event.id == "evt123"
        assert event.type == "subscription.created"
        assert event.data == payload["data"]
        
    @pytest.mark.asyncio
    async def test_verify_signature(self):
        """Test webhook signature verification"""
        handler = InflowWebhookHandler("test-secret")
        
        # Create test payload and signature
        import hmac
        import hashlib
        
        timestamp = "1234567890"
        payload = b'{"test": "data"}'
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        
        expected_sig = hmac.new(
            "test-secret".encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature = f"t={timestamp},v1={expected_sig}"
        
        # Test valid signature
        assert await handler.verify_signature(payload, signature, "test-secret") is True
        
        # Test invalid signature
        assert await handler.verify_signature(payload, "t=123,v1=invalid", "test-secret") is False