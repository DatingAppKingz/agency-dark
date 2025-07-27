"""
Unit tests for API key encryption service.
"""
import pytest
from datetime import datetime, timedelta

from core.security.encryption import (
    EncryptionService, APIKeyEncryption, FieldEncryption, TokenEncryption
)


class TestEncryptionService:
    
    def test_encrypt_decrypt_string(self):
        """Test basic string encryption and decryption."""
        service = EncryptionService()
        
        original = "This is a secret message"
        encrypted = service.encrypt(original)
        
        assert encrypted != original
        assert isinstance(encrypted, str)
        
        decrypted = service.decrypt(encrypted)
        assert decrypted == original
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        service = EncryptionService()
        
        encrypted = service.encrypt("")
        assert encrypted == ""
        
        decrypted = service.decrypt("")
        assert decrypted == ""
    
    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        service = EncryptionService()
        
        original = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "metadata": {"created_by": "test_user"}
        }
        
        encrypted = service.encrypt_dict(original)
        assert isinstance(encrypted, str)
        assert encrypted != str(original)
        
        decrypted = service.decrypt_dict(encrypted)
        assert decrypted == original
    
    def test_decrypt_invalid_data(self):
        """Test decrypting invalid data."""
        service = EncryptionService()
        
        with pytest.raises(ValueError):
            service.decrypt("invalid_encrypted_data")


class TestAPIKeyEncryption:
    
    def test_generate_key_pair(self):
        """Test API key pair generation."""
        encryption = APIKeyEncryption()
        
        api_key, api_secret = encryption.generate_key_pair()
        
        assert api_key.startswith("ak_")
        assert api_secret.startswith("sk_")
        assert len(api_key) > 20
        assert len(api_secret) > 30
        
        # Generate another pair - should be different
        api_key2, api_secret2 = encryption.generate_key_pair()
        assert api_key != api_key2
        assert api_secret != api_secret2
    
    def test_encrypt_decrypt_api_key(self):
        """Test API key encryption and decryption."""
        encryption = APIKeyEncryption()
        
        api_key, api_secret = encryption.generate_key_pair()
        metadata = {"owner": "test_user", "purpose": "testing"}
        
        # Encrypt
        encrypted_data = encryption.encrypt_api_key(
            api_key=api_key,
            api_secret=api_secret,
            metadata=metadata
        )
        
        assert "key_id" in encrypted_data
        assert "encrypted_data" in encrypted_data
        assert "version" in encrypted_data
        assert encrypted_data["version"] == "1.0"
        
        # Decrypt
        decrypted_data = encryption.decrypt_api_key(encrypted_data)
        
        assert decrypted_data["api_key"] == api_key
        assert decrypted_data["api_secret"] == api_secret
        assert decrypted_data["metadata"] == metadata
        assert "created_at" in decrypted_data
    
    def test_rotate_api_key(self):
        """Test API key rotation."""
        encryption = APIKeyEncryption()
        
        # Create initial key
        api_key, api_secret = encryption.generate_key_pair()
        encrypted_data = encryption.encrypt_api_key(api_key, api_secret)
        
        # Rotate
        new_encrypted_data = encryption.rotate_api_key(encrypted_data)
        
        # Decrypt new data
        new_data = encryption.decrypt_api_key(new_encrypted_data)
        old_data = encryption.decrypt_api_key(encrypted_data)
        
        # API key should remain the same
        assert new_data["api_key"] == old_data["api_key"]
        
        # Secret should be different
        assert new_data["api_secret"] != old_data["api_secret"]
        assert new_data["api_secret"].startswith("sk_")
        
        # Metadata should be preserved with rotation info
        assert "rotated_at" in new_data["metadata"]
        assert new_data["metadata"]["rotation_count"] == 1
    
    def test_unsupported_version(self):
        """Test handling of unsupported encryption version."""
        encryption = APIKeyEncryption()
        
        encrypted_data = {
            "key_id": "test",
            "encrypted_data": "test",
            "version": "2.0"  # Unsupported version
        }
        
        with pytest.raises(ValueError, match="Unsupported encryption version"):
            encryption.decrypt_api_key(encrypted_data)


class TestFieldEncryption:
    
    def test_encrypt_string_field(self):
        """Test string field encryption."""
        encryption = FieldEncryption()
        
        value = "sensitive data"
        encrypted = encryption.encrypt_field(value, "string")
        
        assert encrypted != value
        
        decrypted = encryption.decrypt_field(encrypted, "string")
        assert decrypted == value
    
    def test_encrypt_json_field(self):
        """Test JSON field encryption."""
        encryption = FieldEncryption()
        
        value = {"key": "value", "number": 42}
        encrypted = encryption.encrypt_field(value, "json")
        
        assert isinstance(encrypted, str)
        
        decrypted = encryption.decrypt_field(encrypted, "json")
        assert decrypted == value
    
    def test_encrypt_none_value(self):
        """Test encrypting None value."""
        encryption = FieldEncryption()
        
        encrypted = encryption.encrypt_field(None, "string")
        assert encrypted == ""
        
        decrypted = encryption.decrypt_field("", "string")
        assert decrypted is None


class TestTokenEncryption:
    
    def test_generate_secure_token(self):
        """Test secure token generation."""
        token1 = TokenEncryption.generate_secure_token()
        token2 = TokenEncryption.generate_secure_token()
        
        assert len(token1) > 20
        assert token1 != token2
        
        # Test custom length
        token3 = TokenEncryption.generate_secure_token(length=64)
        assert len(token3) > 40
    
    def test_hash_token(self):
        """Test token hashing."""
        token = "my_secret_token"
        
        hash1 = TokenEncryption.hash_token(token)
        hash2 = TokenEncryption.hash_token(token)
        
        # Same token should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars
        
        # Different token should produce different hash
        hash3 = TokenEncryption.hash_token("different_token")
        assert hash3 != hash1