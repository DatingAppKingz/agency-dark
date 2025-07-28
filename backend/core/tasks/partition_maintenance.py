"""
Background task for automatic partition maintenance
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.partitioning import partition_manager
from core.logging import get_logger
from core.celery import celery_app

logger = get_logger(__name__)


class PartitionMaintenanceTask:
    """Handles automatic partition maintenance"""
    
    def __init__(self):
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
    
    async def run_maintenance(self, db: AsyncSession):
        """Run partition maintenance tasks"""
        if self.is_running:
            logger.warning("Partition maintenance already running, skipping...")
            return
        
        self.is_running = True
        try:
            logger.info("Starting partition maintenance task")
            
            # 1. Create future partitions
            await partition_manager.maintain_partitions(db)
            
            # 2. Analyze partition statistics
            stats = await self._collect_partition_stats(db)
            logger.info(f"Partition statistics: {stats}")
            
            # 3. Check for bloated partitions
            bloated = await self._check_bloated_partitions(db)
            if bloated:
                logger.warning(f"Found bloated partitions: {bloated}")
                await self._vacuum_partitions(db, bloated)
            
            # 4. Update partition constraints
            await partition_manager.optimize_partition_constraints(db)
            
            self.last_run = datetime.utcnow()
            self.next_run = self.last_run + timedelta(days=1)
            
            logger.info("Partition maintenance completed successfully")
            
        except Exception as e:
            logger.error(f"Partition maintenance failed: {e}")
            raise
        finally:
            self.is_running = False
    
    async def _collect_partition_stats(self, db: AsyncSession) -> dict:
        """Collect statistics about all partitions"""
        stats = {}
        
        for table_name in partition_manager.partitioned_tables.keys():
            partitions = await partition_manager.get_partition_info(db, table_name)
            
            total_size = 0
            total_rows = 0
            needs_vacuum = []
            needs_analyze = []
            
            for partition in partitions:
                # Parse size
                size_str = partition["size"]
                if "MB" in size_str:
                    total_size += float(size_str.replace(" MB", ""))
                elif "GB" in size_str:
                    total_size += float(size_str.replace(" GB", "")) * 1024
                
                total_rows += partition["row_count"] or 0
                
                # Check if maintenance needed
                if partition["last_vacuum"] is None or \
                   (datetime.utcnow() - partition["last_vacuum"]).days > 7:
                    needs_vacuum.append(partition["name"])
                
                if partition["last_analyze"] is None or \
                   (datetime.utcnow() - partition["last_analyze"]).days > 3:
                    needs_analyze.append(partition["name"])
            
            stats[table_name] = {
                "partition_count": len(partitions),
                "total_size_mb": round(total_size, 2),
                "total_rows": total_rows,
                "needs_vacuum": needs_vacuum,
                "needs_analyze": needs_analyze
            }
        
        return stats
    
    async def _check_bloated_partitions(self, db: AsyncSession) -> list:
        """Check for partitions with high bloat"""
        bloated_partitions = []
        
        bloat_query = text("""
            WITH bloat_data AS (
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS size,
                    ROUND(100.0 * pg_relation_size(schemaname||'.'||tablename) / 
                          NULLIF(SUM(pg_relation_size(schemaname||'.'||tablename)) 
                          OVER (PARTITION BY substring(tablename FROM '^[^_]+(?=_)')), 0), 2) AS pct_of_parent,
                    n_dead_tup,
                    n_live_tup,
                    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND tablename ~ '_[0-9]{4}_[0-9]{2}$'
            )
            SELECT 
                tablename,
                size,
                dead_pct
            FROM bloat_data
            WHERE dead_pct > 20  -- More than 20% dead tuples
            OR (n_dead_tup > 10000 AND dead_pct > 10)  -- Or many dead tuples
            ORDER BY dead_pct DESC
        """)
        
        result = await db.execute(bloat_query)
        
        for row in result:
            bloated_partitions.append({
                "name": row.tablename,
                "size": row.size,
                "dead_percentage": row.dead_pct
            })
        
        return bloated_partitions
    
    async def _vacuum_partitions(self, db: AsyncSession, partitions: list):
        """Vacuum bloated partitions"""
        for partition in partitions:
            try:
                partition_name = partition["name"]
                
                # Run VACUUM ANALYZE on the partition
                vacuum_query = text(f"VACUUM ANALYZE {partition_name}")
                await db.execute(vacuum_query)
                await db.commit()
                
                logger.info(f"Vacuumed partition {partition_name} "
                          f"(was {partition['dead_percentage']}% dead)")
                
            except Exception as e:
                logger.error(f"Failed to vacuum partition {partition_name}: {e}")


# Celery tasks
@celery_app.task(name="partition_maintenance")
def run_partition_maintenance():
    """Celery task for partition maintenance"""
    async def _run():
        async with get_db() as db:
            task = PartitionMaintenanceTask()
            await task.run_maintenance(db)
    
    asyncio.run(_run())


@celery_app.task(name="partition_health_check")
def check_partition_health():
    """Quick health check for partitions"""
    async def _check():
        async with get_db() as db:
            # Check if any tables are missing partitions for current month
            check_query = text("""
                SELECT 
                    parent.relname AS table_name,
                    TO_CHAR(CURRENT_DATE, 'YYYY_MM') AS expected_partition
                FROM pg_class parent
                WHERE parent.relkind = 'p'  -- Partitioned table
                AND NOT EXISTS (
                    SELECT 1 
                    FROM pg_class child
                    JOIN pg_inherits ON child.oid = pg_inherits.inhrelid
                    WHERE pg_inherits.inhparent = parent.oid
                    AND child.relname = parent.relname || '_' || TO_CHAR(CURRENT_DATE, 'YYYY_MM')
                )
            """)
            
            result = await db.execute(check_query)
            missing = []
            
            for row in result:
                missing.append({
                    "table": row.table_name,
                    "missing_partition": f"{row.table_name}_{row.expected_partition}"
                })
            
            if missing:
                logger.error(f"Missing partitions detected: {missing}")
                # Trigger immediate maintenance
                run_partition_maintenance.delay()
            else:
                logger.info("All partitions are healthy")
            
            return {"healthy": len(missing) == 0, "missing": missing}
    
    return asyncio.run(_check())


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule.update({
    'partition-maintenance': {
        'task': 'partition_maintenance',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    },
    'partition-health-check': {
        'task': 'partition_health_check',
        'schedule': crontab(minute='*/30'),  # Run every 30 minutes
    },
})


# Manual execution functions
async def manual_partition_maintenance():
    """Manually trigger partition maintenance"""
    async with get_db() as db:
        task = PartitionMaintenanceTask()
        await task.run_maintenance(db)


async def get_partition_report():
    """Generate a detailed partition report"""
    async with get_db() as db:
        report = {
            "generated_at": datetime.utcnow(),
            "tables": {}
        }
        
        for table_name in partition_manager.partitioned_tables.keys():
            stats = await partition_manager.get_partition_statistics(db, table_name)
            partitions = await partition_manager.get_partition_info(db, table_name)
            
            # Calculate growth rate
            if len(partitions) >= 2:
                recent_partitions = sorted(
                    partitions, 
                    key=lambda p: p["name"], 
                    reverse=True
                )[:2]
                
                if recent_partitions[0]["row_count"] and recent_partitions[1]["row_count"]:
                    growth_rate = (
                        (recent_partitions[0]["row_count"] - recent_partitions[1]["row_count"]) 
                        / recent_partitions[1]["row_count"] * 100
                    )
                else:
                    growth_rate = 0
            else:
                growth_rate = 0
            
            report["tables"][table_name] = {
                "statistics": stats,
                "growth_rate_pct": round(growth_rate, 2),
                "health_status": "healthy" if growth_rate < 50 else "high_growth"
            }
        
        return report


from sqlalchemy import text