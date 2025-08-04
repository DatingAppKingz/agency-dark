"""Database optimization service for performance improvements."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
import json

from core.database import engine, get_db
from core.logger import get_logger
from core.redis import redis_manager

logger = get_logger(__name__)


class DatabaseOptimizationService:
    """Service for database performance optimization."""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for analysis results
    
    async def analyze_slow_queries(
        self,
        db: AsyncSession,
        min_duration_ms: int = 100,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Analyze slow queries from pg_stat_statements."""
        # Check if pg_stat_statements is enabled
        check_extension = await db.execute(
            text("SELECT * FROM pg_extension WHERE extname = 'pg_stat_statements'")
        )
        if not check_extension.first():
            logger.warning("pg_stat_statements extension not installed")
            return []
        
        # Get slow queries
        query = text("""
            SELECT 
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                stddev_exec_time,
                min_exec_time,
                max_exec_time,
                rows,
                100.0 * shared_blks_hit / 
                    NULLIF(shared_blks_hit + shared_blks_read, 0) AS cache_hit_ratio
            FROM pg_stat_statements
            WHERE mean_exec_time > :min_duration
            ORDER BY mean_exec_time DESC
            LIMIT :limit
        """)
        
        result = await db.execute(
            query,
            {"min_duration": min_duration_ms, "limit": limit}
        )
        
        slow_queries = []
        for row in result:
            slow_queries.append({
                "query": row.query[:200],  # Truncate long queries
                "calls": row.calls,
                "total_time_ms": round(row.total_exec_time, 2),
                "mean_time_ms": round(row.mean_exec_time, 2),
                "stddev_time_ms": round(row.stddev_exec_time, 2),
                "min_time_ms": round(row.min_exec_time, 2),
                "max_time_ms": round(row.max_exec_time, 2),
                "rows": row.rows,
                "cache_hit_ratio": round(row.cache_hit_ratio or 0, 2)
            })
        
        return slow_queries
    
    async def analyze_missing_indexes(
        self,
        db: AsyncSession,
        min_scans: int = 50
    ) -> List[Dict[str, Any]]:
        """Analyze tables that might benefit from additional indexes."""
        query = text("""
            SELECT 
                schemaname,
                tablename,
                seq_scan,
                seq_tup_read,
                idx_scan,
                idx_tup_fetch,
                n_tup_ins + n_tup_upd + n_tup_del as total_writes,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size
            FROM pg_stat_user_tables
            WHERE seq_scan > :min_scans
                AND seq_scan > COALESCE(idx_scan, 0)
            ORDER BY seq_scan DESC
        """)
        
        result = await db.execute(query, {"min_scans": min_scans})
        
        missing_indexes = []
        for row in result:
            ratio = row.seq_scan / (row.seq_scan + (row.idx_scan or 1))
            missing_indexes.append({
                "schema": row.schemaname,
                "table": row.tablename,
                "seq_scans": row.seq_scan,
                "seq_rows_read": row.seq_tup_read,
                "idx_scans": row.idx_scan or 0,
                "idx_rows_fetched": row.idx_tup_fetch or 0,
                "total_writes": row.total_writes,
                "table_size": row.table_size,
                "seq_scan_ratio": round(ratio * 100, 2),
                "recommendation": self._generate_index_recommendation(row.tablename, ratio)
            })
        
        return missing_indexes
    
    def _generate_index_recommendation(self, table_name: str, seq_scan_ratio: float) -> str:
        """Generate index recommendations based on table name and scan patterns."""
        recommendations = {
            "messages": "Consider index on (conversation_id, created_at) for chat queries",
            "conversations": "Consider index on (model_id, status, last_message_at)",
            "models": "Consider index on (agency_id, is_active) for listing queries",
            "users": "Consider index on (email, is_active) for login queries",
            "transactions": "Consider index on (model_id, created_at) for financial reports",
            "payouts": "Consider index on (model_id, status, created_at)",
            "email_queue": "Consider index on (status, scheduled_at) for queue processing"
        }
        
        if seq_scan_ratio > 0.8:
            prefix = "URGENT: "
        elif seq_scan_ratio > 0.5:
            prefix = "RECOMMENDED: "
        else:
            prefix = "OPTIONAL: "
        
        return prefix + recommendations.get(
            table_name,
            f"Analyze query patterns for {table_name} to determine optimal indexes"
        )
    
    async def create_recommended_indexes(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Create recommended indexes based on analysis."""
        indexes_created = []
        
        # Define indexes to create
        index_definitions = [
            # Chat system indexes
            {
                "name": "idx_messages_conversation_created",
                "table": "messages",
                "columns": "(conversation_id, created_at DESC)",
                "condition": None
            },
            {
                "name": "idx_messages_sender_type",
                "table": "messages",
                "columns": "(sender_id, sender_type)",
                "condition": "WHERE is_deleted = false"
            },
            {
                "name": "idx_conversations_model_status",
                "table": "conversations",
                "columns": "(model_id, status, last_message_at DESC)",
                "condition": None
            },
            {
                "name": "idx_conversations_assigned_chatter",
                "table": "conversations",
                "columns": "(assigned_chatter_id, status)",
                "condition": "WHERE assigned_chatter_id IS NOT NULL"
            },
            
            # Financial indexes
            {
                "name": "idx_transactions_model_date",
                "table": "transactions",
                "columns": "(model_id, created_at DESC)",
                "condition": None
            },
            {
                "name": "idx_payouts_model_status",
                "table": "payouts",
                "columns": "(model_id, status, created_at DESC)",
                "condition": None
            },
            {
                "name": "idx_earnings_model_period",
                "table": "earnings",
                "columns": "(model_id, period_start, period_end)",
                "condition": None
            },
            
            # User/Model indexes
            {
                "name": "idx_users_email_active",
                "table": "users",
                "columns": "(email, is_active)",
                "condition": "WHERE is_active = true"
            },
            {
                "name": "idx_models_agency_active",
                "table": "models",
                "columns": "(agency_id, is_active, approval_status)",
                "condition": None
            },
            
            # Email system indexes
            {
                "name": "idx_email_queue_processing",
                "table": "email_queue",
                "columns": "(status, priority DESC, scheduled_at)",
                "condition": "WHERE status IN ('pending', 'processing')"
            }
        ]
        
        for index_def in index_definitions:
            try:
                # Check if index exists
                check_query = text("""
                    SELECT 1 FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND indexname = :index_name
                """)
                
                exists = await db.execute(
                    check_query,
                    {"index_name": index_def["name"]}
                )
                
                if not exists.first():
                    # Create index
                    create_sql = f"""
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_def['name']}
                        ON {index_def['table']} {index_def['columns']}
                    """
                    
                    if index_def["condition"]:
                        create_sql += f" {index_def['condition']}"
                    
                    await db.execute(text(create_sql))
                    await db.commit()
                    
                    indexes_created.append({
                        "index": index_def["name"],
                        "table": index_def["table"],
                        "status": "created"
                    })
                    
                    logger.info(f"Created index: {index_def['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create index {index_def['name']}: {e}")
                indexes_created.append({
                    "index": index_def["name"],
                    "table": index_def["table"],
                    "status": "failed",
                    "error": str(e)
                })
        
        return indexes_created
    
    async def analyze_table_bloat(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Analyze table bloat and recommend vacuum operations."""
        query = text("""
            WITH constants AS (
                SELECT current_setting('block_size')::numeric AS bs, 23 AS hdr, 4 AS ma
            ),
            bloat_info AS (
                SELECT
                    schemaname,
                    tablename,
                    cc.relpages,
                    bs,
                    CEIL((cc.reltuples*((datahdr+ma-
                        (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::float)) AS otta
                FROM (
                    SELECT
                        schemaname,
                        tablename,
                        hdr,
                        ma,
                        bs,
                        SUM((1-null_frac)*avg_width) AS datawidth,
                        MAX(null_frac) AS maxfracsum,
                        hdr+(
                            SELECT 1+count(*)/8
                            FROM pg_stats s2
                            WHERE null_frac<>0 AND s2.schemaname = s.schemaname AND s2.tablename = s.tablename
                        ) AS nullhdr2
                    FROM pg_stats s, constants
                    GROUP BY 1,2,3,4,5
                ) AS foo
                JOIN pg_class cc ON cc.relname = foo.tablename
                JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = foo.schemaname
                WHERE cc.relpages > 0
            )
            SELECT
                schemaname,
                tablename,
                relpages::bigint AS pages,
                otta::bigint AS optimal_pages,
                CASE WHEN relpages > 0 
                    THEN round((relpages-otta)::numeric/relpages::numeric*100)
                    ELSE 0 
                END AS bloat_pct,
                pg_size_pretty((relpages-otta)*bs::bigint) AS bloat_size
            FROM bloat_info
            WHERE relpages > otta + 10
                AND round((relpages-otta)::numeric/relpages::numeric*100) > 20
            ORDER BY (relpages-otta) DESC
            LIMIT 20
        """)
        
        result = await db.execute(query)
        
        bloated_tables = []
        for row in result:
            bloated_tables.append({
                "schema": row.schemaname,
                "table": row.tablename,
                "pages": row.pages,
                "optimal_pages": row.optimal_pages,
                "bloat_percentage": float(row.bloat_pct),
                "bloat_size": row.bloat_size,
                "recommendation": self._generate_vacuum_recommendation(row.tablename, float(row.bloat_pct))
            })
        
        return bloated_tables
    
    def _generate_vacuum_recommendation(self, table_name: str, bloat_pct: float) -> str:
        """Generate vacuum recommendations based on bloat percentage."""
        if bloat_pct > 50:
            return f"URGENT: Run VACUUM FULL on {table_name} (consider maintenance window)"
        elif bloat_pct > 30:
            return f"RECOMMENDED: Schedule VACUUM FULL on {table_name}"
        else:
            return f"Monitor {table_name} and ensure autovacuum is tuned properly"
    
    async def optimize_autovacuum_settings(self, db: AsyncSession) -> Dict[str, Any]:
        """Analyze and optimize autovacuum settings for tables."""
        # Get current autovacuum settings
        current_settings = await db.execute(
            text("""
                SELECT 
                    name,
                    setting,
                    unit,
                    short_desc
                FROM pg_settings
                WHERE name LIKE 'autovacuum%'
                ORDER BY name
            """)
        )
        
        settings = {}
        for row in current_settings:
            settings[row.name] = {
                "current": row.setting,
                "unit": row.unit,
                "description": row.short_desc
            }
        
        # Recommend optimizations
        recommendations = []
        
        # Check autovacuum_max_workers
        max_workers = int(settings.get("autovacuum_max_workers", {}).get("current", "3"))
        if max_workers < 4:
            recommendations.append({
                "setting": "autovacuum_max_workers",
                "current": max_workers,
                "recommended": 4,
                "reason": "Increase parallel vacuum operations for better performance"
            })
        
        # Check autovacuum_naptime
        naptime = int(settings.get("autovacuum_naptime", {}).get("current", "60"))
        if naptime > 30:
            recommendations.append({
                "setting": "autovacuum_naptime",
                "current": f"{naptime}s",
                "recommended": "30s",
                "reason": "More frequent checks for tables needing vacuum"
            })
        
        # Table-specific settings for high-activity tables
        high_activity_tables = ["messages", "conversations", "email_queue", "transactions"]
        
        for table in high_activity_tables:
            recommendations.append({
                "setting": f"ALTER TABLE {table}",
                "current": "default",
                "recommended": "autovacuum_vacuum_scale_factor = 0.1",
                "reason": f"More aggressive vacuuming for high-activity table {table}"
            })
        
        return {
            "current_settings": settings,
            "recommendations": recommendations
        }
    
    async def create_query_performance_views(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Create materialized views for common expensive queries."""
        views_created = []
        
        # Define materialized views
        view_definitions = [
            {
                "name": "mv_daily_model_stats",
                "refresh": "CONCURRENTLY",
                "query": """
                    SELECT 
                        m.id as model_id,
                        m.stage_name,
                        DATE(msg.created_at) as date,
                        COUNT(DISTINCT c.id) as active_conversations,
                        COUNT(msg.id) as total_messages,
                        SUM(CASE WHEN msg.sender_type = 'fan' THEN 1 ELSE 0 END) as fan_messages,
                        SUM(CASE WHEN msg.type = 'tip' AND msg.is_paid THEN msg.amount ELSE 0 END) as tips_revenue,
                        SUM(CASE WHEN msg.type = 'ppv' AND msg.is_paid THEN msg.amount ELSE 0 END) as ppv_revenue
                    FROM models m
                    LEFT JOIN conversations c ON c.model_id = m.id
                    LEFT JOIN messages msg ON msg.conversation_id = c.id
                    WHERE msg.created_at >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY m.id, m.stage_name, DATE(msg.created_at)
                """,
                "indexes": [
                    "CREATE INDEX idx_mv_daily_model_stats_model_date ON mv_daily_model_stats(model_id, date DESC)",
                    "CREATE INDEX idx_mv_daily_model_stats_date ON mv_daily_model_stats(date DESC)"
                ]
            },
            {
                "name": "mv_conversation_summary",
                "refresh": "CONCURRENTLY",
                "query": """
                    SELECT 
                        c.id as conversation_id,
                        c.model_id,
                        c.fan_username,
                        COUNT(m.id) as message_count,
                        MAX(m.created_at) as last_message_at,
                        SUM(CASE WHEN m.sender_type = 'fan' THEN 1 ELSE 0 END) as fan_message_count,
                        SUM(CASE WHEN m.is_paid THEN m.amount ELSE 0 END) as total_revenue,
                        AVG(CASE 
                            WHEN m.sender_type != 'fan' AND prev.sender_type = 'fan' 
                            THEN EXTRACT(EPOCH FROM (m.created_at - prev.created_at))
                            ELSE NULL 
                        END) as avg_response_time_seconds
                    FROM conversations c
                    LEFT JOIN messages m ON m.conversation_id = c.id
                    LEFT JOIN LATERAL (
                        SELECT sender_type, created_at 
                        FROM messages 
                        WHERE conversation_id = c.id 
                            AND created_at < m.created_at 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    ) prev ON true
                    WHERE c.status = 'active'
                    GROUP BY c.id, c.model_id, c.fan_username
                """,
                "indexes": [
                    "CREATE INDEX idx_mv_conversation_summary_model ON mv_conversation_summary(model_id)",
                    "CREATE INDEX idx_mv_conversation_summary_revenue ON mv_conversation_summary(total_revenue DESC)"
                ]
            }
        ]
        
        for view_def in view_definitions:
            try:
                # Drop existing view if exists
                await db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_def['name']} CASCADE"))
                
                # Create materialized view
                await db.execute(text(f"""
                    CREATE MATERIALIZED VIEW {view_def['name']} AS
                    {view_def['query']}
                """))
                
                # Create indexes
                for index_sql in view_def.get("indexes", []):
                    await db.execute(text(index_sql))
                
                await db.commit()
                
                views_created.append({
                    "view": view_def["name"],
                    "status": "created",
                    "refresh": view_def["refresh"]
                })
                
                logger.info(f"Created materialized view: {view_def['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create view {view_def['name']}: {e}")
                views_created.append({
                    "view": view_def["name"],
                    "status": "failed",
                    "error": str(e)
                })
        
        return views_created
    
    async def setup_query_monitoring(self, db: AsyncSession) -> Dict[str, Any]:
        """Setup query monitoring and alerting."""
        try:
            # Enable query logging for slow queries
            await db.execute(text("ALTER SYSTEM SET log_min_duration_statement = '100ms'"))
            
            # Enable auto_explain for slow queries
            await db.execute(text("ALTER SYSTEM SET session_preload_libraries = 'auto_explain'"))
            await db.execute(text("ALTER SYSTEM SET auto_explain.log_min_duration = '100ms'"))
            await db.execute(text("ALTER SYSTEM SET auto_explain.log_analyze = true"))
            
            # Create monitoring function
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION monitor_query_performance()
                RETURNS TABLE(
                    query_text text,
                    calls bigint,
                    total_time double precision,
                    mean_time double precision,
                    max_time double precision
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        LEFT(query, 100) as query_text,
                        calls,
                        total_exec_time as total_time,
                        mean_exec_time as mean_time,
                        max_exec_time as max_time
                    FROM pg_stat_statements
                    WHERE mean_exec_time > 50
                    ORDER BY mean_exec_time DESC
                    LIMIT 20;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            await db.commit()
            
            return {
                "status": "success",
                "monitoring_enabled": True,
                "slow_query_threshold": "100ms",
                "auto_explain_enabled": True
            }
            
        except Exception as e:
            logger.error(f"Failed to setup query monitoring: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def generate_optimization_report(self, db: AsyncSession) -> Dict[str, Any]:
        """Generate comprehensive database optimization report."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "slow_queries": await self.analyze_slow_queries(db),
            "missing_indexes": await self.analyze_missing_indexes(db),
            "table_bloat": await self.analyze_table_bloat(db),
            "autovacuum": await self.optimize_autovacuum_settings(db),
            "connection_stats": await self._get_connection_stats(db),
            "cache_hit_ratio": await self._get_cache_hit_ratio(db)
        }
        
        # Cache report
        cache_key = "db_optimization_report"
        await redis_manager.set(
            cache_key,
            json.dumps(report, default=str),
            expire=self.cache_ttl
        )
        
        return report
    
    async def _get_connection_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get database connection statistics."""
        result = await db.execute(text("""
            SELECT 
                count(*) as total,
                count(*) FILTER (WHERE state = 'active') as active,
                count(*) FILTER (WHERE state = 'idle') as idle,
                count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                max(EXTRACT(EPOCH FROM (now() - query_start))) as longest_query_seconds
            FROM pg_stat_activity
            WHERE datname = current_database()
        """))
        
        row = result.first()
        return {
            "total_connections": row.total,
            "active_connections": row.active,
            "idle_connections": row.idle,
            "idle_in_transaction": row.idle_in_transaction,
            "longest_running_query_seconds": round(row.longest_query_seconds or 0, 2)
        }
    
    async def _get_cache_hit_ratio(self, db: AsyncSession) -> Dict[str, float]:
        """Get database cache hit ratios."""
        result = await db.execute(text("""
            SELECT 
                sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100 as heap_hit_ratio,
                sum(idx_blks_hit) / NULLIF(sum(idx_blks_hit) + sum(idx_blks_read), 0) * 100 as index_hit_ratio
            FROM pg_statio_user_tables
        """))
        
        row = result.first()
        return {
            "heap_cache_hit_ratio": round(row.heap_hit_ratio or 0, 2),
            "index_cache_hit_ratio": round(row.index_hit_ratio or 0, 2)
        }