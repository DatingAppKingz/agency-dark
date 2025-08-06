"""
Migration layer for transitioning from old security to security_v2.
Provides compatibility adapters and migration utilities.
"""

from .auth_adapter import (
    AuthAdapter,
    get_auth_adapter,
    migrate_user_authentication,
    create_compatible_token
)

from .permission_mapper import (
    PermissionMapper,
    map_old_permission_to_new,
    map_old_role_to_new,
    get_permission_mapper
)

__all__ = [
    'AuthAdapter',
    'get_auth_adapter',
    'migrate_user_authentication',
    'create_compatible_token',
    'PermissionMapper',
    'map_old_permission_to_new',
    'map_old_role_to_new',
    'get_permission_mapper'
]