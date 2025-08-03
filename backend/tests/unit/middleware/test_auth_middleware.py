"""Comprehensive tests for authentication middleware."""
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient
import jwt
from unittest.mock import AsyncMock, patch

from middleware.auth_middleware import (
    AuthMiddleware, 
    JWTAuthenticationBackend,
    APIKeyAuthenticationBackend,
    SessionAuthenticationBackend,
    requires_auth,
    requires_permission,
    requires_any_permission,
    requires_all_permissions
)
from models.user import User, UserRole, UserStatus
from models.api_key import APIKey, APIKeyScope
from tests.factories import create_test_user, create_test_api_key


class TestAuthMiddleware:
    """Test cases for authentication middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with middleware."""
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        
        @app.get("/public")
        async def public_endpoint():
            return {"message": "Public access"}
        
        @app.get("/protected")
        @requires_auth
        async def protected_endpoint(request: Request):
            return {"user_id": request.state.user.id}
        
        @app.get("/admin")
        @requires_permission("admin:access")
        async def admin_endpoint(request: Request):
            return {"message": "Admin access"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_public_endpoint_access(self, app):
        """Test accessing public endpoints without authentication."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/public")
            assert response.status_code == 200
            assert response.json() == {"message": "Public access"}
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, app):
        """Test accessing protected endpoint without authentication."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/protected")
            assert response.status_code == 401
            assert response.json()["detail"] == "Authentication required"
    
    @pytest.mark.asyncio
    async def test_invalid_auth_header_format(self, app):
        """Test various invalid authentication header formats."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Missing Bearer prefix
            response = await client.get(
                "/protected",
                headers={"Authorization": "token123"}
            )
            assert response.status_code == 401
            
            # Wrong auth type
            response = await client.get(
                "/protected", 
                headers={"Authorization": "Basic dXNlcjpwYXNz"}
            )
            assert response.status_code == 401
            
            # Empty bearer token
            response = await client.get(
                "/protected",
                headers={"Authorization": "Bearer "}
            )
            assert response.status_code == 401


class TestJWTAuthentication:
    """Test cases for JWT authentication backend."""
    
    @pytest.fixture
    def jwt_backend(self):
        """Create JWT authentication backend."""
        return JWTAuthenticationBackend(
            secret_key="test_secret_key",
            algorithm="HS256"
        )
    
    @pytest.mark.asyncio
    async def test_valid_jwt_authentication(self, jwt_backend, db_session):
        """Test authentication with valid JWT token."""
        user = await create_test_user()
        
        # Create valid token
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "type": "access"
        }
        token = jwt.encode(token_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        # Authenticate
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is True
        assert auth_result["user"].id == user.id
        assert auth_result["auth_method"] == "jwt"
    
    @pytest.mark.asyncio
    async def test_expired_jwt_token(self, jwt_backend, db_session):
        """Test authentication with expired JWT token."""
        user = await create_test_user()
        
        # Create expired token
        token_data = {
            "sub": str(user.id),
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        token = jwt.encode(token_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        # Authenticate
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Token expired"
    
    @pytest.mark.asyncio
    async def test_jwt_with_invalid_signature(self, jwt_backend, db_session):
        """Test JWT token with invalid signature."""
        user = await create_test_user()
        
        # Create token with different secret
        token_data = {
            "sub": str(user.id),
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(token_data, "wrong_secret", algorithm="HS256")
        
        # Authenticate
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Invalid token signature"
    
    @pytest.mark.asyncio
    async def test_jwt_token_refresh(self, jwt_backend, db_session):
        """Test JWT refresh token flow."""
        user = await create_test_user()
        
        # Create refresh token
        refresh_data = {
            "sub": str(user.id),
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        refresh_token = jwt.encode(refresh_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        # Attempt to use refresh token for access
        auth_result = await jwt_backend.authenticate(
            token=refresh_token,
            db_session=db_session,
            token_type="access"
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Invalid token type"
        
        # Refresh to get new access token
        new_tokens = await jwt_backend.refresh_token(
            refresh_token=refresh_token,
            db_session=db_session
        )
        
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != refresh_token
    
    @pytest.mark.asyncio
    async def test_jwt_claims_validation(self, jwt_backend, db_session):
        """Test JWT claims validation."""
        user = await create_test_user()
        
        # Token missing required claims
        token_data = {
            "exp": datetime.utcnow() + timedelta(hours=1)
            # Missing 'sub' claim
        }
        token = jwt.encode(token_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Invalid token claims"
    
    @pytest.mark.asyncio
    async def test_jwt_user_status_check(self, jwt_backend, db_session):
        """Test JWT authentication with various user statuses."""
        # Suspended user
        suspended_user = await create_test_user(status=UserStatus.SUSPENDED)
        suspended_user.suspended_at = datetime.utcnow()
        suspended_user.suspension_ends_at = datetime.utcnow() + timedelta(hours=24)
        await db_session.commit()
        
        token_data = {
            "sub": str(suspended_user.id),
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(token_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Account suspended"
        
        # Deleted user
        deleted_user = await create_test_user()
        deleted_user.soft_delete()
        await db_session.commit()
        
        token_data["sub"] = str(deleted_user.id)
        token = jwt.encode(token_data, jwt_backend.secret_key, algorithm=jwt_backend.algorithm)
        
        auth_result = await jwt_backend.authenticate(
            token=token,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "User not found"


class TestAPIKeyAuthentication:
    """Test cases for API key authentication backend."""
    
    @pytest.fixture
    def api_key_backend(self):
        """Create API key authentication backend."""
        return APIKeyAuthenticationBackend()
    
    @pytest.mark.asyncio
    async def test_valid_api_key_authentication(self, api_key_backend, db_session):
        """Test authentication with valid API key."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(
            user=user,
            scopes=[APIKeyScope.READ, APIKeyScope.WRITE]
        )
        
        # Authenticate
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session,
            ip_address="192.168.1.1"
        )
        
        assert auth_result["success"] is True
        assert auth_result["user"].id == user.id
        assert auth_result["api_key"].id == api_key.id
        assert auth_result["auth_method"] == "api_key"
        
        # Verify usage was recorded
        await db_session.refresh(api_key)
        assert api_key.last_used_at is not None
        assert api_key.usage_count == 1
    
    @pytest.mark.asyncio
    async def test_api_key_with_ip_restriction(self, api_key_backend, db_session):
        """Test API key with IP address restrictions."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(
            user=user,
            allowed_ips=["192.168.1.0/24"]
        )
        
        # Allowed IP
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session,
            ip_address="192.168.1.100"
        )
        assert auth_result["success"] is True
        
        # Disallowed IP
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session,
            ip_address="10.0.0.1"
        )
        assert auth_result["success"] is False
        assert auth_result["error"] == "IP address not allowed"
    
    @pytest.mark.asyncio
    async def test_api_key_rate_limiting(self, api_key_backend, db_session):
        """Test API key rate limiting."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(
            user=user,
            rate_limit_per_hour=5
        )
        
        # Make requests up to limit
        for i in range(5):
            auth_result = await api_key_backend.authenticate(
                api_key=raw_key,
                db_session=db_session
            )
            assert auth_result["success"] is True
        
        # Next request should be rate limited
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session
        )
        assert auth_result["success"] is False
        assert auth_result["error"] == "Rate limit exceeded"
    
    @pytest.mark.asyncio
    async def test_api_key_scope_validation(self, api_key_backend, db_session):
        """Test API key scope validation."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(
            user=user,
            scopes=[APIKeyScope.READ]
        )
        
        # Check for READ scope (should pass)
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session,
            required_scopes=[APIKeyScope.READ]
        )
        assert auth_result["success"] is True
        
        # Check for WRITE scope (should fail)
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session,
            required_scopes=[APIKeyScope.WRITE]
        )
        assert auth_result["success"] is False
        assert auth_result["error"] == "Insufficient permissions"
    
    @pytest.mark.asyncio
    async def test_expired_api_key(self, api_key_backend, db_session):
        """Test authentication with expired API key."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(
            user=user,
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "API key expired"
    
    @pytest.mark.asyncio
    async def test_revoked_api_key(self, api_key_backend, db_session):
        """Test authentication with revoked API key."""
        user = await create_test_user()
        raw_key, api_key = await create_test_api_key(user=user)
        
        # Revoke the key
        api_key.revoke(reason="Security breach")
        await db_session.commit()
        
        auth_result = await api_key_backend.authenticate(
            api_key=raw_key,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "API key revoked"


class TestSessionAuthentication:
    """Test cases for session-based authentication."""
    
    @pytest.fixture
    def session_backend(self):
        """Create session authentication backend."""
        return SessionAuthenticationBackend(
            session_store=AsyncMock()  # Mock Redis/cache
        )
    
    @pytest.mark.asyncio
    async def test_valid_session_authentication(self, session_backend, db_session):
        """Test authentication with valid session."""
        user = await create_test_user()
        session_id = "session_123456"
        
        # Mock session data
        session_backend.session_store.get.return_value = {
            "user_id": str(user.id),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0"
        }
        
        auth_result = await session_backend.authenticate(
            session_id=session_id,
            db_session=db_session
        )
        
        assert auth_result["success"] is True
        assert auth_result["user"].id == user.id
        assert auth_result["auth_method"] == "session"
    
    @pytest.mark.asyncio
    async def test_expired_session(self, session_backend, db_session):
        """Test authentication with expired session."""
        user = await create_test_user()
        session_id = "expired_session"
        
        # Mock expired session
        session_backend.session_store.get.return_value = {
            "user_id": str(user.id),
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
        
        auth_result = await session_backend.authenticate(
            session_id=session_id,
            db_session=db_session
        )
        
        assert auth_result["success"] is False
        assert auth_result["error"] == "Session expired"
        
        # Verify session was deleted
        session_backend.session_store.delete.assert_called_once_with(session_id)
    
    @pytest.mark.asyncio
    async def test_session_ip_validation(self, session_backend, db_session):
        """Test session IP address validation."""
        user = await create_test_user()
        session_id = "ip_bound_session"
        
        # Mock session with IP binding
        session_backend.session_store.get.return_value = {
            "user_id": str(user.id),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "ip_address": "192.168.1.1",
            "ip_binding": True
        }
        
        # Same IP should succeed
        auth_result = await session_backend.authenticate(
            session_id=session_id,
            db_session=db_session,
            ip_address="192.168.1.1"
        )
        assert auth_result["success"] is True
        
        # Different IP should fail
        auth_result = await session_backend.authenticate(
            session_id=session_id,
            db_session=db_session,
            ip_address="10.0.0.1"
        )
        assert auth_result["success"] is False
        assert auth_result["error"] == "Session IP mismatch"
    
    @pytest.mark.asyncio
    async def test_session_renewal(self, session_backend, db_session):
        """Test session renewal on activity."""
        user = await create_test_user()
        session_id = "renewable_session"
        
        # Mock session near expiry
        original_expiry = datetime.utcnow() + timedelta(minutes=10)
        session_backend.session_store.get.return_value = {
            "user_id": str(user.id),
            "expires_at": original_expiry.isoformat(),
            "renewable": True
        }
        
        auth_result = await session_backend.authenticate(
            session_id=session_id,
            db_session=db_session
        )
        
        assert auth_result["success"] is True
        
        # Verify session was renewed
        session_backend.session_store.set.assert_called_once()
        renewed_data = session_backend.session_store.set.call_args[0][1]
        renewed_expiry = datetime.fromisoformat(renewed_data["expires_at"])
        assert renewed_expiry > original_expiry


class TestAuthorizationDecorators:
    """Test cases for authorization decorators."""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request with user."""
        request = AsyncMock()
        request.state = AsyncMock()
        return request
    
    @pytest.mark.asyncio
    async def test_requires_permission_decorator(self, mock_request):
        """Test requires_permission decorator."""
        # Admin user with permission
        admin = User(
            id="admin123",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        mock_request.state.user = admin
        
        @requires_permission("admin:access")
        async def admin_function(request):
            return {"success": True}
        
        result = await admin_function(mock_request)
        assert result["success"] is True
        
        # Regular user without permission
        regular_user = User(
            id="user123",
            email="user@test.com",
            role=UserRole.MODEL
        )
        mock_request.state.user = regular_user
        
        with pytest.raises(PermissionError, match="Permission denied"):
            await admin_function(mock_request)
    
    @pytest.mark.asyncio
    async def test_requires_any_permission_decorator(self, mock_request):
        """Test requires_any_permission decorator."""
        manager = User(
            id="manager123",
            email="manager@test.com",
            role=UserRole.MANAGER
        )
        mock_request.state.user = manager
        
        @requires_any_permission(["admin:access", "manager:access"])
        async def manager_function(request):
            return {"success": True}
        
        # Manager has one of the required permissions
        result = await manager_function(mock_request)
        assert result["success"] is True
        
        # Model has none of the permissions
        model = User(
            id="model123",
            email="model@test.com",
            role=UserRole.MODEL
        )
        mock_request.state.user = model
        
        with pytest.raises(PermissionError):
            await manager_function(mock_request)
    
    @pytest.mark.asyncio
    async def test_requires_all_permissions_decorator(self, mock_request):
        """Test requires_all_permissions decorator."""
        admin = User(
            id="admin123",
            email="admin@test.com",
            role=UserRole.ADMIN
        )
        mock_request.state.user = admin
        
        @requires_all_permissions(["admin:access", "financial:manage"])
        async def financial_admin_function(request):
            return {"success": True}
        
        # Admin has all required permissions
        result = await financial_admin_function(mock_request)
        assert result["success"] is True
        
        # Manager missing admin:access
        manager = User(
            id="manager123",
            email="manager@test.com",
            role=UserRole.MANAGER
        )
        mock_request.state.user = manager
        
        with pytest.raises(PermissionError):
            await financial_admin_function(mock_request)


class TestMiddlewareIntegration:
    """Test middleware integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_multiple_auth_methods(self, app, db_session):
        """Test fallback between multiple authentication methods."""
        user = await create_test_user()
        
        # Create both JWT and API key
        jwt_token = create_test_jwt(user)
        raw_key, api_key = await create_test_api_key(user)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # JWT in header
            response = await client.get(
                "/protected",
                headers={"Authorization": f"Bearer {jwt_token}"}
            )
            assert response.status_code == 200
            
            # API key in header
            response = await client.get(
                "/protected",
                headers={"X-API-Key": raw_key}
            )
            assert response.status_code == 200
            
            # Session cookie
            response = await client.get(
                "/protected",
                cookies={"session_id": "valid_session"}
            )
            # Would work with proper session setup
    
    @pytest.mark.asyncio
    async def test_auth_caching(self, app, db_session):
        """Test authentication result caching."""
        user = await create_test_user()
        jwt_token = create_test_jwt(user)
        
        with patch("middleware.auth_middleware.cache") as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # First request - cache miss
                response = await client.get(
                    "/protected",
                    headers={"Authorization": f"Bearer {jwt_token}"}
                )
                assert response.status_code == 200
                mock_cache.set.assert_called_once()
                
                # Second request - cache hit
                mock_cache.get.return_value = {
                    "user_id": user.id,
                    "permissions": ["read", "write"]
                }
                response = await client.get(
                    "/protected",
                    headers={"Authorization": f"Bearer {jwt_token}"}
                )
                assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_auth_metrics(self, app, db_session):
        """Test authentication metrics collection."""
        with patch("middleware.auth_middleware.metrics") as mock_metrics:
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Successful auth
                user = await create_test_user()
                jwt_token = create_test_jwt(user)
                
                response = await client.get(
                    "/protected",
                    headers={"Authorization": f"Bearer {jwt_token}"}
                )
                mock_metrics.increment.assert_called_with(
                    "auth.success",
                    tags={"method": "jwt"}
                )
                
                # Failed auth
                response = await client.get(
                    "/protected",
                    headers={"Authorization": "Bearer invalid"}
                )
                mock_metrics.increment.assert_called_with(
                    "auth.failure",
                    tags={"method": "jwt", "reason": "invalid_token"}
                )