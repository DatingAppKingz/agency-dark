"""
Token encryption service for secure storage of OAuth tokens.
Uses Fernet symmetric encryption with key rotation support.
"""
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta, timezone
import secrets
import json
import base64
import logging
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import os

logger = logging.getLogger(__name__)


class TokenEncryptionService:
    """
    Service for encrypting and decrypting OAuth tokens.
    Supports key rotation and versioning.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            master_key: Master encryption key (base64 encoded)
                       If not provided, will use environment variable
        """
        self.master_key = master_key or os.getenv("OAUTH_ENCRYPTION_KEY")
        
        if not self.master_key:
            # Generate a new key if none exists (should be stored securely)
            self.master_key = Fernet.generate_key().decode()
            logger.warning(
                "No encryption key provided. Generated new key. "
                "Please store this securely: %s", self.master_key
            )
        
        # Initialize cipher with current and previous keys for rotation
        self.ciphers = self._initialize_ciphers()
        self.current_version = 1
    
    def _initialize_ciphers(self) -> MultiFernet:
        """
        Initialize encryption ciphers with key rotation support.
        """
        keys = []
        
        # Current key
        if isinstance(self.master_key, str):
            keys.append(Fernet(self.master_key.encode() if len(self.master_key) < 50 else self.master_key))
        else:
            keys.append(Fernet(self.master_key))
        
        # Previous keys for rotation (from environment or config)
        for i in range(1, 4):  # Support up to 3 previous keys
            old_key = os.getenv(f"OAUTH_ENCRYPTION_KEY_V{i}")
            if old_key:
                keys.append(Fernet(old_key.encode() if len(old_key) < 50 else old_key))
        
        return MultiFernet(keys)
    
    def encrypt_token(self, token: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Encrypt an OAuth token.
        
        Args:
            token: Plain text token to encrypt
            metadata: Optional metadata to include with encrypted token
            
        Returns:
            Encrypted token as base64 string
        """
        try:
            # Create payload with token and metadata
            payload = {
                "token": token,
                "version": self.current_version,
                "encrypted_at": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {}
            }
            
            # Serialize and encrypt
            payload_bytes = json.dumps(payload).encode()
            encrypted = self.ciphers.encrypt(payload_bytes)
            
            # Return as base64 string for storage
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt token: {e}")
            raise
    
    def decrypt_token(self, encrypted_token: str) -> tuple[str, Dict[str, Any]]:
        """
        Decrypt an OAuth token.
        
        Args:
            encrypted_token: Encrypted token (base64 string)
            
        Returns:
            Tuple of (decrypted token, metadata)
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode())
            
            # Decrypt (MultiFernet handles key rotation)
            decrypted = self.ciphers.decrypt(encrypted_bytes)
            
            # Parse payload
            payload = json.loads(decrypted.decode())
            
            return payload["token"], payload.get("metadata", {})
            
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            raise
    
    def rotate_encryption(self, encrypted_token: str) -> str:
        """
        Re-encrypt a token with the current key.
        Used for key rotation.
        
        Args:
            encrypted_token: Token encrypted with old key
            
        Returns:
            Token encrypted with current key
        """
        try:
            # Decrypt with old key
            token, metadata = self.decrypt_token(encrypted_token)
            
            # Re-encrypt with current key
            return self.encrypt_token(token, metadata)
            
        except Exception as e:
            logger.error(f"Failed to rotate token encryption: {e}")
            raise
    
    @staticmethod
    def generate_encryption_key() -> str:
        """
        Generate a new Fernet encryption key.
        
        Returns:
            Base64 encoded encryption key
        """
        return Fernet.generate_key().decode()
    
    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> str:
        """
        Derive an encryption key from a password.
        
        Args:
            password: Password to derive key from
            salt: Optional salt (will generate if not provided)
            
        Returns:
            Base64 encoded encryption key
        """
        if not salt:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode()


class SecureTokenStorage:
    """
    Secure storage service for OAuth tokens with encryption.
    """
    
    def __init__(self, encryption_service: Optional[TokenEncryptionService] = None):
        """
        Initialize secure storage.
        
        Args:
            encryption_service: Encryption service instance
        """
        self.encryption = encryption_service or TokenEncryptionService()
    
    def store_token(
        self,
        provider: str,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        scope: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Securely store OAuth tokens.
        
        Args:
            provider: OAuth provider name
            user_id: User ID
            access_token: Access token to store
            refresh_token: Optional refresh token
            expires_at: Token expiration time
            scope: Token scope
            additional_data: Additional data to store
            
        Returns:
            Dictionary with encrypted tokens
        """
        result = {}
        
        # Encrypt access token
        access_metadata = {
            "provider": provider,
            "user_id": user_id,
            "type": "access",
            "scope": scope,
            "expires_at": expires_at.isoformat() if expires_at else None
        }
        
        if additional_data:
            access_metadata.update(additional_data)
        
        result["access_token"] = self.encryption.encrypt_token(
            access_token,
            access_metadata
        )
        
        # Encrypt refresh token if provided
        if refresh_token:
            refresh_metadata = {
                "provider": provider,
                "user_id": user_id,
                "type": "refresh",
                "scope": scope
            }
            
            result["refresh_token"] = self.encryption.encrypt_token(
                refresh_token,
                refresh_metadata
            )
        
        return result
    
    def retrieve_token(
        self,
        encrypted_token: str,
        expected_provider: Optional[str] = None,
        expected_user_id: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Retrieve and decrypt a token with validation.
        
        Args:
            encrypted_token: Encrypted token
            expected_provider: Expected provider for validation
            expected_user_id: Expected user ID for validation
            
        Returns:
            Tuple of (decrypted token, metadata)
            
        Raises:
            ValueError: If validation fails
        """
        token, metadata = self.encryption.decrypt_token(encrypted_token)
        
        # Validate provider if specified
        if expected_provider and metadata.get("provider") != expected_provider:
            raise ValueError(f"Token provider mismatch: expected {expected_provider}")
        
        # Validate user if specified
        if expected_user_id and metadata.get("user_id") != expected_user_id:
            raise ValueError(f"Token user mismatch: expected {expected_user_id}")
        
        # Check expiration
        if metadata.get("expires_at"):
            expires_at = datetime.fromisoformat(metadata["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                logger.warning("Attempting to retrieve expired token")
        
        return token, metadata
    
    def batch_encrypt_tokens(
        self,
        tokens: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Encrypt multiple tokens in batch.
        
        Args:
            tokens: List of token dictionaries
            
        Returns:
            List of encrypted token dictionaries
        """
        encrypted_tokens = []
        
        for token_data in tokens:
            encrypted = self.store_token(
                provider=token_data.get("provider"),
                user_id=token_data.get("user_id"),
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                expires_at=token_data.get("expires_at"),
                scope=token_data.get("scope"),
                additional_data=token_data.get("additional_data")
            )
            encrypted_tokens.append(encrypted)
        
        return encrypted_tokens
    
    def rotate_all_tokens(
        self,
        encrypted_tokens: List[str]
    ) -> List[str]:
        """
        Rotate encryption for multiple tokens.
        
        Args:
            encrypted_tokens: List of encrypted tokens
            
        Returns:
            List of re-encrypted tokens
        """
        rotated = []
        
        for encrypted_token in encrypted_tokens:
            try:
                rotated_token = self.encryption.rotate_encryption(encrypted_token)
                rotated.append(rotated_token)
            except Exception as e:
                logger.error(f"Failed to rotate token: {e}")
                rotated.append(encrypted_token)  # Keep original if rotation fails
        
        return rotated


class TokenEncryptionMiddleware:
    """
    Middleware to automatically encrypt/decrypt tokens in database operations.
    """
    
    def __init__(self, encryption_service: Optional[TokenEncryptionService] = None):
        """
        Initialize middleware.
        
        Args:
            encryption_service: Encryption service instance
        """
        self.encryption = encryption_service or TokenEncryptionService()
    
    def before_save(self, token_model: Any) -> Any:
        """
        Encrypt tokens before saving to database.
        
        Args:
            token_model: Token model instance
            
        Returns:
            Model with encrypted tokens
        """
        if hasattr(token_model, "access_token") and token_model.access_token:
            # Skip if already encrypted (check for base64 format)
            if not self._is_encrypted(token_model.access_token):
                metadata = {
                    "provider": getattr(token_model, "provider", None),
                    "user_id": str(getattr(token_model, "user_id", None)),
                    "agency_id": str(getattr(token_model, "agency_id", None))
                }
                token_model.access_token = self.encryption.encrypt_token(
                    token_model.access_token,
                    metadata
                )
        
        if hasattr(token_model, "refresh_token") and token_model.refresh_token:
            if not self._is_encrypted(token_model.refresh_token):
                metadata = {
                    "provider": getattr(token_model, "provider", None),
                    "user_id": str(getattr(token_model, "user_id", None)),
                    "agency_id": str(getattr(token_model, "agency_id", None))
                }
                token_model.refresh_token = self.encryption.encrypt_token(
                    token_model.refresh_token,
                    metadata
                )
        
        return token_model
    
    def after_load(self, token_model: Any) -> Any:
        """
        Decrypt tokens after loading from database.
        
        Args:
            token_model: Token model instance
            
        Returns:
            Model with decrypted tokens
        """
        if hasattr(token_model, "access_token") and token_model.access_token:
            if self._is_encrypted(token_model.access_token):
                try:
                    token, _ = self.encryption.decrypt_token(token_model.access_token)
                    token_model.access_token = token
                except Exception as e:
                    logger.error(f"Failed to decrypt access token: {e}")
        
        if hasattr(token_model, "refresh_token") and token_model.refresh_token:
            if self._is_encrypted(token_model.refresh_token):
                try:
                    token, _ = self.encryption.decrypt_token(token_model.refresh_token)
                    token_model.refresh_token = token
                except Exception as e:
                    logger.error(f"Failed to decrypt refresh token: {e}")
        
        return token_model
    
    def _is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted.
        
        Args:
            value: Value to check
            
        Returns:
            True if value appears encrypted
        """
        # Simple heuristic: encrypted values are base64 and longer
        try:
            if len(value) > 100:  # Encrypted tokens are longer
                base64.urlsafe_b64decode(value)
                return True
        except:
            pass
        
        return False


# Global encryption service instance
token_encryption_service = TokenEncryptionService()
secure_token_storage = SecureTokenStorage(token_encryption_service)
token_encryption_middleware = TokenEncryptionMiddleware(token_encryption_service)