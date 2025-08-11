"""
Simplified analytics endpoints.
"""
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import CurrentUser
from models.user import UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])


class RealtimeAnalyticsResponse(BaseModel):
    active_users: int = 0
    total_messages: int = 0
    revenue_today: float = 0.0
    timestamp: datetime


@router.get("/realtime-analytics", response_model=RealtimeAnalyticsResponse)
async def get_realtime_analytics(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Get real-time analytics (simplified mock data).
    """
    return RealtimeAnalyticsResponse(
        active_users=5,
        total_messages=150,
        revenue_today=1250.50,
        timestamp=datetime.now()
    )