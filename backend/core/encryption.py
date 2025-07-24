"""
Data encryption utilities for sensitive information.
"""
from typing import Optional, Union, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import json
import os
from datetime import datetime

from core.config import settings
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        # Generate encryption key from secret
        self.master_key = self._derive_key(settings.SECRET_KEY)
        self.fernet = Fernet(self.master_key)
        
        # For field-level encryption
        self.field_key = self._derive_key(f"{settings.SECRET_KEY}_field")
        self.field_cipher = AESGCM(self.field_key[:32])
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'AgencyDark2024',  # In production, use random salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """Encrypt data and return base64 encoded string."""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            encrypted = self.fernet.encrypt(data)
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded data."""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise
    
    def encrypt_field(self, value: str) -> Dict[str, str]:
        """Encrypt a field value with additional metadata."""
        try:
            # Generate nonce
            nonce = os.urandom(12)
            
            # Encrypt value
            ciphertext = self.field_cipher.encrypt(
                nonce,
                value.encode(),
                None  # Additional authenticated data
            )
            
            # Return encrypted data with metadata
            return {
                "version": "1",
                "nonce": base64.b64encode(nonce).decode(),
                "ciphertext": base64.b64encode(ciphertext).decode(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Field encryption failed: {str(e)}")
            raise
    
    def decrypt_field(self, encrypted_field: Dict[str, str]) -> str:
        """Decrypt a field value."""
        try:
            nonce = base64.b64decode(encrypted_field["nonce"])
            ciphertext = base64.b64decode(encrypted_field["ciphertext"])
            
            plaintext = self.field_cipher.decrypt(
                nonce,
                ciphertext,
                None
            )
            
            return plaintext.decode()
            
        except Exception as e:
            logger.error(f"Field decryption failed: {str(e)}")
            raise
    
    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """Encrypt JSON data."""
        json_str = json.dumps(data, separators=(',', ':'))
        return self.encrypt(json_str)
    
    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt JSON data."""
        decrypted = self.decrypt(encrypted_data)
        return json.loads(decrypted)
    
    def hash_sensitive_data(self, data: str) -> str:
        """Create a one-way hash of sensitive data for comparison."""
        # Use SHA-256 for consistent hashing
        import hashlib
        return hashlib.sha256(data.encode()).hexdigest()


class EncryptedString(str):
    """Custom type for encrypted string fields in SQLAlchemy."""
    pass


class EncryptedJSON(dict):
    """Custom type for encrypted JSON fields in SQLAlchemy."""
    pass


# SQLAlchemy type decorators
from sqlalchemy.types import TypeDecorator, String, JSON


class EncryptedStringType(TypeDecorator):
    """SQLAlchemy type for encrypted strings."""
    impl = String
    cache_ok = True
    
    def __init__(self, encryption_service: Optional[EncryptionService] = None, *args, **kwargs):
        self.encryption_service = encryption_service or EncryptionService()
        super().__init__(*args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        """Encrypt value before storing."""
        if value is None:
            return None
        return self.encryption_service.encrypt(value)
    
    def process_result_value(self, value, dialect):
        """Decrypt value after retrieving."""
        if value is None:
            return None
        return self.encryption_service.decrypt(value)


class EncryptedJSONType(TypeDecorator):
    """SQLAlchemy type for encrypted JSON."""
    impl = String
    cache_ok = True
    
    def __init__(self, encryption_service: Optional[EncryptionService] = None, *args, **kwargs):
        self.encryption_service = encryption_service or EncryptionService()
        super().__init__(*args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        """Encrypt JSON before storing."""
        if value is None:
            return None
        return self.encryption_service.encrypt_json(value)
    
    def process_result_value(self, value, dialect):
        """Decrypt JSON after retrieving."""
        if value is None:
            return None
        return self.encryption_service.decrypt_json(value)


# Utility functions for sensitive data handling
def mask_sensitive_string(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive string showing only first/last few characters."""
    if not value or len(value) <= visible_chars * 2:
        return "****"
    
    return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"


def mask_email(email: str) -> str:
    """Mask email address."""
    if '@' not in email:
        return mask_sensitive_string(email)
    
    local, domain = email.split('@', 1)
    masked_local = mask_sensitive_string(local, 2)
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """Mask phone number."""
    # Keep country code and last 4 digits
    if len(phone) <= 8:
        return "****"
    
    if phone.startswith('+'):
        # Keep country code
        parts = phone.split(' ', 1)
        if len(parts) == 2:
            return f"{parts[0]} ****{phone[-4:]}"
    
    return f"****{phone[-4:]}"


def mask_api_key(api_key: str) -> str:
    """Mask API key showing only prefix."""
    if len(api_key) <= 12:
        return "****"
    
    return f"{api_key[:8]}...{api_key[-4:]}"


# Global encryption service instance
encryption_service = EncryptionService()


# Example usage in models:
"""
from core.encryption import EncryptedStringType, EncryptedJSONType

class SensitiveDataModel(Base):
    __tablename__ = "sensitive_data"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    
    # Encrypted fields
    ssn = Column(EncryptedStringType(255))
    bank_account = Column(EncryptedStringType(255))
    api_credentials = Column(EncryptedJSONType())
    
    # Regular fields
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
"""