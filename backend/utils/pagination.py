"""Pagination utilities for database queries."""

from typing import TypeVar, Generic, List, Optional, Type, Tuple
from sqlalchemy import select, func, Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query
from fastapi import Query as FastAPIQuery

from schemas.pagination import PaginatedResponse, PaginationParams


T = TypeVar("T")


class Paginator(Generic[T]):
    """Generic paginator for SQLAlchemy queries."""
    
    def __init__(
        self,
        db: AsyncSession,
        model: Type[T],
        query: Optional[Select] = None
    ):
        self.db = db
        self.model = model
        self.query = query or select(model)
    
    async def paginate(
        self,
        page: int = 1,
        limit: int = 20,
        filters: Optional[dict] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True
    ) -> PaginatedResponse[T]:
        """
        Paginate a query.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            filters: Additional filters to apply
            order_by: Field to order by
            order_desc: Whether to order descending
            
        Returns:
            PaginatedResponse with items and metadata
        """
        # Apply filters if provided
        query = self.query
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_field.desc())
            else:
                query = query.order_by(order_field.asc())
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return PaginatedResponse.create(
            items=items,
            total=total,
            page=page,
            limit=limit
        )


def paginate_params(
    page: int = FastAPIQuery(1, ge=1, description="Page number"),
    limit: int = FastAPIQuery(20, ge=1, le=100, description="Items per page")
) -> PaginationParams:
    """FastAPI dependency for pagination parameters."""
    return PaginationParams(page=page, limit=limit)


async def paginate_query(
    query: Select,
    db: AsyncSession,
    page: int = 1,
    limit: int = 20
) -> Tuple[List[T], int]:
    """
    Paginate a SQLAlchemy query.
    
    Returns:
        Tuple of (items, total_count)
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * limit
    paginated_query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(paginated_query)
    items = result.scalars().all()
    
    return items, total