"""Simple users endpoint for admin panel."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db

router = APIRouter()

class UserInfo(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    agency_id: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: str
    last_login: Optional[str]

class UsersResponse(BaseModel):
    data: List[UserInfo]
    total: int
    page: int
    size: int

@router.get("/list")
async def list_all_users(
    page: int = 1,
    size: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get all users with pagination."""
    offset = (page - 1) * size
    
    # Get total count
    count_result = await db.execute(text("SELECT COUNT(*) FROM users"))
    total = count_result.scalar()
    
    # Get users
    result = await db.execute(text("""
        SELECT 
            id, 
            email, 
            full_name, 
            role, 
            agency_id, 
            is_active, 
            is_verified, 
            created_at,
            last_login
        FROM users 
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"limit": size, "offset": offset})
    
    users = []
    for row in result:
        users.append(UserInfo(
            id=str(row.id),
            email=row.email,
            full_name=row.full_name,
            role=row.role,
            agency_id=str(row.agency_id) if row.agency_id else None,
            is_active=row.is_active,
            is_verified=row.is_verified,
            created_at=row.created_at.isoformat() if row.created_at else datetime.now().isoformat(),
            last_login=row.last_login.isoformat() if row.last_login else None
        ))
    
    return UsersResponse(
        data=users,
        total=total,
        page=page,
        size=size
    )