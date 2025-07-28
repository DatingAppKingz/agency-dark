"""
API endpoints for materialized view management
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_user
from core.permissions import check_permission
from core.database.materialized_views import materialized_view_manager
from core.tasks.materialized_view_refresh import (
    refresh_scheduler,
    force_refresh_all_views,
    get_refresh_status,
    analyze_materialized_views
)
from core.redis import redis_client
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/materialized-views", tags=["materialized-views"])


class MaterializedViewInfo(BaseModel):
    name: str
    size: str
    last_refresh: Optional[datetime]
    refresh_duration: Optional[float]
    refresh_count: int
    query_calls: int
    efficiency_score: float


class MaterializedViewStatus(BaseModel):
    view_name: str
    exists: bool
    size: Optional[str]
    last_refresh: Optional[datetime]
    next_refresh: Optional[datetime]
    refresh_interval: str
    is_refreshing: bool


class RefreshRequest(BaseModel):
    view_names: Optional[List[str]] = None
    concurrent: bool = True
    force: bool = False


class RefreshResponse(BaseModel):
    refreshed: List[str]
    failed: List[Dict[str, str]]
    total_duration: float


@router.get("/", response_model=List[MaterializedViewInfo])
async def list_materialized_views(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all materialized views with statistics"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        # Get view statistics
        stats = await materialized_view_manager.get_view_stats(db)
        
        # Get analysis data from Redis
        analysis_str = await redis_client.get("mv_analysis:latest")
        analysis = json.loads(analysis_str) if analysis_str else {"views": []}
        
        # Combine data
        views = []
        for view_data in analysis.get("views", []):
            view_name = view_data["name"]
            if view_name in [v.name for v in materialized_view_manager.views.values()]:
                views.append(MaterializedViewInfo(
                    name=view_name,
                    size=view_data.get("size", "Unknown"),
                    last_refresh=view_data.get("last_refresh"),
                    refresh_duration=view_data.get("refresh_duration"),
                    refresh_count=view_data.get("refresh_count", 0),
                    query_calls=view_data.get("query_calls", 0),
                    efficiency_score=view_data.get("efficiency_score", 0)
                ))
        
        # Add any missing views
        for view_name, view in materialized_view_manager.views.items():
            if view.name not in [v.name for v in views]:
                view_stats = stats.get(view.name, {})
                views.append(MaterializedViewInfo(
                    name=view.name,
                    size=view_stats.get("size", "Unknown"),
                    last_refresh=view_stats.get("last_refresh"),
                    refresh_duration=view_stats.get("refresh_duration"),
                    refresh_count=0,
                    query_calls=0,
                    efficiency_score=0
                ))
        
        return views
        
    except Exception as e:
        logger.error(f"Error listing materialized views: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=List[MaterializedViewStatus])
async def get_materialized_view_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get refresh status for all materialized views"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        status_data = await get_refresh_status()
        
        statuses = []
        for view_name, interval in refresh_scheduler.refresh_intervals.items():
            view_status = status_data["views"].get(view_name, {})
            
            # Check if view exists in database
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews 
                    WHERE matviewname = :view_name
                )
            """)
            result = await db.execute(check_query, {"view_name": view_name})
            exists = result.scalar()
            
            # Check if currently refreshing
            refresh_lock = await redis_client.get(f"mv_refresh:{view_name}:lock")
            is_refreshing = refresh_lock is not None
            
            statuses.append(MaterializedViewStatus(
                view_name=view_name,
                exists=exists,
                size=view_status.get("size"),
                last_refresh=view_status.get("last_refresh"),
                next_refresh=status_data["next_refresh_times"].get(view_name),
                refresh_interval=str(interval),
                is_refreshing=is_refreshing
            ))
        
        return statuses
        
    except Exception as e:
        logger.error(f"Error getting view status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_materialized_views(
    request: RefreshRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually refresh materialized views"""
    await check_permission(current_user["role"], "admin.execute")
    
    start_time = datetime.utcnow()
    refreshed = []
    failed = []
    
    try:
        if request.view_names:
            # Refresh specific views
            for view_name in request.view_names:
                # Remove mv_ prefix if present
                clean_name = view_name.replace("mv_", "")
                
                if clean_name not in materialized_view_manager.views:
                    failed.append({
                        "view": view_name,
                        "error": "View not found"
                    })
                    continue
                
                try:
                    # Check if should refresh or force
                    if request.force or await refresh_scheduler.should_refresh(f"mv_{clean_name}"):
                        await materialized_view_manager.refresh_view(
                            db, clean_name, request.concurrent
                        )
                        refreshed.append(view_name)
                    else:
                        failed.append({
                            "view": view_name,
                            "error": "Recently refreshed, use force=true to override"
                        })
                except Exception as e:
                    failed.append({
                        "view": view_name,
                        "error": str(e)
                    })
        else:
            # Refresh all views
            if request.force:
                results = await force_refresh_all_views()
                for view_name, duration in results.items():
                    if duration is not None:
                        refreshed.append(view_name)
                    else:
                        failed.append({
                            "view": view_name,
                            "error": "Refresh failed"
                        })
            else:
                # Use background task for non-forced refresh
                background_tasks.add_task(materialized_view_manager.refresh_all_views, db)
                refreshed = ["All views scheduled for refresh"]
        
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        return RefreshResponse(
            refreshed=refreshed,
            failed=failed,
            total_duration=total_duration
        )
        
    except Exception as e:
        logger.error(f"Error refreshing views: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create/{view_name}")
async def create_materialized_view(
    view_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a specific materialized view"""
    await check_permission(current_user["role"], "admin.execute")
    
    if view_name not in materialized_view_manager.views:
        raise HTTPException(
            status_code=404,
            detail=f"View definition not found for {view_name}"
        )
    
    try:
        view = materialized_view_manager.views[view_name]
        await materialized_view_manager.create_view(db, view)
        await db.commit()
        
        # Initial refresh
        await materialized_view_manager.refresh_view(db, view_name)
        
        return {
            "status": "success",
            "message": f"Created and refreshed materialized view {view.name}"
        }
        
    except Exception as e:
        logger.error(f"Error creating view {view_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create view: {str(e)}"
        )


@router.delete("/drop/{view_name}")
async def drop_materialized_view(
    view_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Drop a materialized view"""
    await check_permission(current_user["role"], "admin.execute")
    
    clean_name = view_name.replace("mv_", "")
    
    if clean_name not in materialized_view_manager.views:
        raise HTTPException(
            status_code=404,
            detail=f"View {view_name} not managed by system"
        )
    
    try:
        await materialized_view_manager.drop_view(db, clean_name)
        
        # Clear Redis data
        await redis_client.delete(f"mv_refresh:{view_name}:*")
        
        return {
            "status": "success",
            "message": f"Dropped materialized view {view_name}"
        }
        
    except Exception as e:
        logger.error(f"Error dropping view {view_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to drop view: {str(e)}"
        )


@router.get("/analysis")
async def get_materialized_view_analysis(
    current_user: dict = Depends(get_current_user)
):
    """Get latest analysis of materialized views"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        # Get cached analysis
        analysis_str = await redis_client.get("mv_analysis:latest")
        
        if analysis_str:
            return json.loads(analysis_str)
        else:
            # Run analysis now
            analysis = await analyze_materialized_views()
            return analysis
            
    except Exception as e:
        logger.error(f"Error getting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/refresh-patterns")
async def get_refresh_patterns(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recommended refresh patterns for views"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        patterns = await materialized_view_manager.analyze_refresh_patterns(db)
        
        # Add current configuration
        for view_name, pattern in patterns.items():
            mv_name = f"mv_{view_name}"
            if mv_name in refresh_scheduler.refresh_intervals:
                pattern["current_interval"] = str(
                    refresh_scheduler.refresh_intervals[mv_name]
                )
        
        return patterns
        
    except Exception as e:
        logger.error(f"Error analyzing refresh patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_all_views(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initialize all materialized views (creates and refreshes)"""
    await check_permission(current_user["role"], "admin.execute")
    
    try:
        # Use background task for initialization
        background_tasks.add_task(
            materialized_view_manager.create_all_views, db
        )
        
        return {
            "status": "initiated",
            "message": "Materialized view initialization started in background",
            "views": list(materialized_view_manager.views.keys())
        }
        
    except Exception as e:
        logger.error(f"Error initializing views: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize views: {str(e)}"
        )


@router.get("/query/{view_name}")
async def query_materialized_view(
    view_name: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Query data from a materialized view"""
    await check_permission(current_user["role"], "analytics.view")
    
    # Validate view name
    allowed_views = [v.name for v in materialized_view_manager.views.values()]
    if view_name not in allowed_views:
        raise HTTPException(
            status_code=404,
            detail=f"View {view_name} not found"
        )
    
    try:
        # Build safe query
        query = text(f"""
            SELECT * FROM {view_name}
            LIMIT :limit OFFSET :offset
        """)
        
        result = await db.execute(query, {"limit": limit, "offset": offset})
        
        # Get column names
        columns = result.keys()
        
        # Convert to list of dicts
        data = []
        for row in result:
            data.append(dict(zip(columns, row)))
        
        # Get total count
        count_query = text(f"SELECT COUNT(*) FROM {view_name}")
        total_count = await db.scalar(count_query)
        
        return {
            "view": view_name,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "data": data
        }
        
    except Exception as e:
        logger.error(f"Error querying view {view_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query view: {str(e)}"
        )


from sqlalchemy import text