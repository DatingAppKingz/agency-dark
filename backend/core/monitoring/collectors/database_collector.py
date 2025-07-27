"""
Database metrics collector for connection pools, query performance, etc.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.pool import Pool
import logging

from core.monitoring.models import Metric, MetricType
from core.database import get_db, engine
from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseMetricsCollector:
    """Collects database-related metrics."""
    
    def __init__(self):
        self.collection_interval = 60  # seconds
        self.is_running = False
        
    async def start(self):
        """Start the metrics collection loop."""
        self.is_running = True
        logger.info("Starting database metrics collector")
        
        while self.is_running:
            try:
                async for db in get_db():
                    await self.collect_all_metrics(db)
                    break
            except Exception as e:
                logger.error(f"Error collecting database metrics: {e}")
            
            await asyncio.sleep(self.collection_interval)
    
    async def stop(self):
        """Stop the metrics collection."""
        self.is_running = False
        logger.info("Stopping database metrics collector")
    
    async def collect_all_metrics(self, db: AsyncSession):
        """Collect all database metrics."""
        timestamp = datetime.utcnow()
        metrics = []
        
        # Connection pool metrics
        pool_metrics = self._collect_pool_metrics(timestamp)
        metrics.extend(pool_metrics)
        
        # Database statistics
        db_stats = await self._collect_database_stats(db, timestamp)
        metrics.extend(db_stats)
        
        # Save all metrics
        if metrics:
            db.add_all(metrics)
            await db.commit()
            logger.debug(f"Collected {len(metrics)} database metrics")
    
    def _collect_pool_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect connection pool metrics."""
        metrics = []
        
        try:
            pool = engine.pool
            if hasattr(pool, 'size'):
                # Pool size
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_POOL_SIZE,
                    metric_name="db_pool_size",
                    value=float(pool.size()),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            if hasattr(pool, 'checked_in_connections'):
                # Available connections
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_connections_available",
                    value=float(pool.checked_in_connections()),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            if hasattr(pool, 'checked_out_connections'):
                # Active connections
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_connections_active",
                    value=float(pool.checked_out_connections()),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            if hasattr(pool, 'overflow'):
                # Overflow connections
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_connections_overflow",
                    value=float(pool.overflow()),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            if hasattr(pool, 'total'):
                # Total connections
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_connections_total",
                    value=float(pool.total()),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
        
        except Exception as e:
            logger.error(f"Error collecting pool metrics: {e}")
        
        return metrics
    
    async def _collect_database_stats(self, db: AsyncSession, timestamp: datetime) -> List[Metric]:
        """Collect database statistics."""
        metrics = []
        
        try:
            # Database size
            size_query = text("""
                SELECT pg_database_size(current_database()) as size
            """)
            result = await db.execute(size_query)
            db_size = result.scalar()
            
            if db_size:
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_size_bytes",
                    value=float(db_size),
                    unit="bytes",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            # Active connections
            conn_query = text("""
                SELECT count(*) as count 
                FROM pg_stat_activity 
                WHERE state = 'active'
            """)
            result = await db.execute(conn_query)
            active_conns = result.scalar()
            
            if active_conns is not None:
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_active_queries",
                    value=float(active_conns),
                    unit="queries",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            # Idle connections
            idle_query = text("""
                SELECT count(*) as count 
                FROM pg_stat_activity 
                WHERE state = 'idle'
            """)
            result = await db.execute(idle_query)
            idle_conns = result.scalar()
            
            if idle_conns is not None:
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_idle_connections",
                    value=float(idle_conns),
                    unit="connections",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            # Long running queries
            long_query = text("""
                SELECT count(*) as count 
                FROM pg_stat_activity 
                WHERE state = 'active' 
                AND now() - query_start > interval '5 seconds'
            """)
            result = await db.execute(long_query)
            long_queries = result.scalar()
            
            if long_queries is not None:
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_QUERY_TIME,
                    metric_name="db_long_running_queries",
                    value=float(long_queries),
                    unit="queries",
                    tags={"threshold": "5s"},
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
            
            # Table statistics
            table_stats_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
                LIMIT 10
            """)
            result = await db.execute(table_stats_query)
            
            for row in result:
                # Row count per table
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    metric_name="db_table_row_count",
                    value=float(row.row_count or 0),
                    unit="rows",
                    tags={
                        "schema": row.schemaname,
                        "table": row.tablename
                    },
                    entity_type="table",
                    entity_id=f"{row.schemaname}.{row.tablename}",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
                
                # Dead rows (needs vacuum)
                if row.dead_rows and row.dead_rows > 0:
                    metrics.append(Metric(
                        metric_type=MetricType.DATABASE_CONNECTIONS,
                        metric_name="db_table_dead_rows",
                        value=float(row.dead_rows),
                        unit="rows",
                        tags={
                            "schema": row.schemaname,
                            "table": row.tablename
                        },
                        entity_type="table",
                        entity_id=f"{row.schemaname}.{row.tablename}",
                        hostname=settings.HOSTNAME,
                        service_name="database",
                        timestamp=timestamp
                    ))
            
            # Index usage statistics
            index_stats_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                AND idx_scan > 0
                ORDER BY idx_scan DESC
                LIMIT 10
            """)
            result = await db.execute(index_stats_query)
            
            for row in result:
                metrics.append(Metric(
                    metric_type=MetricType.DATABASE_QUERY_TIME,
                    metric_name="db_index_scans",
                    value=float(row.idx_scan or 0),
                    unit="scans",
                    tags={
                        "schema": row.schemaname,
                        "table": row.tablename,
                        "index": row.indexname
                    },
                    entity_type="index",
                    entity_id=f"{row.schemaname}.{row.tablename}.{row.indexname}",
                    hostname=settings.HOSTNAME,
                    service_name="database",
                    timestamp=timestamp
                ))
        
        except Exception as e:
            logger.error(f"Error collecting database stats: {e}")
        
        return metrics
    
    async def analyze_slow_queries(self, db: AsyncSession, threshold_ms: int = 1000) -> List[Dict[str, Any]]:
        """Analyze slow queries from pg_stat_statements."""
        slow_queries = []
        
        try:
            # Check if pg_stat_statements is available
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_extension 
                    WHERE extname = 'pg_stat_statements'
                )
            """)
            result = await db.execute(check_query)
            has_extension = result.scalar()
            
            if not has_extension:
                logger.warning("pg_stat_statements extension not available")
                return slow_queries
            
            # Get slow queries
            slow_query = text("""
                SELECT 
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    stddev_exec_time,
                    rows
                FROM pg_stat_statements
                WHERE mean_exec_time > :threshold
                ORDER BY mean_exec_time DESC
                LIMIT 20
            """)
            
            result = await db.execute(slow_query, {"threshold": threshold_ms})
            
            for row in result:
                slow_queries.append({
                    "query": row.query[:200],  # Truncate long queries
                    "calls": row.calls,
                    "total_time_ms": round(row.total_exec_time, 2),
                    "avg_time_ms": round(row.mean_exec_time, 2),
                    "stddev_time_ms": round(row.stddev_exec_time, 2),
                    "rows_returned": row.rows
                })
        
        except Exception as e:
            logger.error(f"Error analyzing slow queries: {e}")
        
        return slow_queries


# Global instance
database_collector = DatabaseMetricsCollector()