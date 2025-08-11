"""
Agency management endpoints.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel, EmailStr

from core.database import get_db
from core.security_v2 import get_current_user
from core.dependencies import CurrentUser
from models.user import UserRole
from models.agency import Agency

router = APIRouter(prefix="/agencies", tags=["agencies"])


# Pydantic models for request/response
class AgencyBase(BaseModel):
    name: str
    slug: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    timezone: str = "UTC"
    primary_color: str = "#3B82F6"
    secondary_color: str = "#1E40AF"
    default_commission_rate: Decimal = Decimal("20.00")
    payment_frequency: str = "monthly"
    minimum_payout: Decimal = Decimal("100.00")
    max_models: int = 100
    max_chatters: int = 50
    max_staff: int = 20
    storage_quota_gb: int = 100


class AgencyCreate(AgencyBase):
    pass


class AgencyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    default_commission_rate: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    minimum_payout: Optional[Decimal] = None
    max_models: Optional[int] = None
    max_chatters: Optional[int] = None
    max_staff: Optional[int] = None
    storage_quota_gb: Optional[int] = None
    is_active: Optional[bool] = None


class AgencyResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    country: Optional[str]
    timezone: str
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str
    default_commission_rate: Decimal
    payment_frequency: str
    minimum_payout: Decimal
    max_models: int
    max_chatters: int
    max_staff: int
    storage_quota_gb: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgencyListResponse(BaseModel):
    agencies: List[AgencyResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("/", response_model=AgencyListResponse)
async def list_agencies(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    List agencies with pagination and filters.
    
    Permissions:
    - Super admins can see all agencies
    - Agency owners/admins can see only their agency
    - Regular users cannot see agencies
    """
    # Get user info from token
    user_role = current_user.get("role")
    user_agency_id = current_user.get("agency_id")
    
    # Check permissions
    if user_role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list agencies"
        )
    
    # Build base query
    query = select(Agency)
    count_query = select(func.count(Agency.id))
    
    # Apply permission filters
    if user_role != UserRole.SUPER_ADMIN:
        # Can only see their own agency
        query = query.where(Agency.id == user_agency_id)
        count_query = count_query.where(Agency.id == user_agency_id)
    
    # Apply filters
    if search:
        search_filter = or_(
            Agency.name.ilike(f"%{search}%"),
            Agency.email.ilike(f"%{search}%"),
            Agency.slug.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    if is_active is not None:
        query = query.where(Agency.is_active == is_active)
        count_query = count_query.where(Agency.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    agencies = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    # Convert to response models
    agency_responses = [
        AgencyResponse(
            id=agency.id,
            name=agency.name,
            slug=agency.slug,
            email=agency.email,
            phone=agency.phone,
            address=agency.address,
            country=agency.country,
            timezone=agency.timezone,
            logo_url=agency.logo_url,
            primary_color=agency.primary_color,
            secondary_color=agency.secondary_color,
            default_commission_rate=agency.default_commission_rate,
            payment_frequency=agency.payment_frequency,
            minimum_payout=agency.minimum_payout,
            max_models=agency.max_models,
            max_chatters=agency.max_chatters,
            max_staff=agency.max_staff,
            storage_quota_gb=agency.storage_quota_gb,
            is_active=agency.is_active,
            is_verified=agency.is_verified,
            created_at=agency.created_at,
            updated_at=agency.updated_at
        )
        for agency in agencies
    ]
    
    return AgencyListResponse(
        agencies=agency_responses,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{agency_id}", response_model=AgencyResponse)
async def get_agency(
    agency_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific agency by ID.
    
    Permissions:
    - Super admins can get any agency
    - Agency owners/admins can get their own agency
    - Regular users cannot get agencies
    """
    # Get current user info
    curr_user_role = current_user.get("role")
    curr_user_agency_id = current_user.get("agency_id")
    
    # Check basic permissions
    if curr_user_role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view agencies"
        )
    
    # Get the requested agency
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Check specific permissions
    if curr_user_role != UserRole.SUPER_ADMIN:
        # Can only get their own agency
        if str(agency.id) != str(curr_user_agency_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    return AgencyResponse(
        id=agency.id,
        name=agency.name,
        slug=agency.slug,
        email=agency.email,
        phone=agency.phone,
        address=agency.address,
        country=agency.country,
        timezone=agency.timezone,
        logo_url=agency.logo_url,
        primary_color=agency.primary_color,
        secondary_color=agency.secondary_color,
        default_commission_rate=agency.default_commission_rate,
        payment_frequency=agency.payment_frequency,
        minimum_payout=agency.minimum_payout,
        max_models=agency.max_models,
        max_chatters=agency.max_chatters,
        max_staff=agency.max_staff,
        storage_quota_gb=agency.storage_quota_gb,
        is_active=agency.is_active,
        is_verified=agency.is_verified,
        created_at=agency.created_at,
        updated_at=agency.updated_at
    )


@router.post("/", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
async def create_agency(
    agency_data: AgencyCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new agency.
    
    Permissions:
    - Only super admins can create agencies
    """
    # Check permissions
    if current_user.get("role") != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create agencies"
        )
    
    # Check if slug already exists
    existing = await db.execute(
        select(Agency).where(Agency.slug == agency_data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency slug already exists"
        )
    
    # Create new agency
    new_agency = Agency(
        name=agency_data.name,
        slug=agency_data.slug,
        email=agency_data.email,
        phone=agency_data.phone,
        address=agency_data.address,
        country=agency_data.country,
        timezone=agency_data.timezone,
        primary_color=agency_data.primary_color,
        secondary_color=agency_data.secondary_color,
        default_commission_rate=agency_data.default_commission_rate,
        payment_frequency=agency_data.payment_frequency,
        minimum_payout=agency_data.minimum_payout,
        max_models=agency_data.max_models,
        max_chatters=agency_data.max_chatters,
        max_staff=agency_data.max_staff,
        storage_quota_gb=agency_data.storage_quota_gb,
        is_active=True,
        is_verified=False
    )
    
    db.add(new_agency)
    await db.commit()
    await db.refresh(new_agency)
    
    return AgencyResponse(
        id=new_agency.id,
        name=new_agency.name,
        slug=new_agency.slug,
        email=new_agency.email,
        phone=new_agency.phone,
        address=new_agency.address,
        country=new_agency.country,
        timezone=new_agency.timezone,
        logo_url=new_agency.logo_url,
        primary_color=new_agency.primary_color,
        secondary_color=new_agency.secondary_color,
        default_commission_rate=new_agency.default_commission_rate,
        payment_frequency=new_agency.payment_frequency,
        minimum_payout=new_agency.minimum_payout,
        max_models=new_agency.max_models,
        max_chatters=new_agency.max_chatters,
        max_staff=new_agency.max_staff,
        storage_quota_gb=new_agency.storage_quota_gb,
        is_active=new_agency.is_active,
        is_verified=new_agency.is_verified,
        created_at=new_agency.created_at,
        updated_at=new_agency.updated_at
    )


@router.put("/{agency_id}", response_model=AgencyResponse)
async def update_agency(
    agency_id: UUID,
    agency_update: AgencyUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an agency.
    
    Permissions:
    - Super admins can update any agency
    - Agency owners can update their own agency (limited fields)
    """
    # Get current user info
    curr_user_role = current_user.get("role")
    curr_user_agency_id = current_user.get("agency_id")
    
    # Check permissions
    if curr_user_role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update agencies"
        )
    
    # Get the agency to update
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Check specific permissions
    if curr_user_role != UserRole.SUPER_ADMIN:
        # Can only update their own agency
        if str(agency.id) != str(curr_user_agency_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Apply updates
    update_data = agency_update.dict(exclude_unset=True)
    
    # Agency owners can only update limited fields
    if curr_user_role == UserRole.AGENCY_OWNER:
        allowed_fields = {
            "name", "email", "phone", "address", "country", "timezone",
            "logo_url", "primary_color", "secondary_color",
            "default_commission_rate", "payment_frequency", "minimum_payout"
        }
        update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    for field, value in update_data.items():
        setattr(agency, field, value)
    
    await db.commit()
    await db.refresh(agency)
    
    return AgencyResponse(
        id=agency.id,
        name=agency.name,
        slug=agency.slug,
        email=agency.email,
        phone=agency.phone,
        address=agency.address,
        country=agency.country,
        timezone=agency.timezone,
        logo_url=agency.logo_url,
        primary_color=agency.primary_color,
        secondary_color=agency.secondary_color,
        default_commission_rate=agency.default_commission_rate,
        payment_frequency=agency.payment_frequency,
        minimum_payout=agency.minimum_payout,
        max_models=agency.max_models,
        max_chatters=agency.max_chatters,
        max_staff=agency.max_staff,
        storage_quota_gb=agency.storage_quota_gb,
        is_active=agency.is_active,
        is_verified=agency.is_verified,
        created_at=agency.created_at,
        updated_at=agency.updated_at
    )


@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agency(
    agency_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an agency.
    
    Permissions:
    - Only super admins can delete agencies
    """
    # Check permissions
    if current_user.get("role") != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete agencies"
        )
    
    # Get the agency
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Check if agency has users
    from models.user import User
    users_result = await db.execute(
        select(func.count(User.id)).where(User.agency_id == agency_id)
    )
    user_count = users_result.scalar()
    
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete agency with {user_count} users. Remove users first."
        )
    
    await db.delete(agency)
    await db.commit()
    
    return None