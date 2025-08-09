"""
Authorization module.
Handles RBAC, permissions, and access control.
"""

from .rbac import (
    Permission,
    Role,
    RoleDefinition,
    RBACManager,
    rbac_manager,
    has_permission,
    get_role_permissions,
    validate_role,
    check_multiple_permissions
)

from .decorators import (
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
    # RBAC
    'Permission',
    'Role',
    'RoleDefinition',
    'RBACManager',
    'rbac_manager',
    'has_permission',
    'get_role_permissions',
    'validate_role',
    'check_multiple_permissions',
    
    # Decorators and dependencies
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