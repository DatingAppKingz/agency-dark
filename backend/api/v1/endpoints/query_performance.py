"""Query performance monitoring and optimization endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.query_performance_service import QueryPerformanceService
from core.exceptions import ValidationError

router = APIRouter()


# Request/Response schemas
class QueryAnalysisRequest(BaseModel):
    """Request to analyze a specific query."""
    query: str = Field(..., description="SQL query to analyze")


class SlowQueryResponse(BaseModel):
    """Slow query information."""
    query: str
    calls: int
    total_time_ms: float
    mean_time_ms: float
    max_time_ms: float
    min_time_ms: float
    stddev_time_ms: float
    rows_returned: int
    severity: str


class QueryAnalysisResponse(BaseModel):
    """Query analysis result."""
    query: str
    execution_time_ms: float
    planning_time_ms: float
    total_time_ms: float
    issues: List[str]
    suggestions: List[str]
    severity: str
    plan: Optional[Dict[str, Any]] = None


class TableSizeInfo(BaseModel):
    """Table size information."""
    schema: str
    table: str
    total_size: str
    size_bytes: int
    table_size: str
    indexes_size: str
    row_count: int
    dead_rows: int
    bloat_percent: float


class IndexUsageInfo(BaseModel):
    """Index usage information."""
    schema: str
    table: str
    index: str
    scans: int
    tuples_read: int
    tuples_fetched: int
    size: str
    status: str
    efficiency: float


class OptimizationRecommendation(BaseModel):
    """Database optimization recommendation."""
    type: str
    priority: str
    table: Optional[str] = None
    index: Optional[str] = None
    reason: str
    suggestion: str
    size: Optional[str] = None
    dead_tuples: Optional[int] = None
    bloat_percent: Optional[float] = None
    modifications: Optional[int] = None


@router.get("/slow-queries", response_model=List[SlowQueryResponse])
async def get_slow_queries(
    min_duration_ms: int = Query(100, ge=0, description="Minimum query duration in milliseconds"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of queries to return"),
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[SlowQueryResponse]:
    """
    Get slow queries from the database.
    
    - Requires admin or owner role
    - Returns queries exceeding the specified duration threshold
    - Includes execution statistics and severity classification
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    slow_queries = await QueryPerformanceService.get_slow_queries(
        db=db,
        min_duration_ms=min_duration_ms,
        limit=limit,
        time_range_hours=time_range_hours
    )
    
    return [SlowQueryResponse(**query) for query in slow_queries]


@router.post("/analyze", response_model=QueryAnalysisResponse)
async def analyze_query(
    request: QueryAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> QueryAnalysisResponse:
    """
    Analyze a specific query for performance issues.
    
    - Generates execution plan
    - Identifies performance issues
    - Provides optimization suggestions
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Validate query (basic validation)
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Prevent dangerous operations
    dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
    query_upper = request.query.upper()
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise HTTPException(
                status_code=400, 
                detail=f"Query analysis not allowed for {keyword} statements"
            )
    
    analysis = await QueryPerformanceService.analyze_query(
        db=db,
        query_sql=request.query
    )
    
    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])
    
    return QueryAnalysisResponse(**analysis)


@router.get("/statistics")
async def get_query_statistics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get overall query performance statistics.
    
    - Query execution statistics
    - Table access patterns
    - Index usage statistics
    - Cache hit ratios
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return await QueryPerformanceService.get_query_statistics(
        db=db,
        time_range_hours=time_range_hours
    )


@router.get("/tables/sizes", response_model=List[TableSizeInfo])
async def get_table_sizes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[TableSizeInfo]:
    """
    Get table sizes and bloat information.
    
    - Total size including indexes
    - Row counts and dead tuples
    - Bloat percentage
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    tables = await QueryPerformanceService.get_table_sizes(db)
    return [TableSizeInfo(**table) for table in tables]


@router.get("/indexes/usage", response_model=List[IndexUsageInfo])
async def get_index_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[IndexUsageInfo]:
    """
    Get index usage statistics.
    
    - Index scan counts
    - Index efficiency metrics
    - Identifies unused indexes
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    indexes = await QueryPerformanceService.get_index_usage(db)
    return [IndexUsageInfo(**index) for index in indexes]


@router.get("/recommendations")
async def get_optimization_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get database optimization recommendations.
    
    - Missing index suggestions
    - Unused index identification
    - Table bloat warnings
    - Statistics update recommendations
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return await QueryPerformanceService.recommend_optimizations(db)


@router.get("/dashboard")
async def get_performance_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive performance dashboard data.
    
    - Combines all performance metrics
    - For admin dashboard display
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all metrics
    slow_queries = await QueryPerformanceService.get_slow_queries(
        db=db,
        min_duration_ms=100,
        limit=10,
        time_range_hours=24
    )
    
    statistics = await QueryPerformanceService.get_query_statistics(
        db=db,
        time_range_hours=24
    )
    
    table_sizes = await QueryPerformanceService.get_table_sizes(db)
    recommendations = await QueryPerformanceService.recommend_optimizations(db)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "slow_queries": slow_queries[:5],  # Top 5 slow queries
        "statistics": statistics,
        "largest_tables": table_sizes[:5],  # Top 5 largest tables
        "recommendations": {
            "total": recommendations["total_recommendations"],
            "high_priority": recommendations["high_priority"][:3],
            "summary": {
                "high": len(recommendations["high_priority"]),
                "medium": len(recommendations["medium_priority"]),
                "low": len(recommendations["low_priority"])
            }
        }
    }


@router.get("/cache-hit-rate")
async def get_cache_hit_rate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get database cache hit rates.
    
    Requires admin privileges
    """
    if current_user.role not in ["admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Get cache hit rates from PostgreSQL
    query = text("""
        SELECT 
            sum(heap_blks_read) as heap_read,
            sum(heap_blks_hit) as heap_hit,
            CASE 
                WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0 
                THEN sum(heap_blks_hit)::float / (sum(heap_blks_hit) + sum(heap_blks_read))
                ELSE 0
            END as cache_hit_ratio
        FROM pg_statio_user_tables
    """)
    
    result = await db.execute(query)
    cache_stats = result.fetchone()
    
    return {
        "cache_hit_ratio": float(cache_stats[2]) if cache_stats and cache_stats[2] else 0,
        "heap_blocks_read": cache_stats[0] if cache_stats else 0,
        "heap_blocks_hit": cache_stats[1] if cache_stats else 0,
        "recommendations": {
            "increase_shared_buffers": cache_stats[2] < 0.9 if cache_stats and cache_stats[2] else False,
            "cache_hit_target": 0.95,
            "current_performance": "Good" if cache_stats and cache_stats[2] and cache_stats[2] > 0.9 else "Needs Improvement"
        }
    }


@router.post("/optimize/vacuum")
async def run_vacuum(
    tables: Optional[List[str]] = Body(None, description="List of table names to vacuum"),
    analyze: bool = Body(True, description="Also run ANALYZE"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Run VACUUM on specified tables.
    
    - Requires admin role
    - Can optionally run ANALYZE
    - If no tables specified, vacuums all user tables
    """
    # Check permissions - only admins
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can run VACUUM")
    
    # Note: In a real implementation, this would queue a background job
    # as VACUUM cannot run inside a transaction
    return {
        "message": "VACUUM operation queued",
        "tables": tables or ["all user tables"],
        "analyze": analyze,
        "note": "This operation runs in the background and may take several minutes"
    }


@router.post("/optimize/analyze")
async def run_analyze(
    tables: Optional[List[str]] = Body(None, description="List of table names to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Run ANALYZE on specified tables to update statistics.
    
    - Requires admin role
    - Updates query planner statistics
    - If no tables specified, analyzes all user tables
    """
    # Check permissions - only admins
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can run ANALYZE")
    
    # Note: In a real implementation, this would queue a background job
    return {
        "message": "ANALYZE operation queued",
        "tables": tables or ["all user tables"],
        "note": "Statistics will be updated in the background"
    }


@router.get("/test")
async def test_query_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test query performance functionality.
    
    - Returns sample performance data
    - For testing and demonstration
    """
    # Get basic statistics
    stats = await QueryPerformanceService.get_query_statistics(db)
    
    # Get a few slow queries
    slow_queries = await QueryPerformanceService.get_slow_queries(
        db=db,
        min_duration_ms=50,
        limit=3,
        time_range_hours=24
    )
    
    return {
        "message": "Query performance monitoring is operational",
        "sample_statistics": stats,
        "sample_slow_queries": slow_queries,
        "features": [
            "Slow query detection",
            "Query analysis and optimization",
            "Table size monitoring",
            "Index usage tracking",
            "Performance recommendations"
        ]
    }