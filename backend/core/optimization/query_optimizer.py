"""
Database query optimization utilities.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import text, inspect, select, func
from sqlalchemy.orm import Query, Session, selectinload, joinedload, subqueryload
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging
from functools import wraps
from collections import defaultdict

from core.database import get_db_engine
from core.logging import get_logger

logger = get_logger(__name__)


class QueryOptimizer:
    """Optimize database queries for performance."""
    
    def __init__(self):
        self.slow_query_threshold = 0.1  # 100ms
        self.query_stats = defaultdict(lambda: {"count": 0, "total_time": 0, "max_time": 0})
        self.index_suggestions = defaultdict(set)
    
    async def analyze_query_plan(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze query execution plan."""
        engine = get_db_engine()
        
        async with engine.connect() as conn:
            # Get query plan
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS) {query}"
            result = await conn.execute(text(explain_query), params or {})
            plan = [row[0] for row in result]
            
            # Parse plan for insights
            analysis = {
                "plan": plan,
                "issues": [],
                "suggestions": [],
                "estimated_cost": self._extract_cost(plan),
                "actual_time": self._extract_time(plan),
                "index_scans": self._count_index_scans(plan),
                "seq_scans": self._count_seq_scans(plan),
            }
            
            # Identify issues
            if analysis["seq_scans"] > 0:
                analysis["issues"].append("Sequential scan detected")
                analysis["suggestions"].append("Consider adding indexes")
            
            if analysis["actual_time"] > 1000:  # 1 second
                analysis["issues"].append("Slow query detected")
                analysis["suggestions"].append("Review query structure and indexes")
            
            return analysis
    
    def _extract_cost(self, plan: List[str]) -> float:
        """Extract estimated cost from query plan."""
        for line in plan:
            if "cost=" in line:
                parts = line.split("cost=")[1].split("..")
                if len(parts) >= 2:
                    return float(parts[1].split()[0])
        return 0.0
    
    def _extract_time(self, plan: List[str]) -> float:
        """Extract actual execution time from query plan."""
        for line in plan:
            if "actual time=" in line:
                parts = line.split("actual time=")[1].split("..")
                if len(parts) >= 2:
                    return float(parts[1].split()[0])
        return 0.0
    
    def _count_index_scans(self, plan: List[str]) -> int:
        """Count index scans in query plan."""
        return sum(1 for line in plan if "Index Scan" in line or "Index Only Scan" in line)
    
    def _count_seq_scans(self, plan: List[str]) -> int:
        """Count sequential scans in query plan."""
        return sum(1 for line in plan if "Seq Scan" in line)
    
    async def suggest_indexes(self, table_name: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """Suggest indexes based on query patterns."""
        suggestions = []
        
        # Analyze frequently used WHERE clauses
        query = text("""
            SELECT 
                attname as column_name,
                n_distinct,
                correlation
            FROM pg_stats
            WHERE tablename = :table_name
            AND n_distinct > 10
            AND correlation < 0.9
            ORDER BY n_distinct DESC
        """)
        
        result = await db.execute(query, {"table_name": table_name})
        
        for row in result:
            if row.column_name not in await self._get_indexed_columns(table_name, db):
                suggestions.append({
                    "table": table_name,
                    "column": row.column_name,
                    "reason": f"High cardinality ({row.n_distinct}) with low correlation ({row.correlation})",
                    "type": "btree",
                    "sql": f"CREATE INDEX idx_{table_name}_{row.column_name} ON {table_name}({row.column_name});"
                })
        
        return suggestions
    
    async def _get_indexed_columns(self, table_name: str, db: AsyncSession) -> Set[str]:
        """Get columns that already have indexes."""
        query = text("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            WHERE c.relname = :table_name
        """)
        
        result = await db.execute(query, {"table_name": table_name})
        return {row[0] for row in result}
    
    def optimize_orm_query(self, query: Query) -> Query:
        """Optimize SQLAlchemy ORM query."""
        # Add eager loading for relationships
        mapper = query.column_descriptions[0]['type']
        
        if hasattr(mapper, '__mapper__'):
            relationships = mapper.__mapper__.relationships
            
            for rel in relationships:
                if rel.lazy == 'select':
                    # Use joinedload for many-to-one or one-to-one
                    if rel.direction.name in ['MANYTOONE', 'ONETOONE']:
                        query = query.options(joinedload(rel.key))
                    # Use selectinload for one-to-many or many-to-many
                    else:
                        query = query.options(selectinload(rel.key))
        
        return query
    
    async def batch_operations(self, operations: List[Tuple[str, Dict]], db: AsyncSession) -> List[Any]:
        """Execute multiple operations in a batch."""
        results = []
        
        # Start transaction
        async with db.begin():
            for query, params in operations:
                result = await db.execute(text(query), params)
                results.append(result)
        
        return results


def optimize_query(threshold: float = 0.1):
    """Decorator to monitor and optimize queries."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Measure execution time
            execution_time = time.time() - start_time
            
            # Log slow queries
            if execution_time > threshold:
                logger.warning(
                    f"Slow query detected in {func.__name__}: {execution_time:.3f}s",
                    extra={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "threshold": threshold
                    }
                )
            
            return result
        
        return wrapper
    return decorator


class QueryBatcher:
    """Batch multiple queries for efficiency."""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.pending_queries = []
    
    def add_query(self, query: str, params: Optional[Dict] = None):
        """Add query to batch."""
        self.pending_queries.append((query, params or {}))
    
    async def execute_batch(self, db: AsyncSession) -> List[Any]:
        """Execute all pending queries."""
        if not self.pending_queries:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(self.pending_queries), self.batch_size):
            batch = self.pending_queries[i:i + self.batch_size]
            
            async with db.begin():
                for query, params in batch:
                    result = await db.execute(text(query), params)
                    results.append(result)
        
        # Clear pending queries
        self.pending_queries = []
        
        return results


# Query optimization hints
OPTIMIZATION_HINTS = {
    "n_plus_one": {
        "pattern": "Multiple SELECT statements for related objects",
        "solution": "Use joinedload() or selectinload() for eager loading",
        "example": "query.options(joinedload(Model.relationship))"
    },
    "missing_index": {
        "pattern": "Sequential scan on large table",
        "solution": "Add index on frequently queried columns",
        "example": "CREATE INDEX idx_table_column ON table(column)"
    },
    "large_offset": {
        "pattern": "OFFSET > 1000 in pagination",
        "solution": "Use cursor-based pagination",
        "example": "WHERE id > last_id ORDER BY id LIMIT 100"
    },
    "select_star": {
        "pattern": "SELECT * with large columns",
        "solution": "Select only required columns",
        "example": "SELECT id, name, email FROM users"
    },
    "missing_limit": {
        "pattern": "Query without LIMIT",
        "solution": "Add LIMIT to prevent loading too many rows",
        "example": "SELECT * FROM table LIMIT 100"
    }
}