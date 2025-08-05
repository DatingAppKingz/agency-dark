"""Simple agency endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from core.auth.decorators import require_super_admin, require_roles, require_agency_match
from models.agency import Agency
from models.user import User, UserRole
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


class AgencyCreate(BaseModel):
    name: str
    email: str
    country: str
    timezone: str
    phone: Optional[str] = None
    address: Optional[str] = None


class AgencyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None


class AgencyResponse(BaseModel):
    id: int
    name: str
    email: str
    country: str
    timezone: str
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=AgencyResponse)
@require_super_admin()
async def create_agency(
    agency: AgencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new agency."""
    # For testing, allow any authenticated user to create agencies
    # In production, you'd restrict this to admins only
    # if current_user.role not in ["ADMIN", "SUPERUSER"]:
    #     raise HTTPException(status_code=403, detail="Not authorized")
    
    # Generate slug from name
    import re
    slug = re.sub(r'[^a-z0-9-]', '-', agency.name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    
    new_agency = Agency(
        name=agency.name,
        slug=slug,
        email=agency.email,
        country=agency.country,
        timezone=agency.timezone,
        phone=agency.phone,
        address=agency.address
    )
    
    db.add(new_agency)
    await db.commit()
    await db.refresh(new_agency)
    
    return new_agency


@router.get("/", response_model=List[AgencyResponse])
@require_super_admin()
async def list_agencies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of agencies."""
    stmt = select(Agency).offset(skip).limit(limit)
    result = await db.execute(stmt)
    agencies = result.scalars().all()
    return agencies


@router.get("/{agency_id}", response_model=AgencyResponse)
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value, UserRole.AGENCY_ADMIN.value])
async def get_agency(
    agency_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agency by ID."""
    stmt = select(Agency).where(Agency.id == agency_id)
    result = await db.execute(stmt)
    agency = result.scalar_one_or_none()
    
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    return agency


@router.patch("/{agency_id}", response_model=AgencyResponse)
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value])
async def update_agency(
    agency_id: int,
    agency_update: AgencyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update agency."""
    # For testing, allow any authenticated user to update agencies
    # In production, you'd restrict this to admins only
    # if current_user.role not in ["ADMIN", "SUPERUSER"]:
    #     raise HTTPException(status_code=403, detail="Not authorized")
    
    stmt = select(Agency).where(Agency.id == agency_id)
    result = await db.execute(stmt)
    agency = result.scalar_one_or_none()
    
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    # Update fields
    update_data = agency_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agency, field, value)
    
    await db.commit()
    await db.refresh(agency)
    
    return agency