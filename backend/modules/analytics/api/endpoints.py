"""
Analytics API endpoints.
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user, RoleChecker
from core.domain.models import User, UserRole, ModelProfile
from modules.analytics.application.service import AnalyticsService
from modules.analytics.application.exporter import AnalyticsExporter
from modules.analytics.application.data_sync_service import AnalyticsDataSyncService
from modules.analytics.domain.schemas import (
    TimeGranularity,
    ChartRequest,
    ChartResponse,
    SubscriberGrowthData,
    RevenueTimeSeriesData,
    CategoryPopularityData,
    ContentPerformanceData,
    DashboardSummary,
    ExportRequest,
    ExportResponse,
    ExportFormat
)


router = APIRouter(prefix="/analytics", tags=["analytics"])

# Import agency stats router
from .agency_stats import router as agency_router
router.include_router(agency_router)


async def get_model_profile_for_analytics(
    model_id: str,
    user: User,
    db: AsyncSession
) -> ModelProfile:
    """Get model profile with analytics permission check."""
    # Get model profile
    from sqlalchemy import select
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model profile not found")
    
    # Check permissions
    if user.role == UserRole.SUPER_ADMIN:
        pass  # Super admin can view any analytics
    elif user.role == UserRole.AGENCY_OWNER:
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    elif user.role == UserRole.MODEL:
        if model_profile.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your model profile")
    elif user.role in [UserRole.AGENCY_MEMBER, UserRole.AGENCY_MEMBER]:
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    elif user.role == UserRole.CHATTER:
        # Chatters have limited analytics access
        if model_profile.agency_id != user.agency_id:
            raise HTTPException(status_code=403, detail="Model not in your agency")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return model_profile


@router.get("/dashboard/{model_id}", response_model=DashboardSummary)
async def get_dashboard_summary(
    model_id: str,
    period: str = Query("today", pattern="^(today|week|month)$"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER,
            UserRole.CHATTER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard summary metrics.
    
    - **model_id**: Model profile ID
    - **period**: Time period (today, week, month)
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    summary = await service.get_dashboard_summary(model_id, period)
    
    return summary


@router.post("/charts/subscriber-growth", response_model=ChartResponse)
async def get_subscriber_growth_chart(
    model_id: str = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get subscriber growth chart data.
    
    - **model_id**: Model profile ID
    - **period_start**: Start date
    - **period_end**: End date
    - **granularity**: Time granularity (hour, day, week, month)
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    chart_data = await service.get_subscriber_growth_chart(
        model_id,
        period_start,
        period_end,
        granularity
    )
    
    return chart_data


@router.post("/charts/revenue-timeline", response_model=ChartResponse)
async def get_revenue_timeline_chart(
    model_id: str = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get revenue timeline chart data.
    
    Shows:
    - Total revenue
    - Subscription revenue
    - Tip revenue
    - PPV revenue
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    chart_data = await service.get_revenue_timeline_chart(
        model_id,
        period_start,
        period_end,
        granularity
    )
    
    return chart_data


@router.post("/charts/fan-revenue", response_model=ChartResponse)
async def get_fan_revenue_chart(
    request: ChartRequest,
    model_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get revenue chart for specific fans (up to 10).
    
    - **model_id**: Model profile ID
    - **request**: Chart request with fan IDs and date range
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    if not request.entity_ids:
        raise HTTPException(status_code=400, detail="Fan IDs required")
    
    service = AnalyticsService(db)
    chart_data = await service.get_per_fan_revenue_chart(
        model_id,
        request.entity_ids,
        request.period_start,
        request.period_end,
        request.granularity
    )
    
    return chart_data


@router.get("/categories/{model_id}", response_model=CategoryPopularityData)
async def get_category_popularity(
    model_id: str,
    period_start: date = Query(...),
    period_end: date = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get content category popularity metrics.
    
    - **model_id**: Model profile ID
    - **period_start**: Start date
    - **period_end**: End date
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    category_data = await service.get_category_popularity_data(
        model_id,
        period_start,
        period_end
    )
    
    return category_data


@router.post("/content/performance", response_model=List[ContentPerformanceData])
async def get_content_performance(
    model_id: str = Query(...),
    content_ids: List[str] = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get performance data for specific content pieces.
    
    - **model_id**: Model profile ID
    - **content_ids**: List of content IDs
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    performance_data = await service.get_content_performance_data(
        model_id,
        content_ids
    )
    
    return performance_data


@router.post("/export", response_model=ExportResponse)
async def export_analytics_data(
    request: ExportRequest,
    model_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Export analytics data in various formats.
    
    - **model_id**: Model profile ID
    - **request**: Export request details
    
    Export types:
    - revenue: Revenue transactions
    - subscribers: Subscriber metrics over time
    - content: Content performance data
    - fans: Fan spending data
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    exporter = AnalyticsExporter(db)
    export_response = await exporter.export_data(model_id, request)
    
    return export_response


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download an exported analytics file.
    
    - **export_id**: Export ID from export request
    """
    # In production, this would validate the export belongs to the user
    # and serve the file from S3 or similar storage
    
    # For now, serve from temporary storage
    file_path = f"/tmp/export_{export_id}.csv"  # or .json
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Determine content type based on file extension
        if file_path.endswith('.csv'):
            media_type = "text/csv"
            filename = f"analytics_export_{export_id}.csv"
        else:
            media_type = "application/json"
            filename = f"analytics_export_{export_id}.json"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Export not found")


@router.post("/charts/generic", response_model=ChartResponse)
async def get_generic_chart(
    request: ChartRequest,
    model_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chart data based on chart type.
    
    Supported chart types:
    - subscriber_growth
    - revenue_timeline
    - fan_revenue
    - category_popularity
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    service = AnalyticsService(db)
    
    if request.chart_type == "subscriber_growth":
        return await service.get_subscriber_growth_chart(
            model_id,
            request.period_start,
            request.period_end,
            request.granularity
        )
    elif request.chart_type == "revenue_timeline":
        return await service.get_revenue_timeline_chart(
            model_id,
            request.period_start,
            request.period_end,
            request.granularity
        )
    elif request.chart_type == "fan_revenue":
        if not request.entity_ids:
            raise HTTPException(status_code=400, detail="Fan IDs required")
        return await service.get_per_fan_revenue_chart(
            model_id,
            request.entity_ids,
            request.period_start,
            request.period_end,
            request.granularity
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown chart type: {request.chart_type}")


@router.post("/sync/{model_id}")
async def sync_analytics_data(
    model_id: str,
    force: bool = Query(False, description="Force resync even if data exists"),
    lookback_days: int = Query(90, description="Days to look back for metrics"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync analytics data from financial transactions.
    
    This endpoint:
    - Syncs revenue transactions from financial transactions
    - Updates metric snapshots
    - Updates content performance data
    - Updates fan spending history
    - Updates category performance
    
    - **model_id**: Model profile ID to sync
    - **force**: Force resync even if data already exists
    - **lookback_days**: Number of days to look back for metrics (default: 90)
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    sync_service = AnalyticsDataSyncService(db)
    
    try:
        # Start full sync
        await sync_service.sync_all_model_data(model_id, force=force)
        
        # Update metrics for specified lookback period
        await sync_service.update_metric_snapshots(model_id, lookback_days=lookback_days)
        
        return {
            "status": "success",
            "message": f"Analytics data synced for model {model_id}",
            "model_id": model_id,
            "lookback_days": lookback_days,
            "force": force
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync analytics data: {str(e)}"
        )


@router.post("/sync/{model_id}/revenue")
async def sync_revenue_data(
    model_id: str,
    start_date: Optional[datetime] = Query(None, description="Start date for sync"),
    force: bool = Query(False, description="Force resync"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.AGENCY_MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync only revenue transaction data.
    
    - **model_id**: Model profile ID
    - **start_date**: Only sync transactions after this date
    - **force**: Force resync even if data exists
    """
    model_profile = await get_model_profile_for_analytics(model_id, current_user, db)
    
    sync_service = AnalyticsDataSyncService(db)
    
    try:
        await sync_service.sync_revenue_transactions(model_id, force=force, start_date=start_date)
        
        return {
            "status": "success",
            "message": f"Revenue data synced for model {model_id}",
            "model_id": model_id,
            "start_date": start_date,
            "force": force
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync revenue data: {str(e)}"
        )