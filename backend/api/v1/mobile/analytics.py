"""
Mobile optimized analytics endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, date, timedelta

from core.database import get_db
from core.security_v2 import get_current_user
from core.performance import cached
from models.user import User
from modules.analytics.application.service import AnalyticsService

router = APIRouter(prefix="/mobile/analytics", tags=["mobile-analytics"])


class MobileDashboardMetric(BaseModel):
    """Single dashboard metric"""
    label: str
    value: float
    change: float  # Percentage change
    change_direction: str  # 'up', 'down', 'stable'
    formatted_value: str
    icon: Optional[str] = None


class MobileChartData(BaseModel):
    """Chart data for mobile"""
    labels: List[str]
    datasets: List[dict]
    chart_type: str = "line"


class MobileDashboardResponse(BaseModel):
    """Mobile dashboard response"""
    metrics: List[MobileDashboardMetric]
    revenue_chart: MobileChartData
    engagement_chart: MobileChartData
    quick_stats: dict
    last_updated: datetime


@router.get("/dashboard/{model_id}", response_model=MobileDashboardResponse)
@cached(ttl=300, namespace="mobile_dashboard")
async def get_mobile_dashboard(
    model_id: UUID,
    period: str = Query("week", pattern="^(day|week|month)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get mobile optimized dashboard data
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    analytics_service = AnalyticsService()
    
    # Determine date range
    end_date = date.today()
    if period == "day":
        start_date = end_date
        comparison_start = end_date - timedelta(days=1)
        comparison_end = comparison_start
    elif period == "week":
        start_date = end_date - timedelta(days=6)
        comparison_start = start_date - timedelta(days=7)
        comparison_end = end_date - timedelta(days=7)
    else:  # month
        start_date = end_date - timedelta(days=29)
        comparison_start = start_date - timedelta(days=30)
        comparison_end = end_date - timedelta(days=30)
    
    # Get current period data
    current_data = await analytics_service.get_model_analytics(
        model_id, start_date, end_date, db
    )
    
    # Get comparison period data
    comparison_data = await analytics_service.get_model_analytics(
        model_id, comparison_start, comparison_end, db
    )
    
    # Format metrics
    metrics = _format_dashboard_metrics(current_data, comparison_data)
    
    # Get chart data
    revenue_chart = await _get_revenue_chart_data(
        model_id, start_date, end_date, db
    )
    
    engagement_chart = await _get_engagement_chart_data(
        model_id, start_date, end_date, db
    )
    
    # Quick stats
    from modules.fans.domain.models import Fan
    from modules.messaging.domain.models import Message
    
    # Active fans today
    active_fans_query = (
        db.query(Fan)
        .filter(
            Fan.model_id == model_id,
            Fan.last_activity >= datetime.utcnow() - timedelta(days=1)
        )
        .count()
    )
    active_fans = await db.scalar(active_fans_query)
    
    # Unread messages
    unread_query = (
        db.query(Message)
        .filter(
            Message.model_id == model_id,
            Message.is_read == False,
            Message.sender == "fan"
        )
        .count()
    )
    unread_count = await db.scalar(unread_query)
    
    quick_stats = {
        "active_fans_today": active_fans,
        "unread_messages": unread_count,
        "response_rate": current_data.get("response_rate", 0),
        "avg_response_time": current_data.get("avg_response_time", "N/A")
    }
    
    return MobileDashboardResponse(
        metrics=metrics,
        revenue_chart=revenue_chart,
        engagement_chart=engagement_chart,
        quick_stats=quick_stats,
        last_updated=datetime.utcnow()
    )


@router.get("/quick-stats/{model_id}")
async def get_quick_stats(
    model_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get quick stats for mobile app widget/notification
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    from sqlalchemy import select, func, and_
    from modules.payments.domain.models import Payment
    from modules.messaging.domain.models import Message
    
    # Today's revenue
    today_revenue_query = (
        select(func.sum(Payment.amount))
        .where(
            and_(
                Payment.model_id == model_id,
                func.date(Payment.created_at) == date.today(),
                Payment.status == "completed"
            )
        )
    )
    today_revenue = await db.scalar(today_revenue_query) or 0
    
    # Unread messages
    unread_query = (
        select(func.count(Message.id))
        .where(
            and_(
                Message.model_id == model_id,
                Message.is_read == False,
                Message.sender == "fan"
            )
        )
    )
    unread_count = await db.scalar(unread_query)
    
    # New fans today
    from modules.fans.domain.models import Fan
    new_fans_query = (
        select(func.count(Fan.id))
        .where(
            and_(
                Fan.model_id == model_id,
                func.date(Fan.created_at) == date.today()
            )
        )
    )
    new_fans = await db.scalar(new_fans_query)
    
    return {
        "today_revenue": float(today_revenue),
        "unread_messages": unread_count,
        "new_fans_today": new_fans,
        "timestamp": datetime.utcnow()
    }


@router.get("/trends/{model_id}")
async def get_trends(
    model_id: UUID,
    metric: str = Query(..., pattern="^(revenue|fans|messages|engagement)$"),
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trend data for specific metric
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    data_points = []
    
    if metric == "revenue":
        from modules.payments.domain.models import Payment
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            daily_revenue = await db.scalar(
                select(func.sum(Payment.amount))
                .where(
                    and_(
                        Payment.model_id == model_id,
                        func.date(Payment.created_at) == current_date,
                        Payment.status == "completed"
                    )
                )
            ) or 0
            
            data_points.append({
                "date": current_date.isoformat(),
                "value": float(daily_revenue)
            })
    
    elif metric == "fans":
        from modules.fans.domain.models import Fan
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            new_fans = await db.scalar(
                select(func.count(Fan.id))
                .where(
                    and_(
                        Fan.model_id == model_id,
                        func.date(Fan.created_at) == current_date
                    )
                )
            )
            
            data_points.append({
                "date": current_date.isoformat(),
                "value": new_fans
            })
    
    elif metric == "messages":
        from modules.messaging.domain.models import Message
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            message_count = await db.scalar(
                select(func.count(Message.id))
                .where(
                    and_(
                        Message.model_id == model_id,
                        func.date(Message.created_at) == current_date
                    )
                )
            )
            
            data_points.append({
                "date": current_date.isoformat(),
                "value": message_count
            })
    
    # Calculate trend
    if len(data_points) >= 2:
        values = [p["value"] for p in data_points]
        avg_first_half = sum(values[:len(values)//2]) / (len(values)//2)
        avg_second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        if avg_first_half > 0:
            trend_percentage = ((avg_second_half - avg_first_half) / avg_first_half) * 100
        else:
            trend_percentage = 100 if avg_second_half > 0 else 0
    else:
        trend_percentage = 0
    
    return {
        "metric": metric,
        "data_points": data_points,
        "trend": {
            "direction": "up" if trend_percentage > 0 else "down" if trend_percentage < 0 else "stable",
            "percentage": abs(trend_percentage)
        },
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        }
    }


def _format_dashboard_metrics(
    current_data: dict,
    comparison_data: dict
) -> List[MobileDashboardMetric]:
    """Format metrics for mobile dashboard"""
    metrics = []
    
    # Revenue metric
    current_revenue = current_data.get("total_revenue", 0)
    comparison_revenue = comparison_data.get("total_revenue", 0)
    revenue_change = _calculate_change(current_revenue, comparison_revenue)
    
    metrics.append(MobileDashboardMetric(
        label="Revenue",
        value=current_revenue,
        change=revenue_change,
        change_direction=_get_change_direction(revenue_change),
        formatted_value=f"${current_revenue:,.2f}",
        icon="dollar"
    ))
    
    # Fans metric
    current_fans = current_data.get("new_fans", 0)
    comparison_fans = comparison_data.get("new_fans", 0)
    fans_change = _calculate_change(current_fans, comparison_fans)
    
    metrics.append(MobileDashboardMetric(
        label="New Fans",
        value=current_fans,
        change=fans_change,
        change_direction=_get_change_direction(fans_change),
        formatted_value=str(current_fans),
        icon="users"
    ))
    
    # Messages metric
    current_messages = current_data.get("total_messages", 0)
    comparison_messages = comparison_data.get("total_messages", 0)
    messages_change = _calculate_change(current_messages, comparison_messages)
    
    metrics.append(MobileDashboardMetric(
        label="Messages",
        value=current_messages,
        change=messages_change,
        change_direction=_get_change_direction(messages_change),
        formatted_value=str(current_messages),
        icon="message"
    ))
    
    # Engagement rate
    current_engagement = current_data.get("engagement_rate", 0)
    comparison_engagement = comparison_data.get("engagement_rate", 0)
    engagement_change = current_engagement - comparison_engagement
    
    metrics.append(MobileDashboardMetric(
        label="Engagement",
        value=current_engagement,
        change=engagement_change,
        change_direction=_get_change_direction(engagement_change),
        formatted_value=f"{current_engagement:.1f}%",
        icon="activity"
    ))
    
    return metrics


def _calculate_change(current: float, previous: float) -> float:
    """Calculate percentage change"""
    if previous == 0:
        return 100 if current > 0 else 0
    return ((current - previous) / previous) * 100


def _get_change_direction(change: float) -> str:
    """Get change direction"""
    if change > 0:
        return "up"
    elif change < 0:
        return "down"
    return "stable"


async def _get_revenue_chart_data(
    model_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession
) -> MobileChartData:
    """Get revenue chart data for mobile"""
    from modules.analytics.domain.models import Analytics
    
    analytics = await db.query(Analytics).filter(
        Analytics.model_id == model_id,
        Analytics.date >= start_date,
        Analytics.date <= end_date,
        Analytics.metric_type == "revenue"
    ).order_by(Analytics.date).all()
    
    labels = []
    values = []
    
    current_date = start_date
    while current_date <= end_date:
        labels.append(current_date.strftime("%m/%d"))
        
        day_data = next(
            (a for a in analytics if a.date == current_date),
            None
        )
        values.append(float(day_data.value) if day_data else 0)
        
        current_date += timedelta(days=1)
    
    return MobileChartData(
        labels=labels,
        datasets=[{
            "label": "Revenue",
            "data": values,
            "borderColor": "#4F46E5",
            "backgroundColor": "rgba(79, 70, 229, 0.1)"
        }],
        chart_type="line"
    )


async def _get_engagement_chart_data(
    model_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession
) -> MobileChartData:
    """Get engagement chart data for mobile"""
    # Similar implementation for engagement metrics
    # This would show messages sent/received over time
    
    labels = []
    sent_values = []
    received_values = []
    
    current_date = start_date
    while current_date <= end_date:
        labels.append(current_date.strftime("%m/%d"))
        
        # Get message counts for the day
        # ... query implementation ...
        
        sent_values.append(0)  # Placeholder
        received_values.append(0)  # Placeholder
        
        current_date += timedelta(days=1)
    
    return MobileChartData(
        labels=labels,
        datasets=[
            {
                "label": "Sent",
                "data": sent_values,
                "borderColor": "#10B981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)"
            },
            {
                "label": "Received",
                "data": received_values,
                "borderColor": "#F59E0B",
                "backgroundColor": "rgba(245, 158, 11, 0.1)"
            }
        ],
        chart_type="line"
    )


async def _user_has_model_access(
    user: User,
    model_id: UUID,
    db: AsyncSession
) -> bool:
    """Check if user has access to model"""
    from modules.models.domain.models import Model
    
    model = await db.get(Model, model_id)
    if not model:
        return False
    
    return (
        user.agency_id == model.agency_id or
        user.id == model.user_id
    )