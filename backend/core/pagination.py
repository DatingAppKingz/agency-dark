"""
Simplified pagination utilities for API endpoints
"""
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from fastapi import Query

ModelType = TypeVar("ModelType", bound=BaseModel)


class PaginationParams(BaseModel):
    """Standard pagination parameters for API endpoints"""
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for query"""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit for query"""
        return self.per_page


class PaginationMeta(BaseModel):
    """Metadata for paginated responses"""
    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[ModelType]):
    """Generic paginated response model"""
    items: List[ModelType]
    meta: PaginationMeta
    
    class Config:
        arbitrary_types_allowed = True


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page")
) -> PaginationParams:
    """Dependency to get pagination parameters from query params"""
    return PaginationParams(page=page, per_page=per_page)


async def paginate(
    db: AsyncSession,
    query: Select,
    params: PaginationParams,
    response_model: Optional[ModelType] = None
) -> PaginatedResponse:
    """
    Apply pagination to a query and return paginated response
    
    Args:
        db: Database session
        query: SQLAlchemy query
        params: Pagination parameters
        response_model: Optional pydantic model to transform results
        
    Returns:
        PaginatedResponse with items and metadata
    """
    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Calculate pages
    pages = (total + params.per_page - 1) // params.per_page if total > 0 else 0
    
    # Apply pagination
    paginated_query = query.offset(params.offset).limit(params.limit)
    result = await db.execute(paginated_query)
    items = result.scalars().all()
    
    # Transform items if response model provided
    if response_model:
        items = [response_model.from_orm(item) for item in items]
    
    # Create metadata
    meta = PaginationMeta(
        page=params.page,
        per_page=params.per_page,
        total=total,
        pages=pages,
        has_next=params.page < pages,
        has_prev=params.page > 1
    )
    
    return PaginatedResponse(items=items, meta=meta)


# Backwards compatibility aliases
PageParams = PaginationParams
PageMeta = PaginationMeta