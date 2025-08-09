"""
Dependencies using security_v2 system.
Provides FastAPI dependencies for authentication and authorization.
"""

from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status

from core.database import get_db
from core.security_v2 import (
    get_current_user,
    get_current_user_optional,
    RequireAuthenticated,
    RequireSuperAdmin,
    RequireAgencyOwner,
    RequireAgencyAdmin,
    require_permission,
    require_role
)
from models.user import User


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return user


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]

# Role-based dependencies
SuperAdmin = Annotated[User, Depends(RequireSuperAdmin)]
AgencyOwner = Annotated[User, Depends(RequireAgencyOwner)]
AgencyAdmin = Annotated[User, Depends(RequireAgencyAdmin)]
Authenticated = Annotated[User, Depends(RequireAuthenticated)]

# Model dependencies (placeholder for now)
async def get_current_model(user: User = Depends(get_current_user)) -> User:
    """Get current model user - placeholder implementation."""
    # TODO: Implement proper model authentication
    if user.role != "MODEL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Model role required."
        )
    return user

async def require_model(user: User = Depends(get_current_user)) -> User:
    """Require model role."""
    if user.role != "MODEL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Model role required."
        )
    return user

Model = Annotated[User, Depends(get_current_model)]

# Role checker dependency (for backward compatibility)
class RoleChecker:
    """Check if user has required role(s)."""
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        # Check if user role is in allowed roles
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(self.allowed_roles)}. Your role: {user.role}"
            )
        return user

# Re-export dependencies for backward compatibility
get_optional_current_user = get_current_user_optional  # Alias for backward compatibility

# Re-export all dependencies
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_optional",
    "get_optional_current_user",  # Backward compatibility alias
    "get_current_active_user",
    "CurrentUser",
    "CurrentUserOptional",
    "SuperAdmin",
    "AgencyOwner", 
    "AgencyAdmin",
    "Authenticated",
    "Model",
    "require_model",
    "RoleChecker",
    "require_permission",
    "require_role"
]