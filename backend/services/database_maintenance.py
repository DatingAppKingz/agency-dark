"""Database maintenance service for routine optimization tasks."""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text, select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database import engine, get_db
from core.logger import get_logger
from core.redis import redis_manager
from models.base import BaseModel

logger = get_logger(__name__)


class DatabaseMaintenanceService:
    """Service for automated database maintenance tasks."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.maintenance_history: List[Dict[str, Any]] = []
    
    async def initialize(self):
        """Initialize maintenance scheduler with tasks."""
        # Daily maintenance at 2 AM
        self.scheduler.add_job(
            self.daily_maintenance,
            CronTrigger(hour=2, minute=0),
            id="daily_maintenance",
            name="Daily Database Maintenance",
            replace_existing=True
        )
        
        # Weekly optimization on Sunday at 3 AM
        self.scheduler.add_job(
            self.weekly_optimization,
            CronTrigger(day_of_week=6, hour=3, minute=0),
            id="weekly_optimization",
            name="Weekly Database Optimization",
            replace_existing=True
        )
        
        # Hourly stats update
        self.scheduler.add_job(
            self.update_statistics,
            CronTrigger(minute=0),
            id="hourly_stats",
            name="Hourly Statistics Update",
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        logger.info("Database maintenance scheduler initialized")
    
    async def daily_maintenance(self):
        """Run daily maintenance tasks."""
        start_time = datetime.utcnow()
        results = {}
        
        try:
            async with AsyncSessionLocal() as db:
                # 1. Clean up old data
                results["cleanup"] = await self.cleanup_old_data(db)
                
                # 2. Update table statistics
                results["analyze"] = await self.analyze_tables(db)
                
                # 3. Vacuum tables with high bloat
                results["vacuum"] = await self.vacuum_tables(db)
                
                # 4. Refresh materialized views
                results["refresh_views"] = await self.refresh_materialized_views(db)
                
                # 5. Archive old messages
                results["archive"] = await self.archive_old_messages(db)
            
            # Record maintenance history
            self._record_maintenance(
                task="daily_maintenance",
                start_time=start_time,
                results=results,
                status="success"
            )
            
            logger.info(f"Daily maintenance completed: {results}")
            
        except Exception as e:
            logger.error(f"Daily maintenance failed: {e}")
            self._record_maintenance(
                task="daily_maintenance",
                start_time=start_time,
                results=results,
                status="failed",
                error=str(e)
            )
    
    async def weekly_optimization(self):
        """Run weekly optimization tasks."""
        start_time = datetime.utcnow()
        results = {}
        
        try:
            async with AsyncSessionLocal() as db:
                # 1. Reindex tables if needed
                results["reindex"] = await self.reindex_tables(db)
                
                # 2. Update query planner statistics
                results["statistics"] = await self.update_planner_statistics(db)
                
                # 3. Analyze query performance
                results["slow_queries"] = await self.analyze_slow_queries(db)
                
                # 4. Optimize table storage
                results["cluster"] = await self.cluster_tables(db)
            
            self._record_maintenance(
                task="weekly_optimization",
                start_time=start_time,
                results=results,
                status="success"
            )
            
            logger.info(f"Weekly optimization completed: {results}")
            
        except Exception as e:
            logger.error(f"Weekly optimization failed: {e}")
            self._record_maintenance(
                task="weekly_optimization",
                start_time=start_time,
                results=results,
                status="failed",
                error=str(e)
            )
    
    async def cleanup_old_data(self, db: AsyncSession) -> Dict[str, int]:
        """Clean up old/unused data."""
        cleanup_results = {}
        
        # 1. Delete old email logs (> 90 days)
        email_logs_deleted = await db.execute(
            text("""
                DELETE FROM email_logs 
                WHERE created_at < :cutoff_date
            """),
            {"cutoff_date": (datetime.utcnow() - timedelta(days=90)).isoformat()}
        )
        cleanup_results["email_logs"] = email_logs_deleted.rowcount
        
        # 2. Delete processed email queue items (> 30 days)
        email_queue_deleted = await db.execute(
            text("""
                DELETE FROM email_queue 
                WHERE status IN ('sent', 'failed') 
                AND created_at < :cutoff_date
            """),
            {"cutoff_date": (datetime.utcnow() - timedelta(days=30)).isoformat()}
        )
        cleanup_results["email_queue"] = email_queue_deleted.rowcount
        
        # 3. Delete old moderation logs (> 180 days)
        moderation_deleted = await db.execute(
            text("""
                DELETE FROM moderation_log 
                WHERE created_at < :cutoff_date
            """),
            {"cutoff_date": (datetime.utcnow() - timedelta(days=180)).isoformat()}
        )
        cleanup_results["moderation_logs"] = moderation_deleted.rowcount
        
        # 4. Clean up orphaned records
        orphaned_deleted = await db.execute(
            text("""
                DELETE FROM messages 
                WHERE conversation_id NOT IN (SELECT id FROM conversations)
            """)
        )
        cleanup_results["orphaned_messages"] = orphaned_deleted.rowcount
        
        await db.commit()
        return cleanup_results
    
    async def analyze_tables(self, db: AsyncSession) -> Dict[str, str]:
        """Update table statistics for query planner."""
        tables_analyzed = {}
        
        important_tables = [
            "users", "models", "conversations", "messages",
            "transactions", "payouts", "earnings",
            "email_queue", "email_logs"
        ]
        
        for table in important_tables:
            try:
                await db.execute(text(f"ANALYZE {table}"))
                tables_analyzed[table] = "analyzed"
            except Exception as e:
                tables_analyzed[table] = f"failed: {str(e)}"
                logger.error(f"Failed to analyze table {table}: {e}")
        
        await db.commit()
        return tables_analyzed
    
    async def vacuum_tables(self, db: AsyncSession, threshold_pct: float = 20.0) -> Dict[str, str]:
        """Vacuum tables with significant bloat."""
        vacuum_results = {}
        
        # Get bloated tables
        bloat_query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                round(100 * (1 - pgstattuple.avg_leaf_density)) as bloat_pct
            FROM pg_catalog.pg_stat_user_tables
            JOIN pgstattuple(schemaname||'.'||tablename) ON true
            WHERE n_tup_upd + n_tup_del > 1000
            AND round(100 * (1 - pgstattuple.avg_leaf_density)) > :threshold
        """)
        
        try:
            # Note: This requires pgstattuple extension
            bloated_tables = await db.execute(
                bloat_query,
                {"threshold": threshold_pct}
            )
            
            for row in bloated_tables:
                table_name = f"{row.schemaname}.{row.tablename}"
                try:
                    # Use VACUUM (not FULL) to avoid locking
                    await db.execute(text(f"VACUUM ANALYZE {table_name}"))
                    vacuum_results[table_name] = f"vacuumed (bloat: {row.bloat_pct}%)"
                except Exception as e:
                    vacuum_results[table_name] = f"failed: {str(e)}"
                    
        except Exception as e:
            logger.warning(f"Bloat analysis not available: {e}")
            # Fallback: vacuum high-activity tables
            high_activity_tables = ["messages", "conversations", "transactions"]
            for table in high_activity_tables:
                try:
                    await db.execute(text(f"VACUUM ANALYZE {table}"))
                    vacuum_results[table] = "vacuumed"
                except Exception as e:
                    vacuum_results[table] = f"failed: {str(e)}"
        
        await db.commit()
        return vacuum_results
    
    async def refresh_materialized_views(self, db: AsyncSession) -> Dict[str, str]:
        """Refresh materialized views."""
        refresh_results = {}
        
        # Get all materialized views
        views_query = text("""
            SELECT schemaname, matviewname 
            FROM pg_matviews 
            WHERE schemaname = 'public'
        """)
        
        views = await db.execute(views_query)
        
        for view in views:
            view_name = view.matviewname
            try:
                # Refresh concurrently to avoid locking
                await db.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
                )
                refresh_results[view_name] = "refreshed"
            except Exception as e:
                # Try non-concurrent refresh if concurrent fails
                try:
                    await db.execute(
                        text(f"REFRESH MATERIALIZED VIEW {view_name}")
                    )
                    refresh_results[view_name] = "refreshed (non-concurrent)"
                except Exception as e2:
                    refresh_results[view_name] = f"failed: {str(e2)}"
                    logger.error(f"Failed to refresh view {view_name}: {e2}")
        
        await db.commit()
        return refresh_results
    
    async def archive_old_messages(
        self,
        db: AsyncSession,
        days_old: int = 365
    ) -> Dict[str, int]:
        """Archive old messages to reduce main table size."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Create archive table if not exists
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS messages_archive (
                LIKE messages INCLUDING ALL
            )
        """))
        
        # Move old messages to archive
        archived = await db.execute(
            text("""
                WITH moved AS (
                    DELETE FROM messages
                    WHERE created_at < :cutoff_date
                    AND conversation_id IN (
                        SELECT id FROM conversations 
                        WHERE status IN ('archived', 'blocked')
                    )
                    RETURNING *
                )
                INSERT INTO messages_archive
                SELECT * FROM moved
            """),
            {"cutoff_date": cutoff_date.isoformat()}
        )
        
        await db.commit()
        
        return {
            "messages_archived": archived.rowcount,
            "cutoff_date": cutoff_date.isoformat()
        }
    
    async def reindex_tables(self, db: AsyncSession) -> Dict[str, str]:
        """Reindex tables to reduce index bloat."""
        reindex_results = {}
        
        # Get indexes with high bloat
        bloated_indexes = await db.execute(
            text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                WHERE pg_relation_size(indexrelid) > 10485760  -- 10MB
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 10
            """)
        )
        
        for idx in bloated_indexes:
            try:
                # REINDEX CONCURRENTLY to avoid locking
                await db.execute(
                    text(f"REINDEX INDEX CONCURRENTLY {idx.indexname}")
                )
                reindex_results[idx.indexname] = "reindexed"
            except Exception as e:
                reindex_results[idx.indexname] = f"failed: {str(e)}"
                logger.error(f"Failed to reindex {idx.indexname}: {e}")
        
        await db.commit()
        return reindex_results
    
    async def update_planner_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """Update PostgreSQL planner statistics."""
        # Update default statistics target for important columns
        important_columns = [
            ("conversations", "model_id"),
            ("conversations", "status"),
            ("messages", "conversation_id"),
            ("messages", "sender_type"),
            ("transactions", "model_id"),
            ("users", "agency_id")
        ]
        
        stats_updated = {}
        
        for table, column in important_columns:
            try:
                await db.execute(
                    text(f"""
                        ALTER TABLE {table} 
                        ALTER COLUMN {column} 
                        SET STATISTICS 1000
                    """)
                )
                stats_updated[f"{table}.{column}"] = "updated"
            except Exception as e:
                stats_updated[f"{table}.{column}"] = f"failed: {str(e)}"
        
        # Run ANALYZE on affected tables
        affected_tables = set(table for table, _ in important_columns)
        for table in affected_tables:
            await db.execute(text(f"ANALYZE {table}"))
        
        await db.commit()
        return stats_updated
    
    async def analyze_slow_queries(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Analyze and log slow queries."""
        # This would integrate with pg_stat_statements
        # For now, return empty list
        return []
    
    async def cluster_tables(self, db: AsyncSession) -> Dict[str, str]:
        """Cluster tables by primary key for better performance."""
        cluster_results = {}
        
        # Tables that benefit from clustering
        tables_to_cluster = [
            ("messages", "messages_pkey"),
            ("transactions", "transactions_pkey"),
            ("email_logs", "email_logs_pkey")
        ]
        
        for table, index in tables_to_cluster:
            try:
                # Note: CLUSTER locks the table, so only do during maintenance window
                await db.execute(text(f"CLUSTER {table} USING {index}"))
                cluster_results[table] = "clustered"
            except Exception as e:
                cluster_results[table] = f"failed: {str(e)}"
                logger.error(f"Failed to cluster {table}: {e}")
        
        await db.commit()
        return cluster_results
    
    async def update_statistics(self):
        """Update hourly statistics."""
        try:
            async with AsyncSessionLocal() as db:
                # Update connection pool stats
                from core.database_pool import pool_manager
                pool_stats = await pool_manager.get_pool_status()
                
                # Cache stats in Redis
                await redis_manager.set(
                    "db:pool_stats",
                    json.dumps(pool_stats),
                    expire=3600
                )
                
                logger.debug(f"Updated pool statistics: {pool_stats}")
                
        except Exception as e:
            logger.error(f"Failed to update statistics: {e}")
    
    def _record_maintenance(
        self,
        task: str,
        start_time: datetime,
        results: Dict[str, Any],
        status: str,
        error: Optional[str] = None
    ):
        """Record maintenance task execution."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        record = {
            "task": task,
            "start_time": start_time.isoformat(),
            "duration_seconds": duration,
            "status": status,
            "results": results,
            "error": error
        }
        
        # Keep last 100 records
        self.maintenance_history.append(record)
        if len(self.maintenance_history) > 100:
            self.maintenance_history.pop(0)
        
        # Also log to database or monitoring system
        if status == "failed":
            logger.error(f"Maintenance task {task} failed: {error}")
        else:
            logger.info(f"Maintenance task {task} completed in {duration:.2f}s")
    
    def get_maintenance_history(
        self,
        task: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get maintenance task history."""
        history = self.maintenance_history
        
        if task:
            history = [h for h in history if h["task"] == task]
        
        return history[-limit:]
    
    async def shutdown(self):
        """Shutdown maintenance scheduler."""
        self.scheduler.shutdown()
        logger.info("Database maintenance scheduler shutdown")


# Global maintenance service instance
maintenance_service = DatabaseMaintenanceService()


# Helper function to run maintenance manually
async def run_maintenance_task(task_name: str) -> Dict[str, Any]:
    """Run a specific maintenance task manually."""
    if task_name == "daily":
        await maintenance_service.daily_maintenance()
    elif task_name == "weekly":
        await maintenance_service.weekly_optimization()
    elif task_name == "statistics":
        await maintenance_service.update_statistics()
    else:
        raise ValueError(f"Unknown maintenance task: {task_name}")
    
    return {"status": "completed", "task": task_name}