"""
Performance Monitoring API Endpoints
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.security_v2 import get_current_user
from core.security_v2.authorization import check_permission
from core.performance.query_analyzer import query_analyzer
from core.performance.cache_manager import cache_manager
from core.performance.connection_pool import connection_pool_manager

router = APIRouter(prefix="/performance", tags=["performance"])


class QueryOptimizationSuggestion(BaseModel):
    query: str
    current_performance: Dict[str, Any]
    suggestions: List[str]
    estimated_improvement: Optional[str]


class IndexSuggestion(BaseModel):
    table: str
    columns: List[str]
    type: str
    reason: str
    create_statement: str


class PerformanceMetrics(BaseModel):
    timestamp: datetime
    database: Dict[str, Any]
    cache: Dict[str, Any]
    queries: Dict[str, Any]


@router.get("/metrics", response_model=PerformanceMetrics)
async def get_performance_metrics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get overall system performance metrics"""
    await check_permission(current_user["role"], "admin.view")
    
    # Get database metrics
    db_metrics = {
        "connection_pool": connection_pool_manager.get_pool_stats(),
        "active_connections": connection_pool_manager.get_active_connections(),
        "connection_wait_time": connection_pool_manager.get_average_wait_time()
    }
    
    # Get cache metrics
    cache_metrics = await cache_manager.get_stats()
    
    # Get query metrics
    query_metrics = await query_analyzer.get_monitoring_stats()
    
    return PerformanceMetrics(
        timestamp=datetime.utcnow(),
        database=db_metrics,
        cache=cache_metrics,
        queries=query_metrics
    )


@router.get("/slow-queries")
async def get_slow_queries(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get slow queries analysis"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        slow_queries = await query_analyzer.analyze_slow_queries(db, hours)
        
        # Sort by average execution time
        slow_queries.sort(key=lambda x: x["avg_time"], reverse=True)
        
        return {
            "time_range_hours": hours,
            "threshold_ms": query_analyzer.slow_query_threshold * 1000,
            "total_slow_queries": len(slow_queries),
            "queries": slow_queries[:limit]
        }
    except Exception as e:
        logger.error(f"Error analyzing slow queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze queries")


@router.get("/missing-indexes")
async def get_missing_indexes(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get missing index recommendations"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        missing_indexes = await query_analyzer.get_missing_indexes(db)
        
        recommendations = []
        for idx in missing_indexes:
            for suggestion in idx.get("suggestions", []):
                recommendations.append(IndexSuggestion(
                    table=f"{idx['schema']}.{idx['table']}",
                    columns=[suggestion.get("column", "")],
                    type=suggestion.get("type", "btree"),
                    reason=suggestion.get("reason", ""),
                    create_statement=suggestion.get("suggestion", "")
                ))
        
        return {
            "total_tables_analyzed": len(missing_indexes),
            "index_recommendations": len(recommendations),
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Error analyzing indexes: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze indexes")


@router.get("/unused-indexes")
async def get_unused_indexes(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get unused indexes that can be dropped"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        unused_indexes = await query_analyzer.get_unused_indexes(db)
        
        total_size = 0
        for idx in unused_indexes:
            # Parse size string to calculate total
            size_str = idx.get("size", "0 MB")
            # Simple parsing - would need more robust implementation
            if "MB" in size_str:
                total_size += float(size_str.replace(" MB", ""))
            elif "GB" in size_str:
                total_size += float(size_str.replace(" GB", "")) * 1024
        
        return {
            "total_unused_indexes": len(unused_indexes),
            "total_size_mb": round(total_size, 2),
            "indexes": unused_indexes
        }
    except Exception as e:
        logger.error(f"Error analyzing unused indexes: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze unused indexes")


@router.get("/query-patterns")
async def analyze_query_patterns(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze query patterns for optimization opportunities"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        patterns = await query_analyzer.analyze_query_patterns(db)
        
        return {
            "analysis_timestamp": datetime.utcnow(),
            "patterns": patterns,
            "total_issues": patterns.get("optimization_opportunities", 0)
        }
    except Exception as e:
        logger.error(f"Error analyzing query patterns: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze query patterns")


@router.get("/table-statistics")
async def get_table_statistics(
    schema: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed table statistics and maintenance recommendations"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        statistics = await query_analyzer.get_table_statistics(db)
        
        # Filter by schema if provided
        if schema:
            statistics = [s for s in statistics if s["schema"] == schema]
        
        # Calculate totals
        total_size = sum(
            float(s["total_size"].replace(" MB", "").replace(" GB", "").replace(" TB", "")) *
            (1024 if "GB" in s["total_size"] else 1) *
            (1024 * 1024 if "TB" in s["total_size"] else 1)
            for s in statistics
        )
        
        tables_needing_maintenance = [
            s for s in statistics if s.get("maintenance_needed")
        ]
        
        return {
            "total_tables": len(statistics),
            "total_size_mb": round(total_size, 2),
            "tables_needing_maintenance": len(tables_needing_maintenance),
            "statistics": statistics
        }
    except Exception as e:
        logger.error(f"Error getting table statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get table statistics")


@router.post("/optimize-query")
async def optimize_query(
    query: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze and optimize a specific query"""
    await check_permission(current_user["role"], "admin.execute")
    
    try:
        # Analyze query execution plan
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS) {query}"
        result = await db.execute(text(explain_query))
        plan = result.fetchall()
        
        # Get optimization suggestions
        suggestions = query_analyzer._suggest_optimizations(query)
        
        return {
            "original_query": query,
            "execution_plan": [row[0] for row in plan],
            "suggestions": suggestions
        }
    except Exception as e:
        logger.error(f"Error optimizing query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize query: {str(e)}")


@router.post("/maintenance/vacuum")
async def run_vacuum(
    table: str,
    analyze: bool = True,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run VACUUM on a specific table"""
    await check_permission(current_user["role"], "admin.execute")
    
    try:
        # Validate table name to prevent SQL injection
        if not all(c.isalnum() or c in "._" for c in table):
            raise ValueError("Invalid table name")
        
        # Run VACUUM
        vacuum_cmd = f"VACUUM {'ANALYZE' if analyze else ''} {table}"
        await db.execute(text(vacuum_cmd))
        await db.commit()
        
        return {
            "status": "success",
            "table": table,
            "operation": vacuum_cmd,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error running vacuum: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run vacuum: {str(e)}")


@router.post("/monitoring/toggle")
async def toggle_query_monitoring(
    enabled: bool,
    current_user: dict = Depends(get_current_user)
):
    """Enable or disable query monitoring"""
    await check_permission(current_user["role"], "admin.execute")
    
    if enabled:
        query_analyzer.enable_query_monitoring()
    else:
        query_analyzer.disable_query_monitoring()
    
    return {
        "monitoring_enabled": enabled,
        "timestamp": datetime.utcnow()
    }


from core.logging import get_logger
from sqlalchemy import text

logger = get_logger(__name__)