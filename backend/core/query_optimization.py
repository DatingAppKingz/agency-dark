"""Query optimization utilities and middleware."""

import hashlib
import json
from typing import Any, Dict, Optional, Set, Type, List
from datetime import datetime, timedelta
from functools import wraps
import asyncio

from sqlalchemy import select, inspect
from sqlalchemy.orm import selectinload, joinedload, contains_eager, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from core.redis import redis_manager
from core.logger import get_logger

logger = get_logger(__name__)


class QueryOptimizer:
    """Optimizes database queries to prevent N+1 problems."""
    
    # Define eager loading strategies for models
    EAGER_LOADING_STRATEGIES = {
        "Conversation": {
            "default": ["model", "assigned_chatter"],
            "with_messages": ["model", "assigned_chatter", "messages", "messages.sender"],
            "analytics": ["model", "messages", "analytics"]
        },
        "Message": {
            "default": ["conversation", "sender"],
            "with_conversation": ["conversation", "conversation.model", "conversation.assigned_chatter"]
        },
        "Model": {
            "default": ["user", "agency"],
            "with_conversations": ["user", "agency", "conversations"],
            "with_financials": ["user", "agency", "transactions", "payouts", "earnings"]
        },
        "User": {
            "default": ["agency"],
            "with_models": ["agency", "models"],
            "with_permissions": ["agency", "role_permissions"]
        },
        "Payout": {
            "default": ["model", "payment_method", "created_by"],
            "with_earnings": ["model", "payment_method", "earnings", "created_by"]
        },
        "Transaction": {
            "default": ["model"],
            "detailed": ["model", "model.agency", "invoice"]
        }
    }
    
    @classmethod
    def optimize_query(
        cls,
        query: Select,
        model_name: str,
        strategy: str = "default"
    ) -> Select:
        """Apply eager loading strategy to a query."""
        strategies = cls.EAGER_LOADING_STRATEGIES.get(model_name, {})
        relationships = strategies.get(strategy, [])
        
        for rel in relationships:
            if "." in rel:
                # Nested relationship
                parts = rel.split(".")
                query = query.options(
                    selectinload(parts[0]).selectinload(parts[1])
                )
            else:
                # Direct relationship
                query = query.options(selectinload(rel))
        
        return query
    
    @classmethod
    def detect_n_plus_one(cls, query: Select) -> List[str]:
        """Detect potential N+1 query problems."""
        potential_issues = []
        
        # This is a simplified detection - in production, you'd want more sophisticated analysis
        # Check for relationships that aren't eagerly loaded
        # You could integrate with SQLAlchemy events to track actual queries
        
        return potential_issues


class QueryCache:
    """Redis-based query result caching."""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
    
    def cache_key(
        self,
        model_name: str,
        query_params: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> str:
        """Generate cache key for query."""
        # Create deterministic key from query parameters
        params_str = json.dumps(query_params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        
        if user_id:
            return f"query_cache:{model_name}:{user_id}:{params_hash}"
        return f"query_cache:{model_name}:{params_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached query result."""
        try:
            cached = await redis_manager.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Cache query result."""
        try:
            await redis_manager.set(
                key,
                json.dumps(value, default=str),
                expire=ttl or self.default_ttl
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        try:
            # Note: This requires SCAN command support
            # In production, consider using cache tags instead
            keys = await redis_manager.scan_keys(f"query_cache:{pattern}*")
            if keys:
                await redis_manager.delete_many(keys)
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")


# Global cache instance
query_cache = QueryCache()


def cached_query(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    user_specific: bool = False
):
    """Decorator for caching query results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract cache key components
            cache_key_parts = [key_prefix or func.__name__]
            
            # Add user ID if user-specific
            if user_specific:
                # Assume first argument is self and second is user/user_id
                if len(args) > 1:
                    user_arg = args[1]
                    if hasattr(user_arg, 'id'):
                        cache_key_parts.append(str(user_arg.id))
                    else:
                        cache_key_parts.append(str(user_arg))
            
            # Add kwargs to key
            if kwargs:
                kwargs_str = json.dumps(kwargs, sort_keys=True)
                kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
                cache_key_parts.append(kwargs_hash)
            
            cache_key = ":".join(cache_key_parts)
            
            # Try to get from cache
            cached_result = await query_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            
            # Execute query
            result = await func(*args, **kwargs)
            
            # Cache result
            await query_cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


class PaginationOptimizer:
    """Optimizes pagination for large datasets."""
    
    @staticmethod
    async def get_cursor_pagination(
        db: AsyncSession,
        model: Type,
        cursor_field: str,
        cursor_value: Optional[Any] = None,
        limit: int = 50,
        filters: Optional[List] = None,
        order_desc: bool = True
    ) -> Dict[str, Any]:
        """Implement cursor-based pagination for better performance."""
        query = select(model)
        
        # Apply filters
        if filters:
            for f in filters:
                query = query.where(f)
        
        # Apply cursor
        if cursor_value:
            cursor_attr = getattr(model, cursor_field)
            if order_desc:
                query = query.where(cursor_attr < cursor_value)
            else:
                query = query.where(cursor_attr > cursor_value)
        
        # Order and limit
        cursor_attr = getattr(model, cursor_field)
        if order_desc:
            query = query.order_by(cursor_attr.desc())
        else:
            query = query.order_by(cursor_attr.asc())
        
        query = query.limit(limit + 1)  # Get one extra to check if there's next page
        
        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Check if there's next page
        has_next = len(items) > limit
        if has_next:
            items = items[:-1]  # Remove the extra item
        
        # Get cursor for next page
        next_cursor = None
        if items and has_next:
            last_item = items[-1]
            next_cursor = getattr(last_item, cursor_field)
        
        return {
            "items": items,
            "next_cursor": next_cursor,
            "has_next": has_next
        }
    
    @staticmethod
    def optimize_count_query(
        query: Select,
        use_estimate: bool = True,
        threshold: int = 10000
    ) -> Select:
        """Optimize count queries for large tables."""
        if use_estimate:
            # For very large tables, use approximate count
            # This would use pg_class statistics
            # Implementation depends on specific requirements
            pass
        
        return query


class BatchQueryOptimizer:
    """Optimizes batch operations."""
    
    @staticmethod
    async def batch_load(
        db: AsyncSession,
        model: Type,
        ids: List[int],
        batch_size: int = 100
    ) -> List[Any]:
        """Load multiple records in batches to avoid query size limits."""
        results = []
        
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            query = select(model).where(model.id.in_(batch_ids))
            result = await db.execute(query)
            results.extend(result.scalars().all())
        
        return results
    
    @staticmethod
    async def batch_insert(
        db: AsyncSession,
        records: List[Dict],
        model: Type,
        batch_size: int = 1000
    ) -> int:
        """Insert multiple records in batches."""
        inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.add_all([model(**record) for record in batch])
            await db.flush()
            inserted += len(batch)
        
        await db.commit()
        return inserted


class QueryMonitor:
    """Monitors query performance and logs slow queries."""
    
    def __init__(self, slow_query_threshold_ms: int = 100):
        self.slow_query_threshold = slow_query_threshold_ms / 1000.0
        self.query_stats: Dict[str, Dict] = {}
    
    async def log_query(
        self,
        query: str,
        duration: float,
        params: Optional[Dict] = None
    ):
        """Log query execution."""
        if duration > self.slow_query_threshold:
            logger.warning(
                f"Slow query detected ({duration:.3f}s): {query[:200]}",
                extra={
                    "query": query,
                    "duration": duration,
                    "params": params
                }
            )
        
        # Update statistics
        query_hash = hashlib.md5(query.encode()).hexdigest()
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                "query": query[:200],
                "count": 0,
                "total_time": 0,
                "max_time": 0,
                "avg_time": 0
            }
        
        stats = self.query_stats[query_hash]
        stats["count"] += 1
        stats["total_time"] += duration
        stats["max_time"] = max(stats["max_time"], duration)
        stats["avg_time"] = stats["total_time"] / stats["count"]
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """Get slowest queries by average time."""
        sorted_queries = sorted(
            self.query_stats.values(),
            key=lambda x: x["avg_time"],
            reverse=True
        )
        return sorted_queries[:limit]


# Global query monitor
query_monitor = QueryMonitor()


# Example usage in services:
"""
from core.query_optimization import QueryOptimizer, cached_query, PaginationOptimizer

class ConversationService:
    @cached_query(ttl=300, user_specific=True)
    async def get_user_conversations(self, user_id: int, db: AsyncSession):
        # Query will be automatically cached
        query = select(Conversation).where(Conversation.user_id == user_id)
        
        # Apply optimization
        query = QueryOptimizer.optimize_query(query, "Conversation", "with_messages")
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_conversations_paginated(self, db: AsyncSession, cursor: Optional[str] = None):
        return await PaginationOptimizer.get_cursor_pagination(
            db=db,
            model=Conversation,
            cursor_field="created_at",
            cursor_value=cursor,
            limit=50,
            order_desc=True
        )
"""