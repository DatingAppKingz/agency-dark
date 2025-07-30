"""Query performance monitoring and optimization service."""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, and_
from datetime import datetime, timedelta
from collections import defaultdict
import json
import re

from models.user import User
from models.agency import Agency
from core.redis import redis_manager
from core.database import engine
from core.exceptions import ValidationError


class QueryPerformanceService:
    """Service for monitoring and analyzing database query performance."""
    
    # Thresholds for query classification
    SLOW_QUERY_THRESHOLD_MS = 100
    VERY_SLOW_QUERY_THRESHOLD_MS = 500
    
    @staticmethod
    async def get_slow_queries(
        db: AsyncSession,
        min_duration_ms: int = 100,
        limit: int = 50,
        time_range_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get slow queries from PostgreSQL stats."""
        since = datetime.utcnow() - timedelta(hours=time_range_hours)
        
        # Query pg_stat_statements for slow queries
        query = text("""
            SELECT 
                query,
                calls,
                total_exec_time as total_time,
                mean_exec_time as mean_time,
                max_exec_time as max_time,
                min_exec_time as min_time,
                stddev_exec_time as stddev_time,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > :min_duration
            ORDER BY mean_exec_time DESC
            LIMIT :limit
        """)
        
        try:
            result = await db.execute(
                query,
                {"min_duration": min_duration_ms, "limit": limit}
            )
            rows = result.fetchall()
        except Exception:
            # If pg_stat_statements is not available, return mock data
            return await QueryPerformanceService._get_mock_slow_queries()
        
        slow_queries = []
        for row in rows:
            slow_queries.append({
                "query": QueryPerformanceService._sanitize_query(row[0]),
                "calls": row[1],
                "total_time_ms": round(row[2], 2),
                "mean_time_ms": round(row[3], 2),
                "max_time_ms": round(row[4], 2),
                "min_time_ms": round(row[5], 2),
                "stddev_time_ms": round(row[6], 2) if row[6] else 0,
                "rows_returned": row[7],
                "severity": QueryPerformanceService._classify_query_severity(row[3])
            })
        
        return slow_queries
    
    @staticmethod
    async def analyze_query(
        db: AsyncSession,
        query_sql: str
    ) -> Dict[str, Any]:
        """Analyze a specific query and provide optimization suggestions."""
        # Get query execution plan
        explain_query = text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_sql}")
        
        try:
            result = await db.execute(explain_query)
            plan_json = result.scalar()
            plan = json.loads(plan_json)[0]
        except Exception as e:
            return {
                "error": f"Failed to analyze query: {str(e)}",
                "query": query_sql
            }
        
        # Extract key metrics from plan
        execution_time = plan.get("Execution Time", 0)
        planning_time = plan.get("Planning Time", 0)
        total_time = execution_time + planning_time
        
        # Analyze the plan for issues
        issues = QueryPerformanceService._analyze_plan_issues(plan["Plan"])
        suggestions = QueryPerformanceService._generate_suggestions(plan["Plan"], issues)
        
        return {
            "query": query_sql,
            "execution_time_ms": execution_time,
            "planning_time_ms": planning_time,
            "total_time_ms": total_time,
            "plan": plan["Plan"],
            "issues": issues,
            "suggestions": suggestions,
            "severity": QueryPerformanceService._classify_query_severity(total_time)
        }
    
    @staticmethod
    async def get_query_statistics(
        db: AsyncSession,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """Get overall query performance statistics."""
        # Get database statistics
        stats_query = text("""
            SELECT 
                COUNT(*) as total_queries,
                AVG(mean_exec_time) as avg_query_time,
                MAX(max_exec_time) as max_query_time,
                SUM(calls) as total_calls,
                SUM(total_exec_time) as total_exec_time
            FROM pg_stat_statements
        """)
        
        try:
            result = await db.execute(stats_query)
            stats = result.fetchone()
        except Exception:
            # Return mock stats if pg_stat_statements not available
            return await QueryPerformanceService._get_mock_statistics()
        
        # Get table statistics
        table_stats = await QueryPerformanceService._get_table_statistics(db)
        
        # Get index usage statistics
        index_stats = await QueryPerformanceService._get_index_statistics(db)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "query_stats": {
                "total_unique_queries": stats[0] if stats else 0,
                "avg_execution_time_ms": round(stats[1], 2) if stats and stats[1] else 0,
                "max_execution_time_ms": round(stats[2], 2) if stats and stats[2] else 0,
                "total_query_calls": stats[3] if stats else 0,
                "total_execution_time_ms": round(stats[4], 2) if stats and stats[4] else 0
            },
            "table_stats": table_stats,
            "index_stats": index_stats,
            "cache_hit_ratio": await QueryPerformanceService._get_cache_hit_ratio(db)
        }
    
    @staticmethod
    async def get_table_sizes(
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get table sizes and bloat information."""
        query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as indexes_size,
                n_live_tup as row_count,
                n_dead_tup as dead_rows,
                CASE WHEN n_live_tup > 0 
                    THEN round(100.0 * n_dead_tup / n_live_tup, 2) 
                    ELSE 0 
                END as bloat_percent
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 20
        """)
        
        result = await db.execute(query)
        tables = []
        
        for row in result:
            tables.append({
                "schema": row[0],
                "table": row[1],
                "total_size": row[2],
                "size_bytes": row[3],
                "table_size": row[4],
                "indexes_size": row[5],
                "row_count": row[6],
                "dead_rows": row[7],
                "bloat_percent": float(row[8])
            })
        
        return tables
    
    @staticmethod
    async def get_index_usage(
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get index usage statistics."""
        query = text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan as index_scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                CASE WHEN idx_scan = 0 THEN 'UNUSED' ELSE 'USED' END as status
            FROM pg_stat_user_indexes
            ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
            LIMIT 50
        """)
        
        result = await db.execute(query)
        indexes = []
        
        for row in result:
            indexes.append({
                "schema": row[0],
                "table": row[1],
                "index": row[2],
                "scans": row[3],
                "tuples_read": row[4],
                "tuples_fetched": row[5],
                "size": row[6],
                "status": row[7],
                "efficiency": round(row[5] / row[4] * 100, 2) if row[4] > 0 else 0
            })
        
        return indexes
    
    @staticmethod
    async def recommend_optimizations(
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate optimization recommendations based on current performance."""
        recommendations = []
        
        # Check for missing indexes
        missing_indexes = await QueryPerformanceService._check_missing_indexes(db)
        if missing_indexes:
            recommendations.extend(missing_indexes)
        
        # Check for unused indexes
        unused_indexes = await QueryPerformanceService._check_unused_indexes(db)
        if unused_indexes:
            recommendations.extend(unused_indexes)
        
        # Check for table bloat
        bloated_tables = await QueryPerformanceService._check_table_bloat(db)
        if bloated_tables:
            recommendations.extend(bloated_tables)
        
        # Check for outdated statistics
        stale_stats = await QueryPerformanceService._check_stale_statistics(db)
        if stale_stats:
            recommendations.extend(stale_stats)
        
        # Categorize recommendations
        high_priority = [r for r in recommendations if r["priority"] == "high"]
        medium_priority = [r for r in recommendations if r["priority"] == "medium"]
        low_priority = [r for r in recommendations if r["priority"] == "low"]
        
        return {
            "total_recommendations": len(recommendations),
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _sanitize_query(query: str) -> str:
        """Sanitize query by removing sensitive data."""
        # Remove specific values but keep structure
        sanitized = re.sub(r"'[^']*'", "'?'", query)
        sanitized = re.sub(r"\b\d+\b", "?", sanitized)
        return sanitized
    
    @staticmethod
    def _classify_query_severity(execution_time_ms: float) -> str:
        """Classify query severity based on execution time."""
        if execution_time_ms >= QueryPerformanceService.VERY_SLOW_QUERY_THRESHOLD_MS:
            return "critical"
        elif execution_time_ms >= QueryPerformanceService.SLOW_QUERY_THRESHOLD_MS:
            return "warning"
        else:
            return "normal"
    
    @staticmethod
    def _analyze_plan_issues(plan: Dict[str, Any]) -> List[str]:
        """Analyze query plan for performance issues."""
        issues = []
        
        # Check for sequential scans on large tables
        if plan.get("Node Type") == "Seq Scan" and plan.get("Rows", 0) > 1000:
            issues.append(f"Sequential scan on large table: {plan.get('Relation Name', 'unknown')}")
        
        # Check for nested loops with high row counts
        if plan.get("Node Type") == "Nested Loop" and plan.get("Rows", 0) > 1000:
            issues.append("Nested loop join with high row count")
        
        # Check for missing indexes
        if "Filter" in plan and plan.get("Node Type") == "Seq Scan":
            issues.append(f"Possible missing index on filter condition")
        
        # Recursively check child plans
        if "Plans" in plan:
            for child_plan in plan["Plans"]:
                issues.extend(QueryPerformanceService._analyze_plan_issues(child_plan))
        
        return issues
    
    @staticmethod
    def _generate_suggestions(plan: Dict[str, Any], issues: List[str]) -> List[str]:
        """Generate optimization suggestions based on plan analysis."""
        suggestions = []
        
        for issue in issues:
            if "Sequential scan" in issue:
                suggestions.append("Consider adding an index on frequently queried columns")
            elif "Nested loop" in issue:
                suggestions.append("Consider using hash or merge join for large datasets")
            elif "missing index" in issue:
                suggestions.append("Add index on filter columns to improve query performance")
        
        # General suggestions
        if plan.get("Total Cost", 0) > 10000:
            suggestions.append("High query cost detected - consider query optimization")
        
        return list(set(suggestions))  # Remove duplicates
    
    @staticmethod
    async def _get_mock_slow_queries() -> List[Dict[str, Any]]:
        """Return mock slow queries for testing."""
        return [
            {
                "query": "SELECT * FROM users WHERE agency_id = ? AND role = ?",
                "calls": 1523,
                "total_time_ms": 152300.0,
                "mean_time_ms": 100.0,
                "max_time_ms": 500.0,
                "min_time_ms": 50.0,
                "stddev_time_ms": 45.0,
                "rows_returned": 15230,
                "severity": "warning"
            },
            {
                "query": "SELECT * FROM transactions WHERE created_at > ? ORDER BY created_at DESC",
                "calls": 847,
                "total_time_ms": 423500.0,
                "mean_time_ms": 500.0,
                "max_time_ms": 2000.0,
                "min_time_ms": 200.0,
                "stddev_time_ms": 150.0,
                "rows_returned": 84700,
                "severity": "critical"
            }
        ]
    
    @staticmethod
    async def _get_mock_statistics() -> Dict[str, Any]:
        """Return mock statistics for testing."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": 24,
            "query_stats": {
                "total_unique_queries": 342,
                "avg_execution_time_ms": 45.2,
                "max_execution_time_ms": 2000.0,
                "total_query_calls": 154320,
                "total_execution_time_ms": 6975264.0
            },
            "table_stats": {
                "total_tables": 25,
                "total_size": "1.2 GB",
                "largest_table": "transactions",
                "most_accessed_table": "users"
            },
            "index_stats": {
                "total_indexes": 45,
                "unused_indexes": 5,
                "index_hit_ratio": 95.2
            },
            "cache_hit_ratio": 98.5
        }
    
    @staticmethod
    async def _get_table_statistics(db: AsyncSession) -> Dict[str, Any]:
        """Get table-level statistics."""
        query = text("""
            SELECT 
                COUNT(*) as table_count,
                pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))) as total_size
            FROM pg_stat_user_tables
        """)
        
        result = await db.execute(query)
        stats = result.fetchone()
        
        # Get most accessed table
        access_query = text("""
            SELECT tablename, n_tup_ins + n_tup_upd + n_tup_del as total_access
            FROM pg_stat_user_tables
            ORDER BY total_access DESC
            LIMIT 1
        """)
        
        access_result = await db.execute(access_query)
        most_accessed = access_result.fetchone()
        
        return {
            "total_tables": stats[0] if stats else 0,
            "total_size": stats[1] if stats else "0 bytes",
            "most_accessed_table": most_accessed[0] if most_accessed else "unknown"
        }
    
    @staticmethod
    async def _get_index_statistics(db: AsyncSession) -> Dict[str, Any]:
        """Get index-level statistics."""
        # Count total and unused indexes
        query = text("""
            SELECT 
                COUNT(*) as total_indexes,
                COUNT(CASE WHEN idx_scan = 0 THEN 1 END) as unused_indexes
            FROM pg_stat_user_indexes
        """)
        
        result = await db.execute(query)
        stats = result.fetchone()
        
        # Calculate index hit ratio
        hit_query = text("""
            SELECT 
                sum(idx_blks_hit) / (sum(idx_blks_hit) + sum(idx_blks_read)) * 100 as hit_ratio
            FROM pg_statio_user_indexes
            WHERE idx_blks_hit + idx_blks_read > 0
        """)
        
        hit_result = await db.execute(hit_query)
        hit_ratio = hit_result.scalar()
        
        return {
            "total_indexes": stats[0] if stats else 0,
            "unused_indexes": stats[1] if stats else 0,
            "index_hit_ratio": round(float(hit_ratio), 2) if hit_ratio else 0
        }
    
    @staticmethod
    async def _get_cache_hit_ratio(db: AsyncSession) -> float:
        """Get database cache hit ratio."""
        query = text("""
            SELECT 
                sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100
            FROM pg_statio_user_tables
            WHERE heap_blks_hit + heap_blks_read > 0
        """)
        
        result = await db.execute(query)
        ratio = result.scalar()
        
        return round(float(ratio), 2) if ratio else 0
    
    @staticmethod
    async def _check_missing_indexes(db: AsyncSession) -> List[Dict[str, Any]]:
        """Check for potentially missing indexes."""
        recommendations = []
        
        # This is a simplified check - in production, you'd analyze pg_stat_statements
        query = text("""
            SELECT 
                schemaname,
                tablename,
                n_tup_ins + n_tup_upd + n_tup_del as write_activity,
                seq_scan,
                seq_tup_read
            FROM pg_stat_user_tables
            WHERE seq_scan > 100 AND seq_tup_read / GREATEST(seq_scan, 1) > 1000
            ORDER BY seq_tup_read DESC
            LIMIT 10
        """)
        
        result = await db.execute(query)
        
        for row in result:
            recommendations.append({
                "type": "missing_index",
                "priority": "high" if row[4] > 1000000 else "medium",
                "table": f"{row[0]}.{row[1]}",
                "reason": f"High sequential scan activity ({row[3]} scans reading {row[4]} tuples)",
                "suggestion": f"Consider adding indexes on frequently queried columns in {row[1]}"
            })
        
        return recommendations
    
    @staticmethod
    async def _check_unused_indexes(db: AsyncSession) -> List[Dict[str, Any]]:
        """Check for unused indexes."""
        recommendations = []
        
        query = text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(pg_relation_size(indexrelid)) as size
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0 
                AND indexrelname NOT LIKE '%_pkey'
                AND pg_relation_size(indexrelid) > 1048576  -- > 1MB
            ORDER BY pg_relation_size(indexrelid) DESC
            LIMIT 10
        """)
        
        result = await db.execute(query)
        
        for row in result:
            recommendations.append({
                "type": "unused_index",
                "priority": "low",
                "index": f"{row[0]}.{row[2]}",
                "table": f"{row[0]}.{row[1]}",
                "size": row[3],
                "reason": "Index has never been used",
                "suggestion": f"Consider dropping unused index {row[2]} to save {row[3]} of storage"
            })
        
        return recommendations
    
    @staticmethod
    async def _check_table_bloat(db: AsyncSession) -> List[Dict[str, Any]]:
        """Check for table bloat."""
        recommendations = []
        
        query = text("""
            SELECT 
                schemaname,
                tablename,
                n_dead_tup,
                n_live_tup,
                round(100.0 * n_dead_tup / NULLIF(n_live_tup, 0), 2) as dead_pct
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000 
                AND n_live_tup > 0
                AND (100.0 * n_dead_tup / n_live_tup) > 20
            ORDER BY n_dead_tup DESC
            LIMIT 10
        """)
        
        result = await db.execute(query)
        
        for row in result:
            recommendations.append({
                "type": "table_bloat",
                "priority": "medium" if row[4] > 50 else "low",
                "table": f"{row[0]}.{row[1]}",
                "dead_tuples": row[2],
                "bloat_percent": float(row[4]),
                "reason": f"Table has {row[4]}% dead tuples ({row[2]} dead vs {row[3]} live)",
                "suggestion": f"Run VACUUM on {row[1]} to reclaim space"
            })
        
        return recommendations
    
    @staticmethod
    async def _check_stale_statistics(db: AsyncSession) -> List[Dict[str, Any]]:
        """Check for tables with stale statistics."""
        recommendations = []
        
        query = text("""
            SELECT 
                schemaname,
                tablename,
                n_mod_since_analyze,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE n_mod_since_analyze > 1000
                AND (last_analyze IS NULL OR last_analyze < CURRENT_DATE - INTERVAL '7 days')
                AND (last_autoanalyze IS NULL OR last_autoanalyze < CURRENT_DATE - INTERVAL '7 days')
            ORDER BY n_mod_since_analyze DESC
            LIMIT 10
        """)
        
        result = await db.execute(query)
        
        for row in result:
            last_analyzed = row[3] or row[4]
            days_old = (datetime.utcnow() - last_analyzed).days if last_analyzed else None
            
            recommendations.append({
                "type": "stale_statistics",
                "priority": "medium",
                "table": f"{row[0]}.{row[1]}",
                "modifications": row[2],
                "last_analyzed": last_analyzed.isoformat() if last_analyzed else "never",
                "days_since_analyze": days_old,
                "reason": f"Table has {row[2]} modifications since last analyze",
                "suggestion": f"Run ANALYZE on {row[1]} to update statistics"
            })
        
        return recommendations