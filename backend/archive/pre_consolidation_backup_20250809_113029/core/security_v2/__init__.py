"""
Security module v2 - Clean architecture implementation.
This module provides all security features with proper structure and no circular dependencies.
"""

__version__ = '2.0.0'

from .config import security_config, is_feature_enabled

from .authentication import (
    # Password handling
    hash_password,
    verify_password,
    validate_password,
    generate_secure_password,
    password_handler,
    
    # JWT handling
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_token,
    get_current_user_id,
    refresh_access_token,
    jwt_handler,
    
    # Session management
    session_manager,
    init_session_manager
)

from .authorization import (
    # RBAC
    Permission,
    Role,
    RoleDefinition,
    RBACManager,
    rbac_manager,
    has_permission,
    get_role_permissions,
    validate_role,
    check_multiple_permissions,
    
    # Decorators and dependencies
    PermissionChecker,
    require_permission,
    require_role,
    get_current_user,
    get_current_user_optional,
    RequireSuperAdmin,
    RequireAgencyOwner,
    RequireAgencyAdmin,
    RequireAuthenticated,
    security
)

__all__ = [
    '__version__',
    
    # Config
    'security_config',
    'is_feature_enabled',
    
    # Authentication
    'hash_password',
    'verify_password',
    'validate_password',
    'generate_secure_password',
    'password_handler',
    'create_access_token',
    'create_refresh_token',
    'create_token_pair',
    'decode_token',
    'verify_token',
    'get_current_user_id',
    'refresh_access_token',
    'jwt_handler',
    'session_manager',
    'init_session_manager',
    
    # Authorization
    'Permission',
    'Role',
    'RoleDefinition',
    'RBACManager',
    'rbac_manager',
    'has_permission',
    'get_role_permissions',
    'validate_role',
    'check_multiple_permissions',
    'PermissionChecker',
    'require_permission',
    'require_role',
    'get_current_user',
    'get_current_user_optional',
    'RequireSuperAdmin',
    'RequireAgencyOwner',
    'RequireAgencyAdmin',
    'RequireAuthenticated',
    'security'
]