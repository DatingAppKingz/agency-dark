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

# Re-export dependencies
__all__ = ["get_db", "get_current_user", "get_optional_current_user", "get_current_active_user", "CurrentUser", "CurrentUserOptional"]