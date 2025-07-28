"""
Advanced pagination utilities for lazy loading and performance
"""
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from dataclasses import dataclass, asdict
from math import ceil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from pydantic import BaseModel, Field

from core.database import Base
from core.performance.cache_manager import cache_manager, CacheKeyBuilder

T = TypeVar("T", bound=Base)
ModelType = TypeVar("ModelType", bound=BaseModel)


@dataclass
class PaginationParams:
    """Pagination parameters"""
    page: int = 1
    per_page: int = 20
    max_per_page: int = 100
    
    def __post_init__(self):
        # Validate parameters
        self.page = max(1, self.page)
        self.per_page = min(max(1, self.per_page), self.max_per_page)
    
    @property
    def offset(self) -> int:
        """Calculate offset for query"""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit for query"""
        return self.per_page


@dataclass
class PaginationMetadata:
    """Pagination metadata for responses"""
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None
    
    @classmethod
    def from_params(
        cls,
        params: PaginationParams,
        total: int
    ) -> "PaginationMetadata":
        """Create metadata from parameters and total count"""
        total_pages = ceil(total / params.per_page) if total > 0 else 0
        has_next = params.page < total_pages
        has_prev = params.page > 1
        
        return cls(
            page=params.page,
            per_page=params.per_page,
            total=total,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=params.page + 1 if has_next else None,
            prev_page=params.page - 1 if has_prev else None
        )


class PaginatedResponse(BaseModel, Generic[ModelType]):
    """Generic paginated response model"""
    items: List[ModelType]
    metadata: Dict[str, Any]
    links: Optional[Dict[str, Optional[str]]] = None
    
    class Config:
        arbitrary_types_allowed = True


class CursorPaginationParams:
    """Parameters for cursor-based pagination"""
    
    def __init__(
        self,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: str = "next"
    ):
        self.cursor = cursor
        self.limit = min(limit, 100)
        self.direction = direction
    
    def decode_cursor(self) -> Optional[Any]:
        """Decode cursor value"""
        if not self.cursor:
            return None
        
        import base64
        import json
        
        try:
            decoded = base64.b64decode(self.cursor).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            return None
    
    @staticmethod
    def encode_cursor(value: Any) -> str:
        """Encode cursor value"""
        import base64
        import json
        
        json_str = json.dumps(value)
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')


class PaginationHelper:
    """Helper class for implementing various pagination strategies"""
    
    @staticmethod
    async def paginate(
        db: AsyncSession,
        query: Select[T],
        params: PaginationParams,
        cache_key: Optional[str] = None,
        cache_ttl: int = 300
    ) -> PaginatedResponse:
        """
        Standard offset-based pagination
        
        Args:
            db: Database session
            query: Base query
            params: Pagination parameters
            cache_key: Optional cache key
            cache_ttl: Cache TTL in seconds
            
        Returns:
            Paginated response
        """
        # Check cache
        if cache_key:
            cached = await cache_manager.get(cache_key)
            if cached:
                return PaginatedResponse(**cached)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)
        
        # Apply pagination
        paginated_query = query.limit(params.limit).offset(params.offset)
        result = await db.execute(paginated_query)
        items = result.scalars().all()
        
        # Create metadata
        metadata = PaginationMetadata.from_params(params, total)
        
        # Create response
        response = PaginatedResponse(
            items=items,
            metadata=asdict(metadata)
        )
        
        # Cache response
        if cache_key:
            await cache_manager.set(
                cache_key,
                response.dict(),
                cache_ttl
            )
        
        return response
    
    @staticmethod
    async def cursor_paginate(
        db: AsyncSession,
        query: Select[T],
        params: CursorPaginationParams,
        order_column: Any,
        unique_column: Any = None
    ) -> Dict[str, Any]:
        """
        Cursor-based pagination for large datasets
        
        Args:
            db: Database session
            query: Base query
            params: Cursor pagination parameters
            order_column: Column to order by
            unique_column: Unique column for stable ordering
            
        Returns:
            Paginated response with cursors
        """
        # Decode cursor
        cursor_value = params.decode_cursor()
        
        # Apply cursor filter
        if cursor_value:
            if params.direction == "next":
                query = query.where(order_column > cursor_value)
            else:
                query = query.where(order_column < cursor_value)
                query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
        
        # Add unique column for stable ordering
        if unique_column is not None:
            query = query.order_by(unique_column)
        
        # Fetch one extra item to determine if there are more pages
        query = query.limit(params.limit + 1)
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Check if there are more items
        has_more = len(items) > params.limit
        if has_more:
            items = items[:-1]
        
        # Generate cursors
        next_cursor = None
        prev_cursor = None
        
        if items:
            if has_more:
                last_item = items[-1]
                next_cursor = CursorPaginationParams.encode_cursor(
                    getattr(last_item, order_column.key)
                )
            
            first_item = items[0]
            prev_cursor = CursorPaginationParams.encode_cursor(
                getattr(first_item, order_column.key)
            )
        
        return {
            "items": items,
            "cursors": {
                "next": next_cursor,
                "prev": prev_cursor if cursor_value else None
            },
            "has_more": has_more
        }
    
    @staticmethod
    async def keyset_paginate(
        db: AsyncSession,
        query: Select[T],
        last_id: Optional[int] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Keyset pagination for best performance
        
        Args:
            db: Database session
            query: Base query
            last_id: Last ID from previous page
            limit: Number of items per page
            
        Returns:
            Paginated response
        """
        # Apply keyset filter
        if last_id:
            # Assume we're ordering by ID
            query = query.where(T.id > last_id)
        
        # Order by ID and limit
        query = query.order_by(T.id).limit(limit + 1)
        
        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Check if there are more items
        has_more = len(items) > limit
        if has_more:
            items = items[:-1]
        
        # Get next last_id
        next_last_id = items[-1].id if items else None
        
        return {
            "items": items,
            "pagination": {
                "last_id": next_last_id,
                "has_more": has_more,
                "limit": limit
            }
        }
    
    @staticmethod
    async def infinite_scroll_paginate(
        db: AsyncSession,
        query: Select[T],
        offset: int = 0,
        limit: int = 20,
        total_limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Pagination for infinite scroll interfaces
        
        Args:
            db: Database session
            query: Base query
            offset: Current offset
            limit: Items to load
            total_limit: Maximum items to allow
            
        Returns:
            Response optimized for infinite scroll
        """
        # Ensure we don't exceed total limit
        if offset >= total_limit:
            return {
                "items": [],
                "has_more": False,
                "next_offset": None
            }
        
        # Adjust limit if needed
        limit = min(limit, total_limit - offset)
        
        # Apply pagination
        query = query.limit(limit + 1).offset(offset)
        
        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Check if there are more items
        has_more = len(items) > limit and (offset + limit) < total_limit
        if len(items) > limit:
            items = items[:-1]
        
        return {
            "items": items,
            "has_more": has_more,
            "next_offset": offset + len(items) if has_more else None,
            "loaded": offset + len(items),
            "total_limit": total_limit
        }


class LazyLoadHelper:
    """Helper for implementing lazy loading patterns"""
    
    @staticmethod
    def create_viewport_config(
        initial_items: int = 10,
        buffer_items: int = 5,
        viewport_height: int = 800,
        item_height: int = 100
    ) -> Dict[str, Any]:
        """
        Create configuration for viewport-based lazy loading
        
        Args:
            initial_items: Number of items to load initially
            buffer_items: Extra items to load outside viewport
            viewport_height: Height of viewport in pixels
            item_height: Average height of items in pixels
            
        Returns:
            Viewport configuration
        """
        visible_items = viewport_height // item_height
        
        return {
            "initial_load": initial_items,
            "visible_items": visible_items,
            "buffer_size": buffer_items,
            "load_threshold": visible_items + buffer_items,
            "item_height": item_height,
            "viewport_height": viewport_height
        }
    
    @staticmethod
    def create_intersection_observer_config(
        root_margin: str = "200px",
        threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Create configuration for Intersection Observer API
        
        Args:
            root_margin: Margin around root for triggering
            threshold: Visibility threshold for triggering
            
        Returns:
            Intersection Observer configuration
        """
        return {
            "rootMargin": root_margin,
            "threshold": threshold,
            "strategy": "intersection-observer"
        }
    
    @staticmethod
    async def get_progressive_data(
        db: AsyncSession,
        query: Select[T],
        stages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Load data progressively in stages
        
        Args:
            db: Database session
            query: Base query
            stages: List of loading stages with limits
            
        Returns:
            Progressive loading results
        """
        results = []
        loaded_ids = set()
        
        for stage in stages:
            limit = stage.get("limit", 10)
            delay = stage.get("delay", 0)
            priority = stage.get("priority", "normal")
            
            # Filter out already loaded items
            stage_query = query
            if loaded_ids:
                stage_query = stage_query.where(~T.id.in_(loaded_ids))
            
            # Apply stage-specific ordering
            if priority == "high":
                # Load most important items first
                stage_query = stage_query.order_by(T.created_at.desc())
            
            # Limit results
            stage_query = stage_query.limit(limit)
            
            # Execute query
            result = await db.execute(stage_query)
            items = result.scalars().all()
            
            # Track loaded IDs
            loaded_ids.update(item.id for item in items)
            
            results.append({
                "stage": stage.get("name", f"stage_{len(results) + 1}"),
                "items": items,
                "count": len(items),
                "delay": delay
            })
        
        return results