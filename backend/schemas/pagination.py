"""Pagination schemas for API responses."""

from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field, computed_field
from math import ceil

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""
    
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    
    @computed_field
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int = 1,
        limit: int = 20
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = ceil(total / limit) if limit > 0 else 0
        
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


class SortParams(BaseModel):
    """Query parameters for sorting."""
    
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="Sort order")
    
    @property
    def is_ascending(self) -> bool:
        """Check if sort order is ascending."""
        return self.sort_order == "asc"


class FilterParams(BaseModel):
    """Base class for filter parameters."""
    
    search: Optional[str] = Field(None, description="Search term")
    
    def to_filters(self) -> dict:
        """Convert to filter dictionary."""
        filters = {}
        if self.search:
            filters["search"] = self.search
        return filters


class DateRangeFilter(BaseModel):
    """Date range filter parameters."""
    
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")


class PaginationMetadata(BaseModel):
    """Metadata for pagination in responses."""
    
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total pages")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")
    next_page: Optional[int] = Field(None, description="Next page number")
    prev_page: Optional[int] = Field(None, description="Previous page number")
    
    @classmethod
    def create(cls, total: int, page: int, limit: int) -> "PaginationMetadata":
        """Create pagination metadata."""
        pages = ceil(total / limit) if limit > 0 else 0
        has_next = page < pages
        has_prev = page > 1
        
        return cls(
            total=total,
            page=page,
            per_page=limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=page + 1 if has_next else None,
            prev_page=page - 1 if has_prev else None
        )