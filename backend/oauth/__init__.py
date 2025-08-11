"""
OAuth2 implementation for AgencyDark.
Provides multi-tenant OAuth2 authorization server and client capabilities.
"""

from .models import (
    OAuthClient,
    OAuthToken,
    OAuthAuthorizationCode,
    ExternalOAuthToken,
    OAuthConsentRecord
)

from .provider import (
    oauth_provider,
    create_authorization_server,
    create_resource_protector,
    get_current_oauth_token,
    get_current_oauth_user
)

from .compatibility import (
    DualAuthBearer,
    OAuthToJWTAdapter,
    UnifiedAuthDependency,
    get_current_user,
    get_optional_user,
    MigrationUtilities,
    CurrentUser,
    OptionalUser
)

__all__ = [
    # Models
    'OAuthClient',
    'OAuthToken', 
    'OAuthAuthorizationCode',
    'ExternalOAuthToken',
    'OAuthConsentRecord',
    
    # Provider
    'oauth_provider',
    'create_authorization_server',
    'create_resource_protector',
    'get_current_oauth_token',
    'get_current_oauth_user',
    
    # Compatibility
    'DualAuthBearer',
    'OAuthToJWTAdapter',
    'UnifiedAuthDependency',
    'get_current_user',
    'get_optional_user',
    'MigrationUtilities',
    'CurrentUser',
    'OptionalUser'
]