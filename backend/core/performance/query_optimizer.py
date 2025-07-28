"""
Query optimization utilities for database performance
"""
from typing import Any, Dict, List, Optional, Type, TypeVar, Tuple
from datetime import datetime
import hashlib
import json
from sqlalchemy import and_, func, select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, selectinload, joinedload, contains_eager, subqueryload, lazyload
from sqlalchemy.sql import Select, ClauseElement
from sqlalchemy.orm.interfaces import StrategizedProperty

from core.database import Base
from core.redis import redis_client
from core.logging import get_logger

T = TypeVar("T", bound=Base)
logger = get_logger(__name__)


class QueryOptimizer:
    """Optimize database queries for better performance with advanced caching and analysis"""
    
    def __init__(self):
        self._query_cache = {}
        self._index_cache = {}
        self._cardinality_cache = {}
        
    async def optimize_query(
        self,
        query: Select[T],
        model: Type[T],
        relationships: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> Tuple[Select[T], Dict[str, Any]]:
        """
        Comprehensively optimize a query
        
        Returns:
            Tuple of (optimized_query, optimization_report)
        """
        report = {
            "optimizations": [],
            "warnings": [],
            "estimated_improvement": 0
        }
        
        # Generate cache key
        cache_key = self._generate_query_cache_key(query, model, relationships, filters)
        
        # Check cache
        if cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            if (datetime.utcnow() - cached["timestamp"]).seconds < 300:  # 5 min cache
                report["optimizations"].append("Using cached optimization plan")
                return cached["query"], cached["report"]
        
        # Apply optimizations
        if relationships:
            query = await self._apply_smart_eager_loading(
                query, model, relationships, session, report
            )
            
        if filters:
            query = self._apply_optimized_filters(query, model, filters, report)
            
        if session:
            query = await self._add_index_hints(query, model, filters, session, report)
            
        # Cache the result
        self._query_cache[cache_key] = {
            "query": query,
            "report": report,
            "timestamp": datetime.utcnow()
        }
        
        return query, report
    
    def _generate_query_cache_key(
        self,
        query: Select[T],
        model: Type[T],
        relationships: Optional[List[str]],
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Generate a cache key for the query pattern"""
        key_parts = [
            model.__tablename__,
            str(relationships or []),
            str(sorted(filters.keys()) if filters else [])
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    async def _apply_smart_eager_loading(
        self,
        query: Select[T],
        model: Type[T],
        relationships: List[str],
        session: Optional[AsyncSession],
        report: Dict[str, Any]
    ) -> Select[T]:
        """
        Apply intelligent eager loading based on relationship cardinality
        """
        for relationship in relationships:
            if "." in relationship:
                # Nested relationships - use subquery loading to avoid cartesian product
                query = query.options(subqueryload(relationship))
                report["optimizations"].append(f"Subquery loading for nested: {relationship}")
            else:
                # Determine best strategy
                if session:
                    cardinality = await self._estimate_cardinality(
                        session, model, relationship
                    )
                    
                    if cardinality > 100:
                        query = query.options(selectinload(relationship))
                        report["optimizations"].append(
                            f"SelectIn loading for high cardinality ({cardinality}): {relationship}"
                        )
                    elif cardinality > 10:
                        query = query.options(subqueryload(relationship))
                        report["optimizations"].append(
                            f"Subquery loading for medium cardinality ({cardinality}): {relationship}"
                        )
                    else:
                        query = query.options(joinedload(relationship))
                        report["optimizations"].append(
                            f"Join loading for low cardinality ({cardinality}): {relationship}"
                        )
                else:
                    # Default strategy without session
                    query = query.options(joinedload(relationship))
        
        return query
    
    async def _estimate_cardinality(
        self,
        session: AsyncSession,
        model: Type[T],
        relationship: str
    ) -> int:
        """Estimate the average cardinality of a relationship"""
        cache_key = f"{model.__tablename__}:{relationship}"
        
        if cache_key in self._cardinality_cache:
            return self._cardinality_cache[cache_key]
            
        # Sample cardinality
        try:
            rel_prop = getattr(model, relationship).property
            target_table = rel_prop.mapper.class_.__tablename__
            
            result = await session.execute(
                text(f"""
                    SELECT AVG(cnt) as avg_cardinality
                    FROM (
                        SELECT COUNT(*) as cnt
                        FROM {model.__tablename__} m
                        LEFT JOIN {target_table} r ON m.id = r.{model.__tablename__}_id
                        GROUP BY m.id
                        LIMIT 100
                    ) sample
                """)
            )
            cardinality = int(result.scalar() or 1)
            self._cardinality_cache[cache_key] = cardinality
            return cardinality
        except:
            return 10  # Default medium cardinality
    
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
    
    def _apply_optimized_filters(
        self,
        query: Select[T],
        model: Type[T],
        filters: Dict[str, Any],
        report: Dict[str, Any]
    ) -> Select[T]:
        """Apply filters with optimization hints"""
        conditions = []
        
        for field, value in filters.items():
            if not hasattr(model, field):
                report["warnings"].append(f"Unknown field: {field}")
                continue
                
            column = getattr(model, field)
            
            if isinstance(value, dict):
                # Complex filters
                op = value.get("operator", "eq")
                val = value.get("value")
                
                if op in ["gt", "gte", "lt", "lte"]:
                    # Range queries - suggest indexes
                    report["optimizations"].append(f"Range filter on {field}")
                    if op == "gt":
                        conditions.append(column > val)
                    elif op == "gte":
                        conditions.append(column >= val)
                    elif op == "lt":
                        conditions.append(column < val)
                    elif op == "lte":
                        conditions.append(column <= val)
                elif op in ["like", "ilike"]:
                    pattern = f"%{val}%"
                    if pattern.startswith("%"):
                        report["warnings"].append(
                            f"Leading wildcard on {field} prevents index usage"
                        )
                    conditions.append(
                        column.like(pattern) if op == "like" else column.ilike(pattern)
                    )
            elif isinstance(value, list):
                # Optimize large IN clauses
                if len(value) > 100:
                    report["warnings"].append(
                        f"Large IN clause on {field} ({len(value)} items)"
                    )
                if value:
                    conditions.append(column.in_(value))
            else:
                conditions.append(column == value)
                
        if conditions:
            query = query.where(and_(*conditions))
            
        return query
    
    async def _add_index_hints(
        self,
        query: Select[T],
        model: Type[T],
        filters: Optional[Dict[str, Any]],
        session: AsyncSession,
        report: Dict[str, Any]
    ) -> Select[T]:
        """Add index hints based on available indexes"""
        # Get table indexes
        indexes = await self._get_table_indexes(session, model.__tablename__)
        
        if indexes:
            # Find best matching index
            filter_columns = list(filters.keys()) if filters else []
            best_index = self._find_best_index(indexes, filter_columns)
            
            if best_index:
                report["optimizations"].append(f"Using index: {best_index['name']}")
                # PostgreSQL-specific index hint
                query = query.execution_options(
                    postgresql_use_index=best_index["name"]
                )
                
        return query
    
    async def _get_table_indexes(
        self,
        session: AsyncSession,
        table_name: str
    ) -> List[Dict[str, Any]]:
        """Get indexes for a table"""
        cache_key = f"indexes:{table_name}"
        
        if cache_key in self._index_cache:
            return self._index_cache[cache_key]
            
        try:
            result = await session.execute(
                text("""
                    SELECT 
                        i.indexname,
                        i.indexdef,
                        array_agg(a.attname) as columns
                    FROM pg_indexes i
                    JOIN pg_class c ON c.relname = i.indexname
                    JOIN pg_index ix ON ix.indexrelid = c.oid
                    JOIN pg_attribute a ON a.attrelid = ix.indrelid 
                        AND a.attnum = ANY(ix.indkey)
                    WHERE i.tablename = :table_name
                    GROUP BY i.indexname, i.indexdef
                """),
                {"table_name": table_name}
            )
            
            indexes = [
                {
                    "name": row.indexname,
                    "columns": list(row.columns),
                    "definition": row.indexdef
                }
                for row in result
            ]
            
            self._index_cache[cache_key] = indexes
            return indexes
        except:
            return []
    
    def _find_best_index(
        self,
        indexes: List[Dict[str, Any]],
        filter_columns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching index for given columns"""
        best_index = None
        best_score = 0
        
        for index in indexes:
            score = 0
            index_columns = index.get("columns", [])
            
            # Score based on column matches
            for i, col in enumerate(filter_columns):
                if col in index_columns:
                    # Higher score for earlier positions
                    position = index_columns.index(col)
                    score += (10 - position) if position < 10 else 1
                    
            if score > best_score:
                best_score = score
                best_index = index
                
        return best_index
    
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
    
    def __init__(self):
        self._pattern_cache = {}
        self._optimization_history = []
        
    async def analyze_slow_queries(
        self,
        db: AsyncSession,
        threshold_ms: int = 1000,
        include_suggestions: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get slow queries from PostgreSQL with optimization suggestions
        
        Args:
            db: Database session
            threshold_ms: Threshold in milliseconds
            include_suggestions: Whether to include optimization suggestions
            
        Returns:
            List of slow queries with details and suggestions
        """
        query = text("""
        SELECT 
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            stddev_exec_time,
            rows,
            100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
        FROM pg_stat_statements
        WHERE mean_exec_time > :threshold
        ORDER BY mean_exec_time DESC
        LIMIT 50
        """)
        
        result = await db.execute(query, {"threshold": threshold_ms})
        
        slow_queries = []
        for row in result:
            query_info = {
                "query": self._normalize_query(row.query),
                "calls": row.calls,
                "total_time_ms": row.total_exec_time,
                "mean_time_ms": row.mean_exec_time,
                "stddev_time_ms": row.stddev_exec_time,
                "rows": row.rows,
                "cache_hit_rate": row.hit_percent or 0,
                "avg_rows_per_call": row.rows / row.calls if row.calls > 0 else 0
            }
            
            if include_suggestions:
                query_info["suggestions"] = self._generate_optimization_suggestions(
                    row.query,
                    row.mean_exec_time,
                    row.hit_percent or 0,
                    query_info["avg_rows_per_call"]
                )
                
            slow_queries.append(query_info)
            
        # Cache patterns for future analysis
        self._update_pattern_cache(slow_queries)
        
        return slow_queries
        
    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching"""
        import re
        
        # Replace specific values with placeholders
        query = re.sub(r"'[^']*'", "'?'", query)  # String literals
        query = re.sub(r"\b\d+\b", "?", query)    # Numbers
        query = re.sub(r"\s+", " ", query)        # Whitespace
        
        return query.strip()
        
    def _generate_optimization_suggestions(
        self,
        query: str,
        mean_time_ms: float,
        cache_hit_rate: float,
        avg_rows: float
    ) -> List[str]:
        """Generate specific optimization suggestions for a query"""
        suggestions = []
        query_lower = query.lower()
        
        # Check for missing indexes
        if "seq scan" in query_lower or cache_hit_rate < 90:
            suggestions.append("Consider adding indexes on frequently filtered columns")
            
        # Check for SELECT *
        if "select *" in query_lower:
            suggestions.append("Avoid SELECT *, specify only needed columns")
            
        # Check for missing WHERE
        if "where" not in query_lower and any(
            keyword in query_lower for keyword in ["update", "delete"]
        ):
            suggestions.append("Missing WHERE clause - this affects all rows")
            
        # Check for NOT IN
        if "not in" in query_lower:
            suggestions.append("Replace NOT IN with NOT EXISTS for better performance")
            
        # Check for large result sets
        if avg_rows > 1000 and "limit" not in query_lower:
            suggestions.append("Add LIMIT clause or implement pagination")
            
        # Check for LIKE with wildcards
        if "like '%" in query_lower:
            suggestions.append("Leading wildcard prevents index usage, consider full-text search")
            
        # Check for OR conditions
        if " or " in query_lower and mean_time_ms > 100:
            suggestions.append("OR conditions may prevent index usage, consider UNION")
            
        # Check for subqueries
        if query_lower.count("select") > 1:
            suggestions.append("Consider rewriting subqueries as JOINs")
            
        # Check for missing JOIN conditions
        if "join" in query_lower and "on" not in query_lower:
            suggestions.append("Ensure proper JOIN conditions to avoid cartesian products")
            
        return suggestions
        
    def _update_pattern_cache(self, queries: List[Dict[str, Any]]):
        """Update pattern cache with new query patterns"""
        for query_info in queries:
            pattern = query_info["query"]
            if pattern not in self._pattern_cache:
                self._pattern_cache[pattern] = {
                    "count": 0,
                    "total_time": 0,
                    "suggestions": query_info.get("suggestions", [])
                }
            
            self._pattern_cache[pattern]["count"] += query_info["calls"]
            self._pattern_cache[pattern]["total_time"] += query_info["total_time_ms"]
    
    async def get_missing_indexes(
        self,
        db: AsyncSession,
        min_scans: int = 1000,
        analyze_patterns: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Suggest missing indexes based on query patterns and table statistics
        
        Args:
            db: Database session
            min_scans: Minimum number of sequential scans
            analyze_patterns: Whether to analyze query patterns
            
        Returns:
            List of suggested indexes with priority scores
        """
        # Get tables with high sequential scan activity
        seq_scan_query = text("""
        SELECT 
            schemaname,
            tablename,
            seq_scan,
            seq_tup_read,
            n_live_tup,
            n_tup_ins + n_tup_upd + n_tup_del as write_activity,
            pg_size_pretty(pg_total_relation_size((schemaname||'.'||tablename)::regclass)) as table_size
        FROM pg_stat_user_tables
        WHERE seq_scan > :min_scans
            AND n_live_tup > 1000
        ORDER BY seq_tup_read DESC
        LIMIT 50
        """)
        
        result = await db.execute(seq_scan_query, {"min_scans": min_scans})
        
        suggestions = []
        for row in result:
            # Analyze which columns need indexes
            column_suggestions = await self._analyze_table_for_indexes(
                db, row.schemaname, row.tablename
            )
            
            for col_suggestion in column_suggestions:
                priority_score = self._calculate_index_priority(
                    row.seq_scan,
                    row.seq_tup_read,
                    row.n_live_tup,
                    row.write_activity
                )
                
                suggestions.append({
                    "schema": row.schemaname,
                    "table": row.tablename,
                    "column": col_suggestion["column"],
                    "index_type": col_suggestion["type"],
                    "seq_scans": row.seq_scan,
                    "rows_read": row.seq_tup_read,
                    "table_size": row.table_size,
                    "write_activity": row.write_activity,
                    "priority_score": priority_score,
                    "suggested_index": col_suggestion["create_statement"],
                    "estimated_improvement": col_suggestion.get("estimated_improvement", "High"),
                    "reason": col_suggestion["reason"]
                })
                
        # Sort by priority
        suggestions.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Analyze query patterns if enabled
        if analyze_patterns and self._pattern_cache:
            pattern_suggestions = self._suggest_indexes_from_patterns()
            suggestions.extend(pattern_suggestions)
            
        return suggestions[:20]  # Return top 20 suggestions
        
    async def _analyze_table_for_indexes(
        self,
        db: AsyncSession,
        schema: str,
        table: str
    ) -> List[Dict[str, Any]]:
        """Analyze a table to determine which columns need indexes"""
        suggestions = []
        
        # Check foreign key columns without indexes
        fk_query = text("""
        SELECT 
            a.attname as column_name,
            con.conname as constraint_name
        FROM pg_constraint con
        JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
        LEFT JOIN pg_index idx ON idx.indrelid = con.conrelid 
            AND a.attnum = ANY(idx.indkey)
        WHERE con.contype = 'f'
            AND con.conrelid = (:schema || '.' || :table)::regclass
            AND idx.indexrelid IS NULL
        """)
        
        fk_result = await db.execute(fk_query, {"schema": schema, "table": table})
        
        for row in fk_result:
            suggestions.append({
                "column": row.column_name,
                "type": "btree",
                "create_statement": f"CREATE INDEX idx_{table}_{row.column_name}_fk ON {schema}.{table}({row.column_name})",
                "reason": f"Foreign key without index: {row.constraint_name}",
                "estimated_improvement": "High"
            })
            
        # Analyze column statistics for frequently filtered columns
        stats_query = text("""
        SELECT 
            a.attname,
            s.n_distinct,
            s.correlation
        FROM pg_stats s
        JOIN pg_attribute a ON a.attname = s.attname
            AND a.attrelid = (s.schemaname || '.' || s.tablename)::regclass
        WHERE s.schemaname = :schema
            AND s.tablename = :table
            AND s.n_distinct > 10
            AND a.attnum > 0
            AND NOT EXISTS (
                SELECT 1 FROM pg_index i
                WHERE i.indrelid = a.attrelid
                    AND a.attnum = ANY(i.indkey)
            )
        ORDER BY s.n_distinct DESC
        """)
        
        stats_result = await db.execute(stats_query, {"schema": schema, "table": table})
        
        for row in stats_result:
            # Determine index type based on data characteristics
            if row.n_distinct > 1000:
                index_type = "btree"
            elif row.n_distinct > 100:
                index_type = "hash"
            else:
                index_type = "btree"
                
            suggestions.append({
                "column": row.attname,
                "type": index_type,
                "create_statement": f"CREATE INDEX idx_{table}_{row.attname} ON {schema}.{table} USING {index_type}({row.attname})",
                "reason": f"High cardinality column (distinct values: {row.n_distinct})",
                "estimated_improvement": "Medium"
            })
            
        return suggestions
        
    def _calculate_index_priority(
        self,
        seq_scans: int,
        rows_read: int,
        table_size: int,
        write_activity: int
    ) -> float:
        """Calculate priority score for index creation"""
        # Higher score = higher priority
        
        # Base score from sequential scan impact
        scan_impact = (rows_read / max(table_size, 1)) * seq_scans
        
        # Adjust for write activity (indexes slow down writes)
        write_penalty = 1.0 - (write_activity / (write_activity + rows_read))
        
        # Scale by table size (larger tables benefit more)
        size_factor = min(table_size / 10000, 10)  # Cap at 10x
        
        return scan_impact * write_penalty * size_factor
        
    def _suggest_indexes_from_patterns(self) -> List[Dict[str, Any]]:
        """Suggest indexes based on query patterns"""
        suggestions = []
        
        # Analyze cached query patterns
        for pattern, stats in self._pattern_cache.items():
            if stats["count"] > 100:  # Frequently executed
                # Extract table and column references
                # This is simplified - real implementation would use SQL parser
                if "where" in pattern.lower():
                    # Look for column references after WHERE
                    suggestions.append({
                        "pattern": pattern,
                        "execution_count": stats["count"],
                        "total_time": stats["total_time"],
                        "suggested_action": "Analyze WHERE clause columns for indexing",
                        "priority_score": stats["total_time"] / 1000
                    })
                    
        return suggestions
    
    async def get_index_usage(
        self,
        db: AsyncSession,
        include_unused: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive index usage statistics
        
        Args:
            db: Database session
            include_unused: Include unused indexes
            
        Returns:
            Dictionary with index usage analysis
        """
        # Get all index statistics
        usage_query = text("""
        SELECT 
            s.schemaname,
            s.tablename,
            s.indexname,
            s.idx_scan,
            s.idx_tup_read,
            s.idx_tup_fetch,
            pg_size_pretty(pg_relation_size(s.indexrelid)) as index_size,
            pg_relation_size(s.indexrelid) as size_bytes,
            i.indisunique,
            i.indisprimary
        FROM pg_stat_user_indexes s
        JOIN pg_index i ON s.indexrelid = i.indexrelid
        ORDER BY s.idx_scan DESC
        """)
        
        result = await db.execute(usage_query)
        
        indexes = []
        total_size = 0
        unused_count = 0
        unused_size = 0
        
        for row in result:
            index_info = {
                "schema": row.schemaname,
                "table": row.tablename,
                "index": row.indexname,
                "scans": row.idx_scan,
                "tuples_read": row.idx_tup_read,
                "tuples_fetched": row.idx_tup_fetch,
                "size": row.index_size,
                "size_bytes": row.size_bytes,
                "is_unique": row.indisunique,
                "is_primary": row.indisprimary,
                "efficiency": row.idx_tup_fetch / row.idx_scan if row.idx_scan > 0 else 0
            }
            
            total_size += row.size_bytes
            
            # Check if unused
            if row.idx_scan == 0 and not row.indisprimary and not row.indisunique:
                index_info["status"] = "unused"
                index_info["recommendation"] = "Consider dropping this index"
                unused_count += 1
                unused_size += row.size_bytes
            elif row.idx_scan < 100:
                index_info["status"] = "rarely_used"
                index_info["recommendation"] = "Monitor usage, may be a candidate for removal"
            else:
                index_info["status"] = "active"
                
            if include_unused or index_info["status"] != "unused":
                indexes.append(index_info)
                
        return {
            "indexes": indexes,
            "summary": {
                "total_indexes": len(indexes),
                "total_size": pg_size_pretty(total_size),
                "unused_indexes": unused_count,
                "unused_size": pg_size_pretty(unused_size),
                "potential_savings": f"{(unused_size / total_size * 100):.1f}%" if total_size > 0 else "0%"
            }
        }
        
    async def analyze_table_bloat(
        self,
        db: AsyncSession,
        min_bloat_ratio: float = 0.2
    ) -> List[Dict[str, Any]]:
        """Analyze table bloat and suggest vacuum operations"""
        bloat_query = text("""
        WITH constants AS (
            SELECT current_setting('block_size')::numeric AS bs, 23 AS hdr, 4 AS ma
        ),
        bloat_info AS (
            SELECT
                schemaname,
                tablename,
                cc.relpages,
                bs,
                CEIL((cc.reltuples*((datahdr+ma-
                    (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::float)) AS otta
            FROM (
                SELECT
                    schemaname,
                    tablename,
                    hdr,
                    ma,
                    bs,
                    SUM((1-null_frac)*avg_width) AS nullhdr2,
                    MAX(null_frac) AS maxfracsum,
                    hdr+(
                        SELECT 1+COUNT(*)/8
                        FROM pg_stats s2
                        WHERE null_frac<>0 AND s2.schemaname = s.schemaname AND s2.tablename = s.tablename
                    ) AS datahdr
                FROM pg_stats s, constants
                GROUP BY 1,2,3,4,5
            ) AS foo
            JOIN pg_class cc ON cc.relname = foo.tablename
            JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = foo.schemaname
        )
        SELECT
            schemaname,
            tablename,
            ROUND(100.0 * (1.0 - otta/relpages), 2) AS bloat_ratio,
            pg_size_pretty((bs*(relpages-otta))::bigint) AS bloat_size
        FROM bloat_info
        WHERE relpages > otta
            AND ROUND(100.0 * (1.0 - otta/relpages), 2) > :min_bloat
        ORDER BY bloat_ratio DESC
        """)
        
        result = await db.execute(bloat_query, {"min_bloat": min_bloat_ratio * 100})
        
        return [
            {
                "schema": row.schemaname,
                "table": row.tablename,
                "bloat_ratio": row.bloat_ratio,
                "bloat_size": row.bloat_size,
                "recommendation": "VACUUM FULL" if row.bloat_ratio > 50 else "VACUUM",
                "priority": "high" if row.bloat_ratio > 40 else "medium"
            }
            for row in result
        ]


def pg_size_pretty(size_bytes: int) -> str:
    """Format bytes as human-readable string"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# Global instances
query_optimizer = QueryOptimizer()
query_analyzer = QueryAnalyzer()