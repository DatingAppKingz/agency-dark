"""
Performance monitoring endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.database.query_analyzer import QueryAnalyzer
from core.cache import cache

router = APIRouter(tags=["monitoring"])


@router.get("/performance/database")
async def get_database_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get database performance metrics.
    
    Requires super_admin role.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get slow queries
    slow_queries = await QueryAnalyzer.analyze_slow_queries(db, min_duration_ms=100)
    
    # Get missing indexes
    missing_indexes = await QueryAnalyzer.analyze_missing_indexes(db, min_scans=100)
    
    # Get table bloat
    table_bloat = await QueryAnalyzer.analyze_table_bloat(db, min_bloat_ratio=1.2)
    
    # Get connection stats
    connection_stats = await QueryAnalyzer.analyze_connection_stats(db)
    
    # Get index usage
    index_usage = await QueryAnalyzer.analyze_index_usage(db)
    unused_indexes = [idx for idx in index_usage if idx["status"] == "UNUSED"]
    
    return {
        "slow_queries": {
            "count": len(slow_queries),
            "top_5": slow_queries[:5]
        },
        "missing_indexes": {
            "count": len(missing_indexes),
            "tables": missing_indexes
        },
        "table_bloat": {
            "count": len(table_bloat),
            "tables": table_bloat[:5]
        },
        "unused_indexes": {
            "count": len(unused_indexes),
            "indexes": unused_indexes[:10]
        },
        "connections": connection_stats
    }


@router.get("/performance/cache")
async def get_cache_performance(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get cache performance metrics.
    
    Requires admin role.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get cache stats
    stats = cache.get_stats()
    
    # Get cache health
    from core.cache import monitor
    health = await monitor.get_health_status()
    
    # Get memory analysis
    memory_analysis = await monitor.get_memory_analysis()
    
    return {
        "stats": stats,
        "health": health,
        "memory": {
            "analysis": memory_analysis,
            "total_keys": sum(pattern["count"] for pattern in memory_analysis.values()),
            "estimated_memory_mb": sum(
                pattern["estimated_total_mb"] 
                for pattern in memory_analysis.values()
            )
        }
    }


@router.post("/performance/analyze-query")
async def analyze_query(
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze a specific SQL query.
    
    Requires super_admin role.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        # Get execution plan
        plan = await QueryAnalyzer.get_query_execution_plan(db, query)
        
        # Get optimization suggestions
        from core.database.query_analyzer import QueryOptimizer
        suggestions = QueryOptimizer.optimize_query(query)
        
        return {
            "query": query,
            "execution_plan": plan,
            "optimization_suggestions": suggestions
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to analyze query: {str(e)}"
        )


@router.post("/performance/refresh-views")
async def refresh_materialized_views(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Refresh materialized views.
    
    Requires super_admin role.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        from sqlalchemy import text
        await db.execute(text("CALL refresh_analytics_views()"))
        await db.commit()
        
        return {"status": "success", "message": "Materialized views refreshed"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh views: {str(e)}"
        )


@router.get("/performance/query-stats")
async def get_query_statistics(
    model_id: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get query performance statistics for a model.
    
    Returns cached statistics for better performance.
    """
    # Check permissions
    if model_id:
        # Verify user has access to this model
        from sqlalchemy import select
        from core.domain.models import ModelProfile
        
        result = await db.execute(
            select(ModelProfile).where(
                ModelProfile.id == model_id,
                ModelProfile.agency_id == current_user.agency_id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Model not found")
    
    # Try to get from cache
    cache_key = f"query_stats:{model_id or 'global'}:{current_user.agency_id}"
    cached_stats = await cache.get(cache_key)
    
    if cached_stats:
        return cached_stats
    
    # Calculate stats
    from core.database.query_builders import OptimizedQueries
    from sqlalchemy import text
    
    if model_id:
        # Model-specific stats
        balance_result = await db.execute(
            OptimizedQueries.calculate_model_balance(model_id),
            {"model_id": model_id}
        )
        balance = balance_result.scalar()
        
        fan_segments_result = await db.execute(
            OptimizedQueries.get_fan_value_segments(model_id),
            {"model_id": model_id}
        )
        fan_segments = [dict(row) for row in fan_segments_result]
        
        stats = {
            "model_id": model_id,
            "current_balance": float(balance) if balance else 0,
            "fan_segments": fan_segments,
            "cache_hit": False
        }
    else:
        # Agency-wide stats
        dashboard_result = await db.execute(
            OptimizedQueries.get_agency_dashboard_metrics(current_user.agency_id),
            {"agency_id": current_user.agency_id}
        )
        dashboard_metrics = dict(dashboard_result.fetchone())
        
        stats = {
            "agency_metrics": dashboard_metrics,
            "cache_hit": False
        }
    
    # Cache for 5 minutes
    await cache.set(cache_key, stats, ttl=300)
    
    return stats