"""API v1 dependencies."""

from typing import List
from fastapi import HTTPException, status, Depends
from models.user import User, UserRole
from core.auth import get_current_user


def check_permissions(required_roles: List[UserRole]):
    """Check if user has required permissions."""
    async def permission_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return permission_checker


def check_agency_access(user: User, agency_id: int) -> bool:
    """Check if user has access to an agency."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    return user.agency_id == agency_id


def check_model_access(user: User, model_id: int, model_agency_id: int) -> bool:
    """Check if user has access to a model."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    if user.role == UserRole.MODEL and user.id == model_id:
        return True
    if user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_STAFF]:
        return user.agency_id == model_agency_id
    return False