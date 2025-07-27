"""
Database query analyzer for performance optimization.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes database queries for performance optimization."""
    
    @staticmethod
    async def analyze_slow_queries(
        session: AsyncSession,
        min_duration_ms: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get slow queries from pg_stat_statements.
        
        Args:
            session: Database session
            min_duration_ms: Minimum query duration in milliseconds
            
        Returns:
            List of slow queries with statistics
        """
        query = text("""
            SELECT 
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                min_exec_time,
                max_exec_time,
                stddev_exec_time,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > :min_duration
                AND query NOT LIKE '%pg_stat_statements%'
            ORDER BY mean_exec_time DESC
            LIMIT 50
        """)
        
        try:
            result = await session.execute(
                query,
                {"min_duration": min_duration_ms}
            )
            
            return [
                {
                    "query": row.query,
                    "calls": row.calls,
                    "total_time_ms": round(row.total_exec_time, 2),
                    "mean_time_ms": round(row.mean_exec_time, 2),
                    "min_time_ms": round(row.min_exec_time, 2),
                    "max_time_ms": round(row.max_exec_time, 2),
                    "stddev_time_ms": round(row.stddev_exec_time, 2),
                    "rows_returned": row.rows
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"Could not analyze slow queries: {e}")
            return []
    
    @staticmethod
    async def analyze_missing_indexes(
        session: AsyncSession,
        min_scans: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Identify tables that might benefit from indexes.
        
        Args:
            session: Database session
            min_scans: Minimum number of sequential scans
            
        Returns:
            List of tables with missing index suggestions
        """
        query = text("""
            SELECT 
                schemaname,
                tablename,
                seq_scan,
                seq_tup_read,
                idx_scan,
                idx_tup_fetch,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup,
                CASE 
                    WHEN seq_scan > 0 
                    THEN ROUND(100.0 * seq_scan / (seq_scan + idx_scan), 2)
                    ELSE 0 
                END as seq_scan_ratio
            FROM pg_stat_user_tables
            WHERE seq_scan > :min_scans
                AND schemaname = 'public'
            ORDER BY seq_tup_read DESC
        """)
        
        result = await session.execute(
            query,
            {"min_scans": min_scans}
        )
        
        suggestions = []
        for row in result:
            if row.seq_scan_ratio > 50:  # More than 50% sequential scans
                suggestions.append({
                    "table": row.tablename,
                    "seq_scans": row.seq_scan,
                    "index_scans": row.idx_scan,
                    "seq_scan_ratio": row.seq_scan_ratio,
                    "rows_read_seq": row.seq_tup_read,
                    "live_tuples": row.n_live_tup,
                    "suggestion": "Consider adding indexes to reduce sequential scans"
                })
        
        return suggestions
    
    @staticmethod
    async def analyze_table_bloat(
        session: AsyncSession,
        min_bloat_ratio: float = 1.2
    ) -> List[Dict[str, Any]]:
        """
        Identify tables with significant bloat.
        
        Args:
            session: Database session
            min_bloat_ratio: Minimum bloat ratio to report
            
        Returns:
            List of bloated tables
        """
        query = text("""
            WITH table_bloat AS (
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size,
                    ROUND(100 * pg_total_relation_size(schemaname||'.'||tablename) / 
                        GREATEST(pg_database_size(current_database()), 1)::numeric, 2) as percent_of_db,
                    n_live_tup,
                    n_dead_tup,
                    CASE 
                        WHEN n_live_tup > 0 
                        THEN ROUND(n_dead_tup::numeric / n_live_tup::numeric, 4)
                        ELSE 0 
                    END as bloat_ratio
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            )
            SELECT * FROM table_bloat
            WHERE bloat_ratio >= :min_bloat
            ORDER BY bloat_ratio DESC
        """)
        
        result = await session.execute(
            query,
            {"min_bloat": min_bloat_ratio}
        )
        
        return [
            {
                "table": row.tablename,
                "total_size": row.total_size,
                "table_size": row.table_size,
                "index_size": row.index_size,
                "percent_of_db": row.percent_of_db,
                "live_tuples": row.n_live_tup,
                "dead_tuples": row.n_dead_tup,
                "bloat_ratio": float(row.bloat_ratio),
                "action": "VACUUM ANALYZE" if row.bloat_ratio < 2 else "VACUUM FULL"
            }
            for row in result
        ]
    
    @staticmethod
    async def analyze_index_usage(
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Analyze index usage to identify unused or inefficient indexes.
        
        Args:
            session: Database session
            
        Returns:
            List of index usage statistics
        """
        query = text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                CASE 
                    WHEN idx_scan = 0 THEN 'UNUSED'
                    WHEN idx_scan < 100 THEN 'RARELY_USED'
                    ELSE 'ACTIVE'
                END as usage_status
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
            ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
        """)
        
        result = await session.execute(query)
        
        return [
            {
                "table": row.tablename,
                "index": row.indexname,
                "scans": row.idx_scan,
                "tuples_read": row.idx_tup_read,
                "tuples_fetched": row.idx_tup_fetch,
                "size": row.index_size,
                "status": row.usage_status,
                "recommendation": "Consider dropping" if row.usage_status == 'UNUSED' else None
            }
            for row in result
        ]
    
    @staticmethod
    async def get_query_execution_plan(
        session: AsyncSession,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get execution plan for a query.
        
        Args:
            session: Database session
            query: SQL query to analyze
            params: Query parameters
            
        Returns:
            Execution plan details
        """
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        
        try:
            result = await session.execute(text(explain_query), params or {})
            plan_json = result.scalar()
            
            return plan_json[0] if plan_json else []
        except Exception as e:
            logger.error(f"Failed to get execution plan: {e}")
            return []
    
    @staticmethod
    async def analyze_connection_stats(
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Analyze database connection statistics.
        
        Args:
            session: Database session
            
        Returns:
            Connection statistics
        """
        query = text("""
            SELECT
                COUNT(*) as total_connections,
                COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                COUNT(*) FILTER (WHERE state = 'idle') as idle_connections,
                COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                COUNT(*) FILTER (WHERE wait_event IS NOT NULL) as waiting_connections,
                MAX(EXTRACT(EPOCH FROM (now() - backend_start))) as longest_connection_seconds,
                MAX(EXTRACT(EPOCH FROM (now() - state_change))) as longest_idle_seconds
            FROM pg_stat_activity
            WHERE pid != pg_backend_pid()
        """)
        
        result = await session.execute(query)
        row = result.fetchone()
        
        return {
            "total_connections": row.total_connections,
            "active_connections": row.active_connections,
            "idle_connections": row.idle_connections,
            "idle_in_transaction": row.idle_in_transaction,
            "waiting_connections": row.waiting_connections,
            "longest_connection_minutes": round(row.longest_connection_seconds / 60, 2) if row.longest_connection_seconds else 0,
            "longest_idle_minutes": round(row.longest_idle_seconds / 60, 2) if row.longest_idle_seconds else 0
        }
    
    @staticmethod
    async def generate_optimization_report(
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Generate comprehensive database optimization report.
        
        Args:
            session: Database session
            
        Returns:
            Optimization report with recommendations
        """
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "sections": {}
        }
        
        # Analyze slow queries
        slow_queries = await QueryAnalyzer.analyze_slow_queries(session)
        report["sections"]["slow_queries"] = {
            "count": len(slow_queries),
            "queries": slow_queries[:10],  # Top 10
            "recommendation": "Review and optimize queries with mean execution time > 100ms"
        }
        
        # Analyze missing indexes
        missing_indexes = await QueryAnalyzer.analyze_missing_indexes(session)
        report["sections"]["missing_indexes"] = {
            "count": len(missing_indexes),
            "tables": missing_indexes,
            "recommendation": "Add indexes to tables with high sequential scan ratios"
        }
        
        # Analyze table bloat
        bloated_tables = await QueryAnalyzer.analyze_table_bloat(session)
        report["sections"]["table_bloat"] = {
            "count": len(bloated_tables),
            "tables": bloated_tables,
            "recommendation": "Run VACUUM on bloated tables to reclaim space"
        }
        
        # Analyze index usage
        index_usage = await QueryAnalyzer.analyze_index_usage(session)
        unused_indexes = [idx for idx in index_usage if idx["status"] == "UNUSED"]
        report["sections"]["unused_indexes"] = {
            "count": len(unused_indexes),
            "indexes": unused_indexes[:10],  # Top 10
            "recommendation": "Consider dropping unused indexes to reduce maintenance overhead"
        }
        
        # Analyze connections
        connection_stats = await QueryAnalyzer.analyze_connection_stats(session)
        report["sections"]["connections"] = {
            "stats": connection_stats,
            "recommendation": "Monitor idle connections and consider connection pooling adjustments"
        }
        
        return report


class QueryOptimizer:
    """Provides query optimization suggestions."""
    
    @staticmethod
    def suggest_indexes(
        table: str,
        frequent_filters: List[str],
        frequent_joins: List[str]
    ) -> List[str]:
        """
        Suggest indexes based on query patterns.
        
        Args:
            table: Table name
            frequent_filters: Columns frequently used in WHERE clauses
            frequent_joins: Columns frequently used in JOINs
            
        Returns:
            List of CREATE INDEX statements
        """
        suggestions = []
        
        # Single column indexes for filters
        for column in frequent_filters:
            suggestions.append(
                f"CREATE INDEX idx_{table}_{column} ON {table}({column});"
            )
        
        # Composite indexes for common filter combinations
        if len(frequent_filters) > 1:
            columns = ", ".join(frequent_filters[:3])  # Max 3 columns
            suggestions.append(
                f"CREATE INDEX idx_{table}_composite ON {table}({columns});"
            )
        
        # Join indexes
        for column in frequent_joins:
            if column not in frequent_filters:
                suggestions.append(
                    f"CREATE INDEX idx_{table}_{column}_join ON {table}({column});"
                )
        
        return suggestions
    
    @staticmethod
    def optimize_query(query: str) -> Dict[str, Any]:
        """
        Provide query optimization suggestions.
        
        Args:
            query: SQL query to optimize
            
        Returns:
            Optimization suggestions
        """
        suggestions = []
        
        # Check for SELECT *
        if "SELECT *" in query.upper():
            suggestions.append({
                "issue": "SELECT * usage",
                "suggestion": "Specify only required columns to reduce data transfer"
            })
        
        # Check for missing WHERE clause
        if "WHERE" not in query.upper() and any(keyword in query.upper() 
                                                 for keyword in ["UPDATE", "DELETE"]):
            suggestions.append({
                "issue": "Missing WHERE clause",
                "suggestion": "Add WHERE clause to avoid full table scans"
            })
        
        # Check for LIKE with leading wildcard
        if "LIKE '%" in query:
            suggestions.append({
                "issue": "Leading wildcard in LIKE",
                "suggestion": "Avoid leading wildcards or use full-text search"
            })
        
        # Check for NOT IN subqueries
        if "NOT IN (SELECT" in query.upper():
            suggestions.append({
                "issue": "NOT IN with subquery",
                "suggestion": "Use NOT EXISTS or LEFT JOIN for better performance"
            })
        
        # Check for OR conditions
        if " OR " in query.upper():
            suggestions.append({
                "issue": "OR conditions",
                "suggestion": "Consider using UNION for OR conditions on different columns"
            })
        
        return {
            "original_query": query,
            "suggestions": suggestions,
            "has_issues": len(suggestions) > 0
        }