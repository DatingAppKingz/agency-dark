"""Background tasks for cache management."""

from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.celery_app import celery_app
from core.database_sync import get_db_sync
from core.cache_manager import cache_manager, CacheTag
from core.logger import get_logger
from services.cache_warmup import CacheWarmupService

logger = get_logger(__name__)


@celery_app.task(name="cache_warmup")
def cache_warmup_task():
    """Periodic cache warmup task."""
    try:
        logger.info("Starting scheduled cache warmup")
        
        with get_db_sync() as db:
            service = CacheWarmupService(db)
            
            # Run warmup tasks
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(service.warmup_all())
            
            logger.info("Cache warmup completed successfully")
            return {"status": "success", "result": result}
            
    except Exception as e:
        logger.error(f"Cache warmup failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="cache_cleanup")
def cache_cleanup_task():
    """Clean up expired cache entries and optimize memory."""
    try:
        logger.info("Starting cache cleanup")
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get cache stats before cleanup
        stats_before = loop.run_until_complete(cache_manager.get_stats())
        
        # Redis handles expiration automatically, but we can clean up patterns
        patterns_to_clean = [
            "search:*",  # Clear old search results
            "paginated:*",  # Clear old paginated results
            "api:*:temp:*",  # Clear temporary API cache
        ]
        
        total_cleaned = 0
        for pattern in patterns_to_clean:
            count = loop.run_until_complete(
                cache_manager.invalidate_pattern(pattern)
            )
            total_cleaned += count
        
        # Get cache stats after cleanup
        stats_after = loop.run_until_complete(cache_manager.get_stats())
        
        logger.info(f"Cache cleanup completed. Cleaned {total_cleaned} entries")
        
        return {
            "status": "success",
            "cleaned_entries": total_cleaned,
            "stats_before": stats_before,
            "stats_after": stats_after
        }
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="invalidate_user_cache")
def invalidate_user_cache_task(user_id: str):
    """Invalidate all cache entries for a specific user."""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        count = loop.run_until_complete(
            cache_manager.invalidate_by_tag(f"user:{user_id}")
        )
        
        logger.info(f"Invalidated {count} cache entries for user {user_id}")
        return {"status": "success", "invalidated": count}
        
    except Exception as e:
        logger.error(f"Failed to invalidate user cache: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="invalidate_model_cache")
def invalidate_model_cache_task(model_id: str):
    """Invalidate all cache entries for a specific model."""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        count = loop.run_until_complete(
            cache_manager.invalidate_by_tag(f"model:{model_id}")
        )
        
        logger.info(f"Invalidated {count} cache entries for model {model_id}")
        return {"status": "success", "invalidated": count}
        
    except Exception as e:
        logger.error(f"Failed to invalidate model cache: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="precompute_analytics")
def precompute_analytics_task(date: str = None):
    """Precompute and cache analytics data."""
    try:
        logger.info(f"Precomputing analytics for date: {date or 'today'}")
        
        target_date = datetime.fromisoformat(date) if date else datetime.utcnow().date()
        
        with get_db_sync() as db:
            from sqlalchemy import select, func, and_
            from models.financial import Transaction
            from models.chat import Message
            from models.model import Model
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Compute hourly aggregates
            for hour in range(24):
                hour_start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
                hour_end = hour_start + timedelta(hours=1)
                
                # Transaction volume
                result = db.execute(
                    select(
                        func.count(Transaction.id),
                        func.sum(Transaction.amount),
                        func.avg(Transaction.amount)
                    )
                    .where(
                        and_(
                            Transaction.created_at >= hour_start,
                            Transaction.created_at < hour_end
                        )
                    )
                )
                tx_count, tx_sum, tx_avg = result.one()
                
                # Message volume
                result = db.execute(
                    select(func.count(Message.id))
                    .where(
                        and_(
                            Message.created_at >= hour_start,
                            Message.created_at < hour_end
                        )
                    )
                )
                msg_count = result.scalar() or 0
                
                # Cache the aggregate
                cache_key = f"analytics:hourly:{target_date.isoformat()}:{hour}"
                aggregate_data = {
                    "hour": hour,
                    "transaction_count": tx_count or 0,
                    "transaction_volume": float(tx_sum) if tx_sum else 0,
                    "transaction_avg": float(tx_avg) if tx_avg else 0,
                    "message_count": msg_count,
                    "computed_at": datetime.utcnow().isoformat()
                }
                
                loop.run_until_complete(
                    cache_manager.set(
                        cache_key,
                        aggregate_data,
                        namespace="analytics",
                        ttl=86400 * 7,  # Cache for 7 days
                        tags=[CacheTag.ANALYTICS, "analytics:hourly"]
                    )
                )
            
            # Compute daily summary
            daily_result = db.execute(
                select(
                    func.count(Transaction.id),
                    func.sum(Transaction.amount),
                    func.count(func.distinct(Transaction.model_id))
                )
                .where(
                    and_(
                        Transaction.created_at >= target_date,
                        Transaction.created_at < target_date + timedelta(days=1)
                    )
                )
            )
            daily_tx_count, daily_revenue, active_models = daily_result.one()
            
            daily_summary = {
                "date": target_date.isoformat(),
                "transaction_count": daily_tx_count or 0,
                "revenue": float(daily_revenue) if daily_revenue else 0,
                "active_models": active_models or 0,
                "computed_at": datetime.utcnow().isoformat()
            }
            
            loop.run_until_complete(
                cache_manager.set(
                    f"analytics:daily:{target_date.isoformat()}",
                    daily_summary,
                    namespace="analytics",
                    ttl=86400 * 30,  # Cache for 30 days
                    tags=[CacheTag.ANALYTICS, "analytics:daily"]
                )
            )
            
            logger.info(f"Analytics precomputation completed for {target_date}")
            return {"status": "success", "date": target_date.isoformat()}
            
    except Exception as e:
        logger.error(f"Analytics precomputation failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="cache_health_check")
def cache_health_check_task():
    """Check cache health and performance."""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get cache statistics
        stats = loop.run_until_complete(cache_manager.get_stats())
        
        # Calculate hit rate if available
        if stats.get('redis_info'):
            hits = stats['redis_info'].get('keyspace_hits', 0)
            misses = stats['redis_info'].get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            stats['hit_rate'] = f"{hit_rate:.2f}%"
        
        # Check memory usage
        memory_warning = False
        if stats.get('redis_info', {}).get('used_memory_human'):
            memory_str = stats['redis_info']['used_memory_human']
            memory_value = float(memory_str.rstrip('GMK'))
            if 'G' in memory_str and memory_value > 1:  # More than 1GB
                memory_warning = True
        
        stats['memory_warning'] = memory_warning
        
        logger.info(f"Cache health check completed: {stats}")
        return {"status": "success", "stats": stats}
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {"status": "error", "error": str(e)}