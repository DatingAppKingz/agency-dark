"""
Tests for external API framework
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json

from core.external_api import (
    BaseAPIClient, APIConfig, APICredentials,
    APIError, APIRateLimitError, APIAuthenticationError,
    RetryPolicy, ExponentialBackoff,
    APILogger
)
from core.external_api.rate_limit import RateLimiter, MultiRateLimiter
from core.external_api.webhooks import HMACWebhookHandler, WebhookEvent


class TestAPIClient(BaseAPIClient):
    """Test implementation of BaseAPIClient"""
    
    def get_default_headers(self) -> dict:
        return {
            'User-Agent': 'TestClient/1.0',
            'Accept': 'application/json'
        }
        
    async def authenticate(self) -> dict:
        return {'token': 'test-token'}


@pytest.fixture
def api_config():
    """Create test API configuration"""
    return APIConfig(
        name="test_api",
        base_url="https://api.test.com",
        timeout=30,
        max_retries=3,
        credentials=APICredentials(api_key="test-key")
    )


@pytest.fixture
def api_client(api_config):
    """Create test API client"""
    return TestAPIClient(api_config)


class TestBaseAPIClient:
    """Test BaseAPIClient functionality"""
    
    @pytest.mark.asyncio
    async def test_successful_request(self, api_client):
        """Test successful API request"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.json = AsyncMock(return_value={'success': True})
            mock_request.return_value = mock_response
            
            result = await api_client.get('/test')
            
            assert result == {'success': True}
            mock_request.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, api_client):
        """Test retry logic on rate limit error"""
        with patch.object(api_client, '_make_request') as mock_request:
            # First call returns rate limit error
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {'Retry-After': '2'}
            
            # Second call succeeds
            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.headers = {'Content-Type': 'application/json'}
            mock_response_200.json = AsyncMock(return_value={'success': True})
            
            mock_request.side_effect = [mock_response_429, mock_response_200]
            
            # Use faster retry for testing
            api_client.retry_policy = ExponentialBackoff(
                max_retries=1, base_delay=0.1
            )
            
            result = await api_client.get('/test')
            
            assert result == {'success': True}
            assert mock_request.call_count == 2
            
    @pytest.mark.asyncio
    async def test_authentication_error(self, api_client):
        """Test authentication error handling"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 401
            
            mock_request.return_value = mock_response
            
            with pytest.raises(APIAuthenticationError):
                await api_client.get('/test')
                
    @pytest.mark.asyncio
    async def test_request_with_pydantic_model(self, api_client):
        """Test request with Pydantic model data"""
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            name: str
            value: int
            
        test_data = TestModel(name="test", value=123)
        
        with patch.object(api_client, '_make_request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.json = AsyncMock(return_value={'created': True})
            mock_request.return_value = mock_response
            
            result = await api_client.post('/test', data=test_data)
            
            assert result == {'created': True}
            # Verify data was converted to dict
            call_args = mock_request.call_args
            assert call_args[1]['data'] == {'name': 'test', 'value': 123}


class TestRetryPolicies:
    """Test retry policy implementations"""
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        policy = ExponentialBackoff(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )
        
        assert policy.get_retry_delay(0) == 1.0
        assert policy.get_retry_delay(1) == 2.0
        assert policy.get_retry_delay(2) == 4.0
        assert policy.get_retry_delay(3) == 8.0
        
    def test_exponential_backoff_with_max(self):
        """Test exponential backoff with max delay"""
        policy = ExponentialBackoff(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )
        
        assert policy.get_retry_delay(0) == 1.0
        assert policy.get_retry_delay(1) == 2.0
        assert policy.get_retry_delay(2) == 4.0
        assert policy.get_retry_delay(3) == 5.0  # Capped at max
        assert policy.get_retry_delay(10) == 5.0  # Still capped
        
    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff with jitter"""
        policy = ExponentialBackoff(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True
        )
        
        # With jitter, delay should be between 50% and 100% of base
        delay = policy.get_retry_delay(0)
        assert 0.5 <= delay <= 1.0
        
        delay = policy.get_retry_delay(1)
        assert 1.0 <= delay <= 2.0


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter(rate=10, period=1)  # 10 requests per second
        
        # Should allow 10 requests immediately
        for _ in range(10):
            wait_time = await limiter.acquire()
            assert wait_time == 0
            
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess(self):
        """Test rate limiter blocks when limit exceeded"""
        limiter = RateLimiter(rate=2, period=1)  # 2 requests per second
        
        # Use up all tokens
        await limiter.acquire()
        await limiter.acquire()
        
        # Next request should require waiting
        start = asyncio.get_event_loop().time()
        wait_time = await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        
        assert wait_time > 0
        assert elapsed >= wait_time * 0.9  # Allow small timing variance
        
    @pytest.mark.asyncio
    async def test_multi_rate_limiter(self):
        """Test multi-rate limiter with multiple periods"""
        limits = {
            1: 2,    # 2 per second
            60: 10   # 10 per minute
        }
        limiter = MultiRateLimiter(limits)
        
        # Should allow 2 requests immediately
        assert await limiter.try_acquire() is True
        assert await limiter.try_acquire() is True
        
        # Third request should be blocked
        assert await limiter.try_acquire() is False


class TestWebhooks:
    """Test webhook handling"""
    
    @pytest.mark.asyncio
    async def test_hmac_webhook_verification(self):
        """Test HMAC webhook signature verification"""
        handler = HMACWebhookHandler("test_api", signature_header="x-signature")
        
        payload = b'{"event": "test"}'
        secret = "webhook_secret"
        
        # Generate valid signature
        import hmac
        import hashlib
        valid_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Test valid signature
        assert await handler.verify_signature(payload, valid_signature, secret) is True
        
        # Test invalid signature
        assert await handler.verify_signature(payload, "invalid", secret) is False
        
    def test_webhook_event_parsing(self):
        """Test webhook event parsing"""
        class TestWebhookHandler(HMACWebhookHandler):
            def parse_event(self, payload: dict) -> WebhookEvent:
                return WebhookEvent(
                    id=payload.get('id', 'unknown'),
                    type=payload.get('type', 'unknown'),
                    timestamp=datetime.utcnow(),
                    data=payload
                )
                
        handler = TestWebhookHandler("test_api")
        
        payload = {
            'id': 'evt_123',
            'type': 'payment.completed',
            'amount': 100
        }
        
        event = handler.parse_event(payload)
        
        assert event.id == 'evt_123'
        assert event.type == 'payment.completed'
        assert event.data == payload


class TestAPIConfig:
    """Test API configuration management"""
    
    def test_config_from_env(self):
        """Test creating config from environment variables"""
        env_vars = {
            'TEST_API_NAME': 'test',
            'TEST_API_BASE_URL': 'https://api.test.com',
            'TEST_API_TIMEOUT': '60',
            'TEST_API_API_KEY': 'secret-key',
            'TEST_API_HEADER_X_CUSTOM': 'custom-value'
        }
        
        with patch.dict('os.environ', env_vars):
            config = APIConfig.from_env('TEST_API')
            
            assert config.name == 'test'
            assert config.base_url == 'https://api.test.com'
            assert config.timeout == 60
            assert config.credentials.api_key.get_secret_value() == 'secret-key'
            assert config.custom_headers == {'x-custom': 'custom-value'}
            
    def test_credentials_security(self):
        """Test credentials are properly secured"""
        creds = APICredentials(
            api_key="secret-key",
            api_secret="secret-secret"
        )
        
        # Verify secrets are not exposed in string representation
        creds_str = str(creds)
        assert "secret-key" not in creds_str
        assert "secret-secret" not in creds_str
        
        # Verify we can get secret values when needed
        assert creds.get_secret_value('api_key') == 'secret-key'
        assert creds.get_secret_value('api_secret') == 'secret-secret'