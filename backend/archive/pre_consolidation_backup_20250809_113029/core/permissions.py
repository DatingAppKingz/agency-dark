"""Permission checking utilities."""

from typing import Optional
from models.user import User, UserRole


def check_permission(
    user: User,
    permission: str,
    resource: Optional[str] = None
) -> bool:
    """Check if user has a specific permission."""
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Map permissions to roles
    permission_map = {
        "manage_api_keys": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        "view_analytics": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_STAFF],
        "manage_models": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        "view_reports": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_STAFF],
        "manage_users": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        "manage_experiments": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        "manage_performance": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        "manage_partitions": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
    }
    
    allowed_roles = permission_map.get(permission, [])
    return user.role in allowed_roles


def check_agency_permission(
    user: User,
    agency_id: str,
    permission: str
) -> bool:
    """Check if user has permission for a specific agency."""
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Check if user belongs to the agency
    if str(user.agency_id) != str(agency_id):
        return False
    
    # Check permission
    return check_permission(user, permission)