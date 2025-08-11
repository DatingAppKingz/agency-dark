"""
Health check and status endpoints.
"""
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from core.database import get_db
from core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    # Check database connection
    try:
        result = await db.execute(text("SELECT 1"))
        _ = result.scalar()
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = "unhealthy"
        health_status["status"] = "degraded"
    
    # Check Redis connection
    try:
        redis_client = redis.from_url(settings.REDIS_URL or "redis://localhost:6379")
        await redis_client.ping()
        await redis_client.close()
        health_status["services"]["cache"] = "healthy"
    except Exception as e:
        health_status["services"]["cache"] = "unhealthy"
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/status")
async def status_check():
    """
    API status endpoint.
    Returns basic API information.
    """
    return {
        "status": "operational",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "production",
        "timestamp": datetime.now().isoformat(),
        "api": {
            "name": "AgencyDark API",
            "description": "Multi-tenant agency management platform"
        }
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check for Kubernetes.
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Check if database is accessible
        result = await db.execute(text("SELECT 1"))
        _ = result.scalar()
        
        return {
            "ready": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "ready": False,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/live")
async def liveness_check():
    """
    Liveness check for Kubernetes.
    Returns 200 if the service is alive.
    """
    return {
        "alive": True,
        "timestamp": datetime.now().isoformat()
    }