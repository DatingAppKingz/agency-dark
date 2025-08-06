"""
Permission mapper for migrating from old to new permission system.
Maps old permission strings and roles to new RBAC system.
"""
from typing import Optional, List, Set, Dict, Any
import logging

from ..authorization import Permission, Role, rbac_manager

logger = logging.getLogger(__name__)

class PermissionMapper:
    """
    Maps old permission system to new RBAC system.
    Provides compatibility during migration.
    """
    
    def __init__(self):
        """Initialize permission mapper."""
        self.rbac_manager = rbac_manager
        self._init_permission_mappings()
        self._init_role_mappings()
    
    def _init_permission_mappings(self):
        """Initialize mappings from old permission strings to new Permission enum."""
        self.permission_map = {
            # User permissions
            'users:create': Permission.USER_CREATE,
            'users:read': Permission.USER_READ,
            'users:update': Permission.USER_UPDATE,
            'users:delete': Permission.USER_DELETE,
            'user:create': Permission.USER_CREATE,
            'user:read': Permission.USER_READ,
            'user:update': Permission.USER_UPDATE,
            'user:delete': Permission.USER_DELETE,
            
            # Model permissions
            'models:create': Permission.MODEL_CREATE,
            'models:read': Permission.MODEL_READ,
            'models:update': Permission.MODEL_UPDATE,
            'models:delete': Permission.MODEL_DELETE,
            'models:approve': Permission.MODEL_APPROVE,
            'model:create': Permission.MODEL_CREATE,
            'model:read': Permission.MODEL_READ,
            'model:update': Permission.MODEL_UPDATE,
            'model:delete': Permission.MODEL_DELETE,
            'model:approve': Permission.MODEL_APPROVE,
            
            # Agency permissions
            'agency:create': Permission.AGENCY_CREATE,
            'agency:read': Permission.AGENCY_READ,
            'agency:update': Permission.AGENCY_UPDATE,
            'agency:delete': Permission.AGENCY_DELETE,
            'agency:manage': Permission.AGENCY_MANAGE,
            'agencies:create': Permission.AGENCY_CREATE,
            'agencies:read': Permission.AGENCY_READ,
            'agencies:update': Permission.AGENCY_UPDATE,
            'agencies:delete': Permission.AGENCY_DELETE,
            'agencies:manage': Permission.AGENCY_MANAGE,
            
            # Booking permissions
            'booking:create': Permission.BOOKING_CREATE,
            'booking:read': Permission.BOOKING_READ,
            'booking:update': Permission.BOOKING_UPDATE,
            'booking:delete': Permission.BOOKING_DELETE,
            'booking:approve': Permission.BOOKING_APPROVE,
            'bookings:create': Permission.BOOKING_CREATE,
            'bookings:read': Permission.BOOKING_READ,
            'bookings:update': Permission.BOOKING_UPDATE,
            'bookings:delete': Permission.BOOKING_DELETE,
            'bookings:approve': Permission.BOOKING_APPROVE,
            
            # Financial permissions
            'financial:view': Permission.FINANCIAL_VIEW,
            'financial:manage': Permission.FINANCIAL_MANAGE,
            'financial:export': Permission.FINANCIAL_EXPORT,
            'finance:view': Permission.FINANCIAL_VIEW,
            'finance:manage': Permission.FINANCIAL_MANAGE,
            'finance:export': Permission.FINANCIAL_EXPORT,
            
            # System permissions
            'system:admin': Permission.SYSTEM_ADMIN,
            'system:config': Permission.SYSTEM_CONFIG,
            'system:audit': Permission.SYSTEM_AUDIT,
            'admin:all': Permission.SYSTEM_ADMIN,
            
            # API permissions
            'api_key:create': Permission.API_KEY_CREATE,
            'api_key:read': Permission.API_KEY_READ,
            'api_key:delete': Permission.API_KEY_DELETE,
            'api:create': Permission.API_KEY_CREATE,
            'api:read': Permission.API_KEY_READ,
            'api:delete': Permission.API_KEY_DELETE,
            
            # Report permissions
            'report:view': Permission.REPORT_VIEW,
            'report:create': Permission.REPORT_CREATE,
            'report:export': Permission.REPORT_EXPORT,
            'reports:view': Permission.REPORT_VIEW,
            'reports:create': Permission.REPORT_CREATE,
            'reports:export': Permission.REPORT_EXPORT,
            
            # Legacy/alternative names
            'read': Permission.USER_READ,
            'write': Permission.USER_UPDATE,
            'delete': Permission.USER_DELETE,
            'admin': Permission.SYSTEM_ADMIN,
            'manage': Permission.AGENCY_MANAGE,
            'view': Permission.USER_READ,
            'edit': Permission.USER_UPDATE,
            'create': Permission.USER_CREATE
        }
    
    def _init_role_mappings(self):
        """Initialize mappings from old role names to new Role enum."""
        self.role_map = {
            # Direct mappings
            'super_admin': Role.SUPER_ADMIN,
            'agency_owner': Role.AGENCY_OWNER,
            'agency_admin': Role.AGENCY_ADMIN,
            'agency_user': Role.AGENCY_USER,
            'model': Role.MODEL,
            'client': Role.CLIENT,
            'viewer': Role.VIEWER,
            
            # Alternative names
            'superadmin': Role.SUPER_ADMIN,
            'super-admin': Role.SUPER_ADMIN,
            'admin': Role.AGENCY_ADMIN,
            'owner': Role.AGENCY_OWNER,
            'user': Role.AGENCY_USER,
            'staff': Role.AGENCY_USER,
            'employee': Role.AGENCY_USER,
            'agent': Role.AGENCY_USER,
            'talent': Role.MODEL,
            'customer': Role.CLIENT,
            'guest': Role.VIEWER,
            'readonly': Role.VIEWER,
            'read-only': Role.VIEWER,
            
            # Default
            'default': Role.VIEWER,
            'unknown': Role.VIEWER
        }
    
    def map_permission(self, old_permission: str) -> Optional[Permission]:
        """
        Map old permission string to new Permission enum.
        
        Args:
            old_permission: Old permission string
            
        Returns:
            New Permission enum value or None
        """
        if not old_permission:
            return None
        
        # Normalize the permission string
        normalized = old_permission.lower().strip()
        
        # Direct lookup
        if normalized in self.permission_map:
            return self.permission_map[normalized]
        
        # Try with different separators
        for sep in [':', '_', '-', '.']:
            if sep in normalized:
                alt_format = normalized.replace(sep, ':')
                if alt_format in self.permission_map:
                    return self.permission_map[alt_format]
        
        logger.warning(f"Unknown permission: {old_permission}")
        return None
    
    def map_role(self, old_role: str) -> Role:
        """
        Map old role name to new Role enum.
        
        Args:
            old_role: Old role name
            
        Returns:
            New Role enum value
        """
        if not old_role:
            return Role.VIEWER
        
        # Normalize the role string
        normalized = old_role.lower().strip()
        
        # Direct lookup
        if normalized in self.role_map:
            return self.role_map[normalized]
        
        # Try with different formats
        normalized_underscore = normalized.replace('-', '_').replace(' ', '_')
        if normalized_underscore in self.role_map:
            return self.role_map[normalized_underscore]
        
        logger.warning(f"Unknown role: {old_role}, defaulting to VIEWER")
        return Role.VIEWER
    
    def map_permissions_list(self, old_permissions: List[str]) -> Set[Permission]:
        """
        Map a list of old permissions to new Permission set.
        
        Args:
            old_permissions: List of old permission strings
            
        Returns:
            Set of new Permission enum values
        """
        new_permissions = set()
        
        for old_perm in old_permissions:
            new_perm = self.map_permission(old_perm)
            if new_perm:
                new_permissions.add(new_perm)
        
        return new_permissions
    
    def check_legacy_permission(
        self,
        user_role: str,
        required_permission: str,
        **kwargs
    ) -> bool:
        """
        Check permission using old permission string.
        
        Args:
            user_role: User's role (old or new format)
            required_permission: Required permission (old format)
            **kwargs: Additional context
            
        Returns:
            True if permission is granted
        """
        # Map old formats to new
        new_role = self.map_role(user_role)
        new_permission = self.map_permission(required_permission)
        
        if not new_permission:
            # Unknown permission, deny by default
            return False
        
        # Check using new RBAC system
        return self.rbac_manager.has_permission(
            user_role=new_role,
            permission=new_permission,
            **kwargs
        )
    
    def get_role_permissions_legacy(self, old_role: str) -> List[str]:
        """
        Get permissions for a role in old string format.
        
        Args:
            old_role: Old role name
            
        Returns:
            List of permission strings (old format)
        """
        # Map to new role
        new_role = self.map_role(old_role)
        
        # Get new permissions
        new_permissions = self.rbac_manager.get_role_permissions(new_role)
        
        # Convert back to old format (for backward compatibility)
        old_permissions = []
        for perm in new_permissions:
            # Use the enum value which is already in the format "resource:action"
            old_permissions.append(perm.value)
        
        return old_permissions
    
    def migrate_user_permissions(
        self,
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Migrate user data with old permissions to new format.
        
        Args:
            user_data: User data with old permission format
            
        Returns:
            User data with new permission format
        """
        migrated = user_data.copy()
        
        # Migrate role
        if 'role' in migrated:
            migrated['role'] = self.map_role(migrated['role'])
        
        # Migrate custom permissions if present
        if 'permissions' in migrated:
            old_perms = migrated['permissions']
            if isinstance(old_perms, list):
                new_perms = self.map_permissions_list(old_perms)
                migrated['permissions'] = [p.value for p in new_perms]
        
        return migrated

# Singleton instance
permission_mapper = PermissionMapper()

# Export convenience functions
def get_permission_mapper() -> PermissionMapper:
    """Get the permission mapper instance."""
    return permission_mapper

def map_old_permission_to_new(old_permission: str) -> Optional[Permission]:
    """
    Map old permission string to new Permission enum.
    
    Args:
        old_permission: Old permission string
        
    Returns:
        New Permission enum value or None
    """
    return permission_mapper.map_permission(old_permission)

def map_old_role_to_new(old_role: str) -> Role:
    """
    Map old role name to new Role enum.
    
    Args:
        old_role: Old role name
        
    Returns:
        New Role enum value
    """
    return permission_mapper.map_role(old_role)