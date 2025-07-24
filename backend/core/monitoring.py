"""
Monitoring and health check utilities.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import psutil
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

from core.database import engine
from core.redis import redis_client
from core.config import settings


# Prometheus metrics
request_count = Counter(
    'agencydark_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'agencydark_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

active_users = Gauge(
    'agencydark_active_users',
    'Number of active users'
)

db_connections = Gauge(
    'agencydark_db_connections',
    'Number of database connections'
)

redis_connections = Gauge(
    'agencydark_redis_connections',
    'Number of Redis connections'
)

system_cpu_usage = Gauge(
    'agencydark_system_cpu_percent',
    'System CPU usage percentage'
)

system_memory_usage = Gauge(
    'agencydark_system_memory_percent',
    'System memory usage percentage'
)

system_disk_usage = Gauge(
    'agencydark_system_disk_percent',
    'System disk usage percentage'
)


class HealthChecker:
    """Service for health checks and monitoring."""
    
    @staticmethod
    async def check_database() -> Dict[str, Any]:
        """Check database health."""
        try:
            start = time.time()
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.scalar()
            
            latency = (time.time() - start) * 1000  # ms
            
            # Get connection pool stats
            pool_status = {
                "size": engine.pool.size(),
                "checked_out": engine.pool.checked_out_connections,
                "overflow": engine.pool.overflow,
                "total": engine.pool.size() + engine.pool.overflow
            }
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "pool": pool_status
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    async def check_redis() -> Dict[str, Any]:
        """Check Redis health."""
        try:
            start = time.time()
            await redis_client.ping()
            latency = (time.time() - start) * 1000  # ms
            
            # Get Redis info
            info = await redis_client.info()
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0"),
                "uptime_in_days": info.get("uptime_in_days", 0)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    async def check_external_apis() -> Dict[str, Any]:
        """Check external API connectivity."""
        results = {}
        
        # Check Inflow API
        try:
            # Mock check - in production, make actual API call
            results["inflow_api"] = {
                "status": "healthy",
                "latency_ms": 50
            }
        except Exception as e:
            results["inflow_api"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check OnlyFans API
        try:
            # Mock check - in production, make actual API call
            results["onlyfans_api"] = {
                "status": "healthy",
                "latency_ms": 75
            }
        except Exception as e:
            results["onlyfans_api"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        return results
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Get system resource metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network
        net_io = psutil.net_io_counters()
        
        # Update Prometheus metrics
        system_cpu_usage.set(cpu_percent)
        system_memory_usage.set(memory.percent)
        system_disk_usage.set(disk.percent)
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "load_average": psutil.getloadavg()
            },
            "memory": {
                "percent": memory.percent,
                "total": memory.total,
                "available": memory.available,
                "used": memory.used
            },
            "disk": {
                "percent": disk.percent,
                "total": disk.total,
                "used": disk.used,
                "free": disk.free
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        }
    
    @staticmethod
    async def get_application_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get application-specific metrics."""
        try:
            # Active users (last 5 minutes)
            result = await db.execute(
                text("""
                    SELECT COUNT(DISTINCT user_id) as active_users
                    FROM audit_logs
                    WHERE timestamp > NOW() - INTERVAL '5 minutes'
                """)
            )
            active_user_count = result.scalar() or 0
            active_users.set(active_user_count)
            
            # Total users
            result = await db.execute(
                text("SELECT COUNT(*) FROM users WHERE is_active = true")
            )
            total_users = result.scalar() or 0
            
            # Total models
            result = await db.execute(
                text("SELECT COUNT(*) FROM model_profiles WHERE is_active = true")
            )
            total_models = result.scalar() or 0
            
            # Total fans
            result = await db.execute(
                text("SELECT COUNT(*) FROM fans")
            )
            total_fans = result.scalar() or 0
            
            # Revenue today
            result = await db.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0) as revenue
                    FROM transactions
                    WHERE created_at >= CURRENT_DATE
                    AND status = 'completed'
                """)
            )
            revenue_today = float(result.scalar() or 0)
            
            return {
                "users": {
                    "active": active_user_count,
                    "total": total_users
                },
                "models": {
                    "total": total_models
                },
                "fans": {
                    "total": total_fans
                },
                "revenue": {
                    "today": revenue_today
                }
            }
            
        except Exception as e:
            return {
                "error": str(e)
            }
    
    @staticmethod
    async def full_health_check(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """Perform full health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": {}
        }
        
        # Database check
        db_health = await HealthChecker.check_database()
        health_status["checks"]["database"] = db_health
        if db_health["status"] != "healthy":
            health_status["status"] = "degraded"
        
        # Redis check
        redis_health = await HealthChecker.check_redis()
        health_status["checks"]["redis"] = redis_health
        if redis_health["status"] != "healthy":
            health_status["status"] = "degraded"
        
        # External APIs
        api_health = await HealthChecker.check_external_apis()
        health_status["checks"]["external_apis"] = api_health
        
        # System metrics
        health_status["system"] = HealthChecker.get_system_metrics()
        
        # Application metrics (if db session provided)
        if db:
            health_status["application"] = await HealthChecker.get_application_metrics(db)
        
        return health_status
    
    @staticmethod
    async def liveness_check() -> Dict[str, Any]:
        """Simple liveness check for Kubernetes."""
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def readiness_check() -> Dict[str, Any]:
        """Readiness check for Kubernetes."""
        # Check critical dependencies
        db_health = await HealthChecker.check_database()
        redis_health = await HealthChecker.check_redis()
        
        is_ready = (
            db_health["status"] == "healthy" and
            redis_health["status"] == "healthy"
        )
        
        return {
            "ready": is_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_health["status"],
            "redis": redis_health["status"]
        }


# Background task to collect metrics
async def collect_metrics_task():
    """Background task to collect system metrics."""
    while True:
        try:
            HealthChecker.get_system_metrics()
            await asyncio.sleep(60)  # Collect every minute
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            await asyncio.sleep(60)


# Prometheus metrics endpoint
def get_metrics():
    """Get Prometheus metrics."""
    return generate_latest()