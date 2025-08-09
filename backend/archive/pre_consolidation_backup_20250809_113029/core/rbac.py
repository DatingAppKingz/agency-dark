"""
Role-Based Access Control (RBAC) utilities.
"""
from fastapi import HTTPException, status
from models.user import User, UserRole


def check_permission(user: User, resource: str, action: str) -> None:
    """
    Check if user has permission to perform action on resource.
    
    Args:
        user: Current user
        resource: Resource name (e.g., "webhooks", "users", "agencies")
        action: Action name (e.g., "read", "write", "delete", "admin")
        
    Raises:
        HTTPException: If user doesn't have permission
    """
    # Super admin can do everything
    if user.role == UserRole.SUPER_ADMIN:
        return
    
    # Admin can do most things
    if user.role == UserRole.ADMIN:
        # Admins can't do certain super admin only actions
        if resource == "system" and action == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can perform system administration"
            )
        return
    
    # Agency owner permissions
    if user.role == UserRole.AGENCY_OWNER:
        # Can manage their own agency
        if resource in ["agencies", "models", "users", "webhooks", "api_keys"]:
            return
        # Can't do system-wide operations
        if action == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for admin actions"
            )
    
    # Agency member permissions
    if user.role == UserRole.MEMBER:
        # Can read most things but limited write
        if action == "read":
            return
        # Can write to certain resources
        if action == "write" and resource in ["chats", "content"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Model permissions
    if user.role == UserRole.MODEL:
        # Can manage their own content and chats
        if resource in ["chats", "content", "analytics"] and action in ["read", "write"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Models can only access their own data"
        )
    
    # Chatter permissions
    if user.role == UserRole.CHATTER:
        # Can only manage chats
        if resource == "chats" and action in ["read", "write"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chatters can only access chat functionality"
        )
    
    # Default deny
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied"
    )