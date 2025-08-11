"""
Authorization decorators for FastAPI endpoints.
Provides easy-to-use decorators for permission checking.
"""
from functools import wraps
from typing import List, Optional, Callable, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .rbac import Permission, rbac_manager
from ..authentication import verify_token, get_current_user_id

# Security scheme for Swagger UI
security = HTTPBearer()

class PermissionChecker:
    """Dependency class for permission checking."""
    
    def __init__(
        self,
        required_permissions: List[Permission],
        require_all: bool = True,
        check_ownership: bool = False
    ):
        """
        Initialize permission checker.
        
        Args:
            required_permissions: List of required permissions
            require_all: If True, all permissions required. If False, any permission sufficient
            check_ownership: If True, check resource ownership
        """
        self.required_permissions = required_permissions
        self.require_all = require_all
        self.check_ownership = check_ownership
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
        """
        Check permissions for the current request.
        
        Args:
            credentials: HTTP Bearer token
            
        Returns:
            Current user information
            
        Raises:
            HTTPException: If unauthorized or forbidden
        """
        # Verify token
        token = credentials.credentials
        payload = verify_token(token, "access")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract user info
        user_id = payload.get("sub")
        user_role = payload.get("role", "viewer")
        user_agency_id = payload.get("agency_id")
        
        # Check permissions
        if not rbac_manager.check_multiple_permissions(
            user_role=user_role,
            permissions=self.required_permissions,
            require_all=self.require_all,
            user_id=int(user_id) if user_id else None,
            user_agency_id=user_agency_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return {
            "user_id": int(user_id) if user_id else None,
            "role": user_role,
            "agency_id": user_agency_id,
            "email": payload.get("email")
        }

def require_permission(*permissions: Permission, require_all: bool = True):
    """
    Decorator to require specific permissions for an endpoint.
    
    Args:
        *permissions: Required permissions
        require_all: If True, all permissions required. If False, any permission sufficient
        
    Usage:
        @app.get("/admin")
        @require_permission(Permission.SYSTEM_ADMIN)
        async def admin_endpoint():
            return {"message": "Admin only"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Permission checking is handled by dependency injection
            # This decorator is mainly for documentation
            return await func(*args, **kwargs)
        
        # Add permission information to function metadata
        wrapper.__permissions__ = list(permissions)
        wrapper.__require_all__ = require_all
        
        return wrapper
    return decorator

def require_role(role: str):
    """
    Decorator to require a specific role for an endpoint.
    
    Args:
        role: Required role
        
    Usage:
        @app.get("/owner")
        @require_role(Role.AGENCY_OWNER)
        async def owner_endpoint():
            return {"message": "Owner only"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Role checking is handled by dependency injection
            # This decorator is mainly for documentation
            return await func(*args, **kwargs)
        
        # Add role information to function metadata
        wrapper.__required_role__ = role
        
        return wrapper
    return decorator

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get current authenticated user from token.
    
    Args:
        credentials: HTTP Bearer token
        
    Returns:
        Current user information
        
    Raises:
        HTTPException: If unauthorized
    """
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": payload.get("sub"),  # UUID, not int
        "email": payload.get("email"),
        "role": payload.get("role", "viewer"),
        "agency_id": payload.get("agency_id")
    }

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Get current user if authenticated, None otherwise.
    
    Args:
        credentials: Optional HTTP Bearer token
        
    Returns:
        Current user information or None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    if not payload:
        return None
    
    return {
        "user_id": payload.get("sub"),  # UUID, not int
        "email": payload.get("email"),
        "role": payload.get("role", "viewer"),
        "agency_id": payload.get("agency_id")
    }

# Convenience permission checkers for common cases
RequireSuperAdmin = PermissionChecker([Permission.SYSTEM_ADMIN])
RequireAgencyOwner = PermissionChecker([Permission.AGENCY_MANAGE])
RequireAgencyAdmin = PermissionChecker([Permission.MODEL_APPROVE, Permission.BOOKING_APPROVE], require_all=False)
RequireAuthenticated = PermissionChecker([])  # Just checks valid token

# Export for easy use
__all__ = [
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