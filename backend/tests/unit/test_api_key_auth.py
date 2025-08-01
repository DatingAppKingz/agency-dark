"""
Unit tests for API Key Authentication Middleware
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from core.middleware.api_key_auth import APIKeyAuth, APIKeyOrJWTAuth, require_api_key


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = Mock(spec=Request)
    request.headers = {}
    request.query_params = {}
    request.client = Mock(host="127.0.0.1")
    request.url = Mock(path="/api/v1/test")
    request.method = "GET"
    return request


@pytest.fixture
def mock_api_key_record():
    """Create a mock API key record."""
    return Mock(
        id="123",
        agency_id="456",
        user_id="789",
        scopes=["read:users", "write:users"],
        name="Test API Key"
    )


class TestAPIKeyAuth:
    """Test cases for APIKeyAuth middleware"""
    
    @pytest.mark.asyncio
    async def test_bearer_token_authentication(self, mock_request, mock_api_key_record):
        """Test authentication using Bearer token."""
        mock_request.headers = {"Authorization": "Bearer test_key:test_secret"}
        
        auth = APIKeyAuth(required_scopes=["read:users"])
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal') as mock_session:
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = mock_api_key_record
                
                result = await auth(mock_request)
                
                # Verify API key validation was called correctly
                mock_validate.assert_called_once()
                call_args = mock_validate.call_args[1]
                assert call_args['api_key'] == "test_key"
                assert call_args['api_secret'] == "test_secret"
                assert call_args['required_scopes'] == ["read:users"]
                assert call_args['ip_address'] == "127.0.0.1"
                
                # Check result
                assert result['api_key_id'] == "123"
                assert result['agency_id'] == "456"
                assert result['user_id'] == "789"
                assert result['scopes'] == ["read:users", "write:users"]
    
    @pytest.mark.asyncio
    async def test_custom_header_authentication(self, mock_request, mock_api_key_record):
        """Test authentication using custom headers."""
        mock_request.headers = {
            "X-API-Key": "test_key",
            "X-API-Secret": "test_secret"
        }
        
        auth = APIKeyAuth()
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = mock_api_key_record
                
                result = await auth(mock_request)
                
                mock_validate.assert_called_once()
                call_args = mock_validate.call_args[1]
                assert call_args['api_key'] == "test_key"
                assert call_args['api_secret'] == "test_secret"
    
    @pytest.mark.asyncio
    async def test_query_parameter_authentication(self, mock_request, mock_api_key_record):
        """Test authentication using query parameters."""
        mock_request.query_params = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        
        auth = APIKeyAuth()
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = mock_api_key_record
                
                result = await auth(mock_request)
                
                assert result is not None
                mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_missing_credentials_auto_error(self, mock_request):
        """Test missing credentials with auto_error=True."""
        auth = APIKeyAuth(auto_error=True)
        
        with pytest.raises(HTTPException) as exc_info:
            await auth(mock_request)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing API credentials"
    
    @pytest.mark.asyncio
    async def test_missing_credentials_no_auto_error(self, mock_request):
        """Test missing credentials with auto_error=False."""
        auth = APIKeyAuth(auto_error=False)
        
        result = await auth(mock_request)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_credentials(self, mock_request):
        """Test invalid API credentials."""
        mock_request.headers = {"Authorization": "Bearer invalid:secret"}
        
        auth = APIKeyAuth(auto_error=True)
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = None
                
                with pytest.raises(HTTPException) as exc_info:
                    await auth(mock_request)
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail == "Invalid API credentials"
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(self, mock_request, mock_api_key_record):
        """Test that audit log is created on successful authentication."""
        mock_request.headers = {
            "Authorization": "Bearer test_key:test_secret",
            "User-Agent": "TestAgent/1.0"
        }
        mock_request.query_params = {"param1": "value1"}
        
        auth = APIKeyAuth(required_scopes=["read:users"])
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = mock_api_key_record
                
                await auth(mock_request)
                
                # Verify audit log was created
                assert mock_session.add.called
                audit_log = mock_session.add.call_args[0][0]
                assert audit_log.api_key_id == "123"
                assert audit_log.action == "api_request"
                assert audit_log.ip_address == "127.0.0.1"
                assert audit_log.user_agent == "TestAgent/1.0"
                assert audit_log.request_path == "/api/v1/test"
                assert audit_log.request_method == "GET"


class TestAPIKeyOrJWTAuth:
    """Test cases for APIKeyOrJWTAuth middleware"""
    
    @pytest.mark.asyncio
    async def test_api_key_authentication_success(self, mock_request, mock_api_key_record):
        """Test successful API key authentication."""
        mock_request.headers = {"Authorization": "Bearer test_key:test_secret"}
        
        auth = APIKeyOrJWTAuth(required_scopes=["read:users"])
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = mock_api_key_record
                
                result = await auth(mock_request)
                
                assert result['auth_type'] == "api_key"
                assert result['api_key_id'] == "123"
                assert result['agency_id'] == "456"
    
    @pytest.mark.asyncio
    async def test_jwt_authentication_fallback(self, mock_request):
        """Test fallback to JWT authentication when API key not provided."""
        mock_user = Mock(
            id="user123",
            agency_id="agency456",
            role="admin"
        )
        
        auth = APIKeyOrJWTAuth()
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = None
                
                with patch('core.middleware.api_key_auth.get_current_user_optional') as mock_get_user:
                    mock_get_user.return_value = mock_user
                    
                    result = await auth(mock_request)
                    
                    assert result['auth_type'] == "jwt"
                    assert result['user_id'] == "user123"
                    assert result['agency_id'] == "agency456"
                    assert result['user_role'] == "admin"
    
    @pytest.mark.asyncio
    async def test_no_authentication_raises_error(self, mock_request):
        """Test that error is raised when both API key and JWT fail."""
        auth = APIKeyOrJWTAuth()
        
        with patch('core.middleware.api_key_auth.AsyncSessionLocal'):
            with patch('core.middleware.api_key_auth.APIKeyService.validate_api_key') as mock_validate:
                mock_validate.return_value = None
                
                with patch('core.middleware.api_key_auth.get_current_user_optional') as mock_get_user:
                    mock_get_user.return_value = None
                    
                    with pytest.raises(HTTPException) as exc_info:
                        await auth(mock_request)
                    
                    assert exc_info.value.status_code == 401
                    assert exc_info.value.detail == "Authentication required"


class TestDependencyFunctions:
    """Test dependency functions"""
    
    def test_require_api_key(self):
        """Test require_api_key dependency creation."""
        dep = require_api_key(["read:users", "write:users"])
        
        assert isinstance(dep, APIKeyAuth)
        assert dep.required_scopes == ["read:users", "write:users"]
        assert dep.auto_error is True
    
    def test_require_api_key_no_scopes(self):
        """Test require_api_key with no scopes."""
        from core.middleware.api_key_auth import require_api_key_or_jwt
        
        dep = require_api_key_or_jwt()
        
        assert isinstance(dep, APIKeyOrJWTAuth)
        assert dep.required_scopes == []