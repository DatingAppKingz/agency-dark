"""
Database query optimization for the security system.

Provides query optimization techniques, query result caching,
and database performance monitoring.
"""
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Type
from datetime import datetime, timedelta
import hashlib
from collections import defaultdict
from functools import wraps

from sqlalchemy import select, and_, or_, func, text, Index
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, contains_eager, load_only
from sqlalchemy.sql import Select
from sqlalchemy.dialects.postgresql import insert

from models.user import User
from models.feature_permission import FeaturePermission, FeatureType
from models.rate_limit import RateLimitConfig, RateLimitType
from models.audit_log import AuditLog
from core.logger import get_logger


logger = get_logger(__name__)


class QueryOptimizationStrategies:
    """Collection of query optimization strategies."""
    
    @staticmethod
    def add_permission_indexes(metadata):
        """Add database indexes for permission queries."""
        # Composite indexes for common query patterns
        indexes = [
            # User permission lookups
            Index(
                'idx_feature_permission_user_lookup',
                'user_id', 'feature_type', 'is_active',
                postgresql_where='is_active = true'
            ),
            # Role permission lookups
            Index(
                'idx_feature_permission_role_lookup',
                'role_id', 'feature_type', 'is_active',
                postgresql_where='is_active = true'
            ),
            # Agency permission lookups
            Index(
                'idx_feature_permission_agency_lookup',
                'agency_id', 'feature_type', 'is_active',
                postgresql_where='is_active = true'
            ),
            # Time-based queries
            Index(
                'idx_feature_permission_expiry',
                'expires_at',
                postgresql_where='expires_at IS NOT NULL'
            ),
            # Rate limit lookups
            Index(
                'idx_rate_limit_lookup',
                'limit_type', 'identifier', 'is_active',
                postgresql_where='is_active = true'
            ),
            # Audit log queries
            Index(
                'idx_audit_log_user_time',
                'user_id', 'timestamp'
            ),
            Index(
                'idx_audit_log_action_time',
                'action', 'timestamp'
            )
        ]
        
        return indexes
    
    @staticmethod
    async def optimize_permission_query(
        db: AsyncSession,
        user: User,
        feature_types: Optional[List[FeatureType]] = None
    ) -> Select:
        """Create optimized permission query with proper joins and filters."""
        # Base query with selective loading
        query = select(FeaturePermission).options(
            load_only(
                FeaturePermission.id,
                FeaturePermission.feature_type,
                FeaturePermission.allowed_actions,
                FeaturePermission.denied_actions,
                FeaturePermission.priority,
                FeaturePermission.expires_at,
                FeaturePermission.is_active
            )
        )
        
        # Build WHERE conditions
        conditions = [
            FeaturePermission.is_active == True,
            or_(
                FeaturePermission.expires_at.is_(None),
                FeaturePermission.expires_at > datetime.utcnow()
            )
        ]
        
        # User and role conditions
        user_conditions = [
            FeaturePermission.user_id == user.id
        ]
        
        if hasattr(user, 'roles') and user.roles:
            role_ids = [r.id for r in user.roles]
            user_conditions.append(
                FeaturePermission.role_id.in_(role_ids)
            )
        
        # Agency condition
        if user.agency_id:
            user_conditions.append(
                or_(
                    FeaturePermission.agency_id == user.agency_id,
                    FeaturePermission.agency_id.is_(None)
                )
            )
        
        conditions.append(or_(*user_conditions))
        
        # Feature type filter
        if feature_types:
            conditions.append(
                FeaturePermission.feature_type.in_(feature_types)
            )
        
        # Apply conditions and order by priority
        query = query.where(and_(*conditions)).order_by(
            FeaturePermission.priority.desc(),
            FeaturePermission.created_at.desc()
        )
        
        return query
    
    @staticmethod
    async def batch_load_permissions(
        db: AsyncSession,
        users: List[User],
        feature_type: FeatureType
    ) -> Dict[str, List[FeaturePermission]]:
        """Efficiently load permissions for multiple users."""
        user_ids = [u.id for u in users]
        
        # Collect all role IDs
        all_role_ids = set()
        for user in users:
            if hasattr(user, 'roles'):
                all_role_ids.update(r.id for r in user.roles)
        
        # Single query for all permissions
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                FeaturePermission.feature_type == feature_type,
                or_(
                    FeaturePermission.user_id.in_(user_ids),
                    FeaturePermission.role_id.in_(all_role_ids)
                )
            )
        )
        
        result = await db.execute(query)
        all_permissions = result.scalars().all()
        
        # Group permissions by user
        user_permissions = defaultdict(list)
        role_permissions = defaultdict(list)
        
        for perm in all_permissions:
            if perm.user_id:
                user_permissions[str(perm.user_id)].append(perm)
            elif perm.role_id:
                role_permissions[str(perm.role_id)].append(perm)
        
        # Assign permissions to users
        result_map = {}
        for user in users:
            user_perms = user_permissions.get(str(user.id), [])
            
            # Add role permissions
            if hasattr(user, 'roles'):
                for role in user.roles:
                    user_perms.extend(role_permissions.get(str(role.id), []))
            
            result_map[str(user.id)] = user_perms
        
        return result_map


class QueryResultCache:
    """Cache for database query results."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self.cache = {}
        self._lock = asyncio.Lock()
    
    def _generate_key(self, query: str, params: Dict[str, Any]) -> str:
        """Generate cache key from query and parameters."""
        cache_data = f"{query}:{sorted(params.items())}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    async def get_or_execute(
        self,
        db: AsyncSession,
        query: Select,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Get from cache or execute query."""
        if params is None:
            params = {}
        
        # Generate cache key
        query_str = str(query.compile(compile_kwargs={"literal_binds": True}))
        cache_key = self._generate_key(query_str, params)
        
        # Check cache
        async with self._lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if entry["expires_at"] > time.time():
                    return entry["result"]
                else:
                    del self.cache[cache_key]
        
        # Execute query
        result = await db.execute(query)
        data = result.scalars().all()
        
        # Cache result
        async with self._lock:
            self.cache[cache_key] = {
                "result": data,
                "expires_at": time.time() + self.ttl
            }
        
        return data
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        async with self._lock:
            keys_to_delete = [
                k for k in self.cache.keys()
                if pattern in k
            ]
            for key in keys_to_delete:
                del self.cache[key]


class QueryPerformanceAnalyzer:
    """Analyze and optimize query performance."""
    
    def __init__(self):
        self.query_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "avg_time": 0
        })
        self.slow_query_threshold = 0.1  # 100ms
        self.slow_queries = []
    
    async def analyze_query(
        self,
        db: AsyncSession,
        query: Select,
        label: str
    ) -> Tuple[Any, float]:
        """Execute query and analyze performance."""
        start_time = time.time()
        
        # Execute query
        result = await db.execute(query)
        data = result.scalars().all()
        
        # Record performance
        duration = time.time() - start_time
        self._record_stats(label, duration)
        
        # Check for slow query
        if duration > self.slow_query_threshold:
            self.slow_queries.append({
                "label": label,
                "duration": duration,
                "timestamp": datetime.utcnow(),
                "query": str(query.compile(compile_kwargs={"literal_binds": True}))
            })
            
            # Log slow query
            logger.warning(
                f"Slow query detected: {label}",
                extra={
                    "duration_ms": duration * 1000,
                    "query": str(query)[:200]
                }
            )
        
        return data, duration
    
    def _record_stats(self, label: str, duration: float):
        """Record query statistics."""
        stats = self.query_stats[label]
        stats["count"] += 1
        stats["total_time"] += duration
        stats["min_time"] = min(stats["min_time"], duration)
        stats["max_time"] = max(stats["max_time"], duration)
        stats["avg_time"] = stats["total_time"] / stats["count"]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        return {
            "query_stats": dict(self.query_stats),
            "slow_queries": self.slow_queries[-100:],  # Last 100 slow queries
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Analyze query patterns
        for label, stats in self.query_stats.items():
            if stats["avg_time"] > 0.05:  # 50ms average
                recommendations.append(
                    f"Consider optimizing '{label}' query - avg time: {stats['avg_time']*1000:.1f}ms"
                )
            
            if stats["count"] > 1000 and stats["avg_time"] > 0.01:
                recommendations.append(
                    f"High-frequency query '{label}' could benefit from caching"
                )
        
        # Check for N+1 query patterns
        if self._detect_n_plus_one():
            recommendations.append(
                "Potential N+1 query pattern detected - consider using batch loading"
            )
        
        return recommendations
    
    def _detect_n_plus_one(self) -> bool:
        """Detect potential N+1 query patterns."""
        # Look for repeated similar queries
        for label, stats in self.query_stats.items():
            if "user" in label.lower() and stats["count"] > 100:
                # High count of user-related queries might indicate N+1
                return True
        return False


class BulkOperationOptimizer:
    """Optimize bulk database operations."""
    
    @staticmethod
    async def bulk_insert_permissions(
        db: AsyncSession,
        permissions: List[Dict[str, Any]]
    ):
        """Efficiently insert multiple permissions."""
        if not permissions:
            return
        
        # Use PostgreSQL's INSERT ... ON CONFLICT
        stmt = insert(FeaturePermission).values(permissions)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['id']
        )
        
        await db.execute(stmt)
        await db.commit()
    
    @staticmethod
    async def bulk_update_permissions(
        db: AsyncSession,
        updates: List[Tuple[str, Dict[str, Any]]]
    ):
        """Efficiently update multiple permissions."""
        if not updates:
            return
        
        # Group updates by common values
        update_groups = defaultdict(list)
        for perm_id, values in updates:
            values_key = tuple(sorted(values.items()))
            update_groups[values_key].append(perm_id)
        
        # Execute grouped updates
        for values_tuple, perm_ids in update_groups.items():
            values = dict(values_tuple)
            stmt = (
                select(FeaturePermission)
                .where(FeaturePermission.id.in_(perm_ids))
                .with_for_update()
            )
            
            result = await db.execute(stmt)
            permissions = result.scalars().all()
            
            for perm in permissions:
                for key, value in values.items():
                    setattr(perm, key, value)
        
        await db.commit()
    
    @staticmethod
    async def bulk_delete_expired(
        db: AsyncSession,
        batch_size: int = 1000
    ) -> int:
        """Efficiently delete expired permissions in batches."""
        total_deleted = 0
        
        while True:
            # Delete batch of expired permissions
            stmt = (
                select(FeaturePermission.id)
                .where(
                    and_(
                        FeaturePermission.expires_at.isnot(None),
                        FeaturePermission.expires_at < datetime.utcnow()
                    )
                )
                .limit(batch_size)
            )
            
            result = await db.execute(stmt)
            ids_to_delete = [row[0] for row in result]
            
            if not ids_to_delete:
                break
            
            # Delete batch
            await db.execute(
                text("DELETE FROM feature_permissions WHERE id = ANY(:ids)"),
                {"ids": ids_to_delete}
            )
            await db.commit()
            
            total_deleted += len(ids_to_delete)
            
            # Small delay to prevent overwhelming the database
            if len(ids_to_delete) == batch_size:
                await asyncio.sleep(0.1)
        
        return total_deleted


class ConnectionPoolMonitor:
    """Monitor and optimize database connection pool usage."""
    
    def __init__(self, pool):
        self.pool = pool
        self.metrics = defaultdict(int)
        self._start_time = time.time()
    
    def record_checkout(self, connection):
        """Record connection checkout."""
        self.metrics["checkouts"] += 1
        self.metrics["active_connections"] = self.pool.size() - self.pool.num_overflow()
    
    def record_checkin(self, connection):
        """Record connection checkin."""
        self.metrics["checkins"] += 1
    
    def record_timeout(self):
        """Record connection timeout."""
        self.metrics["timeouts"] += 1
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        uptime = time.time() - self._start_time
        
        return {
            "pool_size": self.pool.size(),
            "checked_out_connections": self.pool.checked_out(),
            "overflow": self.pool.overflow(),
            "total": self.pool.size() + self.pool.overflow(),
            "checkouts": self.metrics["checkouts"],
            "checkins": self.metrics["checkins"],
            "timeouts": self.metrics["timeouts"],
            "utilization": self.pool.checked_out() / self.pool.size() if self.pool.size() > 0 else 0,
            "uptime_seconds": uptime
        }
    
    def get_recommendations(self) -> List[str]:
        """Get pool optimization recommendations."""
        recommendations = []
        stats = self.get_pool_stats()
        
        if stats["utilization"] > 0.8:
            recommendations.append(
                "High connection pool utilization - consider increasing pool size"
            )
        
        if stats["timeouts"] > 10:
            recommendations.append(
                f"Connection timeouts detected ({stats['timeouts']}) - check for long-running queries"
            )
        
        if stats["overflow"] > stats["pool_size"] * 0.5:
            recommendations.append(
                "Frequent overflow usage - increase base pool size"
            )
        
        return recommendations


# Global instances
query_result_cache = QueryResultCache(ttl_seconds=300)
query_analyzer = QueryPerformanceAnalyzer()
bulk_optimizer = BulkOperationOptimizer()


# Decorator for query performance tracking
def track_query_performance(label: str):
    """Decorator to track query performance."""
    def decorator(func):
        @wraps(func)
        async def wrapper(db: AsyncSession, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(db, *args, **kwargs)
                duration = time.time() - start_time
                
                # Record performance
                query_analyzer._record_stats(label, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                query_analyzer._record_stats(f"{label}_error", duration)
                raise
        
        return wrapper
    return decorator