"""
Query optimization utilities for database performance
"""
from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, selectinload, joinedload, contains_eager
from sqlalchemy.sql import Select
from sqlalchemy.orm.interfaces import StrategizedProperty

from core.database import Base

T = TypeVar("T", bound=Base)


class QueryOptimizer:
    """Optimize database queries for better performance"""
    
    @staticmethod
    def apply_eager_loading(
        query: Select[T],
        relationships: List[str]
    ) -> Select[T]:
        """
        Apply eager loading to relationships to avoid N+1 queries
        
        Args:
            query: Base SQLAlchemy query
            relationships: List of relationship names to eager load
            
        Returns:
            Optimized query with eager loading
        """
        for relationship in relationships:
            if "." in relationship:
                # Handle nested relationships
                query = query.options(selectinload(relationship))
            else:
                # Simple relationships
                query = query.options(joinedload(relationship))
        
        return query
    
    @staticmethod
    def apply_pagination(
        query: Select[T],
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100
    ) -> Select[T]:
        """
        Apply pagination to query
        
        Args:
            query: Base SQLAlchemy query
            page: Page number (1-indexed)
            per_page: Items per page
            max_per_page: Maximum allowed items per page
            
        Returns:
            Paginated query
        """
        # Ensure per_page doesn't exceed maximum
        per_page = min(per_page, max_per_page)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        return query.limit(per_page).offset(offset)
    
    @staticmethod
    def apply_filters(
        query: Select[T],
        filters: Dict[str, Any],
        model: Type[T]
    ) -> Select[T]:
        """
        Apply dynamic filters to query
        
        Args:
            query: Base SQLAlchemy query
            filters: Dictionary of field names and values
            model: SQLAlchemy model class
            
        Returns:
            Filtered query
        """
        conditions = []
        
        for field, value in filters.items():
            if hasattr(model, field):
                column = getattr(model, field)
                
                if isinstance(value, list):
                    # IN clause for lists
                    conditions.append(column.in_(value))
                elif isinstance(value, dict):
                    # Handle special operators
                    operator = value.get("operator", "eq")
                    val = value.get("value")
                    
                    if operator == "gt":
                        conditions.append(column > val)
                    elif operator == "gte":
                        conditions.append(column >= val)
                    elif operator == "lt":
                        conditions.append(column < val)
                    elif operator == "lte":
                        conditions.append(column <= val)
                    elif operator == "like":
                        conditions.append(column.like(f"%{val}%"))
                    elif operator == "ilike":
                        conditions.append(column.ilike(f"%{val}%"))
                    elif operator == "between":
                        conditions.append(column.between(val[0], val[1]))
                else:
                    # Simple equality
                    conditions.append(column == value)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    @staticmethod
    def apply_sorting(
        query: Select[T],
        sort_by: str,
        sort_order: str = "asc",
        model: Type[T] = None
    ) -> Select[T]:
        """
        Apply sorting to query
        
        Args:
            query: Base SQLAlchemy query
            sort_by: Field name to sort by
            sort_order: Sort order ('asc' or 'desc')
            model: SQLAlchemy model class
            
        Returns:
            Sorted query
        """
        if model and hasattr(model, sort_by):
            column = getattr(model, sort_by)
            
            if sort_order.lower() == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        
        return query
    
    @staticmethod
    async def get_query_statistics(
        db: AsyncSession,
        query: Select[T]
    ) -> Dict[str, Any]:
        """
        Get statistics about a query without executing it fully
        
        Args:
            db: Database session
            query: Query to analyze
            
        Returns:
            Dictionary with query statistics
        """
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await db.scalar(count_query)
        
        # Get query plan (PostgreSQL specific)
        explain_query = f"EXPLAIN (ANALYZE FALSE, FORMAT JSON) {query}"
        result = await db.execute(explain_query)
        query_plan = result.scalar()
        
        return {
            "total_count": total_count,
            "query_plan": query_plan,
            "estimated_cost": query_plan[0]["Plan"]["Total Cost"] if query_plan else None
        }
    
    @staticmethod
    def optimize_bulk_insert(
        objects: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> List[List[Dict[str, Any]]]:
        """
        Split bulk insert data into optimized batches
        
        Args:
            objects: List of objects to insert
            batch_size: Size of each batch
            
        Returns:
            List of batches
        """
        return [
            objects[i:i + batch_size]
            for i in range(0, len(objects), batch_size)
        ]
    
    @staticmethod
    def build_efficient_count_query(
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None
    ) -> Select:
        """
        Build an efficient count query
        
        Args:
            model: SQLAlchemy model class
            filters: Optional filters to apply
            
        Returns:
            Optimized count query
        """
        query = select(func.count(model.id))
        
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(model, field):
                    column = getattr(model, field)
                    conditions.append(column == value)
            
            if conditions:
                query = query.where(and_(*conditions))
        
        return query
    
    @staticmethod
    def optimize_exists_query(
        model: Type[T],
        **kwargs
    ) -> Select:
        """
        Build an optimized EXISTS query
        
        Args:
            model: SQLAlchemy model class
            **kwargs: Field conditions
            
        Returns:
            Optimized exists query
        """
        conditions = []
        for field, value in kwargs.items():
            if hasattr(model, field):
                column = getattr(model, field)
                conditions.append(column == value)
        
        return select(
            select(1)
            .select_from(model)
            .where(and_(*conditions))
            .exists()
        )


class QueryAnalyzer:
    """Analyze query performance and suggest optimizations"""
    
    @staticmethod
    async def analyze_slow_queries(
        db: AsyncSession,
        threshold_ms: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get slow queries from PostgreSQL
        
        Args:
            db: Database session
            threshold_ms: Threshold in milliseconds
            
        Returns:
            List of slow queries with details
        """
        query = """
        SELECT 
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            stddev_exec_time,
            rows
        FROM pg_stat_statements
        WHERE mean_exec_time > :threshold
        ORDER BY mean_exec_time DESC
        LIMIT 20
        """
        
        result = await db.execute(query, {"threshold": threshold_ms})
        
        return [
            {
                "query": row.query,
                "calls": row.calls,
                "total_time_ms": row.total_exec_time,
                "mean_time_ms": row.mean_exec_time,
                "stddev_time_ms": row.stddev_exec_time,
                "rows": row.rows
            }
            for row in result
        ]
    
    @staticmethod
    async def get_missing_indexes(
        db: AsyncSession,
        min_scans: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Suggest missing indexes based on query patterns
        
        Args:
            db: Database session
            min_scans: Minimum number of sequential scans
            
        Returns:
            List of suggested indexes
        """
        query = """
        SELECT 
            schemaname,
            tablename,
            attname,
            n_tup_ins + n_tup_upd + n_tup_del as write_activity,
            seq_scan,
            seq_tup_read
        FROM pg_stat_user_tables
        JOIN pg_attribute ON (attrelid = (schemaname||'.'||tablename)::regclass)
        WHERE seq_scan > :min_scans
        AND attnum > 0
        ORDER BY seq_tup_read DESC
        """
        
        result = await db.execute(query, {"min_scans": min_scans})
        
        return [
            {
                "schema": row.schemaname,
                "table": row.tablename,
                "column": row.attname,
                "write_activity": row.write_activity,
                "seq_scans": row.seq_scan,
                "rows_read": row.seq_tup_read,
                "suggested_index": f"CREATE INDEX idx_{row.tablename}_{row.attname} ON {row.schemaname}.{row.tablename}({row.attname})"
            }
            for row in result
        ]
    
    @staticmethod
    async def get_index_usage(
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Get index usage statistics
        
        Args:
            db: Database session
            
        Returns:
            List of index usage statistics
        """
        query = """
        SELECT 
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size
        FROM pg_stat_user_indexes
        ORDER BY idx_scan DESC
        """
        
        result = await db.execute(query)
        
        return [
            {
                "schema": row.schemaname,
                "table": row.tablename,
                "index": row.indexname,
                "scans": row.idx_scan,
                "tuples_read": row.idx_tup_read,
                "tuples_fetched": row.idx_tup_fetch,
                "size": row.index_size
            }
            for row in result
        ]