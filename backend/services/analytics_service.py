"""Analytics service with advanced caching."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from core.cache_decorators import cache_analytics, cached_result, cache_computation
from core.cache_manager import cache_manager, CacheTag
from core.logger import get_logger
from models.user import User
from models.model import Model
from models.transaction import Transaction, TransactionType
from models.message import Message
from models.agency import Agency

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics with intelligent caching."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @cache_analytics(ttl=900, granularity="hour")
    async def get_hourly_metrics(
        self,
        agency_id: int,
        date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get hourly metrics with caching."""
        target_date = date or datetime.utcnow().date()
        metrics = []
        
        for hour in range(24):
            hour_start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
            hour_end = hour_start + timedelta(hours=1)
            
            # Try to get from cache first
            cache_key = f"analytics:hourly:{agency_id}:{target_date.isoformat()}:{hour}"
            cached = await cache_manager.get(cache_key, "analytics")
            
            if cached:
                metrics.append(cached)
            else:
                # Compute metrics
                metric = await self._compute_hourly_metrics(
                    agency_id,
                    hour_start,
                    hour_end
                )
                
                # Cache the result
                await cache_manager.set(
                    cache_key,
                    metric,
                    namespace="analytics",
                    ttl=3600 if target_date == datetime.utcnow().date() else 86400,
                    tags=[CacheTag.ANALYTICS, f"agency:{agency_id}"]
                )
                
                metrics.append(metric)
        
        return metrics
    
    @cached_result(ttl=300, namespace="analytics", tags=[CacheTag.ANALYTICS])
    async def get_dashboard_stats(self, agency_id: int) -> Dict[str, Any]:
        """Get dashboard statistics with caching."""
        today = datetime.utcnow().date()
        
        # Get today's revenue
        result = await self.db.execute(
            select(func.sum(Transaction.amount))
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Transaction.created_at >= today,
                    Transaction.status == "completed"
                )
            )
        )
        today_revenue = result.scalar() or 0
        
        # Get active models count
        result = await self.db.execute(
            select(func.count(Model.id))
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Model.is_active == True
                )
            )
        )
        active_models = result.scalar() or 0
        
        # Get total fans
        result = await self.db.execute(
            select(func.sum(Model.total_fans))
            .where(Model.agency_id == agency_id)
        )
        total_fans = result.scalar() or 0
        
        # Get new messages count
        result = await self.db.execute(
            select(func.count(Message.id))
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Message.created_at >= today,
                    Message.is_read == False
                )
            )
        )
        new_messages = result.scalar() or 0
        
        return {
            "today_revenue": float(today_revenue),
            "active_models": active_models,
            "total_fans": total_fans,
            "new_messages": new_messages,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @cache_computation(ttl=1800, max_size=5000)
    async def get_revenue_breakdown(
        self,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get revenue breakdown with computation caching."""
        # Get transactions in date range
        result = await self.db.execute(
            select(
                Transaction.type,
                func.count(Transaction.id),
                func.sum(Transaction.amount)
            )
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Transaction.created_at >= start_date,
                    Transaction.created_at <= end_date,
                    Transaction.status == "completed"
                )
            )
            .group_by(Transaction.type)
        )
        
        breakdown = {}
        total_revenue = 0
        
        for tx_type, count, amount in result:
            breakdown[tx_type.value] = {
                "count": count,
                "amount": float(amount) if amount else 0
            }
            total_revenue += float(amount) if amount else 0
        
        # Calculate percentages
        for tx_type in breakdown:
            amount = breakdown[tx_type]["amount"]
            breakdown[tx_type]["percentage"] = (
                (amount / total_revenue * 100) if total_revenue > 0 else 0
            )
        
        return {
            "breakdown": breakdown,
            "total_revenue": total_revenue,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    
    async def get_model_performance(
        self,
        model_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get model performance metrics."""
        # Check cache first
        cache_key = f"model:{model_id}:performance:{days}days"
        cached = await cache_manager.get(cache_key, "analytics")
        
        if cached:
            return cached
        
        # Compute performance metrics
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get revenue trend
        daily_revenue = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_start = datetime.combine(day.date(), datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            result = await self.db.execute(
                select(func.sum(Transaction.amount))
                .where(
                    and_(
                        Transaction.model_id == model_id,
                        Transaction.created_at >= day_start,
                        Transaction.created_at < day_end,
                        Transaction.status == "completed"
                    )
                )
            )
            revenue = result.scalar() or 0
            
            daily_revenue.append({
                "date": day.date().isoformat(),
                "revenue": float(revenue)
            })
        
        # Get message activity
        result = await self.db.execute(
            select(func.count(Message.id))
            .where(
                and_(
                    Message.model_id == model_id,
                    Message.created_at >= start_date
                )
            )
        )
        total_messages = result.scalar() or 0
        
        # Get fan growth
        # This is simplified - in reality you'd track fan history
        result = await self.db.execute(
            select(Model.total_fans)
            .where(Model.id == model_id)
        )
        current_fans = result.scalar() or 0
        
        performance = {
            "model_id": model_id,
            "period_days": days,
            "daily_revenue": daily_revenue,
            "total_revenue": sum(d["revenue"] for d in daily_revenue),
            "average_daily_revenue": sum(d["revenue"] for d in daily_revenue) / days,
            "total_messages": total_messages,
            "current_fans": current_fans,
            "computed_at": datetime.utcnow().isoformat()
        }
        
        # Cache the result
        await cache_manager.set(
            cache_key,
            performance,
            namespace="analytics",
            ttl=3600,  # 1 hour
            tags=[CacheTag.ANALYTICS, CacheTag.MODEL, f"model:{model_id}"]
        )
        
        return performance
    
    async def invalidate_agency_analytics(self, agency_id: int):
        """Invalidate all analytics cache for an agency."""
        count = await cache_manager.invalidate_by_tag(f"agency:{agency_id}")
        logger.info(f"Invalidated {count} analytics cache entries for agency {agency_id}")
    
    async def _compute_hourly_metrics(
        self,
        agency_id: int,
        hour_start: datetime,
        hour_end: datetime
    ) -> Dict[str, Any]:
        """Compute metrics for a specific hour."""
        # Get transaction metrics
        result = await self.db.execute(
            select(
                func.count(Transaction.id),
                func.sum(Transaction.amount),
                func.avg(Transaction.amount)
            )
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Transaction.created_at >= hour_start,
                    Transaction.created_at < hour_end,
                    Transaction.status == "completed"
                )
            )
        )
        tx_count, tx_sum, tx_avg = result.one()
        
        # Get message metrics
        result = await self.db.execute(
            select(func.count(Message.id))
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Message.created_at >= hour_start,
                    Message.created_at < hour_end
                )
            )
        )
        msg_count = result.scalar() or 0
        
        # Get active models for the hour
        result = await self.db.execute(
            select(func.count(func.distinct(Message.model_id)))
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Message.created_at >= hour_start,
                    Message.created_at < hour_end
                )
            )
        )
        active_models = result.scalar() or 0
        
        return {
            "hour": hour_start.hour,
            "timestamp": hour_start.isoformat(),
            "transactions": {
                "count": tx_count or 0,
                "volume": float(tx_sum) if tx_sum else 0,
                "average": float(tx_avg) if tx_avg else 0
            },
            "messages": {
                "count": msg_count,
                "active_models": active_models
            }
        }


# Cache warmup functions for analytics
async def warmup_analytics_cache(db: AsyncSession):
    """Warmup analytics cache with common queries."""
    service = AnalyticsService(db)
    
    # Get all active agencies
    result = await db.execute(
        select(Agency.id).where(Agency.is_active == True)
    )
    agency_ids = [row[0] for row in result]
    
    # Warmup dashboard stats for each agency
    for agency_id in agency_ids:
        try:
            await service.get_dashboard_stats(agency_id)
            logger.info(f"Warmed up dashboard stats for agency {agency_id}")
        except Exception as e:
            logger.error(f"Failed to warmup stats for agency {agency_id}: {e}")
    
    # Warmup today's hourly metrics
    today = datetime.utcnow().date()
    for agency_id in agency_ids[:10]:  # Limit to first 10 agencies
        try:
            await service.get_hourly_metrics(agency_id, today)
            logger.info(f"Warmed up hourly metrics for agency {agency_id}")
        except Exception as e:
            logger.error(f"Failed to warmup hourly metrics for agency {agency_id}: {e}")