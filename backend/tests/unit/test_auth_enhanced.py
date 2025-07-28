"""
Enhanced Authentication Tests

Comprehensive tests for Phase 1.1 auth improvements.
"""
import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    get_password_hash,
    generate_token_fingerprint,
    verify_token_fingerprint,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    hash_token
)
from core.auth.token_blacklist import token_blacklist_service
from core.auth.session_manager import session_manager
from core.domain.models import User, Session, UserRole
from core.config import settings


class TestEnhancedSecurity:
    """Test enhanced security features."""
    
    def test_access_token_with_security_claims(self):
        """Test access token includes all security claims."""
        data = {"user_id": "123", "email": "test@example.com", "role": "model"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        assert payload["user_id"] == "123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "model"
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "nbf" in payload
        assert "jti" in payload
        assert payload["iss"] == "agencydark"
    
    def test_refresh_token_with_family(self):
        """Test refresh token includes family for rotation."""
        data = {"user_id": "123"}
        token = create_refresh_token(data)
        
        # Decode with refresh key
        refresh_key = hashlib.sha256((settings.SECRET_KEY + "_refresh").encode()).hexdigest()
        payload = jwt.decode(token, refresh_key, algorithms=[settings.ALGORITHM])
        
        assert payload["user_id"] == "123"
        assert payload["type"] == "refresh"
        assert "family" in payload
        assert payload["iss"] == "agencydark"
    
    def test_token_fingerprint(self):
        """Test token fingerprint generation and verification."""
        raw_fp, fp_hash = generate_token_fingerprint()
        
        assert raw_fp is not None
        assert fp_hash is not None
        assert len(fp_hash) == 64  # SHA256 hex
        
        # Verify fingerprint
        assert verify_token_fingerprint(raw_fp, fp_hash) is True
        assert verify_token_fingerprint("wrong_fingerprint", fp_hash) is False
    
    def test_sensitive_data_encryption(self):
        """Test encryption/decryption of sensitive data."""
        sensitive_data = "my_api_key_12345"
        
        encrypted = encrypt_sensitive_data(sensitive_data)
        assert encrypted != sensitive_data
        
        decrypted = decrypt_sensitive_data(encrypted)
        assert decrypted == sensitive_data
    
    def test_token_hash(self):
        """Test token hashing for blacklist storage."""
        token = "some.jwt.token"
        hashed = hash_token(token)
        
        assert hashed != token
        assert len(hashed) == 64  # SHA256 hex
        
        # Same token produces same hash
        assert hash_token(token) == hashed


@pytest.mark.asyncio
class TestTokenBlacklist:
    """Test token blacklist functionality."""
    
    async def test_blacklist_token(self, mock_db: AsyncSession):
        """Test adding token to blacklist."""
        token = "test.jwt.token"
        jti = "unique_jti_123"
        user_id = "user_123"
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        with patch('core.redis.redis_client.setex', new_callable=AsyncMock) as mock_setex:
            result = await token_blacklist_service.blacklist_token(
                token=token,
                jti=jti,
                user_id=user_id,
                expires_at=expires_at,
                reason="Test blacklist",
                db=mock_db
            )
            
            assert result is True
            mock_setex.assert_called_once()
    
    async def test_check_blacklisted_token(self, mock_db: AsyncSession):
        """Test checking if token is blacklisted."""
        jti = "blacklisted_jti"
        
        # Test cache hit
        with patch('core.redis.redis_client.get', new_callable=AsyncMock, return_value="1"):
            is_blacklisted = await token_blacklist_service.is_token_blacklisted(jti, mock_db)
            assert is_blacklisted is True
        
        # Test cache miss, not in DB
        with patch('core.redis.redis_client.get', new_callable=AsyncMock, return_value=None):
            is_blacklisted = await token_blacklist_service.is_token_blacklisted(jti, mock_db)
            assert is_blacklisted is False


@pytest.mark.asyncio
class TestSessionManager:
    """Test session management functionality."""
    
    async def test_create_session(self, mock_db: AsyncSession):
        """Test session creation with device info."""
        user_id = "user_123"
        refresh_token = "refresh_token_123"
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        ip_address = "192.168.1.1"
        fingerprint = "fingerprint_hash"
        
        with patch('core.redis.redis_client.setex', new_callable=AsyncMock):
            session = await session_manager.create_session(
                user_id=user_id,
                refresh_token=refresh_token,
                user_agent=user_agent,
                ip_address=ip_address,
                fingerprint=fingerprint,
                db=mock_db
            )
            
            assert session.user_id == user_id
            assert session.refresh_token == refresh_token
            assert session.device_name is not None
            assert "Desktop" in session.device_name
    
    async def test_session_limit_enforcement(self, mock_db: AsyncSession):
        """Test that session limit is enforced."""
        user_id = "user_123"
        
        # Mock existing sessions count
        with patch.object(mock_db, 'execute', new_callable=AsyncMock) as mock_execute:
            # Mock count query result
            mock_result = Mock()
            mock_result.scalar.return_value = 6  # Over limit
            mock_execute.return_value = mock_result
            
            # Should revoke oldest session
            await session_manager._enforce_session_limit(user_id, mock_db)
            
            # Verify revoke was attempted
            assert mock_execute.call_count >= 2  # Count + select oldest
    
    async def test_revoke_all_sessions(self, mock_db: AsyncSession):
        """Test revoking all user sessions."""
        user_id = "user_123"
        
        with patch.object(mock_db, 'execute', new_callable=AsyncMock) as mock_execute:
            with patch('core.redis.redis_client.scan_iter', new_callable=AsyncMock, return_value=[]):
                count = await session_manager.revoke_all_sessions(
                    user_id,
                    mock_db,
                    reason="Test revocation"
                )
                
                assert mock_execute.called


@pytest.mark.asyncio
class TestAuthEndpoints:
    """Test auth API endpoints with new features."""
    
    async def test_login_with_remember_me(self, test_client, mock_db: AsyncSession):
        """Test login with remember me functionality."""
        # Create test user
        user = User(
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Test User",
            role=UserRole.MODEL,
            is_active=True
        )
        mock_db.add(user)
        await mock_db.commit()
        
        # Login with remember_me
        response = await test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
                "remember_me": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        
        # Check cookie was set
        assert "refresh_token" in response.cookies
    
    async def test_login_rate_limiting(self, test_client):
        """Test rate limiting on login endpoint."""
        # Make multiple rapid requests
        for i in range(15):  # Over the limit
            response = await test_client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"test{i}@example.com",
                    "password": "wrong_password"
                }
            )
            
            if i < 10:  # Within limit
                assert response.status_code in [401, 403]
            else:  # Over limit
                assert response.status_code == 429
                assert "Rate limit exceeded" in response.json()["detail"]
    
    async def test_account_lockout(self, test_client, mock_db: AsyncSession):
        """Test account lockout after failed attempts."""
        # Create test user
        user = User(
            email="lockout@example.com",
            hashed_password=get_password_hash("correct_password"),
            full_name="Lockout User",
            role=UserRole.MODEL,
            is_active=True,
            failed_login_attempts=0
        )
        mock_db.add(user)
        await mock_db.commit()
        
        # Make 5 failed login attempts
        for i in range(5):
            response = await test_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "lockout@example.com",
                    "password": "wrong_password"
                }
            )
            assert response.status_code == 401
        
        # 6th attempt should be locked
        response = await test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "lockout@example.com",
                "password": "correct_password"
            }
        )
        assert response.status_code == 423
        assert "locked" in response.json()["detail"].lower()
    
    async def test_password_reset_flow(self, test_client, mock_db: AsyncSession):
        """Test complete password reset flow."""
        # Create test user
        user = User(
            email="reset@example.com",
            hashed_password=get_password_hash("old_password"),
            full_name="Reset User",
            role=UserRole.MODEL,
            is_active=True
        )
        mock_db.add(user)
        await mock_db.commit()
        
        # Request password reset
        with patch('core.email.email_service.email_service.send_password_reset_email', new_callable=AsyncMock):
            response = await test_client.post(
                "/api/v1/auth/password-reset/request",
                json={"email": "reset@example.com"}
            )
            assert response.status_code == 200
        
        # Get reset token from DB
        await mock_db.refresh(user)
        reset_token = user.password_reset_token
        assert reset_token is not None
        
        # Confirm password reset
        with patch('core.email.email_service.email_service.send_password_changed_email', new_callable=AsyncMock):
            response = await test_client.post(
                "/api/v1/auth/password-reset/confirm",
                json={
                    "token": reset_token,
                    "new_password": "new_password123"
                }
            )
            assert response.status_code == 200
        
        # Verify password was changed
        await mock_db.refresh(user)
        assert verify_password("new_password123", user.hashed_password)
        assert user.password_reset_token is None
    
    async def test_session_management_endpoints(self, test_client, auth_headers):
        """Test session management endpoints."""
        # Get user sessions
        response = await test_client.get(
            "/api/v1/sessions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert "max_allowed" in data
        
        # Revoke all sessions
        response = await test_client.post(
            "/api/v1/sessions/revoke-all",
            headers=auth_headers,
            json={"keep_current": True}
        )
        assert response.status_code == 200
        assert "revoked_count" in response.json()


# Test fixtures
@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = Mock()
    return db


@pytest.fixture
def test_client():
    """Test client fixture."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers with valid token."""
    token = create_access_token({
        "user_id": "test_user_123",
        "email": "test@example.com",
        "role": "model"
    })
    return {"Authorization": f"Bearer {token}"}