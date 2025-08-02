"""
Dependencies compatibility layer.
Maps the existing dependencies to the expected dependency structure.
"""

from typing import Annotated
from fastapi import Depends, HTTPException, status

from core.database import get_db
from api.v1.endpoints.auth_simple import get_current_user, get_optional_current_user
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
CurrentUserOptional = Annotated[User | None, Depends(get_optional_current_user)]

# Model dependencies (placeholder for now)
async def get_current_model(user: User = Depends(get_current_user)) -> User:
    """Get current model user - placeholder implementation."""
    # TODO: Implement proper model authentication
    return user

async def require_model(user: User = Depends(get_current_user)) -> User:
    """Require model role - placeholder implementation."""
    # TODO: Check if user has model role
    return user

Model = Annotated[User, Depends(get_current_model)]

# Role checker dependency
class RoleChecker:
    """Check if user has required role(s)."""
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        # TODO: Implement actual role checking
        # For now, just return the user
        return user

# Re-export dependencies
__all__ = ["get_db", "get_current_user", "get_optional_current_user", "get_current_active_user", "CurrentUser", "CurrentUserOptional", "Model", "require_model", "RoleChecker"]