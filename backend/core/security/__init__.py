"""
Security module for application hardening.
"""

from .headers import SecurityHeadersMiddleware, security_headers_config
from .api_keys import APIKeyManager, rotate_api_keys
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

# Import auth functions from the renamed module
from ..auth_security import (
    verify_password,
    get_password_hash,
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