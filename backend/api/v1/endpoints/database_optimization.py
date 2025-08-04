"""Database optimization API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from core.database import get_db
from core.dependencies import CurrentUser, get_current_active_user
from core.errors import AuthorizationError
from core.logger import get_logger
from models.user import User, UserRole
from services.database_optimization import DatabaseOptimizationService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/optimization/report")
async def get_optimization_report(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive database optimization report."""
    # Only admins can access optimization reports
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    report = await service.generate_optimization_report(db)
    
    return report


@router.get("/optimization/slow-queries")
async def get_slow_queries(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    min_duration_ms: int = 100,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get list of slow queries."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    slow_queries = await service.analyze_slow_queries(db, min_duration_ms, limit)
    
    return slow_queries


@router.get("/optimization/missing-indexes")
async def get_missing_indexes(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    min_scans: int = 50
) -> List[Dict[str, Any]]:
    """Analyze tables that might benefit from additional indexes."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    missing_indexes = await service.analyze_missing_indexes(db, min_scans)
    
    return missing_indexes


@router.post("/optimization/create-indexes")
async def create_recommended_indexes(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create recommended indexes (runs in background)."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    # Run index creation in background
    background_tasks.add_task(
        create_indexes_task,
        db
    )
    
    return {
        "status": "started",
        "message": "Index creation started in background"
    }


async def create_indexes_task(db: AsyncSession):
    """Background task to create indexes."""
    service = DatabaseOptimizationService()
    try:
        results = await service.create_recommended_indexes(db)
        logger.info(f"Index creation completed: {results}")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")


@router.get("/optimization/table-bloat")
async def get_table_bloat(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Analyze table bloat and recommend vacuum operations."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    bloat_analysis = await service.analyze_table_bloat(db)
    
    return bloat_analysis


@router.get("/optimization/autovacuum-settings")
async def get_autovacuum_settings(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get autovacuum settings and recommendations."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    settings = await service.optimize_autovacuum_settings(db)
    
    return settings


@router.post("/optimization/create-materialized-views")
async def create_materialized_views(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create materialized views for performance (runs in background)."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    background_tasks.add_task(
        create_views_task,
        db
    )
    
    return {
        "status": "started",
        "message": "Materialized view creation started in background"
    }


async def create_views_task(db: AsyncSession):
    """Background task to create materialized views."""
    service = DatabaseOptimizationService()
    try:
        results = await service.create_query_performance_views(db)
        logger.info(f"View creation completed: {results}")
    except Exception as e:
        logger.error(f"View creation failed: {e}")


@router.post("/optimization/enable-monitoring")
async def enable_query_monitoring(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Enable query performance monitoring."""
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    
    service = DatabaseOptimizationService()
    result = await service.setup_query_monitoring(db)
    
    return result