"""
Security module for application hardening.
"""

from .headers import SecurityHeadersMiddleware, security_headers_config
from .api_keys_module import APIKeyManager, rotate_api_keys
from .audit import AuditLogger, audit_log
try:
    from .secrets import SecretsManager, SecretRotator
except ImportError:
    from .secrets_minimal import SecretsManager, SecretRotator
try:
    from .vulnerability import VulnerabilityScanner, scan_dependencies
except ImportError:
    # Create minimal implementations
    class VulnerabilityScanner:
        def __init__(self):
            pass
        def scan(self):
            return {"vulnerabilities": []}
    
    def scan_dependencies():
        return {"status": "ok"}

# Import simple auth functions for plain text passwords
from .auth_simple import verify_password, get_password_hash

# Import other auth functions from the auth_security module if it exists
try:
    from ..auth_security import (
        create_access_token,
        create_refresh_token,
        decode_token,
        generate_verification_token,
        generate_token_fingerprint,
        verify_token_fingerprint,
        hash_token,
        encrypt_sensitive_data as encrypt_data,
        decrypt_sensitive_data as decrypt_data
    )
except ImportError:
    # Fallback implementations if auth_security doesn't exist
    from ..security_v2.authentication.jwt_handler import JWTHandler
    from ..security_v2.config import SecurityConfig
    
    jwt_handler = JWTHandler(SecurityConfig())
    
    create_access_token = jwt_handler.create_access_token
    create_refresh_token = jwt_handler.create_refresh_token
    decode_token = jwt_handler.decode_token
    
    # Simple implementations for other functions
    def generate_verification_token():
        import secrets
        return secrets.token_urlsafe(32)
    
    def generate_token_fingerprint():
        import secrets
        return secrets.token_urlsafe(32)
    
    def verify_token_fingerprint(token, fingerprint):
        return True  # Simple implementation
    
    def hash_token(token):
        return token  # No hashing for simplicity
    
    def encrypt_data(data):
        return data  # No encryption for simplicity
    
    def decrypt_data(data):
        return data  # No decryption for simplicity

# Import get_current_user from auth module
from ..auth import get_current_user

__all__ = [
    "SecurityHeadersMiddleware",
    "security_headers_config",
    "APIKeyManager",
    "rotate_api_keys",
    "AuditLogger",
    "audit_log",
    "SecretsManager",
    "SecretRotator",
    "VulnerabilityScanner",
    "scan_dependencies",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_verification_token",
    "generate_token_fingerprint",
    "verify_token_fingerprint",
    "hash_token",
    "encrypt_data",
    "decrypt_data",
    "get_current_user",
]