"""
OAuth2 configuration and settings for AgencyDark.
Centralizes all OAuth-related configuration parameters.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, Field
from datetime import timedelta
import os


class OAuthConfig(BaseSettings):
    """
    OAuth2 configuration settings.
    Can be overridden via environment variables.
    """
    
    # Token Lifetimes (in seconds)
    ACCESS_TOKEN_LIFETIME: int = Field(
        default=3600,  # 1 hour
        env="OAUTH_ACCESS_TOKEN_LIFETIME",
        description="Access token lifetime in seconds"
    )
    
    REFRESH_TOKEN_LIFETIME: int = Field(
        default=1209600,  # 14 days
        env="OAUTH_REFRESH_TOKEN_LIFETIME",
        description="Refresh token lifetime in seconds"
    )
    
    AUTHORIZATION_CODE_LIFETIME: int = Field(
        default=600,  # 10 minutes
        env="OAUTH_AUTHORIZATION_CODE_LIFETIME",
        description="Authorization code lifetime in seconds"
    )
    
    # PKCE Settings
    REQUIRE_PKCE: bool = Field(
        default=True,
        env="OAUTH_REQUIRE_PKCE",
        description="Require PKCE for authorization code flow"
    )
    
    PKCE_METHODS_SUPPORTED: List[str] = Field(
        default=["S256", "plain"],
        description="Supported PKCE challenge methods"
    )
    
    # OAuth2 Server Configuration
    ISSUER: str = Field(
        default="https://api.agencydark.com",
        env="OAUTH_ISSUER",
        description="OAuth2 issuer URL"
    )
    
    AUTHORIZATION_ENDPOINT: str = Field(
        default="/oauth/authorize",
        description="OAuth2 authorization endpoint"
    )
    
    TOKEN_ENDPOINT: str = Field(
        default="/oauth/token",
        description="OAuth2 token endpoint"
    )
    
    INTROSPECTION_ENDPOINT: str = Field(
        default="/oauth/introspect",
        description="OAuth2 token introspection endpoint"
    )
    
    REVOCATION_ENDPOINT: str = Field(
        default="/oauth/revoke",
        description="OAuth2 token revocation endpoint"
    )
    
    USERINFO_ENDPOINT: str = Field(
        default="/oauth/userinfo",
        description="OpenID Connect userinfo endpoint"
    )
    
    # Supported OAuth2 Features
    SUPPORTED_GRANT_TYPES: List[str] = Field(
        default=[
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "password"  # For legacy support during migration
        ],
        description="Supported OAuth2 grant types"
    )
    
    SUPPORTED_RESPONSE_TYPES: List[str] = Field(
        default=[
            "code",
            "token",  # For implicit flow (discouraged)
            "id_token",  # For OpenID Connect
            "code id_token",  # Hybrid flow
        ],
        description="Supported OAuth2 response types"
    )
    
    SUPPORTED_RESPONSE_MODES: List[str] = Field(
        default=[
            "query",
            "fragment",
            "form_post"
        ],
        description="Supported OAuth2 response modes"
    )
    
    # Scopes Configuration
    SUPPORTED_SCOPES: Dict[str, str] = Field(
        default={
            # Basic scopes
            "read": "Read access to resources",
            "write": "Write access to resources",
            "delete": "Delete access to resources",
            
            # User scopes
            "profile": "Access to user profile information",
            "email": "Access to user email address",
            "phone": "Access to user phone number",
            
            # Agency scopes
            "agency:read": "Read agency information",
            "agency:write": "Modify agency settings",
            "agency:admin": "Full agency administration",
            
            # Content creator scopes
            "creator:read": "Read creator profiles",
            "creator:write": "Modify creator profiles",
            "creator:messages": "Access creator messages",
            "creator:analytics": "View creator analytics",
            
            # Chat scopes
            "chat:read": "Read chat messages",
            "chat:write": "Send chat messages",
            "chat:moderate": "Moderate chat content",
            
            # Financial scopes
            "billing:read": "View billing information",
            "billing:write": "Modify billing settings",
            "transactions:read": "View transaction history",
            
            # Admin scopes
            "admin:users": "Manage users",
            "admin:agencies": "Manage agencies",
            "admin:system": "System administration",
            
            # OpenID Connect scopes
            "openid": "OpenID Connect authentication",
            "offline_access": "Offline access (refresh tokens)",
        },
        description="Supported OAuth2 scopes and their descriptions"
    )
    
    DEFAULT_SCOPES: List[str] = Field(
        default=["read", "profile", "email"],
        description="Default scopes for new clients"
    )
    
    # Security Settings
    TOKEN_ENDPOINT_AUTH_METHODS: List[str] = Field(
        default=[
            "client_secret_basic",
            "client_secret_post",
            "client_secret_jwt",
            "private_key_jwt",
            "none"  # For public clients with PKCE
        ],
        description="Supported client authentication methods"
    )
    
    ALLOW_PUBLIC_CLIENTS: bool = Field(
        default=True,
        env="OAUTH_ALLOW_PUBLIC_CLIENTS",
        description="Allow public clients (mobile apps, SPAs)"
    )
    
    REQUIRE_CONSENT: bool = Field(
        default=True,
        env="OAUTH_REQUIRE_CONSENT",
        description="Require user consent for authorization"
    )
    
    CONSENT_VALIDITY_DAYS: int = Field(
        default=365,
        env="OAUTH_CONSENT_VALIDITY_DAYS",
        description="How long user consent is valid (days)"
    )
    
    # Rate Limiting
    MAX_FAILED_ATTEMPTS: int = Field(
        default=5,
        env="OAUTH_MAX_FAILED_ATTEMPTS",
        description="Max failed authentication attempts before lockout"
    )
    
    LOCKOUT_DURATION_MINUTES: int = Field(
        default=30,
        env="OAUTH_LOCKOUT_DURATION_MINUTES",
        description="Account lockout duration in minutes"
    )
    
    # Token Settings
    TOKEN_SIGNING_ALGORITHM: str = Field(
        default="RS256",
        env="OAUTH_TOKEN_SIGNING_ALGORITHM",
        description="Algorithm for signing tokens"
    )
    
    USE_JWT_TOKENS: bool = Field(
        default=False,
        env="OAUTH_USE_JWT_TOKENS",
        description="Use JWT format for access tokens"
    )
    
    # Session Settings
    SESSION_COOKIE_NAME: str = Field(
        default="oauth_session",
        description="Name of the OAuth session cookie"
    )
    
    SESSION_COOKIE_SECURE: bool = Field(
        default=True,
        env="OAUTH_SESSION_COOKIE_SECURE",
        description="Use secure flag for session cookies"
    )
    
    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="Use HttpOnly flag for session cookies"
    )
    
    SESSION_COOKIE_SAMESITE: str = Field(
        default="lax",
        description="SameSite attribute for session cookies"
    )
    
    # Multi-Tenant Settings
    ENABLE_CROSS_AGENCY_ACCESS: bool = Field(
        default=False,
        env="OAUTH_ENABLE_CROSS_AGENCY_ACCESS",
        description="Allow OAuth clients to access multiple agencies"
    )
    
    AGENCY_ISOLATION_STRICT: bool = Field(
        default=True,
        env="OAUTH_AGENCY_ISOLATION_STRICT",
        description="Enforce strict agency isolation"
    )
    
    # External OAuth Providers
    EXTERNAL_PROVIDERS_ENABLED: List[str] = Field(
        default=["google", "instagram"],
        env="OAUTH_EXTERNAL_PROVIDERS_ENABLED",
        description="Enabled external OAuth providers"
    )
    
    # Development Settings
    ALLOW_INSECURE_HTTP: bool = Field(
        default=False,
        env="OAUTH_ALLOW_INSECURE_HTTP",
        description="Allow HTTP in redirect URIs (development only)"
    )
    
    DEBUG_MODE: bool = Field(
        default=False,
        env="OAUTH_DEBUG_MODE",
        description="Enable OAuth debug logging"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def get_token_expiry_timedelta(self, token_type: str) -> timedelta:
        """Get token expiry as timedelta object."""
        if token_type == "access":
            return timedelta(seconds=self.ACCESS_TOKEN_LIFETIME)
        elif token_type == "refresh":
            return timedelta(seconds=self.REFRESH_TOKEN_LIFETIME)
        elif token_type == "authorization_code":
            return timedelta(seconds=self.AUTHORIZATION_CODE_LIFETIME)
        else:
            raise ValueError(f"Unknown token type: {token_type}")
    
    def get_scope_description(self, scope: str) -> str:
        """Get human-readable description for a scope."""
        return self.SUPPORTED_SCOPES.get(scope, f"Unknown scope: {scope}")
    
    def validate_scopes(self, scopes: List[str]) -> List[str]:
        """Validate and filter scopes to only supported ones."""
        supported = set(self.SUPPORTED_SCOPES.keys())
        requested = set(scopes)
        return list(requested & supported)
    
    def is_grant_type_supported(self, grant_type: str) -> bool:
        """Check if a grant type is supported."""
        return grant_type in self.SUPPORTED_GRANT_TYPES
    
    def is_response_type_supported(self, response_type: str) -> bool:
        """Check if a response type is supported."""
        return response_type in self.SUPPORTED_RESPONSE_TYPES
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get OAuth2 server metadata for discovery endpoints.
        Follows RFC 8414 OAuth 2.0 Authorization Server Metadata.
        """
        return {
            "issuer": self.ISSUER,
            "authorization_endpoint": f"{self.ISSUER}{self.AUTHORIZATION_ENDPOINT}",
            "token_endpoint": f"{self.ISSUER}{self.TOKEN_ENDPOINT}",
            "introspection_endpoint": f"{self.ISSUER}{self.INTROSPECTION_ENDPOINT}",
            "revocation_endpoint": f"{self.ISSUER}{self.REVOCATION_ENDPOINT}",
            "userinfo_endpoint": f"{self.ISSUER}{self.USERINFO_ENDPOINT}",
            "jwks_uri": f"{self.ISSUER}/.well-known/jwks.json",
            "registration_endpoint": f"{self.ISSUER}/oauth/register",
            "scopes_supported": list(self.SUPPORTED_SCOPES.keys()),
            "response_types_supported": self.SUPPORTED_RESPONSE_TYPES,
            "response_modes_supported": self.SUPPORTED_RESPONSE_MODES,
            "grant_types_supported": self.SUPPORTED_GRANT_TYPES,
            "token_endpoint_auth_methods_supported": self.TOKEN_ENDPOINT_AUTH_METHODS,
            "code_challenge_methods_supported": self.PKCE_METHODS_SUPPORTED if self.REQUIRE_PKCE else [],
            "service_documentation": f"{self.ISSUER}/docs/oauth",
            "ui_locales_supported": ["en-US"],
            "claims_supported": [
                "sub", "iss", "aud", "exp", "iat", "jti",
                "email", "email_verified", "name", "picture",
                "agency_id", "role", "permissions"
            ],
            "request_parameter_supported": True,
            "request_uri_parameter_supported": False,
            "require_request_uri_registration": False,
            "claims_parameter_supported": False,
            "revocation_endpoint_auth_methods_supported": self.TOKEN_ENDPOINT_AUTH_METHODS,
            "introspection_endpoint_auth_methods_supported": self.TOKEN_ENDPOINT_AUTH_METHODS,
        }


# Singleton instance
oauth_config = OAuthConfig()


# Helper functions for easy access
def get_oauth_config() -> OAuthConfig:
    """Get OAuth configuration instance."""
    return oauth_config


def get_supported_scopes() -> Dict[str, str]:
    """Get supported OAuth scopes."""
    return oauth_config.SUPPORTED_SCOPES


def validate_redirect_uri(uri: str) -> bool:
    """
    Validate a redirect URI based on configuration.
    
    Args:
        uri: Redirect URI to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not uri:
        return False
    
    # Check for insecure HTTP
    if uri.startswith("http://") and not oauth_config.ALLOW_INSECURE_HTTP:
        # Allow localhost for development
        if not any(uri.startswith(f"http://{host}") for host in ["localhost", "127.0.0.1", "[::1]"]):
            return False
    
    # Additional validation can be added here
    return True


def get_token_lifetime(token_type: str) -> int:
    """
    Get token lifetime in seconds.
    
    Args:
        token_type: Type of token (access, refresh, authorization_code)
        
    Returns:
        Lifetime in seconds
    """
    if token_type == "access":
        return oauth_config.ACCESS_TOKEN_LIFETIME
    elif token_type == "refresh":
        return oauth_config.REFRESH_TOKEN_LIFETIME
    elif token_type == "authorization_code":
        return oauth_config.AUTHORIZATION_CODE_LIFETIME
    else:
        raise ValueError(f"Unknown token type: {token_type}")