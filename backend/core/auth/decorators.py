"""
Role-based access control decorators for FastAPI endpoints.
"""
from functools import wraps
from typing import List, Optional, Callable, Union
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.auth.dependencies import get_current_user
from core.database import get_db
from models.user import User, UserRole
from models.model_assignment import ModelAssignment
import logging

logger = logging.getLogger(__name__)

# Security scheme for API documentation
security = HTTPBearer()


class PermissionDeniedError(HTTPException):
    """Custom exception for permission denied errors."""
    def __init__(self, detail: str = "Permission denied", required_roles: Optional[List[str]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "permission_denied",
                "message": detail,
                "required_roles": required_roles
            }
        )


def require_roles(allowed_roles: List[Union[str, UserRole]]) -> Callable:
    """
    Decorator to check if user has one of the required roles.
    
    Usage:
        @router.get("/admin")
        @require_roles([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
        async def admin_endpoint(current_user: User = Depends(get_current_user)):
            return {"message": "Admin access granted"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get('current_user')
            
            if not current_user:
                # Try to find it in Depends injection
                for key, value in kwargs.items():
                    if isinstance(value, User):
                        current_user = value
                        break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Convert roles to strings for comparison
            allowed_role_strings = [
                role if isinstance(role, str) else role.value 
                for role in allowed_roles
            ]
            
            # Check if user's role is in allowed roles
            user_role = current_user.role
            if user_role not in allowed_role_strings:
                logger.warning(
                    f"Access denied for user {current_user.email} with role {user_role}. "
                    f"Required roles: {allowed_role_strings}"
                )
                raise PermissionDeniedError(
                    detail=f"Access denied. Your role: {user_role}",
                    required_roles=allowed_role_strings
                )
            
            logger.info(f"Access granted for user {current_user.email} with role {user_role}")
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_agency_match(agency_id_param: str = "agency_id") -> Callable:
    """
    Decorator to check if user's agency matches the requested resource's agency.
    Super admins bypass this check.
    
    Usage:
        @router.get("/agencies/{agency_id}/users")
        @require_agency_match(agency_id_param="agency_id")
        async def get_agency_users(
            agency_id: str,
            current_user: User = Depends(get_current_user)
        ):
            return {"users": []}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Super admins can access any agency
            if current_user.role == UserRole.SUPER_ADMIN.value:
                return await func(*args, **kwargs)
            
            # Get agency_id from path parameters
            requested_agency_id = kwargs.get(agency_id_param)
            
            if not requested_agency_id:
                # Try to get from request body if not in path
                request = kwargs.get('request')
                if request and hasattr(request, 'json'):
                    body = await request.json()
                    requested_agency_id = body.get(agency_id_param)
            
            # Check if user's agency matches
            if not current_user.agency_id:
                raise PermissionDeniedError(
                    detail="You are not associated with any agency"
                )
            
            if str(current_user.agency_id) != str(requested_agency_id):
                logger.warning(
                    f"Agency mismatch for user {current_user.email}. "
                    f"User agency: {current_user.agency_id}, Requested: {requested_agency_id}"
                )
                raise PermissionDeniedError(
                    detail="You can only access resources from your own agency"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_self_or_admin(user_id_param: str = "user_id") -> Callable:
    """
    Decorator to check if user is accessing their own data or is an admin.
    Admins can access any user's data within their agency scope.
    
    Usage:
        @router.get("/users/{user_id}")
        @require_self_or_admin(user_id_param="user_id")
        async def get_user_profile(
            user_id: str,
            current_user: User = Depends(get_current_user)
        ):
            return {"user": {}}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Get requested user_id
            requested_user_id = kwargs.get(user_id_param)
            
            # Check if accessing own data
            if str(current_user.id) == str(requested_user_id):
                return await func(*args, **kwargs)
            
            # Check if user is an admin
            admin_roles = [
                UserRole.SUPER_ADMIN.value,
                UserRole.AGENCY_OWNER.value,
                UserRole.AGENCY_ADMIN.value
            ]
            
            if current_user.role not in admin_roles:
                logger.warning(
                    f"Non-admin user {current_user.email} tried to access user {requested_user_id}"
                )
                raise PermissionDeniedError(
                    detail="You can only access your own data"
                )
            
            # For agency admins, verify they're accessing users in their agency
            if current_user.role != UserRole.SUPER_ADMIN.value:
                db = kwargs.get('db')
                if db:
                    # Verify the requested user belongs to the same agency
                    result = await db.execute(
                        select(User).where(
                            and_(
                                User.id == requested_user_id,
                                User.agency_id == current_user.agency_id
                            )
                        )
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        raise PermissionDeniedError(
                            detail="User not found or not in your agency"
                        )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_model_assignment(model_id_param: str = "model_id") -> Callable:
    """
    Decorator to check if a chatter is assigned to the specified model.
    Other roles have different access rules.
    
    Usage:
        @router.get("/models/{model_id}/chat")
        @require_model_assignment(model_id_param="model_id")
        async def get_model_chat(
            model_id: str,
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db)
        ):
            return {"messages": []}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            db = kwargs.get('db')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database connection required"
                )
            
            requested_model_id = kwargs.get(model_id_param)
            
            # Different access rules based on role
            if current_user.role == UserRole.SUPER_ADMIN.value:
                # Super admins can access any model
                return await func(*args, **kwargs)
            
            elif current_user.role in [UserRole.AGENCY_OWNER.value, UserRole.AGENCY_ADMIN.value]:
                # Agency admins can access models in their agency
                result = await db.execute(
                    select(User).where(
                        and_(
                            User.id == requested_model_id,
                            User.agency_id == current_user.agency_id,
                            User.role == UserRole.MODEL.value
                        )
                    )
                )
                model = result.scalar_one_or_none()
                
                if not model:
                    raise PermissionDeniedError(
                        detail="Model not found or not in your agency"
                    )
                
            elif current_user.role == UserRole.MODEL.value:
                # Models can only access their own data
                if str(current_user.id) != str(requested_model_id):
                    raise PermissionDeniedError(
                        detail="You can only access your own data"
                    )
                
            elif current_user.role == UserRole.CHATTER.value:
                # Chatters need to be assigned to the model
                result = await db.execute(
                    select(ModelAssignment).where(
                        and_(
                            ModelAssignment.chatter_id == current_user.id,
                            ModelAssignment.model_id == requested_model_id,
                            ModelAssignment.is_active == True
                        )
                    )
                )
                assignment = result.scalar_one_or_none()
                
                if not assignment:
                    logger.warning(
                        f"Chatter {current_user.email} tried to access unassigned model {requested_model_id}"
                    )
                    raise PermissionDeniedError(
                        detail="You are not assigned to this model"
                    )
            
            else:
                # Other roles don't have access
                raise PermissionDeniedError(
                    detail="Your role does not have access to model data"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Composite decorators for common patterns
def require_admin() -> Callable:
    """Shorthand for admin-only endpoints."""
    return require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.AGENCY_OWNER.value,
        UserRole.AGENCY_ADMIN.value
    ])


def require_super_admin() -> Callable:
    """Shorthand for super admin-only endpoints."""
    return require_roles([UserRole.SUPER_ADMIN.value])


def require_agency_admin() -> Callable:
    """Shorthand for agency admin endpoints."""
    return require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.AGENCY_OWNER.value,
        UserRole.AGENCY_ADMIN.value
    ])