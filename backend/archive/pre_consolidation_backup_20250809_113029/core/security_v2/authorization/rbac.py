"""
Role-Based Access Control (RBAC) implementation.
Manages roles, permissions, and access control decisions.
"""
from typing import List, Optional, Dict, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from functools import lru_cache

from ..config import security_config

class Permission(str, Enum):
    """System permissions."""
    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # Model management
    MODEL_CREATE = "model:create"
    MODEL_READ = "model:read"
    MODEL_UPDATE = "model:update"
    MODEL_DELETE = "model:delete"
    MODEL_APPROVE = "model:approve"
    
    # Agency management
    AGENCY_CREATE = "agency:create"
    AGENCY_READ = "agency:read"
    AGENCY_UPDATE = "agency:update"
    AGENCY_DELETE = "agency:delete"
    AGENCY_MANAGE = "agency:manage"
    
    # Booking management
    BOOKING_CREATE = "booking:create"
    BOOKING_READ = "booking:read"
    BOOKING_UPDATE = "booking:update"
    BOOKING_DELETE = "booking:delete"
    BOOKING_APPROVE = "booking:approve"
    
    # Financial management
    FINANCIAL_VIEW = "financial:view"
    FINANCIAL_MANAGE = "financial:manage"
    FINANCIAL_EXPORT = "financial:export"
    
    # System administration
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"
    
    # API management
    API_KEY_CREATE = "api_key:create"
    API_KEY_READ = "api_key:read"
    API_KEY_DELETE = "api_key:delete"
    
    # Reports
    REPORT_VIEW = "report:view"
    REPORT_CREATE = "report:create"
    REPORT_EXPORT = "report:export"

class Role(str, Enum):
    """System roles."""
    SUPER_ADMIN = "super_admin"
    AGENCY_OWNER = "agency_owner"
    AGENCY_ADMIN = "agency_admin"
    AGENCY_USER = "agency_user"
    MODEL = "model"
    CLIENT = "client"
    VIEWER = "viewer"

@dataclass
class RoleDefinition:
    """Definition of a role with its permissions."""
    name: str
    display_name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    inherits_from: Optional[List[str]] = None

class RBACManager:
    """Manages role-based access control."""
    
    def __init__(self):
        """Initialize RBAC manager with role definitions."""
        self.enabled = security_config.ENABLE_RBAC
        self.roles = self._initialize_roles()
        self._permission_cache = {}
    
    def _initialize_roles(self) -> Dict[str, RoleDefinition]:
        """Initialize role definitions with permissions."""
        return {
            Role.SUPER_ADMIN: RoleDefinition(
                name=Role.SUPER_ADMIN,
                display_name="Super Administrator",
                description="Full system access",
                permissions={p for p in Permission}  # All permissions
            ),
            
            Role.AGENCY_OWNER: RoleDefinition(
                name=Role.AGENCY_OWNER,
                display_name="Agency Owner",
                description="Full control over agency and its resources",
                permissions={
                    # Agency management
                    Permission.AGENCY_READ,
                    Permission.AGENCY_UPDATE,
                    Permission.AGENCY_MANAGE,
                    
                    # User management (within agency)
                    Permission.USER_CREATE,
                    Permission.USER_READ,
                    Permission.USER_UPDATE,
                    Permission.USER_DELETE,
                    
                    # Model management
                    Permission.MODEL_CREATE,
                    Permission.MODEL_READ,
                    Permission.MODEL_UPDATE,
                    Permission.MODEL_DELETE,
                    Permission.MODEL_APPROVE,
                    
                    # Booking management
                    Permission.BOOKING_CREATE,
                    Permission.BOOKING_READ,
                    Permission.BOOKING_UPDATE,
                    Permission.BOOKING_DELETE,
                    Permission.BOOKING_APPROVE,
                    
                    # Financial access
                    Permission.FINANCIAL_VIEW,
                    Permission.FINANCIAL_MANAGE,
                    Permission.FINANCIAL_EXPORT,
                    
                    # API management
                    Permission.API_KEY_CREATE,
                    Permission.API_KEY_READ,
                    Permission.API_KEY_DELETE,
                    
                    # Reports
                    Permission.REPORT_VIEW,
                    Permission.REPORT_CREATE,
                    Permission.REPORT_EXPORT
                }
            ),
            
            Role.AGENCY_ADMIN: RoleDefinition(
                name=Role.AGENCY_ADMIN,
                display_name="Agency Administrator",
                description="Manage agency operations",
                permissions={
                    # Agency read
                    Permission.AGENCY_READ,
                    
                    # User management (limited)
                    Permission.USER_CREATE,
                    Permission.USER_READ,
                    Permission.USER_UPDATE,
                    
                    # Model management
                    Permission.MODEL_CREATE,
                    Permission.MODEL_READ,
                    Permission.MODEL_UPDATE,
                    Permission.MODEL_APPROVE,
                    
                    # Booking management
                    Permission.BOOKING_CREATE,
                    Permission.BOOKING_READ,
                    Permission.BOOKING_UPDATE,
                    Permission.BOOKING_APPROVE,
                    
                    # Financial view only
                    Permission.FINANCIAL_VIEW,
                    
                    # Reports
                    Permission.REPORT_VIEW,
                    Permission.REPORT_CREATE
                }
            ),
            
            Role.AGENCY_USER: RoleDefinition(
                name=Role.AGENCY_USER,
                display_name="Agency User",
                description="Basic agency staff member",
                permissions={
                    # Agency read
                    Permission.AGENCY_READ,
                    
                    # User read only
                    Permission.USER_READ,
                    
                    # Model read/update
                    Permission.MODEL_READ,
                    Permission.MODEL_UPDATE,
                    
                    # Booking management
                    Permission.BOOKING_CREATE,
                    Permission.BOOKING_READ,
                    Permission.BOOKING_UPDATE,
                    
                    # Reports view
                    Permission.REPORT_VIEW
                }
            ),
            
            Role.MODEL: RoleDefinition(
                name=Role.MODEL,
                display_name="Model",
                description="Agency model with limited access",
                permissions={
                    # Self read/update
                    Permission.USER_READ,
                    Permission.USER_UPDATE,
                    
                    # Model profile
                    Permission.MODEL_READ,
                    
                    # Booking view
                    Permission.BOOKING_READ,
                    
                    # Financial view (own)
                    Permission.FINANCIAL_VIEW
                }
            ),
            
            Role.CLIENT: RoleDefinition(
                name=Role.CLIENT,
                display_name="Client",
                description="External client with booking access",
                permissions={
                    # Model browsing
                    Permission.MODEL_READ,
                    
                    # Booking creation
                    Permission.BOOKING_CREATE,
                    Permission.BOOKING_READ,
                    Permission.BOOKING_UPDATE
                }
            ),
            
            Role.VIEWER: RoleDefinition(
                name=Role.VIEWER,
                display_name="Viewer",
                description="Read-only access",
                permissions={
                    Permission.USER_READ,
                    Permission.MODEL_READ,
                    Permission.BOOKING_READ,
                    Permission.REPORT_VIEW
                }
            )
        }
    
    def has_permission(
        self, 
        user_role: str, 
        permission: Permission,
        resource_owner_id: Optional[int] = None,
        user_id: Optional[int] = None,
        agency_id: Optional[int] = None,
        user_agency_id: Optional[int] = None
    ) -> bool:
        """
        Check if a role has a specific permission.
        
        Args:
            user_role: User's role
            permission: Permission to check
            resource_owner_id: ID of resource owner (for ownership checks)
            user_id: Current user's ID
            agency_id: Resource's agency ID
            user_agency_id: User's agency ID
            
        Returns:
            True if permission is granted
        """
        if not self.enabled:
            return True  # RBAC disabled, allow all
        
        # Super admin always has access
        if user_role == Role.SUPER_ADMIN:
            return True
        
        # Get role definition
        role_def = self.roles.get(user_role)
        if not role_def:
            return False
        
        # Check base permission
        if permission not in role_def.permissions:
            return False
        
        # Additional checks for agency-scoped resources
        if user_role in [Role.AGENCY_OWNER, Role.AGENCY_ADMIN, Role.AGENCY_USER]:
            # Check agency scope
            if agency_id and user_agency_id and agency_id != user_agency_id:
                return False  # Different agency, no access
        
        # Ownership checks for models
        if user_role == Role.MODEL:
            # Models can only update their own profile
            if permission == Permission.USER_UPDATE:
                if resource_owner_id and user_id and resource_owner_id != user_id:
                    return False
        
        return True
    
    @lru_cache(maxsize=128)
    def get_role_permissions(self, role: str) -> Set[Permission]:
        """
        Get all permissions for a role (cached).
        
        Args:
            role: Role name
            
        Returns:
            Set of permissions
        """
        role_def = self.roles.get(role)
        if not role_def:
            return set()
        
        permissions = role_def.permissions.copy()
        
        # Handle inheritance if defined
        if role_def.inherits_from:
            for parent_role in role_def.inherits_from:
                parent_perms = self.get_role_permissions(parent_role)
                permissions.update(parent_perms)
        
        return permissions
    
    def get_role_display_name(self, role: str) -> str:
        """Get display name for a role."""
        role_def = self.roles.get(role)
        return role_def.display_name if role_def else role
    
    def get_role_description(self, role: str) -> str:
        """Get description for a role."""
        role_def = self.roles.get(role)
        return role_def.description if role_def else ""
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """List all available roles."""
        return [
            {
                "name": role_def.name,
                "display_name": role_def.display_name,
                "description": role_def.description,
                "permissions": [p.value for p in role_def.permissions]
            }
            for role_def in self.roles.values()
        ]
    
    def validate_role(self, role: str) -> bool:
        """Check if a role is valid."""
        return role in self.roles
    
    def check_multiple_permissions(
        self,
        user_role: str,
        permissions: List[Permission],
        require_all: bool = True,
        **kwargs
    ) -> bool:
        """
        Check multiple permissions at once.
        
        Args:
            user_role: User's role
            permissions: List of permissions to check
            require_all: If True, all permissions required. If False, any permission sufficient
            **kwargs: Additional context (user_id, agency_id, etc.)
            
        Returns:
            True if permission check passes
        """
        if not permissions:
            return True
        
        results = [
            self.has_permission(user_role, perm, **kwargs)
            for perm in permissions
        ]
        
        if require_all:
            return all(results)
        else:
            return any(results)

# Create singleton instance
rbac_manager = RBACManager()

# Export convenience functions
has_permission = rbac_manager.has_permission
get_role_permissions = rbac_manager.get_role_permissions
validate_role = rbac_manager.validate_role
check_multiple_permissions = rbac_manager.check_multiple_permissions