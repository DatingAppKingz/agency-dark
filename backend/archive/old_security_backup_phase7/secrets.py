"""
Secrets management and rotation system.
"""

import os
import json
import base64
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hvac
import boto3
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from core.config import settings
from core.logging import get_logger
from core.security.audit import audit_logger, AuditEventType, AuditSeverity

logger = get_logger(__name__)


class SecretsProvider:
    """Base class for secrets providers."""
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        raise NotImplementedError
    
    async def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None):
        """Set a secret value."""
        raise NotImplementedError
    
    async def delete_secret(self, key: str):
        """Delete a secret."""
        raise NotImplementedError
    
    async def list_secrets(self) -> List[str]:
        """List all secret keys."""
        raise NotImplementedError
    
    async def rotate_secret(self, key: str) -> str:
        """Rotate a secret and return new value."""
        raise NotImplementedError


class LocalSecretsProvider(SecretsProvider):
    """Local file-based secrets provider for development."""
    
    def __init__(self, secrets_file: str = ".secrets.json"):
        self.secrets_file = secrets_file
        self.fernet = Fernet(self._get_or_create_key())
        self._load_secrets()
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = ".secrets.key"
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        
        # Generate new key
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        
        return key
    
    def _load_secrets(self):
        """Load secrets from file."""
        if os.path.exists(self.secrets_file):
            with open(self.secrets_file, "rb") as f:
                encrypted_data = f.read()
                if encrypted_data:
                    decrypted_data = self.fernet.decrypt(encrypted_data)
                    self.secrets = json.loads(decrypted_data)
                else:
                    self.secrets = {}
        else:
            self.secrets = {}
    
    def _save_secrets(self):
        """Save secrets to file."""
        encrypted_data = self.fernet.encrypt(json.dumps(self.secrets).encode())
        with open(self.secrets_file, "wb") as f:
            f.write(encrypted_data)
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        return self.secrets.get(key)
    
    async def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None):
        """Set a secret value."""
        self.secrets[key] = {
            "value": value,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        self._save_secrets()
    
    async def delete_secret(self, key: str):
        """Delete a secret."""
        if key in self.secrets:
            del self.secrets[key]
            self._save_secrets()
    
    async def list_secrets(self) -> List[str]:
        """List all secret keys."""
        return list(self.secrets.keys())
    
    async def rotate_secret(self, key: str) -> str:
        """Rotate a secret and return new value."""
        import secrets
        new_value = secrets.token_urlsafe(32)
        await self.set_secret(key, new_value)
        return new_value


class HashiCorpVaultProvider(SecretsProvider):
    """HashiCorp Vault secrets provider."""
    
    def __init__(self, vault_url: str, vault_token: str, mount_point: str = "secret"):
        self.client = hvac.Client(url=vault_url, token=vault_token)
        self.mount_point = mount_point
        
        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=self.mount_point
            )
            return response["data"]["data"].get("value")
        except Exception as e:
            logger.error(f"Error getting secret from Vault: {e}")
            return None
    
    async def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None):
        """Set a secret value."""
        secret_data = {
            "value": value,
            "metadata": metadata or {},
            "updated_at": datetime.utcnow().isoformat()
        }
        
        self.client.secrets.kv.v2.create_or_update_secret(
            path=key,
            secret=secret_data,
            mount_point=self.mount_point
        )
    
    async def delete_secret(self, key: str):
        """Delete a secret."""
        self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=key,
            mount_point=self.mount_point
        )
    
    async def list_secrets(self) -> List[str]:
        """List all secret keys."""
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                mount_point=self.mount_point
            )
            return response["data"]["keys"]
        except Exception:
            return []
    
    async def rotate_secret(self, key: str) -> str:
        """Rotate a secret and return new value."""
        import secrets
        new_value = secrets.token_urlsafe(32)
        
        # Keep old version in Vault history
        await self.set_secret(key, new_value, {"rotated_at": datetime.utcnow().isoformat()})
        
        return new_value


class AWSSecretsProvider(SecretsProvider):
    """AWS Secrets Manager provider."""
    
    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region_name)
        self.region = region_name
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        try:
            response = self.client.get_secret_value(SecretId=key)
            
            if "SecretString" in response:
                secret_data = json.loads(response["SecretString"])
                return secret_data.get("value")
            else:
                # Binary secret
                return base64.b64decode(response["SecretBinary"]).decode()
                
        except self.client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logger.error(f"Error getting secret from AWS: {e}")
            return None
    
    async def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None):
        """Set a secret value."""
        secret_data = {
            "value": value,
            "metadata": metadata or {},
            "updated_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Try to update existing secret
            self.client.update_secret(
                SecretId=key,
                SecretString=json.dumps(secret_data)
            )
        except self.client.exceptions.ResourceNotFoundException:
            # Create new secret
            self.client.create_secret(
                Name=key,
                SecretString=json.dumps(secret_data),
                Tags=[
                    {"Key": "Environment", "Value": settings.ENVIRONMENT},
                    {"Key": "ManagedBy", "Value": "AgencyBackend"}
                ]
            )
    
    async def delete_secret(self, key: str):
        """Delete a secret."""
        try:
            self.client.delete_secret(
                SecretId=key,
                RecoveryWindowInDays=7  # Soft delete with recovery window
            )
        except Exception as e:
            logger.error(f"Error deleting secret from AWS: {e}")
    
    async def list_secrets(self) -> List[str]:
        """List all secret keys."""
        secrets = []
        
        try:
            paginator = self.client.get_paginator("list_secrets")
            
            for page in paginator.paginate():
                for secret in page["SecretList"]:
                    secrets.append(secret["Name"])
                    
        except Exception as e:
            logger.error(f"Error listing secrets from AWS: {e}")
        
        return secrets
    
    async def rotate_secret(self, key: str) -> str:
        """Rotate a secret and return new value."""
        import secrets
        new_value = secrets.token_urlsafe(32)
        
        # AWS supports automatic rotation, but we'll do manual for now
        await self.set_secret(key, new_value, {"rotated_at": datetime.utcnow().isoformat()})
        
        return new_value


class SecretsManager:
    """Central secrets management system."""
    
    def __init__(self, provider: Optional[SecretsProvider] = None):
        self.provider = provider or self._get_default_provider()
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Rotation configuration
        self.rotation_schedule = {
            "database_password": 30,  # days
            "api_keys": 90,
            "encryption_keys": 180,
            "jwt_secret": 90,
            "oauth_secrets": 365
        }
    
    def _get_default_provider(self) -> SecretsProvider:
        """Get default secrets provider based on environment."""
        if settings.ENVIRONMENT == "development":
            return LocalSecretsProvider()
        
        elif settings.SECRETS_PROVIDER == "vault":
            return HashiCorpVaultProvider(
                vault_url=settings.VAULT_URL,
                vault_token=settings.VAULT_TOKEN
            )
        
        elif settings.SECRETS_PROVIDER == "aws":
            return AWSSecretsProvider(region_name=settings.AWS_REGION)
        
        else:
            # Default to local provider
            return LocalSecretsProvider()
    
    async def get_secret(
        self,
        key: str,
        use_cache: bool = True,
        decrypt: bool = True
    ) -> Optional[str]:
        """Get a secret value with caching."""
        # Check cache
        if use_cache and key in self.cache:
            cached_entry = self.cache[key]
            if cached_entry["expires_at"] > datetime.utcnow():
                return cached_entry["value"]
        
        # Get from provider
        value = await self.provider.get_secret(key)
        
        if value and use_cache:
            # Cache the value
            self.cache[key] = {
                "value": value,
                "expires_at": datetime.utcnow() + timedelta(seconds=self.cache_ttl)
            }
        
        # Log access
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_READ,
            severity=AuditSeverity.INFO,
            resource_type="secret",
            resource_id=key,
            action="get_secret"
        )
        
        return value
    
    async def set_secret(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict] = None,
        encrypt: bool = True
    ):
        """Set a secret value."""
        # Validate secret strength
        if not self._validate_secret_strength(key, value):
            raise ValueError(f"Secret does not meet strength requirements for {key}")
        
        # Set in provider
        await self.provider.set_secret(key, value, metadata)
        
        # Invalidate cache
        if key in self.cache:
            del self.cache[key]
        
        # Log change
        await audit_logger.log_event(
            event_type=AuditEventType.CONFIG_CHANGED,
            severity=AuditSeverity.WARNING,
            resource_type="secret",
            resource_id=key,
            action="set_secret",
            metadata={"has_metadata": bool(metadata)}
        )
    
    async def rotate_secret(self, key: str) -> Tuple[str, str]:
        """Rotate a secret and return old and new values."""
        # Get old value
        old_value = await self.get_secret(key, use_cache=False)
        
        # Generate new value
        new_value = await self.provider.rotate_secret(key)
        
        # Invalidate cache
        if key in self.cache:
            del self.cache[key]
        
        # Log rotation
        await audit_logger.log_event(
            event_type=AuditEventType.CONFIG_CHANGED,
            severity=AuditSeverity.WARNING,
            resource_type="secret",
            resource_id=key,
            action="rotate_secret"
        )
        
        return old_value, new_value
    
    async def check_rotation_needed(self) -> List[Dict[str, Any]]:
        """Check which secrets need rotation."""
        secrets_needing_rotation = []
        
        for secret_pattern, rotation_days in self.rotation_schedule.items():
            secrets = await self.provider.list_secrets()
            
            for secret_key in secrets:
                if secret_pattern in secret_key:
                    # Check last rotation date
                    # In production, store rotation metadata
                    secrets_needing_rotation.append({
                        "key": secret_key,
                        "pattern": secret_pattern,
                        "rotation_days": rotation_days
                    })
        
        return secrets_needing_rotation
    
    def _validate_secret_strength(self, key: str, value: str) -> bool:
        """Validate secret strength based on type."""
        if "password" in key.lower():
            # Password requirements
            return (
                len(value) >= 12 and
                any(c.isupper() for c in value) and
                any(c.islower() for c in value) and
                any(c.isdigit() for c in value) and
                any(c in "!@#$%^&*()_+-=" for c in value)
            )
        
        elif "key" in key.lower() or "token" in key.lower():
            # API key/token requirements
            return len(value) >= 32
        
        # Default minimum length
        return len(value) >= 16


class SecretRotator:
    """Automated secret rotation system."""
    
    def __init__(self, secrets_manager: SecretsManager):
        self.secrets_manager = secrets_manager
        self.rotation_callbacks = {}
    
    def register_rotation_callback(self, secret_pattern: str, callback: callable):
        """Register a callback for when a secret is rotated."""
        self.rotation_callbacks[secret_pattern] = callback
    
    async def rotate_all_due_secrets(self) -> List[Dict[str, Any]]:
        """Rotate all secrets that are due for rotation."""
        rotated_secrets = []
        
        secrets_to_rotate = await self.secrets_manager.check_rotation_needed()
        
        for secret_info in secrets_to_rotate:
            try:
                key = secret_info["key"]
                old_value, new_value = await self.secrets_manager.rotate_secret(key)
                
                # Execute callback if registered
                for pattern, callback in self.rotation_callbacks.items():
                    if pattern in key:
                        await callback(key, old_value, new_value)
                
                rotated_secrets.append({
                    "key": key,
                    "status": "success",
                    "rotated_at": datetime.utcnow()
                })
                
                logger.info(f"Successfully rotated secret: {key}")
                
            except Exception as e:
                logger.error(f"Failed to rotate secret {key}: {e}")
                
                rotated_secrets.append({
                    "key": key,
                    "status": "failed",
                    "error": str(e)
                })
        
        return rotated_secrets


# Secret validation utilities
def validate_database_url(url: str) -> bool:
    """Validate database URL format and security."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ["postgresql", "postgres", "mysql", "sqlite"]:
            return False
        
        # Check for password in URL (should use separate secret)
        if parsed.password and len(parsed.password) < 12:
            return False
        
        # Check for SSL/TLS
        if parsed.scheme in ["postgresql", "postgres", "mysql"]:
            query_params = dict(
                param.split("=") for param in parsed.query.split("&")
                if "=" in param
            )
            
            if query_params.get("sslmode") not in ["require", "verify-full"]:
                logger.warning("Database URL should use SSL/TLS")
        
        return True
        
    except Exception:
        return False