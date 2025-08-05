"""Simple agencies endpoint for admin panel."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db

router = APIRouter()

class AgencyInfo(BaseModel):
    id: str
    name: str
    owner_id: Optional[str]
    created_at: str
    is_active: bool

class AgenciesResponse(BaseModel):
    data: List[AgencyInfo]
    total: int
    page: int
    size: int

@router.get("/list")
async def list_all_agencies(
    page: int = 1,
    size: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get all agencies from users data."""
    # Since we don't have an agencies table, we'll extract unique agencies from users
    result = await db.execute(text("""
        SELECT DISTINCT 
            agency_id,
            COUNT(*) as user_count
        FROM users 
        WHERE agency_id IS NOT NULL
        GROUP BY agency_id
    """))
    
    agencies = []
    agency_map = {
        'bda0dac4-715e-46ed-b645-a57206f63090': 'Test Agency',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890': 'Test Agency Premium',
        'e882651f-2743-4c18-82e2-d8c1e502a40a': 'Elite Models',
        'fd13c60d-9d06-4e41-b4b1-77b611032d30': 'Competitor Agency',
    }
    
    for row in result:
        if row.agency_id:
            agency_id = str(row.agency_id)
            agencies.append(AgencyInfo(
                id=agency_id,
                name=agency_map.get(agency_id, f'Agency {agency_id[:8]}'),
                owner_id=None,  # We don't have this info
                created_at=datetime.now().isoformat(),
                is_active=True
            ))
    
    return AgenciesResponse(
        data=agencies,
        total=len(agencies),
        page=page,
        size=size
    )