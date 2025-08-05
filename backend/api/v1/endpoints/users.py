"""
Users API endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.auth import get_current_user
from core.auth.decorators import require_roles, require_agency_match, require_self_or_admin, require_admin
from models.user import User, UserRole
from api.v1.dependencies import check_permissions
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])


class UserListResponse(BaseModel):
    id: UUID
    agency_id: Optional[UUID]
    email: str
    full_name: Optional[str]
    username: Optional[str]
    stage_name: Optional[str]
    role: UserRole
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class PaginatedUsersResponse(BaseModel):
    data: List[UserListResponse]
    total: int
    page: int
    per_page: int
    pages: int


@router.get("/", response_model=PaginatedUsersResponse)
@require_admin()
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    agency_id: Optional[UUID] = Query(None, description="Filter by agency ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List users with optional filters.
    
    Permissions:
    - Super admins can see all users
    - Agency owners/admins can see users in their agency
    - Models can only see themselves
    - Chatters can only see models they're assigned to
    """
    # Build base query with model profile eager loading
    query = select(User).options(selectinload(User.model_profile))
    
    # Apply permission filters
    if current_user.role == UserRole.SUPER_ADMIN:
        # Can see all users
        pass
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        # Can only see users in their agency
        query = query.where(User.agency_id == current_user.agency_id)
    elif current_user.role == UserRole.MODEL:
        # Can only see themselves
        query = query.where(User.id == current_user.id)
    else:
        # Chatters - would need additional logic for assigned models
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list users"
        )
    
    # Apply filters
    if role:
        query = query.where(User.role == role)
    
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.where(User.agency_id == agency_id)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    if search:
        search_filter = or_(
            User.full_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Transform users to response model
    user_list = []
    for user in users:
        user_data = UserListResponse(
            id=user.id,
            agency_id=user.agency_id,
            email=user.email,
            full_name=user.full_name,
            username=user.username,
            stage_name=user.model_profile.stage_name if user.model_profile else user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login=user.last_login_at,
            created_at=user.created_at,
            avatar_url=user.avatar_url
        )
        user_list.append(user_data)
    
    # Calculate pages
    pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    return PaginatedUsersResponse(
        data=user_list,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/models", response_model=List[UserListResponse])
@require_roles([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL])
async def list_model_users(
    agency_id: Optional[UUID] = Query(None, description="Filter by agency ID"),
    is_active: bool = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users with MODEL role.
    
    This is a convenience endpoint specifically for listing models.
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list models"
        )
    
    # Build query with model profile eager loading
    query = select(User).options(selectinload(User.model_profile)).where(User.role == UserRole.MODEL)
    
    # Apply agency filter based on user role
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(User.agency_id == current_user.agency_id)
    elif agency_id:
        query = query.where(User.agency_id == agency_id)
    
    # Apply active filter
    query = query.where(User.is_active == is_active)
    
    # Execute query
    result = await db.execute(query)
    models = result.scalars().all()
    
    # Transform to response
    return [
        UserListResponse(
            id=model.id,
            agency_id=model.agency_id,
            email=model.email,
            full_name=model.full_name,
            username=model.username,
            stage_name=model.model_profile.stage_name if model.model_profile else model.full_name,
            role=model.role,
            is_active=model.is_active,
            is_verified=model.is_verified,
            last_login=model.last_login_at,
            created_at=model.created_at,
            avatar_url=model.avatar_url
        )
        for model in models
    ]


@router.get("/{user_id}", response_model=UserListResponse)
@require_self_or_admin(user_id_param="user_id")
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific user by ID.
    """
    # Build query with permission check
    query = select(User).where(User.id == user_id)
    
    # Apply permission filters
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            query = query.where(User.agency_id == current_user.agency_id)
        elif current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this user"
            )
    
    # Execute query
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserListResponse(
        id=user.id,
        agency_id=user.agency_id,
        email=user.email,
        full_name=user.full_name,
        username=getattr(user, 'username', None),
        stage_name=getattr(user, 'stage_name', user.full_name),
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        avatar_url=getattr(user, 'avatar_url', None)
    )