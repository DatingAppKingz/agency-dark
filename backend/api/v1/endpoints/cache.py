"""Cache management API endpoints."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from core.cache_manager import cache_manager, CacheTag
from core.logger import get_logger
from models.user import User
from tasks.cache_tasks import (
    cache_warmup_task,
    cache_cleanup_task,
    invalidate_user_cache_task,
    invalidate_model_cache_task,
    cache_health_check_task
)

logger = get_logger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get cache statistics and health metrics.
    
    Permissions:
    - cache:read (admin only)
    """
    check_permission(current_user, "cache", "read")
    
    try:
        stats = await cache_manager.get_stats()
        
        # Add hit rate calculation if Redis info available
        if stats.get('redis_info'):
            hits = stats['redis_info'].get('keyspace_hits', 0)
            misses = stats['redis_info'].get('keyspace_misses', 0)
            total = hits + misses
            
            stats['hit_rate'] = {
                'hits': hits,
                'misses': misses,
                'rate': f"{(hits / total * 100):.2f}%" if total > 0 else "0%"
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.post("/warmup")
async def trigger_cache_warmup(
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger cache warmup task.
    
    Permissions:
    - cache:write (admin only)
    """
    check_permission(current_user, "cache", "write")
    
    # Queue warmup task
    task = cache_warmup_task.delay()
    
    return {
        "message": "Cache warmup task queued",
        "task_id": task.id
    }


@router.post("/cleanup")
async def trigger_cache_cleanup(
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger cache cleanup task.
    
    Permissions:
    - cache:write (admin only)
    """
    check_permission(current_user, "cache", "write")
    
    # Queue cleanup task
    task = cache_cleanup_task.delay()
    
    return {
        "message": "Cache cleanup task queued",
        "task_id": task.id
    }


@router.delete("/invalidate/tag/{tag}")
async def invalidate_by_tag(
    tag: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Invalidate cache entries by tag.
    
    Permissions:
    - cache:delete (admin only)
    """
    check_permission(current_user, "cache", "delete")
    
    # Validate tag
    valid_tags = [
        CacheTag.USER, CacheTag.MODEL, CacheTag.AGENCY,
        CacheTag.TRANSACTION, CacheTag.MESSAGE,
        CacheTag.ANALYTICS, CacheTag.SEARCH, CacheTag.API
    ]
    
    if tag not in valid_tags and not tag.startswith(("user:", "model:", "agency:")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tag: {tag}"
        )
    
    count = await cache_manager.invalidate_by_tag(tag)
    
    return {
        "message": f"Invalidated {count} cache entries",
        "tag": tag,
        "count": count
    }


@router.delete("/invalidate/pattern")
async def invalidate_by_pattern(
    pattern: str = Query(..., description="Cache key pattern to match"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Invalidate cache entries matching a pattern.
    
    Permissions:
    - cache:delete (admin only)
    """
    check_permission(current_user, "cache", "delete")
    
    # Validate pattern (basic safety check)
    if len(pattern) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pattern too short (minimum 3 characters)"
        )
    
    count = await cache_manager.invalidate_pattern(pattern)
    
    return {
        "message": f"Invalidated {count} cache entries",
        "pattern": pattern,
        "count": count
    }


@router.delete("/invalidate/user/{user_id}")
async def invalidate_user_cache(
    user_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Invalidate all cache entries for a specific user.
    
    Permissions:
    - cache:delete or own user
    """
    if str(current_user.id) != user_id:
        check_permission(current_user, "cache", "delete")
    
    # Queue task
    task = invalidate_user_cache_task.delay(user_id)
    
    return {
        "message": "User cache invalidation queued",
        "user_id": user_id,
        "task_id": task.id
    }


@router.delete("/invalidate/model/{model_id}")
async def invalidate_model_cache(
    model_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Invalidate all cache entries for a specific model.
    
    Permissions:
    - cache:delete or model owner
    """
    # Check if user owns the model
    # For now, just check permission
    check_permission(current_user, "cache", "delete")
    
    # Queue task
    task = invalidate_model_cache_task.delay(model_id)
    
    return {
        "message": "Model cache invalidation queued",
        "model_id": model_id,
        "task_id": task.id
    }


@router.get("/health")
async def check_cache_health(
    current_user: User = Depends(get_current_active_user)
):
    """
    Check cache health and performance.
    
    Permissions:
    - cache:read
    """
    check_permission(current_user, "cache", "read")
    
    # Run health check
    task = cache_health_check_task.apply_async()
    result = task.get(timeout=5)  # Wait up to 5 seconds
    
    # Determine health status
    health_status = "healthy"
    issues = []
    
    if result['status'] == 'error':
        health_status = "unhealthy"
        issues.append(f"Health check failed: {result['error']}")
    else:
        stats = result.get('stats', {})
        
        # Check memory usage
        if stats.get('memory_warning'):
            health_status = "warning"
            issues.append("High memory usage detected")
        
        # Check hit rate
        hit_rate_str = stats.get('hit_rate', '0%')
        hit_rate = float(hit_rate_str.rstrip('%'))
        if hit_rate < 50:
            health_status = "warning" if health_status == "healthy" else health_status
            issues.append(f"Low cache hit rate: {hit_rate_str}")
    
    return {
        "status": health_status,
        "issues": issues,
        "details": result
    }


@router.get("/keys", response_model=Dict[str, Any])
async def list_cache_keys(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    pattern: Optional[str] = Query(None, description="Filter by pattern"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user)
):
    """
    List cache keys (for debugging).
    
    Permissions:
    - cache:read (admin only)
    """
    check_permission(current_user, "cache", "read")
    
    # This is a simplified version - in production you'd want pagination
    stats = await cache_manager.get_stats()
    
    keys = stats.get('memory_cache_keys', [])
    
    # Apply filters
    if namespace:
        keys = [k for k in keys if f":{namespace}:" in k]
    
    if pattern:
        keys = [k for k in keys if pattern in k]
    
    return {
        "total": len(keys),
        "keys": keys[:limit],
        "limited": len(keys) > limit
    }


@router.get("/config")
async def get_cache_configuration(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get cache configuration.
    
    Permissions:
    - cache:read
    """
    check_permission(current_user, "cache", "read")
    
    from core.config import settings
    
    return {
        "backend": "redis",
        "redis_url": settings.REDIS_URL.split('@')[-1],  # Hide password
        "key_prefix": settings.CACHE_KEY_PREFIX,
        "memory_max_size": settings.CACHE_MEMORY_MAX_SIZE,
        "default_ttl": 3600,
        "features": {
            "multi_level": True,
            "tag_invalidation": True,
            "pattern_invalidation": True,
            "write_behind": True,
            "refresh_ahead": True
        }
    }