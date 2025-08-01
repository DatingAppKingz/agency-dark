"""Encryption service for sensitive data like API keys."""

import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        """Initialize encryption service with key from environment."""
        self._cipher = self._get_cipher()
    
    def _get_cipher(self) -> Fernet:
        """Create Fernet cipher from environment key or generate one."""
        # Get encryption key from environment
        encryption_key = settings.ENCRYPTION_KEY
        
        if not encryption_key:
            # In production, this should never happen
            # For development, generate a key but warn
            logger.warning("ENCRYPTION_KEY not set in environment! Generating temporary key.")
            encryption_key = Fernet.generate_key().decode()
            
        # If the key is not a valid Fernet key, derive one from it
        try:
            # Try to use it directly as a Fernet key
            return Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception:
            # Derive a proper key from the provided string
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'agencydark-salt',  # In production, use a proper salt
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
            return Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not plaintext:
            return ""
            
        try:
            encrypted = self._cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: Base64 encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
            
        try:
            # Decode from base64
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            # Decrypt
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
    
    def generate_key(self) -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()
    
    def rotate_key(self, old_key: str, new_key: str, ciphertext: str) -> str:
        """
        Rotate encryption key by re-encrypting data.
        
        Args:
            old_key: The current encryption key
            new_key: The new encryption key
            ciphertext: Data encrypted with old key
            
        Returns:
            Data encrypted with new key
        """
        # Create ciphers for both keys
        old_cipher = Fernet(old_key.encode())
        new_cipher = Fernet(new_key.encode())
        
        try:
            # Decrypt with old key
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = old_cipher.decrypt(encrypted)
            
            # Encrypt with new key
            new_encrypted = new_cipher.encrypt(decrypted)
            return base64.urlsafe_b64encode(new_encrypted).decode()
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise ValueError("Failed to rotate encryption key")


# Global instance
encryption_service = EncryptionService()