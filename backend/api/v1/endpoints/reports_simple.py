"""
Simplified reporting endpoints.
"""
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import CurrentUser

router = APIRouter(prefix="/enhanced-reports", tags=["reports"])


class RevenueReportResponse(BaseModel):
    total_revenue: float = 0.0
    period: str = "month"
    data: Dict[str, Any] = {}


class PerformanceDashboardResponse(BaseModel):
    metrics: Dict[str, Any] = {}
    timestamp: datetime


@router.get("/revenue", response_model=RevenueReportResponse)
async def get_revenue_report(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Get revenue report (simplified mock data).
    """
    return RevenueReportResponse(
        total_revenue=15750.25,
        period="month",
        data={"chart": [], "summary": {}}
    )


@router.get("/performance-dashboard", response_model=PerformanceDashboardResponse)
async def get_performance_dashboard(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Get performance dashboard (simplified mock data).
    """
    return PerformanceDashboardResponse(
        metrics={
            "conversion_rate": 3.5,
            "average_order_value": 125.50,
            "total_users": 1543
        },
        timestamp=datetime.now()
    )