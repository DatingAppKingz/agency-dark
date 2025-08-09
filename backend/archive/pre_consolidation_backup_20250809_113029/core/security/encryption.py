"""
Encryption service for secure data handling.
"""
import os
import base64
import json
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets

from core.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        self._master_key = self._get_or_create_master_key()
        self._fernet = Fernet(self._master_key)
        
    def _get_or_create_master_key(self) -> bytes:
        """Get or create the master encryption key."""
        # In production, this should be stored in a secure key management service
        # For now, we'll use an environment variable
        key = settings.ENCRYPTION_KEY
        
        if not key:
            # Generate a new key if none exists
            key = Fernet.generate_key().decode()
            # Log warning - in production, this should be stored securely
            import logging
            logging.warning(
                "Generated new encryption key. "
                "Set ENCRYPTION_KEY environment variable to persist."
            )
        
        return key.encode() if isinstance(key, str) else key
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt a string value.
        
        Args:
            data: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not data:
            return ""
        
        encrypted = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted string
        """
        if not encrypted_data:
            return ""
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted string
        """
        json_str = json.dumps(data, separators=(',', ':'))
        return self.encrypt(json_str)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt to a dictionary.
        
        Args:
            encrypted_data: Encrypted string
            
        Returns:
            Decrypted dictionary
        """
        decrypted_str = self.decrypt(encrypted_data)
        return json.loads(decrypted_str) if decrypted_str else {}


class APIKeyEncryption:
    """Specialized encryption for API keys with rotation support."""
    
    def __init__(self):
        self.encryption_service = EncryptionService()
        
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Generate a new API key pair (public key and secret).
        
        Returns:
            Tuple of (api_key, api_secret)
        """
        # Generate API key (public identifier)
        api_key = f"ak_{secrets.token_urlsafe(24)}"
        
        # Generate API secret (private key)
        api_secret = f"sk_{secrets.token_urlsafe(32)}"
        
        return api_key, api_secret
    
    def encrypt_api_key(self, api_key: str, api_secret: str, 
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Encrypt API key data for storage.
        
        Args:
            api_key: Public API key
            api_secret: Secret API key
            metadata: Additional metadata to store
            
        Returns:
            Dictionary with encrypted data
        """
        key_data = {
            "api_key": api_key,
            "api_secret": api_secret,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Encrypt the entire payload
        encrypted_payload = self.encryption_service.encrypt_dict(key_data)
        
        # Return storage format
        return {
            "key_id": api_key,
            "encrypted_data": encrypted_payload,
            "version": "1.0"
        }
    
    def decrypt_api_key(self, encrypted_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Decrypt API key data.
        
        Args:
            encrypted_data: Encrypted key data
            
        Returns:
            Decrypted key data
        """
        if encrypted_data.get("version") != "1.0":
            raise ValueError("Unsupported encryption version")
        
        return self.encryption_service.decrypt_dict(
            encrypted_data["encrypted_data"]
        )
    
    def rotate_api_key(self, old_encrypted_data: Dict[str, str]) -> Dict[str, str]:
        """
        Rotate an API key by generating a new secret.
        
        Args:
            old_encrypted_data: Current encrypted key data
            
        Returns:
            New encrypted key data
        """
        # Decrypt old data
        old_data = self.decrypt_api_key(old_encrypted_data)
        
        # Generate new secret
        new_api_key = old_data["api_key"]  # Keep the same public key
        new_api_secret = f"sk_{secrets.token_urlsafe(32)}"
        
        # Preserve metadata and add rotation info
        metadata = old_data.get("metadata", {})
        metadata["rotated_at"] = datetime.utcnow().isoformat()
        metadata["rotation_count"] = metadata.get("rotation_count", 0) + 1
        
        # Encrypt with new data
        return self.encrypt_api_key(new_api_key, new_api_secret, metadata)


class FieldEncryption:
    """Encryption for specific database fields."""
    
    def __init__(self):
        self.encryption_service = EncryptionService()
        
    def encrypt_field(self, value: Any, field_type: str = "string") -> str:
        """
        Encrypt a field value based on its type.
        
        Args:
            value: Value to encrypt
            field_type: Type of the field
            
        Returns:
            Encrypted string
        """
        if value is None:
            return ""
        
        if field_type == "string":
            return self.encryption_service.encrypt(str(value))
        elif field_type == "json":
            return self.encryption_service.encrypt_dict(value)
        else:
            # Convert to string for other types
            return self.encryption_service.encrypt(str(value))
    
    def decrypt_field(self, encrypted_value: str, field_type: str = "string") -> Any:
        """
        Decrypt a field value based on its type.
        
        Args:
            encrypted_value: Encrypted value
            field_type: Type of the field
            
        Returns:
            Decrypted value in appropriate type
        """
        if not encrypted_value:
            return None
        
        if field_type == "string":
            return self.encryption_service.decrypt(encrypted_value)
        elif field_type == "json":
            return self.encryption_service.decrypt_dict(encrypted_value)
        else:
            # Return as string for other types
            return self.encryption_service.decrypt(encrypted_value)


class TokenEncryption:
    """Encryption for authentication tokens."""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """
        Create a one-way hash of a token for comparison.
        
        Args:
            token: Token to hash
            
        Returns:
            Hashed token
        """
        # Use SHA-256 for token hashing
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()


# Global instances
encryption_service = EncryptionService()
api_key_encryption = APIKeyEncryption()
field_encryption = FieldEncryption()


def data_masking(data: str, mask_type: str = "partial") -> str:
    """
    Mask sensitive data for display.
    
    Args:
        data: Data to mask
        mask_type: Type of masking (partial, full)
        
    Returns:
        Masked data
    """
    if not data:
        return ""
    
    if mask_type == "full":
        return "*" * len(data)
    elif mask_type == "partial":
        # Show first 4 and last 4 characters
        if len(data) <= 8:
            return "*" * len(data)
        return f"{data[:4]}{'*' * (len(data) - 8)}{data[-4:]}"
    else:
        return data