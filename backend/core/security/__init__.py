"""
Security module for application hardening.
"""

from .headers import SecurityHeadersMiddleware, security_headers_config
from .api_keys import APIKeyManager, rotate_api_key
from .audit import AuditLogger, audit_log
from .secrets import SecretsManager, SecretRotator
from .vulnerability import VulnerabilityScanner, scan_dependencies

__all__ = [
    "SecurityHeadersMiddleware",
    "security_headers_config",
    "APIKeyManager",
    "rotate_api_key",
    "AuditLogger",
    "audit_log",
    "SecretsManager",
    "SecretRotator",
    "VulnerabilityScanner",
    "scan_dependencies",
]