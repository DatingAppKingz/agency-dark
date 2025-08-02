"""
Background tasks for materialized view maintenance
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db
from core.database_utils.materialized_views import materialized_view_manager
from core.logging import get_logger
from core.celery_app import celery_app
from core.redis import redis_client

logger = get_logger(__name__)


class MaterializedViewRefreshScheduler:
    """Manages scheduled refresh of materialized views"""
    
    def __init__(self):
        self.refresh_intervals = {
            "mv_analytics_hourly_rollup": timedelta(minutes=15),
            "mv_model_performance_daily": timedelta(hours=1),
            "mv_model_performance_monthly": timedelta(hours=6),
            "mv_agency_dashboard_metrics": timedelta(minutes=30),
            "mv_top_performers": timedelta(hours=2),
            "mv_financial_summary": timedelta(minutes=30),
            "mv_model_engagement_scores": timedelta(hours=1)
        }
        self.last_refresh_times = {}
        self.refresh_stats = {}
    
    async def should_refresh(self, view_name: str) -> bool:
        """Check if a view needs refreshing"""
        # Get last refresh time from Redis
        last_refresh_key = f"mv_refresh:{view_name}:last"
        last_refresh_str = await redis_client.get(last_refresh_key)
        
        if not last_refresh_str:
            return True
        
        try:
            last_refresh = datetime.fromisoformat(last_refresh_str)
            interval = self.refresh_intervals.get(view_name, timedelta(hours=2))
            
            return datetime.utcnow() - last_refresh >= interval
        except:
            return True
    
    async def record_refresh(self, view_name: str, duration: float, success: bool):
        """Record refresh statistics"""
        # Store last refresh time
        last_refresh_key = f"mv_refresh:{view_name}:last"
        await redis_client.set(last_refresh_key, datetime.utcnow().isoformat())
        
        # Store refresh stats
        stats_key = f"mv_refresh:{view_name}:stats"
        stats = {
            "last_refresh": datetime.utcnow().isoformat(),
            "duration_seconds": duration,
            "success": success,
            "refresh_count": await self._increment_refresh_count(view_name)
        }
        
        await redis_client.setex(
            stats_key,
            86400 * 7,  # Keep stats for 7 days
            json.dumps(stats)
        )
    
    async def _increment_refresh_count(self, view_name: str) -> int:
        """Increment and return refresh count"""
        count_key = f"mv_refresh:{view_name}:count"
        count = await redis_client.incr(count_key)
        
        # Reset counter monthly
        await redis_client.expire(count_key, 86400 * 30)
        
        return count
    
    async def refresh_views_batch(self, db: AsyncSession, view_names: List[str]):
        """Refresh a batch of views concurrently"""
        tasks = []
        
        for view_name in view_names:
            if await self.should_refresh(view_name):
                tasks.append(self._refresh_single_view(db, view_name))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log results
            for view_name, result in zip(view_names, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to refresh {view_name}: {result}")
                else:
                    logger.info(f"Successfully refreshed {view_name}")
    
    async def _refresh_single_view(self, db: AsyncSession, view_name: str):
        """Refresh a single view with monitoring"""
        start_time = datetime.utcnow()
        success = False
        
        try:
            # Check if view exists
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews 
                    WHERE matviewname = :view_name
                )
            """)
            result = await db.execute(check_query, {"view_name": view_name})
            
            if not result.scalar():
                logger.warning(f"Materialized view {view_name} does not exist")
                return
            
            # Refresh the view
            await materialized_view_manager.refresh_view(
                db, 
                view_name.replace("mv_", ""), 
                concurrent=True
            )
            
            success = True
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Record statistics
            await self.record_refresh(view_name, duration, success)
            
            # Log slow refreshes
            if duration > 60:
                logger.warning(f"Slow refresh for {view_name}: {duration:.2f} seconds")
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self.record_refresh(view_name, duration, False)
            raise


# Global scheduler instance
refresh_scheduler = MaterializedViewRefreshScheduler()


# Celery tasks
@celery_app.task(name="refresh_materialized_views_fast")
def refresh_fast_views():
    """Refresh views that need frequent updates (15-30 min intervals)"""
    async def _refresh():
        async with get_db() as db:
            fast_views = [
                "mv_analytics_hourly_rollup",
                "mv_agency_dashboard_metrics",
                "mv_financial_summary"
            ]
            await refresh_scheduler.refresh_views_batch(db, fast_views)
    
    asyncio.run(_refresh())


@celery_app.task(name="refresh_materialized_views_medium")
def refresh_medium_views():
    """Refresh views with medium update frequency (1-2 hour intervals)"""
    async def _refresh():
        async with get_db() as db:
            medium_views = [
                "mv_model_performance_daily",
                "mv_model_engagement_scores",
                "mv_top_performers"
            ]
            await refresh_scheduler.refresh_views_batch(db, medium_views)
    
    asyncio.run(_refresh())


@celery_app.task(name="refresh_materialized_views_slow")
def refresh_slow_views():
    """Refresh views with low update frequency (6+ hour intervals)"""
    async def _refresh():
        async with get_db() as db:
            slow_views = [
                "mv_model_performance_monthly"
            ]
            await refresh_scheduler.refresh_views_batch(db, slow_views)
    
    asyncio.run(_refresh())


@celery_app.task(name="analyze_materialized_views")
def analyze_materialized_views():
    """Analyze materialized view performance and usage"""
    async def _analyze():
        async with get_db() as db:
            # Get view sizes and refresh times
            size_query = text("""
                SELECT 
                    matviewname,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||matviewname)) as size,
                    pg_relation_size(schemaname||'.'||matviewname) as size_bytes
                FROM pg_matviews
                WHERE schemaname = 'public'
                ORDER BY pg_relation_size(schemaname||'.'||matviewname) DESC
            """)
            
            result = await db.execute(size_query)
            
            analysis = {
                "timestamp": datetime.utcnow().isoformat(),
                "views": []
            }
            
            for row in result:
                view_name = row.matviewname
                
                # Get refresh stats from Redis
                stats_key = f"mv_refresh:{view_name}:stats"
                stats_str = await redis_client.get(stats_key)
                stats = json.loads(stats_str) if stats_str else {}
                
                # Get query performance
                perf_query = text("""
                    SELECT 
                        calls,
                        mean_exec_time,
                        total_exec_time
                    FROM pg_stat_user_tables
                    WHERE relname = :view_name
                """)
                
                perf_result = await db.execute(perf_query, {"view_name": view_name})
                perf_row = perf_result.first()
                
                view_analysis = {
                    "name": view_name,
                    "size": row.size,
                    "size_bytes": row.size_bytes,
                    "last_refresh": stats.get("last_refresh"),
                    "refresh_duration": stats.get("duration_seconds"),
                    "refresh_count": stats.get("refresh_count", 0),
                    "query_calls": perf_row.calls if perf_row else 0,
                    "avg_query_time": perf_row.mean_exec_time if perf_row else 0
                }
                
                # Calculate efficiency score
                if view_analysis["refresh_count"] > 0 and view_analysis["query_calls"] > 0:
                    # Higher score = more efficient (many queries, few refreshes)
                    efficiency_score = (
                        view_analysis["query_calls"] / 
                        (view_analysis["refresh_count"] * view_analysis["refresh_duration"])
                    )
                    view_analysis["efficiency_score"] = round(efficiency_score, 2)
                else:
                    view_analysis["efficiency_score"] = 0
                
                analysis["views"].append(view_analysis)
            
            # Store analysis
            await redis_client.setex(
                "mv_analysis:latest",
                86400,  # Keep for 24 hours
                json.dumps(analysis)
            )
            
            # Generate recommendations
            recommendations = []
            for view in analysis["views"]:
                if view["efficiency_score"] < 1:
                    recommendations.append({
                        "view": view["name"],
                        "issue": "low_efficiency",
                        "recommendation": f"View {view['name']} has low query-to-refresh ratio. Consider reducing refresh frequency."
                    })
                
                if view["size_bytes"] > 1073741824:  # 1GB
                    recommendations.append({
                        "view": view["name"],
                        "issue": "large_size",
                        "recommendation": f"View {view['name']} is {view['size']}. Consider partitioning or filtering old data."
                    })
                
                if view["refresh_duration"] and view["refresh_duration"] > 300:  # 5 minutes
                    recommendations.append({
                        "view": view["name"],
                        "issue": "slow_refresh",
                        "recommendation": f"View {view['name']} takes {view['refresh_duration']}s to refresh. Optimize the underlying query."
                    })
            
            analysis["recommendations"] = recommendations
            
            # Store final analysis
            await redis_client.setex(
                "mv_analysis:latest",
                86400,
                json.dumps(analysis)
            )
            
            logger.info(f"Materialized view analysis completed. Found {len(recommendations)} recommendations.")
            
            return analysis
    
    return asyncio.run(_analyze())


@celery_app.task(name="cleanup_stale_views")
def cleanup_stale_views():
    """Clean up stale or unused materialized views"""
    async def _cleanup():
        async with get_db() as db:
            # Find views not accessed in 30 days
            stale_query = text("""
                SELECT 
                    mv.matviewname,
                    s.last_vacuum,
                    s.last_analyze,
                    s.n_tup_ins + s.n_tup_upd + s.n_tup_del as write_activity
                FROM pg_matviews mv
                LEFT JOIN pg_stat_user_tables s ON mv.matviewname = s.relname
                WHERE mv.schemaname = 'public'
                    AND (s.last_vacuum < CURRENT_DATE - INTERVAL '30 days' 
                         OR s.last_vacuum IS NULL)
                    AND (s.last_analyze < CURRENT_DATE - INTERVAL '30 days'
                         OR s.last_analyze IS NULL)
            """)
            
            result = await db.execute(stale_query)
            
            stale_views = []
            for row in result:
                # Check if view is in our managed list
                if row.matviewname not in [v.name for v in materialized_view_manager.views.values()]:
                    stale_views.append({
                        "name": row.matviewname,
                        "last_vacuum": row.last_vacuum,
                        "last_analyze": row.last_analyze,
                        "write_activity": row.write_activity
                    })
            
            if stale_views:
                logger.warning(f"Found {len(stale_views)} potentially stale views: {[v['name'] for v in stale_views]}")
            
            return stale_views
    
    return asyncio.run(_cleanup())


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule.update({
    'refresh-fast-views': {
        'task': 'refresh_materialized_views_fast',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'refresh-medium-views': {
        'task': 'refresh_materialized_views_medium',
        'schedule': crontab(minute='0'),  # Every hour
    },
    'refresh-slow-views': {
        'task': 'refresh_materialized_views_slow',
        'schedule': crontab(hour='*/6', minute='0'),  # Every 6 hours
    },
    'analyze-materialized-views': {
        'task': 'analyze_materialized_views',
        'schedule': crontab(hour='3', minute='0'),  # Daily at 3 AM
    },
    'cleanup-stale-views': {
        'task': 'cleanup_stale_views',
        'schedule': crontab(day_of_week=0, hour='4', minute='0'),  # Weekly on Sunday at 4 AM
    },
})


# Manual execution functions
async def force_refresh_all_views():
    """Force refresh all materialized views"""
    async with get_db() as db:
        results = await materialized_view_manager.refresh_all_views(db)
        
        # Update Redis with refresh times
        for view_name, duration in results.items():
            if duration is not None:
                await refresh_scheduler.record_refresh(f"mv_{view_name}", duration, True)
        
        return results


async def get_refresh_status() -> Dict[str, Any]:
    """Get current refresh status for all views"""
    status = {
        "views": {},
        "next_refresh_times": {}
    }
    
    for view_name in refresh_scheduler.refresh_intervals.keys():
        # Get last refresh info
        stats_key = f"mv_refresh:{view_name}:stats"
        stats_str = await redis_client.get(stats_key)
        
        if stats_str:
            stats = json.loads(stats_str)
            status["views"][view_name] = stats
            
            # Calculate next refresh time
            if stats.get("last_refresh"):
                last_refresh = datetime.fromisoformat(stats["last_refresh"])
                interval = refresh_scheduler.refresh_intervals[view_name]
                next_refresh = last_refresh + interval
                status["next_refresh_times"][view_name] = next_refresh.isoformat()
        else:
            status["views"][view_name] = {"status": "never_refreshed"}
    
    return status