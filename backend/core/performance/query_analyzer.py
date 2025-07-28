"""
Query Performance Analyzer - Analyzes and optimizes database queries
"""
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.orm import Query

from core.logging import get_logger
from core.redis import redis_client
from core.database import get_db

logger = get_logger(__name__)


class QueryPerformanceAnalyzer:
    """Analyzes database query performance and suggests optimizations"""
    
    def __init__(self):
        self.slow_query_threshold = 0.1  # 100ms
        self.query_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "max_time": 0,
            "min_time": float('inf'),
            "avg_time": 0,
            "samples": []
        })
        self._monitoring_enabled = True
        
    async def analyze_slow_queries(
        self,
        db: AsyncSession,
        time_range_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Analyze slow queries from PostgreSQL logs"""
        # Query pg_stat_statements for slow queries
        query = text("""
            SELECT 
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                stddev_exec_time,
                min_exec_time,
                max_exec_time,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > :threshold_ms
            ORDER BY mean_exec_time DESC
            LIMIT 50
        """)
        
        result = await db.execute(
            query,
            {"threshold_ms": self.slow_query_threshold * 1000}
        )
        
        slow_queries = []
        for row in result:
            slow_queries.append({
                "query": self._normalize_query(row.query),
                "calls": row.calls,
                "total_time": row.total_exec_time,
                "avg_time": row.mean_exec_time,
                "stddev_time": row.stddev_exec_time,
                "min_time": row.min_exec_time,
                "max_time": row.max_exec_time,
                "avg_rows": row.rows / row.calls if row.calls > 0 else 0,
                "optimization_suggestions": self._suggest_optimizations(row.query)
            })
            
        return slow_queries
        
    async def get_missing_indexes(
        self,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Identify potentially missing indexes"""
        # Query for tables with sequential scans
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
                n_dead_tup
            FROM pg_stat_user_tables
            WHERE seq_scan > idx_scan 
                AND n_live_tup > 10000
                AND seq_scan > 1000
            ORDER BY seq_tup_read DESC
            LIMIT 20
        """)
        
        result = await db.execute(query)
        
        missing_indexes = []
        for row in result:
            # Analyze table usage patterns
            suggestions = await self._analyze_table_for_indexes(
                db, row.schemaname, row.tablename
            )
            
            missing_indexes.append({
                "schema": row.schemaname,
                "table": row.tablename,
                "seq_scans": row.seq_scan,
                "index_scans": row.idx_scan,
                "rows_read_seq": row.seq_tup_read,
                "rows_read_idx": row.idx_tup_fetch,
                "table_size": row.n_live_tup,
                "suggestions": suggestions
            })
            
        return missing_indexes
        
    async def get_unused_indexes(
        self,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Identify unused or rarely used indexes"""
        query = text("""
            SELECT 
                s.schemaname,
                s.tablename,
                s.indexname,
                s.idx_scan,
                pg_size_pretty(pg_relation_size(s.indexrelid)) as index_size,
                i.indisunique,
                i.indisprimary
            FROM pg_stat_user_indexes s
            JOIN pg_index i ON s.indexrelid = i.indexrelid
            WHERE s.idx_scan < 100
                AND s.schemaname NOT IN ('pg_catalog', 'information_schema')
                AND NOT i.indisprimary
                AND NOT i.indisunique
                AND pg_relation_size(s.indexrelid) > 1000000  -- > 1MB
            ORDER BY pg_relation_size(s.indexrelid) DESC
        """)
        
        result = await db.execute(query)
        
        unused_indexes = []
        for row in result:
            unused_indexes.append({
                "schema": row.schemaname,
                "table": row.tablename,
                "index": row.indexname,
                "scans": row.idx_scan,
                "size": row.index_size,
                "recommendation": "Consider dropping this index to save space"
            })
            
        return unused_indexes
        
    async def analyze_query_patterns(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze common query patterns and suggest optimizations"""
        # Get most common query patterns
        patterns = await self._get_query_patterns(db)
        
        # Analyze N+1 queries
        n_plus_one = await self._detect_n_plus_one_queries(patterns)
        
        # Analyze missing joins
        missing_joins = await self._detect_missing_joins(patterns)
        
        # Analyze full table scans
        full_scans = await self._detect_full_table_scans(db)
        
        return {
            "n_plus_one_queries": n_plus_one,
            "missing_joins": missing_joins,
            "full_table_scans": full_scans,
            "optimization_opportunities": len(n_plus_one) + len(missing_joins) + len(full_scans)
        }
        
    async def get_table_statistics(
        self,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get detailed table statistics for optimization"""
        query = text("""
            SELECT 
                n.nspname as schema,
                c.relname as table,
                pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
                pg_size_pretty(pg_relation_size(c.oid)) as table_size,
                pg_size_pretty(pg_indexes_size(c.oid)) as indexes_size,
                pg_stat_get_live_tuples(c.oid) as live_rows,
                pg_stat_get_dead_tuples(c.oid) as dead_rows,
                CASE 
                    WHEN pg_stat_get_live_tuples(c.oid) > 0 
                    THEN pg_stat_get_dead_tuples(c.oid)::float / pg_stat_get_live_tuples(c.oid) 
                    ELSE 0 
                END as bloat_ratio,
                pg_stat_get_last_vacuum_time(c.oid) as last_vacuum,
                pg_stat_get_last_autovacuum_time(c.oid) as last_autovacuum,
                pg_stat_get_last_analyze_time(c.oid) as last_analyze,
                pg_stat_get_last_autoanalyze_time(c.oid) as last_autoanalyze
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
                AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                AND pg_relation_size(c.oid) > 1000000  -- > 1MB
            ORDER BY pg_total_relation_size(c.oid) DESC
        """)
        
        result = await db.execute(query)
        
        statistics = []
        for row in result:
            maintenance_needed = self._check_maintenance_needed(row)
            
            statistics.append({
                "schema": row.schema,
                "table": row.table,
                "total_size": row.total_size,
                "table_size": row.table_size,
                "indexes_size": row.indexes_size,
                "live_rows": row.live_rows,
                "dead_rows": row.dead_rows,
                "bloat_ratio": round(row.bloat_ratio * 100, 2),
                "last_vacuum": row.last_vacuum,
                "last_autovacuum": row.last_autovacuum,
                "last_analyze": row.last_analyze,
                "last_autoanalyze": row.last_autoanalyze,
                "maintenance_needed": maintenance_needed
            })
            
        return statistics
        
    def _normalize_query(self, query: str) -> str:
        """Normalize query for comparison"""
        # Remove specific values to group similar queries
        import re
        
        # Replace numbers with ?
        query = re.sub(r'\b\d+\b', '?', query)
        
        # Replace string literals with ?
        query = re.sub(r"'[^']*'", '?', query)
        
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        return query
        
    def _suggest_optimizations(self, query: str) -> List[str]:
        """Suggest query optimizations"""
        suggestions = []
        
        query_lower = query.lower()
        
        # Check for SELECT *
        if 'select *' in query_lower:
            suggestions.append("Avoid SELECT *, specify only needed columns")
            
        # Check for missing WHERE clause
        if 'where' not in query_lower and ('update' in query_lower or 'delete' in query_lower):
            suggestions.append("Missing WHERE clause - this will affect all rows")
            
        # Check for NOT IN
        if 'not in' in query_lower:
            suggestions.append("Consider using NOT EXISTS instead of NOT IN")
            
        # Check for OR conditions
        if ' or ' in query_lower and 'where' in query_lower:
            suggestions.append("OR conditions may prevent index usage, consider UNION")
            
        # Check for functions on indexed columns
        if any(func in query_lower for func in ['lower(', 'upper(', 'substr(', 'date(']):
            suggestions.append("Functions on columns prevent index usage, consider functional indexes")
            
        # Check for LIKE with leading wildcard
        if "like '%" in query_lower:
            suggestions.append("Leading wildcard in LIKE prevents index usage")
            
        # Check for missing LIMIT in large queries
        if 'limit' not in query_lower and 'select' in query_lower:
            suggestions.append("Consider adding LIMIT clause for large result sets")
            
        return suggestions
        
    async def _analyze_table_for_indexes(
        self,
        db: AsyncSession,
        schema: str,
        table: str
    ) -> List[Dict[str, Any]]:
        """Analyze table and suggest indexes"""
        suggestions = []
        
        # Check foreign key columns without indexes
        fk_query = text("""
            SELECT 
                a.attname as column_name,
                NOT EXISTS (
                    SELECT 1 
                    FROM pg_index i 
                    WHERE i.indrelid = c.conrelid 
                    AND a.attnum = ANY(i.indkey)
                ) as missing_index
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE c.contype = 'f'
                AND c.conrelid = :table_oid
        """)
        
        # Get table OID
        oid_result = await db.execute(
            text("SELECT oid FROM pg_class WHERE relname = :table AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = :schema)"),
            {"table": table, "schema": schema}
        )
        table_oid = oid_result.scalar()
        
        if table_oid:
            fk_result = await db.execute(fk_query, {"table_oid": table_oid})
            
            for row in fk_result:
                if row.missing_index:
                    suggestions.append({
                        "type": "foreign_key_index",
                        "column": row.column_name,
                        "suggestion": f"CREATE INDEX idx_{table}_{row.column_name} ON {schema}.{table}({row.column_name})",
                        "reason": "Foreign key without index can slow down joins and deletes"
                    })
                    
        # Check for frequently filtered columns
        # This would require query log analysis
        
        return suggestions
        
    async def _get_query_patterns(
        self,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Extract common query patterns"""
        # Get normalized queries from pg_stat_statements
        query = text("""
            SELECT 
                query,
                calls,
                mean_exec_time
            FROM pg_stat_statements
            WHERE calls > 100
            ORDER BY calls DESC
            LIMIT 1000
        """)
        
        result = await db.execute(query)
        
        patterns = []
        for row in result:
            patterns.append({
                "query": self._normalize_query(row.query),
                "calls": row.calls,
                "avg_time": row.mean_exec_time
            })
            
        return patterns
        
    async def _detect_n_plus_one_queries(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect potential N+1 query problems"""
        n_plus_one = []
        
        # Group patterns by similarity
        pattern_groups = defaultdict(list)
        
        for pattern in patterns:
            # Extract table name from pattern
            query = pattern["query"]
            if "select" in query.lower() and "from" in query.lower():
                # Simple extraction - would need more sophisticated parsing
                parts = query.lower().split("from")
                if len(parts) > 1:
                    table_part = parts[1].split()[0].strip()
                    pattern_groups[table_part].append(pattern)
                    
        # Look for patterns with high call counts on same table
        for table, table_patterns in pattern_groups.items():
            if len(table_patterns) > 10:
                total_calls = sum(p["calls"] for p in table_patterns)
                if total_calls > 1000:
                    n_plus_one.append({
                        "table": table,
                        "pattern_count": len(table_patterns),
                        "total_calls": total_calls,
                        "suggestion": "Consider using eager loading or batch queries"
                    })
                    
        return n_plus_one
        
    async def _detect_missing_joins(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect queries that could benefit from joins"""
        missing_joins = []
        
        # Look for multiple queries on related tables
        # This is a simplified detection - real implementation would be more sophisticated
        
        related_tables = [
            ("users", "agencies"),
            ("fans", "fan_analytics"),
            ("models", "model_analytics"),
            ("messages", "message_analytics")
        ]
        
        for table1, table2 in related_tables:
            table1_queries = [p for p in patterns if table1 in p["query"].lower()]
            table2_queries = [p for p in patterns if table2 in p["query"].lower()]
            
            if table1_queries and table2_queries:
                combined_calls = sum(p["calls"] for p in table1_queries + table2_queries)
                if combined_calls > 500:
                    missing_joins.append({
                        "tables": [table1, table2],
                        "separate_query_count": len(table1_queries) + len(table2_queries),
                        "total_calls": combined_calls,
                        "suggestion": f"Consider joining {table1} and {table2} in a single query"
                    })
                    
        return missing_joins
        
    async def _detect_full_table_scans(
        self,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Detect queries performing full table scans"""
        query = text("""
            SELECT 
                schemaname,
                tablename,
                seq_scan,
                seq_tup_read,
                n_live_tup,
                CASE 
                    WHEN seq_scan > 0 
                    THEN seq_tup_read::float / seq_scan 
                    ELSE 0 
                END as avg_rows_per_scan
            FROM pg_stat_user_tables
            WHERE seq_scan > 100
                AND n_live_tup > 10000
                AND seq_tup_read > n_live_tup * 10
            ORDER BY seq_tup_read DESC
            LIMIT 20
        """)
        
        result = await db.execute(query)
        
        full_scans = []
        for row in result:
            full_scans.append({
                "schema": row.schemaname,
                "table": row.tablename,
                "scan_count": row.seq_scan,
                "rows_scanned": row.seq_tup_read,
                "table_size": row.n_live_tup,
                "avg_rows_per_scan": round(row.avg_rows_per_scan, 2),
                "impact": "high" if row.seq_tup_read > row.n_live_tup * 100 else "medium",
                "suggestion": "Add appropriate indexes to avoid full table scans"
            })
            
        return full_scans
        
    def _check_maintenance_needed(self, row: Any) -> List[str]:
        """Check if table maintenance is needed"""
        maintenance = []
        
        # Check bloat
        if row.bloat_ratio > 0.2:  # 20% dead tuples
            maintenance.append("High bloat - consider VACUUM")
            
        # Check last vacuum
        if row.last_vacuum and row.last_autovacuum:
            last_vacuum_time = max(row.last_vacuum, row.last_autovacuum)
            if last_vacuum_time < datetime.now() - timedelta(days=7):
                maintenance.append("No recent vacuum - consider manual VACUUM")
        elif not row.last_vacuum and not row.last_autovacuum:
            maintenance.append("Never vacuumed - run VACUUM ANALYZE")
            
        # Check last analyze
        if row.last_analyze and row.last_autoanalyze:
            last_analyze_time = max(row.last_analyze, row.last_autoanalyze)
            if last_analyze_time < datetime.now() - timedelta(days=3):
                maintenance.append("Stale statistics - consider ANALYZE")
        elif not row.last_analyze and not row.last_autoanalyze:
            maintenance.append("Never analyzed - run ANALYZE")
            
        return maintenance
        
    def enable_query_monitoring(self):
        """Enable query monitoring"""
        self._monitoring_enabled = True
        logger.info("Query monitoring enabled")
        
    def disable_query_monitoring(self):
        """Disable query monitoring"""
        self._monitoring_enabled = False
        logger.info("Query monitoring disabled")
        
    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get current monitoring statistics"""
        total_queries = sum(stats["count"] for stats in self.query_stats.values())
        slow_queries = sum(
            1 for stats in self.query_stats.values() 
            if stats["avg_time"] > self.slow_query_threshold
        )
        
        return {
            "total_queries_monitored": total_queries,
            "unique_query_patterns": len(self.query_stats),
            "slow_queries": slow_queries,
            "monitoring_enabled": self._monitoring_enabled,
            "slow_query_threshold_ms": self.slow_query_threshold * 1000
        }


# Global instance
query_analyzer = QueryPerformanceAnalyzer()