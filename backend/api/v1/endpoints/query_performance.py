"""
Query Performance Analysis API endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from core.domain.models import User, UserRole
from core.performance.query_analyzer import QueryPerformanceAnalyzer, query_performance_analyzer

router = APIRouter(prefix="/query-performance", tags=["query-performance"])


@router.get("/analyze")
async def analyze_query_performance(
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze query performance for the specified time range
    
    Requires SUPER_ADMIN role
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can analyze query performance")
    
    analyzer = QueryPerformanceAnalyzer()
    
    # Get slow queries
    slow_queries = await analyzer.analyze_slow_queries(db, hours)
    
    # Get missing indexes
    missing_indexes = await analyzer.find_missing_indexes(db)
    
    # Get expensive queries
    expensive_queries = await analyzer.get_expensive_queries(db)
    
    return {
        "time_range_hours": hours,
        "slow_queries": slow_queries[:20],  # Top 20 slow queries
        "missing_indexes": missing_indexes[:10],  # Top 10 missing indexes
        "expensive_queries": expensive_queries[:10],  # Top 10 expensive queries
        "summary": {
            "total_slow_queries": len(slow_queries),
            "total_missing_indexes": len(missing_indexes),
            "total_expensive_queries": len(expensive_queries)
        }
    }


@router.get("/real-time-stats")
async def get_real_time_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get real-time query statistics
    
    Requires admin privileges
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Get stats from the global analyzer
    stats = query_performance_analyzer.get_current_stats()
    
    return {
        "monitoring_enabled": stats.get("monitoring_enabled", False),
        "slow_query_threshold_ms": stats.get("slow_query_threshold", 100),
        "recent_slow_queries": stats.get("recent_slow_queries", [])[:10],
        "query_patterns": stats.get("query_patterns", {}),
        "statistics": {
            "total_queries": stats.get("total_queries", 0),
            "slow_queries": stats.get("slow_queries", 0),
            "avg_query_time_ms": stats.get("avg_query_time", 0),
            "max_query_time_ms": stats.get("max_query_time", 0)
        }
    }


@router.post("/optimize-table/{table_name}")
async def optimize_table(
    table_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Run optimization on a specific table
    
    Requires SUPER_ADMIN role
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can optimize tables")
    
    # Validate table name to prevent SQL injection
    allowed_tables = [
        "users", "model_profiles", "transactions", "messages",
        "fans", "analytics_events", "webhooks", "api_keys"
    ]
    
    if table_name not in allowed_tables:
        raise HTTPException(status_code=400, detail="Invalid table name")
    
    analyzer = QueryPerformanceAnalyzer()
    
    try:
        # Run VACUUM ANALYZE
        await analyzer.vacuum_analyze_table(db, table_name)
        
        # Get table statistics
        stats = await analyzer.get_table_statistics(db, table_name)
        
        # Get index recommendations
        index_recommendations = await analyzer.recommend_indexes_for_table(db, table_name)
        
        return {
            "table": table_name,
            "optimization_complete": True,
            "statistics": stats,
            "index_recommendations": index_recommendations,
            "message": f"Table {table_name} has been optimized"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to optimize table: {str(e)}")


@router.get("/index-usage")
async def get_index_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get index usage statistics
    
    Requires admin privileges
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    analyzer = QueryPerformanceAnalyzer()
    
    # Get unused indexes
    unused_indexes = await analyzer.find_unused_indexes(db)
    
    # Get index hit rate
    index_hit_rate = await analyzer.get_index_hit_rate(db)
    
    # Get most used indexes
    most_used = await analyzer.get_most_used_indexes(db)
    
    return {
        "unused_indexes": unused_indexes,
        "index_hit_rate": index_hit_rate,
        "most_used_indexes": most_used[:20],  # Top 20 most used
        "recommendations": {
            "drop_unused": [idx for idx in unused_indexes if idx.get("scans", 0) == 0],
            "consider_dropping": [idx for idx in unused_indexes if idx.get("scans", 0) < 10]
        }
    }


@router.post("/explain-query")
async def explain_query(
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get EXPLAIN ANALYZE output for a query
    
    Requires SUPER_ADMIN role
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can explain queries")
    
    # Validate query (basic validation)
    query_lower = query.lower().strip()
    if not query_lower.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries can be explained")
    
    # Forbidden keywords
    forbidden = ["drop", "delete", "truncate", "update", "insert", "alter", "create"]
    if any(keyword in query_lower for keyword in forbidden):
        raise HTTPException(status_code=400, detail="Query contains forbidden keywords")
    
    try:
        # Run EXPLAIN ANALYZE
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        result = await db.execute(text(explain_query))
        explain_output = result.scalar()
        
        # Get optimization suggestions
        analyzer = QueryPerformanceAnalyzer()
        suggestions = analyzer.analyze_explain_output(explain_output)
        
        return {
            "query": query,
            "explain_output": explain_output,
            "suggestions": suggestions,
            "performance_issues": analyzer.identify_performance_issues(explain_output)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to explain query: {str(e)}")


@router.get("/cache-hit-rate")
async def get_cache_hit_rate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get database cache hit rates
    
    Requires admin privileges
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Get cache hit rates from PostgreSQL
    query = text("""
        SELECT 
            sum(heap_blks_read) as heap_read,
            sum(heap_blks_hit) as heap_hit,
            sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as cache_hit_ratio
        FROM pg_statio_user_tables
    """)
    
    result = await db.execute(query)
    cache_stats = result.fetchone()
    
    # Get buffer cache stats
    buffer_query = text("""
        SELECT 
            count(*) as buffers,
            count(*) filter (where isdirty) as dirty_buffers,
            pg_size_pretty(count(*) * 8192) as total_size
        FROM pg_buffercache
    """)
    
    try:
        buffer_result = await db.execute(buffer_query)
        buffer_stats = buffer_result.fetchone()
    except:
        buffer_stats = None
    
    return {
        "cache_hit_ratio": float(cache_stats.cache_hit_ratio) if cache_stats.cache_hit_ratio else 0,
        "heap_blocks_read": cache_stats.heap_read,
        "heap_blocks_hit": cache_stats.heap_hit,
        "buffer_cache": {
            "total_buffers": buffer_stats.buffers if buffer_stats else 0,
            "dirty_buffers": buffer_stats.dirty_buffers if buffer_stats else 0,
            "total_size": buffer_stats.total_size if buffer_stats else "0 MB"
        } if buffer_stats else None,
        "recommendations": {
            "increase_shared_buffers": cache_stats.cache_hit_ratio < 0.9 if cache_stats.cache_hit_ratio else False,
            "cache_hit_target": 0.95,
            "current_performance": "Good" if cache_stats.cache_hit_ratio and cache_stats.cache_hit_ratio > 0.9 else "Needs Improvement"
        }
    }