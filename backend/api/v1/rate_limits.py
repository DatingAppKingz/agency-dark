"""
Rate Limiting Management API Endpoints

Provides endpoints for:
- Viewing rate limit status
- Managing blocked identifiers
- Resetting rate limits (admin)
- Configuring rate limits
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from core.security.rate_limiter import rate_limiter, RateLimitStrategy, RateLimitConfig
from core.security_v2 import get_current_user, require_admin
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/rate-limits")


class RateLimitStatusResponse(BaseModel):
    """Rate limit status response"""
    blocked: bool
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset_at: Optional[int] = None
    window: Optional[int] = None
    current_usage: Optional[int] = None
    blocked_until: Optional[int] = None
    blocked_for: Optional[int] = None


class BlockedIdentifierResponse(BaseModel):
    """Blocked identifier information"""
    strategy: str
    identifier: str
    blocked_until: int
    remaining_seconds: int


class RateLimitConfigRequest(BaseModel):
    """Request to update rate limit configuration"""
    requests: int = Field(..., ge=1, le=1000000, description="Number of requests allowed")
    window: int = Field(..., ge=1, le=86400, description="Time window in seconds")
    burst: Optional[int] = Field(None, ge=1, le=10000, description="Burst allowance")
    block_duration: Optional[int] = Field(None, ge=60, le=604800, description="Block duration in seconds")


class RateLimitResetRequest(BaseModel):
    """Request to reset rate limits"""
    identifier: str
    strategy: RateLimitStrategy
    endpoint: Optional[str] = None


@router.get("/status/{strategy}/{identifier}", response_model=RateLimitStatusResponse)
async def get_rate_limit_status(
    strategy: RateLimitStrategy = Path(..., description="Rate limit strategy"),
    identifier: str = Path(..., description="Identifier to check"),
    endpoint: Optional[str] = Query(None, description="Specific endpoint to check"),
    current_user: dict = Depends(get_current_user)
):
    """Get current rate limit status for an identifier"""
    
    # Users can only check their own rate limits unless admin
    if strategy == RateLimitStrategy.USER:
        user_identifier = f"user:{current_user['user_id']}"
        if identifier != user_identifier and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=403,
                detail="You can only check your own rate limit status"
            )
    elif not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin access required to check other rate limit strategies"
        )
    
    try:
        status = await rate_limiter.get_rate_limit_status(
            identifier=identifier,
            strategy=strategy,
            endpoint=endpoint
        )
        
        return RateLimitStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve rate limit status"
        )


@router.get("/my-status", response_model=Dict[str, RateLimitStatusResponse])
async def get_my_rate_limit_status(
    endpoint: Optional[str] = Query(None, description="Specific endpoint to check"),
    current_user: dict = Depends(get_current_user)
):
    """Get current user's rate limit status across all strategies"""
    
    user_id = current_user["user_id"]
    results = {}
    
    # Check user-based rate limit
    user_identifier = f"user:{user_id}"
    try:
        user_status = await rate_limiter.get_rate_limit_status(
            identifier=user_identifier,
            strategy=RateLimitStrategy.USER,
            endpoint=endpoint
        )
        results["user"] = RateLimitStatusResponse(**user_status)
    except Exception as e:
        logger.error(f"Error getting user rate limit: {e}")
    
    # If user has API key in current session, check API key limit
    # This would need to be passed from middleware or stored in JWT
    
    return results


@router.get("/blocked", response_model=List[BlockedIdentifierResponse])
async def get_blocked_identifiers(
    strategy: Optional[RateLimitStrategy] = Query(None, description="Filter by strategy"),
    current_user: dict = Depends(require_admin)
):
    """Get list of currently blocked identifiers (admin only)"""
    
    try:
        blocked = await rate_limiter.get_blocked_identifiers(strategy)
        return [BlockedIdentifierResponse(**b) for b in blocked]
        
    except Exception as e:
        logger.error(f"Error getting blocked identifiers: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve blocked identifiers"
        )


@router.post("/reset")
async def reset_rate_limit(
    request: RateLimitResetRequest,
    current_user: dict = Depends(require_admin)
):
    """Reset rate limit for an identifier (admin only)"""
    
    try:
        await rate_limiter.reset_rate_limit(
            identifier=request.identifier,
            strategy=request.strategy,
            endpoint=request.endpoint
        )
        
        logger.info(
            f"Admin {current_user['email']} reset rate limit for "
            f"{request.strategy}:{request.identifier}"
        )
        
        return {
            "message": "Rate limit reset successfully",
            "identifier": request.identifier,
            "strategy": request.strategy.value
        }
        
    except Exception as e:
        logger.error(f"Error resetting rate limit: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reset rate limit"
        )


@router.delete("/blocked/{strategy}/{identifier}")
async def unblock_identifier(
    strategy: RateLimitStrategy = Path(..., description="Rate limit strategy"),
    identifier: str = Path(..., description="Identifier to unblock"),
    current_user: dict = Depends(require_admin)
):
    """Unblock a blocked identifier (admin only)"""
    
    try:
        # Reset will also remove blocks
        await rate_limiter.reset_rate_limit(
            identifier=identifier,
            strategy=strategy
        )
        
        logger.info(
            f"Admin {current_user['email']} unblocked "
            f"{strategy}:{identifier}"
        )
        
        return {
            "message": "Identifier unblocked successfully",
            "identifier": identifier,
            "strategy": strategy.value
        }
        
    except Exception as e:
        logger.error(f"Error unblocking identifier: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to unblock identifier"
        )


@router.get("/config", response_model=Dict[str, Any])
async def get_rate_limit_config(
    current_user: dict = Depends(require_admin)
):
    """Get current rate limit configuration (admin only)"""
    
    # Return default configurations
    config = {
        "default_limits": {},
        "endpoint_limits": {}
    }
    
    # Convert dataclasses to dicts for response
    for strategy, limit_config in rate_limiter.default_limits.items():
        config["default_limits"][strategy.value] = {
            "requests": limit_config.requests,
            "window": limit_config.window,
            "burst": limit_config.burst,
            "block_duration": limit_config.block_duration
        }
    
    # Include some endpoint configurations
    for endpoint, strategies in rate_limiter.endpoint_limits.items():
        config["endpoint_limits"][endpoint] = {}
        for strategy, limit_config in strategies.items():
            config["endpoint_limits"][endpoint][strategy.value] = {
                "requests": limit_config.requests,
                "window": limit_config.window,
                "burst": limit_config.burst,
                "block_duration": limit_config.block_duration
            }
    
    return config


@router.get("/metrics")
async def get_rate_limit_metrics(
    current_user: dict = Depends(require_admin)
):
    """Get rate limiting metrics and statistics (admin only)"""
    
    try:
        # Get current blocked count
        blocked_identifiers = await rate_limiter.get_blocked_identifiers()
        
        metrics = {
            "total_blocked": len(blocked_identifiers),
            "blocked_by_strategy": {},
            "configuration": {
                "violation_threshold": rate_limiter.violation_threshold,
                "violation_window": rate_limiter.violation_window,
                "default_block_duration": rate_limiter.block_duration
            }
        }
        
        # Count by strategy
        for blocked in blocked_identifiers:
            strategy = blocked["strategy"]
            if strategy not in metrics["blocked_by_strategy"]:
                metrics["blocked_by_strategy"][strategy] = 0
            metrics["blocked_by_strategy"][strategy] += 1
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting rate limit metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve rate limit metrics"
        )


# Health check endpoint for monitoring rate limiter
@router.get("/health")
async def rate_limiter_health():
    """Check rate limiter health status"""
    
    try:
        # Test Redis connection
        from core.redis import redis_client
        await redis_client.ping()
        
        return {
            "status": "healthy",
            "redis": "connected",
            "strategies": [s.value for s in RateLimitStrategy]
        }
        
    except Exception as e:
        logger.error(f"Rate limiter health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }