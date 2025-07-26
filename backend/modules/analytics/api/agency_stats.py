"""
Agency-wide analytics endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from core.database import get_db
from core.dependencies import get_current_user
from core.domain.models import User, UserRole

router = APIRouter()


@router.get("/agency/dashboard-stats")
async def get_agency_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get agency-wide dashboard statistics."""
    
    # Count models in the agency
    models_result = await db.execute(
        select(func.count(User.id))
        .where(User.agency_id == current_user.agency_id)
        .where(User.role == UserRole.MODEL)
        .where(User.is_active == True)
    )
    active_models = models_result.scalar() or 0
    
    # Count chatters
    chatters_result = await db.execute(
        select(func.count(User.id))
        .where(User.agency_id == current_user.agency_id)
        .where(User.role == UserRole.CHATTER)
        .where(User.is_active == True)
    )
    active_chatters = chatters_result.scalar() or 0
    
    # Count total users
    users_result = await db.execute(
        select(func.count(User.id))
        .where(User.agency_id == current_user.agency_id)
        .where(User.is_active == True)
    )
    total_users = users_result.scalar() or 0
    
    # Count new users today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_result = await db.execute(
        select(func.count(User.id))
        .where(User.agency_id == current_user.agency_id)
        .where(User.created_at >= today_start)
    )
    new_users_today = new_users_result.scalar() or 0
    
    # Return mock data for other metrics since we don't have real data
    return {
        "total_users": total_users,
        "active_models": active_models,
        "active_chatters": active_chatters,
        "total_revenue": 15750.50,  # Mock data
        "total_messages": 3847,      # Mock data
        "new_users_today": new_users_today,
        "revenue_today": 2340.75,    # Mock data
        "messages_today": 543,       # Mock data
        "active_chats": 127,         # Mock data
        "conversion_rate": 23.5,     # Mock data
        "avg_response_time": "2m 15s" # Mock data
    }


@router.get("/agency/revenue-chart")
async def get_agency_revenue_chart(
    period: str = "month",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue chart data for the agency."""
    
    # Generate mock data for the last 30 days
    today = datetime.utcnow().date()
    data = []
    
    for i in range(30):
        date = today - timedelta(days=29-i)
        # Generate realistic looking revenue data
        base_revenue = 500 + (i * 10)  # Trending upward
        daily_variance = (i % 7) * 50  # Weekly pattern
        revenue = base_revenue + daily_variance + (300 if i % 7 == 5 else 0)  # Spike on Fridays
        
        data.append({
            "date": date.isoformat(),
            "revenue": revenue,
            "subscriptions": 20 + (i % 5),
            "tips": revenue * 0.3,
            "messages": revenue * 0.2
        })
    
    return {
        "period": period,
        "data": data,
        "summary": {
            "total": sum(d["revenue"] for d in data),
            "average": sum(d["revenue"] for d in data) / len(data),
            "growth": 15.7  # Percentage
        }
    }


@router.get("/agency/model-performance")
async def get_model_performance(
    period: str = "month",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get model performance data."""
    
    # Get models from database
    models_result = await db.execute(
        select(User)
        .where(User.agency_id == current_user.agency_id)
        .where(User.role == UserRole.MODEL)
        .limit(10)
    )
    models = models_result.scalars().all()
    
    # Generate mock performance data
    performance_data = []
    for i, model in enumerate(models):
        performance_data.append({
            "model_id": str(model.id),
            "model_name": model.full_name or f"Model {i+1}",
            "revenue": 5000 + (i * 1000),
            "messages": 500 + (i * 100),
            "fans": 100 + (i * 20),
            "conversion_rate": 20 + (i * 2),
            "growth": 10 + (i * 3)
        })
    
    # Add some mock data if no real models
    if not performance_data:
        for i in range(5):
            performance_data.append({
                "model_id": f"mock-{i}",
                "model_name": f"Model {i+1}",
                "revenue": 5000 + (i * 1000),
                "messages": 500 + (i * 100),
                "fans": 100 + (i * 20),
                "conversion_rate": 20 + (i * 2),
                "growth": 10 + (i * 3)
            })
    
    return performance_data