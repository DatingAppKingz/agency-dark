"""
Unit tests for API Usage Tracking Middleware
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, call
from fastapi import Request, Response, HTTPException
import time

from core.middleware.api_usage import APIUsageMiddleware
from services.api_usage_tracker import UsageMetric


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = Mock(spec=Request)
    request.url = Mock(path="/api/v1/users")
    request.method = "GET"
    request.headers = {}
    request.client = Mock(host="127.0.0.1")
    request.state = Mock()
    return request


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = Mock(spec=Response)
    response.status_code = 200
    response.headers = {"content-length": "1048576"}  # 1MB
    return response


@pytest.fixture
def api_usage_middleware():
    """Create API usage middleware instance."""
    app = Mock()
    with patch('core.middleware.api_usage.get_usage_tracker') as mock_get_tracker:
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        middleware = APIUsageMiddleware(app)
        middleware.usage_tracker = mock_tracker
        return middleware


class TestAPIUsageMiddleware:
    """Test cases for API Usage Middleware"""
    
    @pytest.mark.asyncio
    async def test_skip_non_api_routes(self, api_usage_middleware, mock_request):
        """Test that non-API routes are skipped."""
        mock_request.url.path = "/health"
        
        call_next = AsyncMock(return_value=Mock())
        
        await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should not track usage
        api_usage_middleware.usage_tracker.check_limit.assert_not_called()
        api_usage_middleware.usage_tracker.track_usage.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_skip_auth_endpoints(self, api_usage_middleware, mock_request):
        """Test that auth endpoints are skipped."""
        mock_request.url.path = "/api/auth/login"
        
        call_next = AsyncMock(return_value=Mock())
        
        await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should not track usage
        api_usage_middleware.usage_tracker.check_limit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_api_key_skips_tracking(self, api_usage_middleware, mock_request):
        """Test that requests without API key skip tracking."""
        # No api_key_id in state
        delattr(mock_request.state, 'api_key_id')
        
        call_next = AsyncMock(return_value=Mock())
        
        with patch.object(api_usage_middleware, '_get_api_key_id', return_value=None):
            await api_usage_middleware.dispatch(mock_request, call_next)
        
        api_usage_middleware.usage_tracker.check_limit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, api_usage_middleware, mock_request):
        """Test rate limit enforcement."""
        mock_request.state.api_key_id = "test_key_123"
        
        # Mock rate limit check to fail
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=False)
        
        call_next = AsyncMock()
        
        with patch('core.middleware.api_usage.AuditLoggerMiddleware.log_api_access') as mock_audit:
            with pytest.raises(HTTPException) as exc_info:
                await api_usage_middleware.dispatch(mock_request, call_next)
            
            assert exc_info.value.status_code == 429
            assert "Rate limit exceeded" in exc_info.value.detail
            
            # Verify audit log was called
            mock_audit.assert_called_once()
            assert mock_audit.call_args[0][1] == "test_key_123"
            assert mock_audit.call_args[0][2] is False  # granted=False
    
    @pytest.mark.asyncio
    async def test_successful_request_tracking(self, api_usage_middleware, mock_request, mock_response):
        """Test tracking of successful requests."""
        mock_request.state.api_key_id = "test_key_123"
        
        # Mock rate limit check to pass
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(return_value=mock_response)
        
        with patch('time.time', side_effect=[1000.0, 1000.1]):  # 100ms duration
            response = await api_usage_middleware.dispatch(mock_request, call_next)
        
        assert response == mock_response
        
        # Verify usage was tracked
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        
        # Should have at least one call for request tracking
        assert len(track_calls) >= 1
        
        # Check request tracking call
        request_call = track_calls[0]
        assert request_call[0][0] == "test_key_123"
        assert request_call[0][1] == UsageMetric.REQUESTS
        metadata = request_call[1]["metadata"]
        assert metadata["path"] == "/api/v1/users"
        assert metadata["method"] == "GET"
        assert metadata["status_code"] == 200
        assert metadata["duration_ms"] == 100
        assert metadata["error"] is False
    
    @pytest.mark.asyncio
    async def test_error_tracking(self, api_usage_middleware, mock_request):
        """Test tracking of error responses."""
        mock_request.state.api_key_id = "test_key_123"
        mock_error_response = Mock(status_code=500)
        
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(return_value=mock_error_response)
        
        response = await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should track both request and error
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        assert len(track_calls) >= 2
        
        # Find error tracking call
        error_calls = [call for call in track_calls if call[0][1] == UsageMetric.ERRORS]
        assert len(error_calls) == 1
        
        error_call = error_calls[0]
        assert error_call[0][0] == "test_key_123"
        assert error_call[1]["metadata"]["status_code"] == 500
    
    @pytest.mark.asyncio
    async def test_exception_tracking(self, api_usage_middleware, mock_request):
        """Test tracking when exception is raised."""
        mock_request.state.api_key_id = "test_key_123"
        
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception):
            await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should still track usage
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        assert len(track_calls) >= 1
        
        # Request should be marked as error
        request_call = track_calls[0]
        assert request_call[1]["metadata"]["error"] is True
    
    @pytest.mark.asyncio
    async def test_sync_operation_tracking(self, api_usage_middleware, mock_request, mock_response):
        """Test tracking of sync operations."""
        mock_request.url.path = "/api/v1/sync/platform"
        mock_request.method = "POST"
        mock_request.state.api_key_id = "test_key_123"
        
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(return_value=mock_response)
        
        await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should track sync operation
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        sync_calls = [call for call in track_calls if call[0][1] == UsageMetric.SYNC_OPERATIONS]
        
        assert len(sync_calls) == 1
        assert sync_calls[0][1]["metadata"]["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_webhook_operation_tracking(self, api_usage_middleware, mock_request, mock_response):
        """Test tracking of webhook operations."""
        mock_request.url.path = "/api/v1/webhooks/send"
        mock_request.method = "POST"
        mock_request.state.api_key_id = "test_key_123"
        
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(return_value=mock_response)
        
        await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should track webhook operation
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        webhook_calls = [call for call in track_calls if call[0][1] == UsageMetric.WEBHOOKS_SENT]
        
        assert len(webhook_calls) == 1
    
    @pytest.mark.asyncio
    async def test_data_fetched_tracking(self, api_usage_middleware, mock_request, mock_response):
        """Test tracking of data fetched."""
        mock_request.state.api_key_id = "test_key_123"
        
        api_usage_middleware.usage_tracker.check_limit = AsyncMock(return_value=True)
        api_usage_middleware.usage_tracker.track_usage = AsyncMock()
        
        call_next = AsyncMock(return_value=mock_response)
        
        await api_usage_middleware.dispatch(mock_request, call_next)
        
        # Should track data fetched (1MB response)
        track_calls = api_usage_middleware.usage_tracker.track_usage.call_args_list
        data_calls = [call for call in track_calls if call[0][1] == UsageMetric.DATA_FETCHED]
        
        assert len(data_calls) == 1
        assert data_calls[0][1]["value"] == 10  # 1MB = 10 * 0.1MB units
        assert data_calls[0][1]["metadata"]["size_bytes"] == 1048576
    
    def test_get_api_key_id_from_state(self, api_usage_middleware, mock_request):
        """Test extracting API key ID from request state."""
        mock_request.state.api_key_id = "key_123"
        
        key_id = api_usage_middleware._get_api_key_id(mock_request)
        assert key_id == "key_123"
    
    def test_get_api_key_id_from_header(self, api_usage_middleware, mock_request):
        """Test extracting API key ID from header."""
        delattr(mock_request.state, 'api_key_id')
        mock_request.headers = {"X-API-Key": "pk_test_abcd1234"}
        
        key_id = api_usage_middleware._get_api_key_id(mock_request)
        assert key_id == "pk_test_"  # First 8 chars
    
    def test_get_api_key_id_not_found(self, api_usage_middleware, mock_request):
        """Test when API key ID is not found."""
        delattr(mock_request.state, 'api_key_id')
        mock_request.headers = {}
        
        key_id = api_usage_middleware._get_api_key_id(mock_request)
        assert key_id is None