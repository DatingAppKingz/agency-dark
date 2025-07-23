from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from .database import get_db
from .security import decode_token
from .domain.models import User, UserRole
from .domain.schemas import TokenData


security = HTTPBearer()


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        if not payload:
            return None
        
        token_data = TokenData(**payload)
        user = await db.get(User, token_data.user_id)
        
        if not user or not user.is_active:
            return None
            
        return user
    except (JWTError, Exception):
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user or raise 401."""
    user = await get_current_user_optional(credentials, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


class RoleChecker:
    """Dependency to check if user has required role(s)."""
    
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required roles: {self.allowed_roles}"
            )
        return current_user


# Role-based dependencies
require_super_admin = RoleChecker([UserRole.SUPER_ADMIN])
require_agency_owner = RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
require_agency_admin = RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN])
require_model = RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL])
require_any_role = RoleChecker([role for role in UserRole])


# Tenant-aware dependencies
async def get_current_user_with_tenant(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Ensure user has agency_id (tenant) set."""
    if current_user.role != UserRole.SUPER_ADMIN and not current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any agency"
        )
    return current_user


# Type aliases for cleaner code
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]
SuperAdmin = Annotated[User, Depends(require_super_admin)]
AgencyOwner = Annotated[User, Depends(require_agency_owner)]
AgencyAdmin = Annotated[User, Depends(require_agency_admin)]
Model = Annotated[User, Depends(require_model)]