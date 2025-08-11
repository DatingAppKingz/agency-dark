"""
Simplified user management endpoints.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel, EmailStr

from core.database import get_db
from core.security_v2 import get_current_user, hash_password
from core.dependencies import CurrentUser
from models.user import User, UserRole
from models.agency import Agency

router = APIRouter(prefix="/users", tags=["users"])


# Pydantic models for request/response
class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.AGENCY_MEMBER
    agency_id: Optional[UUID] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    agency_id: Optional[UUID] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: Optional[str]
    full_name: Optional[str]
    role: UserRole
    agency_id: Optional[UUID]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("/", response_model=UserListResponse)
async def list_users(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    agency_id: Optional[UUID] = Query(None, description="Filter by agency"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    List users with pagination and filters.
    
    Permissions:
    - Super admins can see all users
    - Agency owners/admins can see users in their agency
    - Regular users can only see themselves
    """
    # Get user info from token
    user_id = current_user.get("user_id")
    user_role = current_user.get("role")
    user_agency_id = current_user.get("agency_id")
    
    # Build base query
    query = select(User)
    count_query = select(func.count(User.id))
    
    # Apply permission filters
    if user_role != UserRole.SUPER_ADMIN:
        if user_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Can see users in their agency
            query = query.where(User.agency_id == user_agency_id)
            count_query = count_query.where(User.agency_id == user_agency_id)
        else:
            # Can only see themselves
            query = query.where(User.id == user_id)
            count_query = count_query.where(User.id == user_id)
    
    # Apply filters
    if search:
        search_filter = or_(
            User.email.ilike(f"%{search}%"),
            User.username.ilike(f"%{search}%"),
            User._full_name.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    
    if agency_id and user_role == UserRole.SUPER_ADMIN:
        query = query.where(User.agency_id == agency_id)
        count_query = count_query.where(User.agency_id == agency_id)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    # Convert to response models
    user_responses = [
        UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user._full_name,
            role=user.role,
            agency_id=user.agency_id,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at or datetime.now(),
            updated_at=user.updated_at or datetime.now(),
            last_login_at=user.last_login_at
        )
        for user in users
    ]
    
    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific user by ID.
    
    Permissions:
    - Super admins can get any user
    - Agency owners/admins can get users in their agency
    - Regular users can only get themselves
    """
    # Get current user info
    curr_user_id = current_user.get("user_id")
    curr_user_role = current_user.get("role")
    curr_user_agency_id = current_user.get("agency_id")
    
    # Get the requested user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if curr_user_role != UserRole.SUPER_ADMIN:
        if curr_user_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Can only get users in their agency
            if user.agency_id != curr_user_agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        else:
            # Can only get themselves
            if str(user.id) != str(curr_user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user._full_name,
        role=user.role,
        agency_id=user.agency_id,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at or datetime.now(),
        updated_at=user.updated_at or datetime.now(),
        last_login_at=user.last_login_at
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user.
    
    Permissions:
    - Super admins can create any user
    - Agency owners/admins can create users in their agency
    - Regular users cannot create users
    """
    # Get current user info
    curr_user_role = current_user.get("role")
    curr_user_agency_id = current_user.get("agency_id")
    
    # Check permissions
    if curr_user_role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create users"
        )
    
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists (if provided)
    if user_data.username:
        existing_username = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing_username.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Set agency_id based on permissions
    if curr_user_role != UserRole.SUPER_ADMIN:
        # Force agency_id to be the current user's agency
        user_data.agency_id = curr_user_agency_id
    elif user_data.agency_id:
        # Verify agency exists
        agency = await db.execute(
            select(Agency).where(Agency.id == user_data.agency_id)
        )
        if not agency.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency not found"
            )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        username=user_data.username or user_data.email.split('@')[0],
        password_hash=hash_password(user_data.password),
        _full_name=user_data.full_name,
        role=user_data.role,
        agency_id=user_data.agency_id,
        is_active=user_data.is_active,
        is_verified=False
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        full_name=new_user._full_name,
        role=new_user.role,
        agency_id=new_user.agency_id,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at or datetime.now(),
        updated_at=new_user.updated_at or datetime.now(),
        last_login_at=new_user.last_login_at
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user.
    
    Permissions:
    - Super admins can update any user
    - Agency owners/admins can update users in their agency
    - Regular users can update themselves (limited fields)
    """
    # Get current user info
    curr_user_id = current_user.get("user_id")
    curr_user_role = current_user.get("role")
    curr_user_agency_id = current_user.get("agency_id")
    
    # Get the user to update
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    is_self = str(user.id) == str(curr_user_id)
    
    if curr_user_role != UserRole.SUPER_ADMIN:
        if curr_user_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Can only update users in their agency
            if user.agency_id != curr_user_agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        elif not is_self:
            # Regular users can only update themselves
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Apply updates
    update_data = user_update.dict(exclude_unset=True)
    
    # Regular users can only update limited fields
    if is_self and curr_user_role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        allowed_fields = {"email", "username", "full_name"}
        update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    for field, value in update_data.items():
        if field == "full_name":
            setattr(user, "_full_name", value)
        else:
            setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user._full_name,
        role=user.role,
        agency_id=user.agency_id,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at or datetime.now(),
        updated_at=user.updated_at or datetime.now(),
        last_login_at=user.last_login_at
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user.
    
    Permissions:
    - Only super admins can delete users
    """
    # Check permissions
    if current_user.get("role") != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete users"
        )
    
    # Get the user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting the last super admin
    if user.role == UserRole.SUPER_ADMIN:
        count_result = await db.execute(
            select(func.count(User.id)).where(
                User.role == UserRole.SUPER_ADMIN,
                User.id != user_id
            )
        )
        if count_result.scalar() == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last super admin"
            )
    
    await db.delete(user)
    await db.commit()
    
    return None