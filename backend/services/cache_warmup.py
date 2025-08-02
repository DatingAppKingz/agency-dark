"""Cache warmup service for preloading frequently accessed data."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from core.database import get_db
from core.cache_manager import cache_manager, CacheTag
from core.logger import get_logger
from models.user import User
from models.model import Model
from models.agency import Agency
from models.financial import Transaction
from models.chat import Message

logger = get_logger(__name__)


class CacheWarmupService:
    """Service for warming up cache with frequently accessed data."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def warmup_all(self):
        """Warm up all cache categories."""
        logger.info("Starting cache warmup...")
        
        warmup_tasks = [
            self.warmup_active_users(),
            self.warmup_active_models(),
            self.warmup_agency_stats(),
            self.warmup_recent_transactions(),
            self.warmup_popular_searches(),
            self.warmup_analytics_aggregates()
        ]
        
        results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
        
        # Log results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Warmup task {i} failed: {result}")
            else:
                logger.info(f"Warmup task {i} completed: {result}")
        
        logger.info("Cache warmup completed")
    
    async def warmup_active_users(self) -> Dict[str, int]:
        """Warm up cache for active users."""
        try:
            # Get users who logged in within last 24 hours
            cutoff = datetime.utcnow() - timedelta(days=1)
            
            result = await self.db.execute(
                select(User)
                .where(
                    and_(
                        User.is_active == True,
                        User.last_login_at >= cutoff
                    )
                )
                .limit(100)
            )
            
            users = result.scalars().all()
            cached_count = 0
            
            for user in users:
                # Cache user profile
                await cache_manager.set(
                    f"user:{user.id}:profile",
                    {
                        "id": str(user.id),
                        "email": user.email,
                        "username": user.username,
                        "full_name": user.full_name,
                        "role": user.role.value,
                        "agency_id": user.agency_id,
                        "language": user.language
                    },
                    namespace="users",
                    ttl=3600,
                    tags=[CacheTag.USER, f"user:{user.id}"]
                )
                
                # Cache user permissions
                await cache_manager.set(
                    f"user:{user.id}:permissions",
                    user.permissions,
                    namespace="users",
                    ttl=3600,
                    tags=[CacheTag.USER, f"user:{user.id}"]
                )
                
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} active user profiles")
            return {"active_users_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup active users: {e}")
            raise
    
    async def warmup_active_models(self) -> Dict[str, int]:
        """Warm up cache for active models."""
        try:
            # Get active models with recent activity
            result = await self.db.execute(
                select(Model)
                .where(Model.is_active == True)
                .order_by(Model.last_activity_at.desc())
                .limit(50)
            )
            
            models = result.scalars().all()
            cached_count = 0
            
            for model in models:
                # Cache model profile
                await cache_manager.set(
                    f"model:{model.id}:profile",
                    {
                        "id": str(model.id),
                        "stage_name": model.stage_name,
                        "platform": model.platform,
                        "is_active": model.is_active,
                        "total_fans": model.total_fans,
                        "total_revenue": float(model.total_revenue) if model.total_revenue else 0,
                        "commission_rate": float(model.commission_rate) if model.commission_rate else 0
                    },
                    namespace="models",
                    ttl=600,
                    tags=[CacheTag.MODEL, f"model:{model.id}"]
                )
                
                # Cache model stats
                stats = await self._get_model_stats(model.id)
                await cache_manager.set(
                    f"model:{model.id}:stats",
                    stats,
                    namespace="models",
                    ttl=900,
                    tags=[CacheTag.MODEL, f"model:{model.id}", CacheTag.ANALYTICS]
                )
                
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} active model profiles")
            return {"active_models_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup active models: {e}")
            raise
    
    async def warmup_agency_stats(self) -> Dict[str, int]:
        """Warm up cache for agency statistics."""
        try:
            # Get all active agencies
            result = await self.db.execute(
                select(Agency).where(Agency.is_active == True)
            )
            
            agencies = result.scalars().all()
            cached_count = 0
            
            for agency in agencies:
                # Cache agency dashboard stats
                stats = await self._get_agency_stats(agency.id)
                await cache_manager.set(
                    f"agency:{agency.id}:dashboard_stats",
                    stats,
                    namespace="analytics",
                    ttl=300,
                    tags=[CacheTag.AGENCY, f"agency:{agency.id}", CacheTag.ANALYTICS]
                )
                
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} agency statistics")
            return {"agency_stats_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup agency stats: {e}")
            raise
    
    async def warmup_recent_transactions(self) -> Dict[str, int]:
        """Warm up cache for recent transactions."""
        try:
            # Get transaction summaries for last 24 hours
            cutoff = datetime.utcnow() - timedelta(days=1)
            
            result = await self.db.execute(
                select(
                    Transaction.model_id,
                    func.count(Transaction.id).label('count'),
                    func.sum(Transaction.amount).label('total')
                )
                .where(Transaction.created_at >= cutoff)
                .group_by(Transaction.model_id)
                .limit(100)
            )
            
            summaries = result.all()
            cached_count = 0
            
            for model_id, count, total in summaries:
                await cache_manager.set(
                    f"transactions:{model_id}:daily_summary",
                    {
                        "count": count,
                        "total": float(total) if total else 0,
                        "date": datetime.utcnow().date().isoformat()
                    },
                    namespace="transactions",
                    ttl=3600,
                    tags=[CacheTag.TRANSACTION, f"model:{model_id}"]
                )
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} transaction summaries")
            return {"transaction_summaries_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup transactions: {e}")
            raise
    
    async def warmup_popular_searches(self) -> Dict[str, int]:
        """Warm up cache for popular search queries."""
        try:
            # In a real implementation, this would fetch from search logs
            popular_queries = [
                "active models",
                "top earners",
                "recent messages",
                "pending transactions",
                "new fans"
            ]
            
            cached_count = 0
            
            # Cache empty results for popular queries to prevent stampede
            for query in popular_queries:
                await cache_manager.set(
                    f"search:{query.replace(' ', '_')}",
                    {"results": [], "total": 0, "cached_at": datetime.utcnow().isoformat()},
                    namespace="search",
                    ttl=300,
                    tags=[CacheTag.SEARCH]
                )
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} popular search queries")
            return {"search_queries_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup searches: {e}")
            raise
    
    async def warmup_analytics_aggregates(self) -> Dict[str, int]:
        """Warm up cache for analytics aggregates."""
        try:
            cached_count = 0
            
            # Cache hourly aggregates for today
            today = datetime.utcnow().date()
            
            for hour in range(24):
                hour_start = datetime.combine(today, datetime.min.time()) + timedelta(hours=hour)
                hour_end = hour_start + timedelta(hours=1)
                
                # Get message count for the hour
                result = await self.db.execute(
                    select(func.count(Message.id))
                    .where(
                        and_(
                            Message.created_at >= hour_start,
                            Message.created_at < hour_end
                        )
                    )
                )
                message_count = result.scalar() or 0
                
                # Get transaction volume for the hour
                result = await self.db.execute(
                    select(func.sum(Transaction.amount))
                    .where(
                        and_(
                            Transaction.created_at >= hour_start,
                            Transaction.created_at < hour_end
                        )
                    )
                )
                transaction_volume = result.scalar() or 0
                
                # Cache hourly aggregate
                await cache_manager.set(
                    f"analytics:hourly:{today.isoformat()}:{hour}",
                    {
                        "hour": hour,
                        "message_count": message_count,
                        "transaction_volume": float(transaction_volume),
                        "timestamp": hour_start.isoformat()
                    },
                    namespace="analytics",
                    ttl=3600 * 24,  # Cache for 24 hours
                    tags=[CacheTag.ANALYTICS, "analytics:hourly"]
                )
                
                cached_count += 1
            
            logger.info(f"Warmed up {cached_count} analytics aggregates")
            return {"analytics_aggregates_cached": cached_count}
            
        except Exception as e:
            logger.error(f"Failed to warmup analytics: {e}")
            raise
    
    async def _get_model_stats(self, model_id: str) -> Dict[str, Any]:
        """Get model statistics."""
        # Get message count for last 24 hours
        cutoff = datetime.utcnow() - timedelta(days=1)
        
        result = await self.db.execute(
            select(func.count(Message.id))
            .where(
                and_(
                    Message.model_id == model_id,
                    Message.created_at >= cutoff
                )
            )
        )
        daily_messages = result.scalar() or 0
        
        # Get transaction stats
        result = await self.db.execute(
            select(
                func.count(Transaction.id),
                func.sum(Transaction.amount)
            )
            .where(
                and_(
                    Transaction.model_id == model_id,
                    Transaction.created_at >= cutoff
                )
            )
        )
        daily_transactions, daily_revenue = result.one()
        
        return {
            "daily_messages": daily_messages,
            "daily_transactions": daily_transactions or 0,
            "daily_revenue": float(daily_revenue) if daily_revenue else 0,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    async def _get_agency_stats(self, agency_id: int) -> Dict[str, Any]:
        """Get agency statistics."""
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
        
        # Get total revenue for today
        today = datetime.utcnow().date()
        result = await self.db.execute(
            select(func.sum(Transaction.amount))
            .join(Model)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Transaction.created_at >= today
                )
            )
        )
        today_revenue = result.scalar() or 0
        
        # Get total fans
        result = await self.db.execute(
            select(func.sum(Model.total_fans))
            .where(Model.agency_id == agency_id)
        )
        total_fans = result.scalar() or 0
        
        return {
            "active_models": active_models,
            "today_revenue": float(today_revenue),
            "total_fans": total_fans,
            "updated_at": datetime.utcnow().isoformat()
        }


async def run_cache_warmup():
    """Run cache warmup as a standalone task."""
    async for db in get_db():
        try:
            service = CacheWarmupService(db)
            await service.warmup_all()
        finally:
            await db.close()