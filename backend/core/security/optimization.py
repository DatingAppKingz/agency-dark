"""
Performance optimization utilities for the security system.

Provides caching strategies, query optimization, and performance monitoring
for permission checks and rate limiting.
"""
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import hashlib
import json
from functools import lru_cache
from collections import defaultdict
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload

from models.user import User
from models.feature_permission import FeaturePermission, FeatureType
from models.rate_limit import RateLimitConfig, RateLimitType
from core.redis import redis_client
from core.logger import get_logger


logger = get_logger(__name__)


class PermissionCacheOptimizer:
    """Optimizes permission caching for better performance."""
    
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self.metrics = defaultdict(int)
        self.cache_patterns = defaultdict(list)
    
    def generate_cache_key(
        self,
        user_id: str,
        feature_type: FeatureType,
        action: str,
        context_hash: Optional[str] = None
    ) -> str:
        """Generate optimized cache key."""
        # Use shorter keys for better memory efficiency
        key_parts = [
            "perm",
            user_id[:8],  # Use first 8 chars of UUID
            feature_type.value[:3],  # Abbreviate feature type
            hashlib.md5(action.encode()).hexdigest()[:8]  # Hash action
        ]
        
        if context_hash:
            key_parts.append(context_hash[:8])
        
        return ":".join(key_parts)
    
    async def warm_cache_for_user(
        self,
        db: AsyncSession,
        user: User,
        feature_types: List[FeatureType]
    ):
        """Pre-warm cache for a user's common permissions."""
        # Get user's permissions in batch
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                or_(
                    FeaturePermission.user_id == user.id,
                    FeaturePermission.role_id.in_([r.id for r in user.roles])
                ),
                FeaturePermission.feature_type.in_(feature_types)
            )
        ).options(
            selectinload(FeaturePermission.role),
            selectinload(FeaturePermission.user)
        )
        
        result = await db.execute(query)
        permissions = result.scalars().all()
        
        # Group by feature type for efficient caching
        perms_by_type = defaultdict(list)
        for perm in permissions:
            perms_by_type[perm.feature_type].append(perm)
        
        # Cache grouped permissions
        pipeline = redis_client.pipeline()
        for feature_type, perms in perms_by_type.items():
            cache_key = f"user_perms:{user.id}:{feature_type.value}"
            cache_value = json.dumps({
                "permissions": [str(p.id) for p in perms],
                "cached_at": datetime.utcnow().isoformat()
            })
            pipeline.setex(cache_key, self.cache_ttl, cache_value)
        
        await pipeline.execute()
        logger.info(f"Warmed cache for user {user.id} with {len(permissions)} permissions")
    
    async def get_cached_permissions(
        self,
        user_id: str,
        feature_type: FeatureType
    ) -> Optional[List[str]]:
        """Get cached permission IDs for user and feature type."""
        cache_key = f"user_perms:{user_id}:{feature_type.value}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            self.metrics["cache_hits"] += 1
            data = json.loads(cached)
            return data["permissions"]
        
        self.metrics["cache_misses"] += 1
        return None
    
    def analyze_cache_patterns(self) -> Dict[str, Any]:
        """Analyze cache usage patterns for optimization."""
        total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        hit_rate = self.metrics["cache_hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "cache_hits": self.metrics["cache_hits"],
            "cache_misses": self.metrics["cache_misses"],
            "recommendations": self._generate_recommendations(hit_rate)
        }
    
    def _generate_recommendations(self, hit_rate: float) -> List[str]:
        """Generate cache optimization recommendations."""
        recommendations = []
        
        if hit_rate < 0.7:
            recommendations.append("Consider increasing cache TTL for better hit rate")
            recommendations.append("Pre-warm cache for active users during low-traffic periods")
        
        if self.metrics["cache_misses"] > 1000:
            recommendations.append("Implement cache warming for frequently accessed permissions")
        
        return recommendations


class QueryOptimizer:
    """Optimizes database queries for permission and rate limit checks."""
    
    @staticmethod
    async def batch_get_permissions(
        db: AsyncSession,
        user_ids: List[str],
        feature_types: List[FeatureType]
    ) -> Dict[str, List[FeaturePermission]]:
        """Batch fetch permissions for multiple users."""
        # Single optimized query instead of N queries
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                FeaturePermission.user_id.in_(user_ids),
                FeaturePermission.feature_type.in_(feature_types)
            )
        ).options(
            joinedload(FeaturePermission.role),
            joinedload(FeaturePermission.user)
        )
        
        result = await db.execute(query)
        permissions = result.scalars().unique().all()
        
        # Group by user
        perms_by_user = defaultdict(list)
        for perm in permissions:
            if perm.user_id:
                perms_by_user[str(perm.user_id)].append(perm)
        
        return dict(perms_by_user)
    
    @staticmethod
    async def get_permission_with_related(
        db: AsyncSession,
        permission_id: str
    ) -> Optional[FeaturePermission]:
        """Get permission with all related data in single query."""
        query = select(FeaturePermission).where(
            FeaturePermission.id == permission_id
        ).options(
            selectinload(FeaturePermission.role),
            selectinload(FeaturePermission.user),
            selectinload(FeaturePermission.usage_logs)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_rate_limit_configs_optimized(
        db: AsyncSession,
        identifier: str,
        identifier_type: RateLimitType
    ) -> List[RateLimitConfig]:
        """Get rate limit configs with optimized query."""
        # Use indexed columns and avoid N+1
        query = select(RateLimitConfig).where(
            and_(
                RateLimitConfig.is_active == True,
                or_(
                    RateLimitConfig.limit_type == identifier_type,
                    RateLimitConfig.limit_type == RateLimitType.GLOBAL
                ),
                or_(
                    RateLimitConfig.identifier == identifier,
                    RateLimitConfig.identifier.is_(None)
                )
            )
        ).order_by(
            RateLimitConfig.priority.desc()
        )
        
        result = await db.execute(query)
        return result.scalars().all()


class PerformanceMonitor:
    """Monitors and tracks performance metrics."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.slow_query_threshold = 0.1  # 100ms
    
    async def track_operation(
        self,
        operation_type: str,
        operation_id: str,
        start_time: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track performance of an operation."""
        duration = time.time() - start_time
        
        metric = {
            "operation_id": operation_id,
            "duration": duration,
            "success": success,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        self.metrics[operation_type].append(metric)
        
        # Log slow operations
        if duration > self.slow_query_threshold:
            logger.warning(
                f"Slow {operation_type} operation",
                extra={
                    "operation_id": operation_id,
                    "duration_ms": duration * 1000,
                    "metadata": metadata
                }
            )
        
        # Clean old metrics (keep last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.metrics[operation_type] = [
            m for m in self.metrics[operation_type]
            if m["timestamp"] > cutoff_time
        ]
    
    def get_performance_stats(
        self,
        operation_type: str,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance statistics for an operation type."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        recent_metrics = [
            m for m in self.metrics[operation_type]
            if m["timestamp"] > cutoff_time
        ]
        
        if not recent_metrics:
            return {
                "count": 0,
                "avg_duration_ms": 0,
                "p50_duration_ms": 0,
                "p95_duration_ms": 0,
                "p99_duration_ms": 0,
                "success_rate": 0
            }
        
        durations = [m["duration"] * 1000 for m in recent_metrics]  # Convert to ms
        success_count = sum(1 for m in recent_metrics if m["success"])
        
        return {
            "count": len(recent_metrics),
            "avg_duration_ms": statistics.mean(durations),
            "p50_duration_ms": statistics.median(durations),
            "p95_duration_ms": statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else durations[0],
            "p99_duration_ms": statistics.quantiles(durations, n=100)[98] if len(durations) > 1 else durations[0],
            "success_rate": success_count / len(recent_metrics),
            "slow_operations": sum(1 for d in durations if d > self.slow_query_threshold * 1000)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance stats for all tracked operations."""
        return {
            operation_type: self.get_performance_stats(operation_type)
            for operation_type in self.metrics.keys()
        }


class ConnectionPoolOptimizer:
    """Optimizes Redis connection pool usage."""
    
    def __init__(self, max_connections: int = 50):
        self.max_connections = max_connections
        self.connection_metrics = defaultdict(int)
    
    async def execute_with_retry(
        self,
        operation: callable,
        max_retries: int = 3,
        backoff_factor: float = 0.1
    ) -> Any:
        """Execute Redis operation with retry logic."""
        for attempt in range(max_retries):
            try:
                result = await operation()
                self.connection_metrics["successful_operations"] += 1
                return result
            except Exception as e:
                self.connection_metrics["failed_operations"] += 1
                
                if attempt == max_retries - 1:
                    logger.error(f"Redis operation failed after {max_retries} attempts: {e}")
                    raise
                
                # Exponential backoff
                wait_time = backoff_factor * (2 ** attempt)
                await asyncio.sleep(wait_time)
    
    async def batch_redis_operations(
        self,
        operations: List[Tuple[str, callable]]
    ) -> List[Any]:
        """Execute multiple Redis operations in a pipeline."""
        pipeline = redis_client.pipeline()
        
        for op_name, op_func in operations:
            op_func(pipeline)
        
        try:
            results = await pipeline.execute()
            self.connection_metrics["pipeline_operations"] += 1
            return results
        except Exception as e:
            self.connection_metrics["pipeline_failures"] += 1
            logger.error(f"Redis pipeline operation failed: {e}")
            raise
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get Redis connection pool statistics."""
        return {
            "successful_operations": self.connection_metrics["successful_operations"],
            "failed_operations": self.connection_metrics["failed_operations"],
            "pipeline_operations": self.connection_metrics["pipeline_operations"],
            "pipeline_failures": self.connection_metrics["pipeline_failures"],
            "failure_rate": (
                self.connection_metrics["failed_operations"] /
                (self.connection_metrics["successful_operations"] + self.connection_metrics["failed_operations"])
                if (self.connection_metrics["successful_operations"] + self.connection_metrics["failed_operations"]) > 0
                else 0
            )
        }


# Global instances
cache_optimizer = PermissionCacheOptimizer()
query_optimizer = QueryOptimizer()
performance_monitor = PerformanceMonitor()
connection_optimizer = ConnectionPoolOptimizer()


# Utility functions
@lru_cache(maxsize=1000)
def compute_context_hash(context: str) -> str:
    """Compute hash of context for cache keys."""
    return hashlib.md5(context.encode()).hexdigest()[:16]


async def optimize_permission_check(
    db: AsyncSession,
    user: User,
    feature_type: FeatureType,
    action: str
) -> Tuple[bool, Optional[str]]:
    """Optimized permission check with caching and monitoring."""
    start_time = time.time()
    operation_id = f"{user.id}:{feature_type.value}:{action}"
    
    try:
        # Check cache first
        cache_key = cache_optimizer.generate_cache_key(
            str(user.id), feature_type, action
        )
        cached_result = await redis_client.get(cache_key)
        
        if cached_result:
            result = json.loads(cached_result)
            await performance_monitor.track_operation(
                "permission_check_cached",
                operation_id,
                start_time,
                success=True,
                metadata={"cache_hit": True}
            )
            return result["allowed"], result.get("reason")
        
        # Perform actual check (would call the service)
        # This is a placeholder - integrate with actual service
        allowed = True
        reason = None
        
        # Cache result
        await redis_client.setex(
            cache_key,
            cache_optimizer.cache_ttl,
            json.dumps({"allowed": allowed, "reason": reason})
        )
        
        await performance_monitor.track_operation(
            "permission_check_db",
            operation_id,
            start_time,
            success=True,
            metadata={"cache_hit": False}
        )
        
        return allowed, reason
        
    except Exception as e:
        await performance_monitor.track_operation(
            "permission_check_error",
            operation_id,
            start_time,
            success=False,
            metadata={"error": str(e)}
        )
        raise