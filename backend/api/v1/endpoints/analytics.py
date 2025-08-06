"""Analytics and dashboard endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, extract
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel

from core.database import get_db
from core.redis import cached, invalidate_agency_cache, invalidate_model_cache
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model, ModelStatus
from models.chat import Conversation, ConversationStatus, Message
from models.subscriber import Subscriber, SubscriptionTier
from models.financial import Transaction, TransactionType, TransactionStatus, Payout
from core.dependencies import CurrentUser


router = APIRouter()


# Response Models
class DashboardStats(BaseModel):
    total_revenue: Decimal
    total_models: int
    active_chats: int
    total_subscribers: int
    revenue_change: float
    models_change: float
    chats_change: float
    subscribers_change: float
    recent_transactions: List[Dict[str, Any]]
    top_models: List[Dict[str, Any]]
    revenue_chart: List[Dict[str, Any]]
    platform_distribution: Dict[str, int]


class ModelStats(BaseModel):
    model_id: int
    model_name: str
    total_revenue: Decimal
    subscriber_count: int
    message_count: int
    avg_response_time: float
    conversion_rate: float
    churn_rate: float


class RevenueAnalytics(BaseModel):
    period: str
    total_revenue: Decimal
    subscription_revenue: Decimal
    tip_revenue: Decimal
    ppv_revenue: Decimal
    growth_rate: float
    daily_breakdown: List[Dict[str, Any]]
    model_breakdown: List[Dict[str, Any]]


class ChatterPerformance(BaseModel):
    chatter_id: int
    chatter_name: str
    messages_sent: int
    revenue_generated: Decimal
    avg_response_time: float
    conversion_rate: float
    active_chats: int
    satisfaction_score: float


# Helper functions
async def get_user_agency(user: User, db: AsyncSession) -> Optional[Agency]:
    """Get the agency for the current user."""
    if user.role == UserRole.SUPER_ADMIN:
        return None  # Super admin can see all data
    
    if user.agency_id:
        stmt = select(Agency).where(Agency.id == user.agency_id)
        return await db.scalar(stmt)
    
    return None


def calculate_percentage_change(current: float, previous: float) -> float:
    """Calculate percentage change between two values."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100


# Endpoints
def dashboard_cache_key(period: str, current_user: User, db: AsyncSession) -> str:
    """Generate cache key for dashboard stats."""
    agency_id = current_user.agency_id or "all"
    return f"dashboard:{agency_id}:{period}"


@router.get("/dashboard", response_model=DashboardStats)
@cached(expire=300, prefix="analytics", key_func=dashboard_cache_key)  # Cache for 5 minutes
async def get_dashboard_stats(
    period: str = Query("week", pattern="^(day|week|month|year)$"),
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for the current user's agency."""
    # Determine time range
    now = datetime.utcnow()
    if period == "day":
        start_date = now - timedelta(days=1)
        previous_start = start_date - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(days=7)
        previous_start = start_date - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
        previous_start = start_date - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
        previous_start = start_date - timedelta(days=365)
    
    # Build base query filter
    agency = await get_user_agency(current_user, db)
    if agency:
        agency_filter = Transaction.agency_id == agency.id
        model_filter = Model.agency_id == agency.id
    else:
        agency_filter = True  # No filter for super admin
        model_filter = True
    
    # Get current period stats
    # Total revenue
    revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            agency_filter,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= start_date
        )
    )
    total_revenue = await db.scalar(revenue_stmt) or Decimal('0')
    
    # Previous period revenue
    prev_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            agency_filter,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= previous_start,
            Transaction.created_at < start_date
        )
    )
    prev_revenue = await db.scalar(prev_revenue_stmt) or Decimal('0')
    
    # Total models
    models_stmt = select(func.count(Model.id)).where(
        and_(model_filter, Model.status == ModelStatus.ACTIVE)
    )
    total_models = await db.scalar(models_stmt) or 0
    
    # Previous period models
    prev_models_stmt = select(func.count(Model.id)).where(
        and_(
            model_filter,
            Model.status == ModelStatus.ACTIVE,
            Model.created_at < start_date
        )
    )
    prev_models = await db.scalar(prev_models_stmt) or 0
    
    # Active chats
    chats_stmt = select(func.count(Conversation.id)).where(
        and_(
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.model_id.in_(
                select(Model.id).where(model_filter)
            )
        )
    )
    active_chats = await db.scalar(chats_stmt) or 0
    
    # Previous period chats
    prev_chats_stmt = select(func.count(Conversation.id)).where(
        and_(
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.created_at < start_date,
            Conversation.model_id.in_(
                select(Model.id).where(model_filter)
            )
        )
    )
    prev_chats = await db.scalar(prev_chats_stmt) or 0
    
    # Total subscribers
    subs_stmt = select(func.count(func.distinct(Subscriber.id))).where(
        and_(
            Subscriber.is_active == True,
            Subscriber.model_id.in_(
                select(Model.id).where(model_filter)
            )
        )
    )
    total_subscribers = await db.scalar(subs_stmt) or 0
    
    # Previous period subscribers
    prev_subs_stmt = select(func.count(func.distinct(Subscriber.id))).where(
        and_(
            Subscriber.is_active == True,
            Subscriber.created_at < start_date,
            Subscriber.model_id.in_(
                select(Model.id).where(model_filter)
            )
        )
    )
    prev_subscribers = await db.scalar(prev_subs_stmt) or 0
    
    # Calculate percentage changes
    revenue_change = calculate_percentage_change(float(total_revenue), float(prev_revenue))
    models_change = calculate_percentage_change(total_models, prev_models)
    chats_change = calculate_percentage_change(active_chats, prev_chats)
    subscribers_change = calculate_percentage_change(total_subscribers, prev_subscribers)
    
    # Get recent transactions
    recent_trans_stmt = select(Transaction).where(
        and_(
            agency_filter,
            Transaction.status == TransactionStatus.COMPLETED
        )
    ).order_by(Transaction.created_at.desc()).limit(10)
    
    recent_transactions_result = await db.execute(recent_trans_stmt)
    recent_transactions = []
    for trans in recent_transactions_result.scalars():
        # Get model name
        model_stmt = select(Model.stage_name).where(Model.id == trans.model_id)
        model_name = await db.scalar(model_stmt) or "Unknown"
        
        recent_transactions.append({
            "id": trans.id,
            "amount": float(trans.gross_amount),
            "type": trans.type.value,
            "model_name": model_name,
            "created_at": trans.created_at.isoformat()
        })
    
    # Get top models by revenue
    top_models_stmt = select(
        Model.id,
        Model.stage_name,
        Model.profile_photo_url,
        func.coalesce(func.sum(Transaction.gross_amount), 0).label('revenue')
    ).join(
        Transaction, Transaction.model_id == Model.id
    ).where(
        and_(
            model_filter,
            Model.status == ModelStatus.ACTIVE,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= start_date
        )
    ).group_by(Model.id, Model.stage_name, Model.profile_photo_url
    ).order_by(func.sum(Transaction.gross_amount).desc()
    ).limit(5)
    
    top_models_result = await db.execute(top_models_stmt)
    top_models = []
    for row in top_models_result:
        top_models.append({
            "id": row.id,
            "name": row.stage_name,
            "avatar": row.profile_photo_url,
            "revenue": float(row.revenue)
        })
    
    # Get revenue chart data (last 7 days)
    revenue_chart = []
    for i in range(7):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
            and_(
                agency_filter,
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end
            )
        )
        day_revenue = await db.scalar(day_revenue_stmt) or 0
        
        revenue_chart.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "revenue": float(day_revenue)
        })
    
    revenue_chart.reverse()
    
    # Get platform distribution
    platform_stmt = select(
        Model.platform,
        func.count(Model.id)
    ).where(
        and_(model_filter, Model.status == ModelStatus.ACTIVE)
    ).group_by(Model.platform)
    
    platform_result = await db.execute(platform_stmt)
    platform_distribution = {}
    for row in platform_result:
        if row[0]:  # platform might be None
            platform_distribution[row[0].value] = row[1]
    
    return DashboardStats(
        total_revenue=total_revenue,
        total_models=total_models,
        active_chats=active_chats,
        total_subscribers=total_subscribers,
        revenue_change=revenue_change,
        models_change=models_change,
        chats_change=chats_change,
        subscribers_change=subscribers_change,
        recent_transactions=recent_transactions,
        top_models=top_models,
        revenue_chart=revenue_chart,
        platform_distribution=platform_distribution
    )


@router.get("/revenue", response_model=RevenueAnalytics)
async def get_revenue_analytics(
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    model_id: Optional[int] = None,
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed revenue analytics."""
    # Determine time range
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
        previous_start = start_date - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
        previous_start = start_date - timedelta(days=30)
    elif period == "quarter":
        start_date = now - timedelta(days=90)
        previous_start = start_date - timedelta(days=90)
    else:  # year
        start_date = now - timedelta(days=365)
        previous_start = start_date - timedelta(days=365)
    
    # Build filters
    agency = await get_user_agency(current_user, db)
    filters = [
        Transaction.status == TransactionStatus.COMPLETED,
        Transaction.created_at >= start_date
    ]
    
    if agency:
        filters.append(Transaction.agency_id == agency.id)
    
    if model_id:
        filters.append(Transaction.model_id == model_id)
    
    # Get total revenue by type
    revenue_by_type_stmt = select(
        Transaction.type,
        func.coalesce(func.sum(Transaction.gross_amount), 0).label('amount')
    ).where(and_(*filters)).group_by(Transaction.type)
    
    revenue_by_type_result = await db.execute(revenue_by_type_stmt)
    
    total_revenue = Decimal('0')
    subscription_revenue = Decimal('0')
    tip_revenue = Decimal('0')
    ppv_revenue = Decimal('0')
    
    for row in revenue_by_type_result:
        amount = row.amount
        total_revenue += amount
        
        if row.type == TransactionType.SUBSCRIPTION:
            subscription_revenue = amount
        elif row.type == TransactionType.TIP:
            tip_revenue = amount
        elif row.type == TransactionType.PPV_UNLOCK:
            ppv_revenue = amount
    
    # Get previous period total
    prev_filters = [
        Transaction.status == TransactionStatus.COMPLETED,
        Transaction.created_at >= previous_start,
        Transaction.created_at < start_date
    ]
    
    if agency:
        prev_filters.append(Transaction.agency_id == agency.id)
    
    if model_id:
        prev_filters.append(Transaction.model_id == model_id)
    
    prev_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(*prev_filters)
    )
    prev_total = await db.scalar(prev_revenue_stmt) or Decimal('0')
    
    growth_rate = calculate_percentage_change(float(total_revenue), float(prev_total))
    
    # Get daily breakdown
    daily_breakdown = []
    days = 30 if period == "month" else 7 if period == "week" else 90 if period == "quarter" else 365
    
    for i in range(min(days, 30)):  # Limit to 30 days for performance
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_filters = filters + [
            Transaction.created_at >= day_start,
            Transaction.created_at < day_end
        ]
        
        day_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
            and_(*day_filters)
        )
        day_revenue = await db.scalar(day_revenue_stmt) or 0
        
        daily_breakdown.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "revenue": float(day_revenue)
        })
    
    daily_breakdown.reverse()
    
    # Get model breakdown (top 10)
    model_filters = [
        Transaction.status == TransactionStatus.COMPLETED,
        Transaction.created_at >= start_date
    ]
    
    if agency:
        model_filters.append(Transaction.agency_id == agency.id)
    
    model_breakdown_stmt = select(
        Model.id,
        Model.stage_name,
        func.coalesce(func.sum(Transaction.gross_amount), 0).label('revenue')
    ).join(
        Model, Model.id == Transaction.model_id
    ).where(
        and_(*model_filters)
    ).group_by(Model.id, Model.stage_name
    ).order_by(func.sum(Transaction.gross_amount).desc()
    ).limit(10)
    
    model_breakdown_result = await db.execute(model_breakdown_stmt)
    model_breakdown = []
    
    for row in model_breakdown_result:
        model_breakdown.append({
            "model_id": row.id,
            "model_name": row.stage_name,
            "revenue": float(row.revenue)
        })
    
    return RevenueAnalytics(
        period=period,
        total_revenue=total_revenue,
        subscription_revenue=subscription_revenue,
        tip_revenue=tip_revenue,
        ppv_revenue=ppv_revenue,
        growth_rate=growth_rate,
        daily_breakdown=daily_breakdown,
        model_breakdown=model_breakdown
    )


@router.get("/models/{model_id}/stats", response_model=ModelStats)
async def get_model_stats(
    model_id: int,
    period: str = Query("month", pattern="^(week|month|year)$"),
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed statistics for a specific model."""
    # Check access
    agency = await get_user_agency(current_user, db)
    
    # Get model
    model_stmt = select(Model).where(Model.id == model_id)
    if agency:
        model_stmt = model_stmt.where(Model.agency_id == agency.id)
    
    model = await db.scalar(model_stmt)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Determine time range
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    # Get total revenue
    revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.model_id == model_id,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= start_date
        )
    )
    total_revenue = await db.scalar(revenue_stmt) or Decimal('0')
    
    # Get subscriber count
    sub_count_stmt = select(func.count(Subscriber.id)).where(
        and_(
            Subscriber.model_id == model_id,
            Subscriber.is_active == True
        )
    )
    subscriber_count = await db.scalar(sub_count_stmt) or 0
    
    # Get message count
    msg_count_stmt = select(func.count(Message.id)).where(
        and_(
            Message.sender_id == model.user_id,
            Message.created_at >= start_date
        )
    )
    message_count = await db.scalar(msg_count_stmt) or 0
    
    # Calculate average response time (simplified - would need more complex query in production)
    avg_response_time = 5.2  # Mock data
    
    # Calculate conversion rate (new subscribers / total visitors)
    new_subs_stmt = select(func.count(Subscriber.id)).where(
        and_(
            Subscriber.model_id == model_id,
            Subscriber.created_at >= start_date
        )
    )
    new_subs = await db.scalar(new_subs_stmt) or 0
    
    # Mock visitor count (would come from analytics in production)
    visitor_count = new_subs * 10 if new_subs > 0 else 100
    conversion_rate = (new_subs / visitor_count * 100) if visitor_count > 0 else 0
    
    # Calculate churn rate
    churned_subs_stmt = select(func.count(Subscriber.id)).where(
        and_(
            Subscriber.model_id == model_id,
            Subscriber.is_active == False,
            Subscriber.updated_at >= start_date
        )
    )
    churned_subs = await db.scalar(churned_subs_stmt) or 0
    
    churn_rate = (churned_subs / subscriber_count * 100) if subscriber_count > 0 else 0
    
    return ModelStats(
        model_id=model.id,
        model_name=model.stage_name,
        total_revenue=total_revenue,
        subscriber_count=subscriber_count,
        message_count=message_count,
        avg_response_time=avg_response_time,
        conversion_rate=conversion_rate,
        churn_rate=churn_rate
    )


@router.get("/chatters/performance", response_model=List[ChatterPerformance])
async def get_chatter_performance(
    period: str = Query("month", pattern="^(week|month|year)$"),
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get performance metrics for all chatters in the agency."""
    try:
        # Check access
        agency = await get_user_agency(current_user, db)
        
        # Get chatters
        chatter_filters = [User.role == UserRole.CHATTER]
        if agency:
            chatter_filters.append(User.agency_id == agency.id)
        
        chatters_stmt = select(User).where(and_(*chatter_filters))
        chatters_result = await db.execute(chatters_stmt)
        
        # Determine time range
        now = datetime.utcnow()
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        performance_data = []
        
        for chatter in chatters_result.scalars():
            # Get messages sent
            msg_stmt = select(func.count(Message.id)).where(
                and_(
                    Message.sender_id == chatter.id,
                    Message.created_at >= start_date
                )
            )
            messages_sent = await db.scalar(msg_stmt) or 0
            
            # Get revenue generated (from chats managed by this chatter)
            try:
                revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).select_from(
                    Transaction
                ).join(
                    Conversation, Conversation.id == Transaction.conversation_id, isouter=True
                ).where(
                    and_(
                        Conversation.assigned_chatter_id == chatter.id,
                        Transaction.status == TransactionStatus.COMPLETED,
                        Transaction.created_at >= start_date
                    )
                )
                revenue_generated = await db.scalar(revenue_stmt) or Decimal('0')
            except Exception as e:
                # If join fails, default to 0
                revenue_generated = Decimal('0')
            
            # Get active chats
            active_chats_stmt = select(func.count(Conversation.id)).where(
                and_(
                    Conversation.assigned_chatter_id == chatter.id,
                    Conversation.status == ConversationStatus.ACTIVE
                )
            )
            active_chats = await db.scalar(active_chats_stmt) or 0
            
            # Mock data for metrics that would require more complex calculations
            avg_response_time = 3.5  # minutes
            conversion_rate = 15.5  # percentage
            satisfaction_score = 4.2  # out of 5
            
            performance_data.append(ChatterPerformance(
                chatter_id=chatter.id,
                chatter_name=f"{chatter.first_name} {chatter.last_name}",
                messages_sent=messages_sent,
                revenue_generated=revenue_generated,
                avg_response_time=avg_response_time,
                conversion_rate=conversion_rate,
                active_chats=active_chats,
                satisfaction_score=satisfaction_score
            ))
        
        # Sort by revenue generated
        performance_data.sort(key=lambda x: x.revenue_generated, reverse=True)
        
        return performance_data
    except Exception as e:
        # Log the error and return empty list
        print(f"Error in get_chatter_performance: {str(e)}")
        return []