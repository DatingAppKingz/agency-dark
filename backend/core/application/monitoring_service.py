"""Monitoring service for system health and performance tracking."""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime, timedelta, date
from collections import defaultdict
import psutil
import json

from models.user import User
from models.agency import Agency
from core.redis import redis_manager
from core.database import engine
from core.exceptions import ValidationError


class MonitoringService:
    """Service for monitoring system health and performance."""
    
    @staticmethod
    async def get_system_metrics() -> Dict[str, Any]:
        """Get current system metrics."""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024 * 1024 * 1024)  # Convert to GB
        memory_total = memory.total / (1024 * 1024 * 1024)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used / (1024 * 1024 * 1024)
        disk_total = disk.total / (1024 * 1024 * 1024)
        
        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info().rss / (1024 * 1024)  # MB
        process_cpu = process.cpu_percent(interval=0.1)
        
        # Database connection pool stats
        pool_stats = {}
        if hasattr(engine.pool, 'size'):
            pool_stats = {
                "size": engine.pool.size(),
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "total": engine.pool.size() + engine.pool.overflow()
            }
        
        # Redis stats
        redis_info = {}
        try:
            client = await redis_manager.connect()
            info = await client.info()
            redis_info = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "used_memory_peak_mb": info.get("used_memory_peak", 0) / (1024 * 1024),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
        except:
            pass
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count
            },
            "memory": {
                "percent": memory_percent,
                "used_gb": round(memory_used, 2),
                "total_gb": round(memory_total, 2)
            },
            "disk": {
                "percent": disk_percent,
                "used_gb": round(disk_used, 2),
                "total_gb": round(disk_total, 2)
            },
            "process": {
                "memory_mb": round(process_memory, 2),
                "cpu_percent": process_cpu
            },
            "database": pool_stats,
            "redis": redis_info
        }
    
    @staticmethod
    async def get_application_metrics(
        db: AsyncSession,
        time_range_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get application-specific metrics."""
        since = datetime.utcnow() - timedelta(minutes=time_range_minutes)
        
        # Active users
        active_users = await db.execute(
            select(func.count(func.distinct(User.id)))
            .where(User.last_login_at >= since)
        )
        active_count = active_users.scalar() or 0
        
        # Request metrics from Redis
        request_metrics = await MonitoringService._get_request_metrics(since)
        
        # Error metrics
        error_metrics = await MonitoringService._get_error_metrics(since)
        
        # WebSocket connections
        ws_connections = await redis_manager.get("websocket:connection_count") or 0
        
        # Cache hit rate
        cache_stats = await MonitoringService._get_cache_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_minutes": time_range_minutes,
            "users": {
                "active": active_count
            },
            "requests": request_metrics,
            "errors": error_metrics,
            "websockets": {
                "active_connections": int(ws_connections)
            },
            "cache": cache_stats
        }
    
    @staticmethod
    async def get_recent_errors(
        limit: int = 100,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent application errors."""
        # Get errors from Redis
        pattern = "error:*"
        errors = []
        
        cursor = 0
        while True:
            cursor, keys = await redis_manager.client.scan(
                cursor, match=pattern, count=100
            )
            
            for key in keys[:limit - len(errors)]:
                error_data = await redis_manager.get(key.decode())
                if error_data:
                    if not severity or error_data.get("severity") == severity:
                        errors.append(error_data)
            
            if cursor == 0 or len(errors) >= limit:
                break
        
        # Sort by timestamp
        errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return errors[:limit]
    
    @staticmethod
    async def log_error(
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "error"
    ):
        """Log an error for monitoring."""
        error_id = f"{datetime.utcnow().timestamp()}"
        error_data = {
            "id": error_id,
            "type": error_type,
            "message": message,
            "severity": severity,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis with expiration
        await redis_manager.set(
            f"error:{error_id}",
            error_data,
            expire=86400  # 24 hours
        )
        
        # Increment error counters
        await redis_manager.client.hincrby(
            "error_counts",
            error_type,
            1
        )
        
        # Update hourly error rate
        hour_key = f"errors:{datetime.utcnow().strftime('%Y%m%d%H')}"
        await redis_manager.client.incr(hour_key)
        await redis_manager.expire(hour_key, 86400)
    
    @staticmethod
    async def get_performance_metrics(
        db: AsyncSession,
        time_range_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance metrics."""
        since = datetime.utcnow() - timedelta(minutes=time_range_minutes)
        
        # Response time metrics
        response_times = await MonitoringService._get_response_times(since)
        
        # Database query performance
        db_metrics = await MonitoringService._get_database_metrics(db)
        
        # Background job metrics
        job_metrics = await MonitoringService._get_job_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_minutes": time_range_minutes,
            "response_times": response_times,
            "database": db_metrics,
            "background_jobs": job_metrics
        }
    
    @staticmethod
    async def get_health_status() -> Dict[str, Any]:
        """Get overall system health status."""
        checks = {
            "database": await MonitoringService._check_database_health(),
            "redis": await MonitoringService._check_redis_health(),
            "disk_space": await MonitoringService._check_disk_space(),
            "memory": await MonitoringService._check_memory()
        }
        
        # Overall status
        all_healthy = all(check["healthy"] for check in checks.values())
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        }
    
    @staticmethod
    async def _get_request_metrics(since: datetime) -> Dict[str, Any]:
        """Get request metrics from Redis."""
        # This would track actual requests in production
        # For now, return sample data
        total = await redis_manager.get("request_count:total") or 0
        success = await redis_manager.get("request_count:success") or 0
        errors = await redis_manager.get("request_count:error") or 0
        
        return {
            "total": int(total),
            "success": int(success),
            "errors": int(errors),
            "error_rate": (errors / total * 100) if total > 0 else 0
        }
    
    @staticmethod
    async def _get_error_metrics(since: datetime) -> Dict[str, Any]:
        """Get error metrics."""
        error_counts = await redis_manager.client.hgetall("error_counts")
        
        # Convert bytes to string and aggregate
        error_by_type = {}
        total_errors = 0
        
        for error_type, count in error_counts.items():
            type_str = error_type.decode() if isinstance(error_type, bytes) else error_type
            count_int = int(count)
            error_by_type[type_str] = count_int
            total_errors += count_int
        
        return {
            "total": total_errors,
            "by_type": error_by_type
        }
    
    @staticmethod
    async def _get_cache_stats() -> Dict[str, Any]:
        """Get cache statistics."""
        hits = await redis_manager.get("cache:hits") or 0
        misses = await redis_manager.get("cache:misses") or 0
        total = int(hits) + int(misses)
        
        return {
            "hits": int(hits),
            "misses": int(misses),
            "hit_rate": (int(hits) / total * 100) if total > 0 else 0
        }
    
    @staticmethod
    async def _get_response_times(since: datetime) -> Dict[str, Any]:
        """Get response time metrics."""
        # In production, this would track actual response times
        # For now, return sample data
        return {
            "avg_ms": 125,
            "p50_ms": 100,
            "p90_ms": 200,
            "p99_ms": 500
        }
    
    @staticmethod
    async def _get_database_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get database performance metrics."""
        # Get slow query count
        try:
            result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND query_start < now() - interval '5 seconds'
                """)
            )
            slow_queries = result.scalar() or 0
        except:
            slow_queries = 0
        
        return {
            "slow_queries": slow_queries,
            "connection_pool": {
                "active": engine.pool.checkedout() if hasattr(engine.pool, 'checkedout') else 0,
                "idle": engine.pool.checkedin() if hasattr(engine.pool, 'checkedin') else 0
            }
        }
    
    @staticmethod
    async def _get_job_metrics() -> Dict[str, Any]:
        """Get background job metrics."""
        # This would connect to Celery in production
        # For now, return sample data
        return {
            "pending": 0,
            "active": 0,
            "completed": 0,
            "failed": 0
        }
    
    @staticmethod
    async def _check_database_health() -> Dict[str, Any]:
        """Check database health."""
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"healthy": True, "message": "Database is responsive"}
        except Exception as e:
            return {"healthy": False, "message": f"Database error: {str(e)}"}
    
    @staticmethod
    async def _check_redis_health() -> Dict[str, Any]:
        """Check Redis health."""
        try:
            client = await redis_manager.connect()
            await client.ping()
            return {"healthy": True, "message": "Redis is responsive"}
        except Exception as e:
            return {"healthy": False, "message": f"Redis error: {str(e)}"}
    
    @staticmethod
    async def _check_disk_space() -> Dict[str, Any]:
        """Check disk space."""
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            return {"healthy": False, "message": f"Disk usage critical: {disk.percent}%"}
        elif disk.percent > 80:
            return {"healthy": True, "message": f"Disk usage warning: {disk.percent}%"}
        else:
            return {"healthy": True, "message": f"Disk usage normal: {disk.percent}%"}
    
    @staticmethod
    async def _check_memory() -> Dict[str, Any]:
        """Check memory usage."""
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return {"healthy": False, "message": f"Memory usage critical: {memory.percent}%"}
        elif memory.percent > 80:
            return {"healthy": True, "message": f"Memory usage warning: {memory.percent}%"}
        else:
            return {"healthy": True, "message": f"Memory usage normal: {memory.percent}%"}