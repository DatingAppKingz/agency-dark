"""Tests for encryption service."""

import pytest
from services.encryption_service import EncryptionService


class TestEncryptionService:
    """Test encryption service functionality."""
    
    @pytest.fixture
    def encryption_service(self):
        """Create encryption service instance."""
        return EncryptionService()
    
    def test_encrypt_decrypt_cycle(self, encryption_service):
        """Test that we can encrypt and decrypt data successfully."""
        # Test data
        original = "sk_test_4242424242424242"
        
        # Encrypt
        encrypted = encryption_service.encrypt(original)
        assert encrypted != original
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original
    
    def test_encrypt_empty_string(self, encryption_service):
        """Test encrypting empty string."""
        encrypted = encryption_service.encrypt("")
        assert encrypted == ""
        
        decrypted = encryption_service.decrypt("")
        assert decrypted == ""
    
    def test_encrypt_unicode(self, encryption_service):
        """Test encrypting unicode characters."""
        original = "API Key: 🔐 секретный ключ 密钥"
        
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == original
    
    def test_decrypt_invalid_data(self, encryption_service):
        """Test decrypting invalid data raises error."""
        with pytest.raises(ValueError, match="Failed to decrypt data"):
            encryption_service.decrypt("invalid-encrypted-data")
    
    def test_generate_key(self, encryption_service):
        """Test key generation."""
        key = encryption_service.generate_key()
        
        assert len(key) > 0
        assert isinstance(key, str)
        
        # Verify it's a valid Fernet key
        from cryptography.fernet import Fernet
        Fernet(key.encode())  # Should not raise
    
    def test_key_rotation(self, encryption_service):
        """Test rotating encryption keys."""
        # Generate keys
        old_key = encryption_service.generate_key()
        new_key = encryption_service.generate_key()
        
        # Create cipher with old key
        from cryptography.fernet import Fernet
        old_cipher = Fernet(old_key.encode())
        
        # Encrypt with old key
        original = "sensitive-api-key"
        encrypted_old = old_cipher.encrypt(original.encode())
        import base64
        encrypted_old_b64 = base64.urlsafe_b64encode(encrypted_old).decode()
        
        # Rotate to new key
        encrypted_new = encryption_service.rotate_key(
            old_key, new_key, encrypted_old_b64
        )
        
        # Verify we can decrypt with new key
        new_cipher = Fernet(new_key.encode())
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_new.encode())
        decrypted = new_cipher.decrypt(encrypted_bytes).decode()
        
        assert decrypted == original
    
    def test_deterministic_encryption_different(self, encryption_service):
        """Test that same data encrypted twice produces different ciphertext."""
        original = "test-api-key"
        
        encrypted1 = encryption_service.encrypt(original)
        encrypted2 = encryption_service.encrypt(original)
        
        # Ciphertexts should be different (due to random IV)
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same value
        assert encryption_service.decrypt(encrypted1) == original
        assert encryption_service.decrypt(encrypted2) == original