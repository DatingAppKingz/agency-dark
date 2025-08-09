"""
Centralized security configuration.
All security-related settings in one place.
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class SecurityConfig(BaseSettings):
    """Security configuration with feature flags."""
    
    # Feature Flags (can be toggled without code changes)
    ENABLE_RBAC: bool = True
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_AUDIT_LOGGING: bool = True
    ENABLE_API_KEYS: bool = True
    ENABLE_MFA: bool = False
    ENABLE_SESSION_MANAGEMENT: bool = True
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_HASH_SCHEME: str = "bcrypt"
    PASSWORD_BCRYPT_ROUNDS: int = 12
    
    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_ALGORITHM: str = "token_bucket"  # token_bucket, sliding_window, fixed_window, adaptive
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_PER_DAY: int = 10000
    RATE_LIMIT_BURST_SIZE: int = 10
    
    # Audit Configuration
    AUDIT_LOG_LEVEL: str = "INFO"
    AUDIT_RETENTION_DAYS: int = 2555  # 7 years for SOX compliance
    AUDIT_ENABLE_HASH_CHAIN: bool = True
    AUDIT_BATCH_SIZE: int = 100
    AUDIT_ASYNC_WRITE: bool = True
    
    # API Key Configuration
    API_KEY_PREFIX: str = "sk_"
    API_KEY_LENGTH: int = 32
    API_KEY_ROTATION_DAYS: int = 90
    API_KEY_MAX_PER_USER: int = 5
    
    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 60
    SESSION_SLIDING_WINDOW: bool = True
    SESSION_MAX_CONCURRENT: int = 3
    
    # Security Headers
    SECURITY_HEADERS_ENABLED: bool = True
    HSTS_MAX_AGE: int = 31536000  # 1 year
    CSP_ENABLED: bool = True
    CORS_ENABLED: bool = True
    CORS_ALLOWED_ORIGINS: list = ["http://localhost:3000"]
    
    # Geographic Restrictions
    GEO_BLOCKING_ENABLED: bool = False
    BLOCKED_COUNTRIES: list = []
    ALLOWED_COUNTRIES: list = []
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env file

# Create global instance
security_config = SecurityConfig()

def is_feature_enabled(feature: str) -> bool:
    """Check if a security feature is enabled."""
    feature_map = {
        "rbac": security_config.ENABLE_RBAC,
        "rate_limiting": security_config.ENABLE_RATE_LIMITING,
        "audit": security_config.ENABLE_AUDIT_LOGGING,
        "api_keys": security_config.ENABLE_API_KEYS,
        "mfa": security_config.ENABLE_MFA,
        "sessions": security_config.ENABLE_SESSION_MANAGEMENT,
    }
    return feature_map.get(feature.lower(), False)