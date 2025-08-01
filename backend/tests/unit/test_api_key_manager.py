"""
Unit tests for API Key Manager
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json

from core.security.api_key_manager import SecureAPIKeyManager
from models.api_key import APIKey
from models.api_key_audit import APIKeyAudit


@pytest.fixture
def api_key_manager():
    """Create API key manager instance."""
    return SecureAPIKeyManager()


@pytest.fixture
def mock_api_key():
    """Create a mock API key."""
    return APIKey(
        id=1,
        user_id=123,
        name="Test Key",
        key_prefix="live_abc",
        key_hash="test_hash",
        encrypted_data="encrypted_test_data",
        scopes=["read:users", "write:users"],
        expires_at=datetime.utcnow() + timedelta(days=365),
        is_active=True,
        environment="live",
        usage_count=0,
        rotation_count=0
    )


class TestSecureAPIKeyManager:
    """Test cases for SecureAPIKeyManager"""
    
    @pytest.mark.asyncio
    async def test_create_api_key_success(self, api_key_manager, db_session):
        """Test successful API key creation."""
        # Mock the count query
        with patch.object(db_session, 'scalar', return_value=0):
            # Mock encryption
            with patch('core.security.api_key_manager.api_key_encryption.encrypt_api_key') as mock_encrypt:
                mock_encrypt.return_value = {"encrypted_data": "test_encrypted"}
                
                # Mock Redis cache
                with patch('core.security.api_key_manager.redis_client.setex') as mock_redis:
                    mock_redis.return_value = True
                    
                    # Create API key
                    public_key, secret_key, api_key = await api_key_manager.create_api_key(
                        db_session,
                        user_id=123,
                        name="Test API Key",
                        scopes=["read:users"],
                        metadata={"ip_address": "127.0.0.1"}
                    )
                    
                    # Assertions
                    assert public_key.startswith("live_")
                    assert secret_key.startswith("sk_")
                    assert api_key.user_id == 123
                    assert api_key.name == "Test API Key"
                    assert api_key.scopes == ["read:users"]
                    assert api_key.environment == "live"
    
    @pytest.mark.asyncio
    async def test_create_api_key_exceeds_limit(self, api_key_manager, db_session):
        """Test API key creation when limit is exceeded."""
        # Mock count to return max keys
        with patch.object(db_session, 'scalar', return_value=10):
            with pytest.raises(ValueError, match="Maximum of 10 active keys allowed"):
                await api_key_manager.create_api_key(
                    db_session,
                    user_id=123,
                    name="Test Key",
                    scopes=["read:users"]
                )
    
    @pytest.mark.asyncio
    async def test_verify_api_key_with_cache(self, api_key_manager, db_session, mock_api_key):
        """Test API key verification with cached data."""
        test_key = "live_abc123_secret456"
        
        # Mock cache hit
        cached_data = {
            "key_id": 1,
            "key_hash": mock_api_key.key_hash
        }
        
        with patch('core.security.api_key_manager.redis_client.get', return_value=json.dumps(cached_data)):
            # Mock database get
            with patch.object(db_session, 'get', return_value=mock_api_key):
                # Mock hash verification
                with patch.object(api_key_manager, '_verify_key_hash', return_value=True):
                    # Mock cache update
                    with patch('core.security.api_key_manager.redis_client.setex'):
                        result = await api_key_manager.verify_api_key(
                            db_session,
                            test_key,
                            required_scopes=["read:users"]
                        )
                        
                        assert result == mock_api_key
                        assert mock_api_key.last_used_at is not None
                        assert mock_api_key.usage_count == 1
    
    @pytest.mark.asyncio
    async def test_verify_api_key_expired(self, api_key_manager, db_session, mock_api_key):
        """Test verification of expired API key."""
        # Set expired date
        mock_api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        test_key = "live_abc123_secret456"
        
        # Mock cache miss
        with patch('core.security.api_key_manager.redis_client.get', return_value=None):
            # Mock database query
            with patch.object(db_session, 'scalar', return_value=mock_api_key):
                # Mock hash verification
                with patch.object(api_key_manager, '_verify_key_hash', return_value=True):
                    result = await api_key_manager.verify_api_key(db_session, test_key)
                    
                    assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_api_key_insufficient_scopes(self, api_key_manager, db_session, mock_api_key):
        """Test verification with insufficient scopes."""
        test_key = "live_abc123_secret456"
        mock_api_key.scopes = ["read:users"]
        
        # Mock cache miss
        with patch('core.security.api_key_manager.redis_client.get', return_value=None):
            # Mock database query
            with patch.object(db_session, 'scalar', return_value=mock_api_key):
                # Mock hash verification
                with patch.object(api_key_manager, '_verify_key_hash', return_value=True):
                    result = await api_key_manager.verify_api_key(
                        db_session,
                        test_key,
                        required_scopes=["write:users", "admin:all"]
                    )
                    
                    assert result is None
    
    @pytest.mark.asyncio
    async def test_rotate_api_key(self, api_key_manager, db_session, mock_api_key):
        """Test API key rotation."""
        # Mock database get
        with patch.object(db_session, 'get', return_value=mock_api_key):
            # Mock decryption
            with patch('core.security.api_key_manager.api_key_encryption.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = {
                    "api_key": "old_key",
                    "metadata": {"scopes": ["read:users"]}
                }
                
                # Mock encryption
                with patch('core.security.api_key_manager.api_key_encryption.encrypt_api_key') as mock_encrypt:
                    mock_encrypt.return_value = {"encrypted_data": "new_encrypted"}
                    
                    # Mock cache operations
                    with patch('core.security.api_key_manager.redis_client.delete'):
                        new_public, new_secret = await api_key_manager.rotate_api_key(
                            db_session,
                            api_key_id=1,
                            user_id=123
                        )
                        
                        assert new_public.startswith("live_abc")
                        assert new_secret.startswith("sk_")
                        assert mock_api_key.rotation_count == 1
                        assert mock_api_key.rotated_at is not None
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api_key_manager, db_session, mock_api_key):
        """Test API key revocation."""
        # Mock database get
        with patch.object(db_session, 'get', return_value=mock_api_key):
            # Mock cache clear
            with patch.object(api_key_manager, '_clear_key_cache_by_id'):
                result = await api_key_manager.revoke_api_key(
                    db_session,
                    api_key_id=1,
                    user_id=123,
                    reason="security_breach"
                )
                
                assert result is True
                assert mock_api_key.is_active is False
                assert mock_api_key.revoked_at is not None
                assert mock_api_key.revocation_reason == "security_breach"
    
    @pytest.mark.asyncio
    async def test_list_user_keys(self, api_key_manager, db_session):
        """Test listing user API keys."""
        # Create mock keys
        mock_keys = [
            Mock(
                id=1,
                name="Key 1",
                key_prefix="live_abc",
                scopes=["read:users"],
                environment="live",
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),
                last_used_at=None,
                usage_count=0,
                is_active=True,
                encrypted_data="encrypted1",
                rotated_at=None
            ),
            Mock(
                id=2,
                name="Key 2",
                key_prefix="test_xyz",
                scopes=["write:users"],
                environment="test",
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),
                last_used_at=datetime.utcnow(),
                usage_count=10,
                is_active=True,
                encrypted_data="encrypted2",
                rotated_at=None
            )
        ]
        
        # Mock execute
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_keys
        
        with patch.object(db_session, 'execute', return_value=mock_result):
            # Mock decryption
            with patch('core.security.api_key_manager.api_key_encryption.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = {"metadata": {"user_metadata": {"org": "test"}}}
                
                keys_data = await api_key_manager.list_user_keys(db_session, user_id=123)
                
                assert len(keys_data) == 2
                assert keys_data[0]["name"] == "Key 1"
                assert keys_data[0]["key_prefix"] == "live_abc***"
                assert keys_data[1]["usage_count"] == 10
    
    def test_hash_api_key(self, api_key_manager):
        """Test API key hashing."""
        test_key = "sk_test123456789"
        hash1 = api_key_manager._hash_api_key(test_key)
        hash2 = api_key_manager._hash_api_key(test_key)
        
        # Same input should produce same hash
        assert hash1 == hash2
        
        # Hash should be hex string
        assert isinstance(hash1, str)
        assert all(c in '0123456789abcdef' for c in hash1)
        
        # Different keys should produce different hashes
        hash3 = api_key_manager._hash_api_key("sk_different123")
        assert hash1 != hash3
    
    def test_verify_key_hash(self, api_key_manager):
        """Test API key hash verification."""
        test_key = "sk_test123456789"
        stored_hash = api_key_manager._hash_api_key(test_key)
        
        # Correct key should verify
        assert api_key_manager._verify_key_hash(test_key, stored_hash) is True
        
        # Wrong key should not verify
        assert api_key_manager._verify_key_hash("sk_wrong123", stored_hash) is False
    
    def test_check_scopes_exact_match(self, api_key_manager):
        """Test scope checking with exact matches."""
        available = ["read:users", "write:users", "read:posts"]
        
        # Should pass with subset
        assert api_key_manager._check_scopes(available, ["read:users"]) is True
        assert api_key_manager._check_scopes(available, ["read:users", "write:users"]) is True
        
        # Should fail with missing scope
        assert api_key_manager._check_scopes(available, ["admin:users"]) is False
        assert api_key_manager._check_scopes(available, ["read:users", "admin:all"]) is False
    
    def test_check_scopes_wildcard(self, api_key_manager):
        """Test scope checking with wildcards."""
        # Test global wildcard
        assert api_key_manager._check_scopes(["*"], ["read:users", "admin:all"]) is True
        
        # Test partial wildcards
        available = ["read:*", "write:posts"]
        assert api_key_manager._check_scopes(available, ["read:users"]) is True
        assert api_key_manager._check_scopes(available, ["read:posts"]) is True
        assert api_key_manager._check_scopes(available, ["write:posts"]) is True
        assert api_key_manager._check_scopes(available, ["write:users"]) is False
    
    def test_needs_rotation(self, api_key_manager):
        """Test rotation check logic."""
        # Never rotated, created recently
        key1 = Mock(
            created_at=datetime.utcnow() - timedelta(days=30),
            rotated_at=None
        )
        assert api_key_manager._needs_rotation(key1) is False
        
        # Never rotated, created long ago
        key2 = Mock(
            created_at=datetime.utcnow() - timedelta(days=100),
            rotated_at=None
        )
        assert api_key_manager._needs_rotation(key2) is True
        
        # Rotated recently
        key3 = Mock(
            created_at=datetime.utcnow() - timedelta(days=200),
            rotated_at=datetime.utcnow() - timedelta(days=30)
        )
        assert api_key_manager._needs_rotation(key3) is False
        
        # Rotated long ago
        key4 = Mock(
            created_at=datetime.utcnow() - timedelta(days=200),
            rotated_at=datetime.utcnow() - timedelta(days=100)
        )
        assert api_key_manager._needs_rotation(key4) is True
    
    @pytest.mark.asyncio
    async def test_get_key_audit_log(self, api_key_manager, db_session, mock_api_key):
        """Test retrieving audit logs."""
        # Mock audit entries
        mock_audits = [
            Mock(
                action="created",
                details={"key_prefix": "live_abc"},
                ip_address="127.0.0.1",
                user_agent="TestAgent/1.0",
                created_at=datetime.utcnow()
            ),
            Mock(
                action="verified",
                details={},
                ip_address="192.168.1.1", 
                user_agent="TestAgent/1.0",
                created_at=datetime.utcnow()
            )
        ]
        
        # Mock database operations
        with patch.object(db_session, 'get', return_value=mock_api_key):
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_audits
            
            with patch.object(db_session, 'execute', return_value=mock_result):
                logs = await api_key_manager.get_key_audit_log(
                    db_session,
                    api_key_id=1,
                    user_id=123
                )
                
                assert len(logs) == 2
                assert logs[0]["action"] == "created"
                assert logs[0]["ip_address"] == "127.0.0.1"
                assert logs[1]["action"] == "verified"