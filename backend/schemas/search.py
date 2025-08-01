"""Search schemas for request/response validation."""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class SearchType(str, Enum):
    """Search type enumeration."""
    MODELS = "models"
    MESSAGES = "messages"
    MEDIA = "media"
    TRANSACTIONS = "transactions"
    USERS = "users"
    ALL = "all"


class SearchRequest(BaseModel):
    """Base search request."""
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters")
    size: int = Field(20, ge=1, le=100, description="Number of results to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class ModelSearchRequest(SearchRequest):
    """Model search request with specific filters."""
    platform: Optional[str] = Field(None, description="Platform filter")
    is_active: Optional[bool] = Field(None, description="Active status filter")
    min_revenue: Optional[float] = Field(None, ge=0, description="Minimum revenue")
    max_revenue: Optional[float] = Field(None, ge=0, description="Maximum revenue")
    min_fans: Optional[int] = Field(None, ge=0, description="Minimum fan count")
    max_fans: Optional[int] = Field(None, ge=0, description="Maximum fan count")
    sort_by: str = Field("relevance", description="Sort field: relevance, revenue, fans, recent")


class MessageSearchRequest(SearchRequest):
    """Message search request with specific filters."""
    model_id: Optional[str] = Field(None, description="Model ID filter")
    fan_id: Optional[str] = Field(None, description="Fan ID filter")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    has_media: Optional[bool] = Field(None, description="Has media attachment")
    sentiment: Optional[str] = Field(None, description="Sentiment filter: positive, negative, neutral")


class MediaSearchRequest(SearchRequest):
    """Media search request with specific filters."""
    media_type: Optional[str] = Field(None, description="Media type: image, video")
    tags: Optional[List[str]] = Field(None, description="Tag filters")
    uploaded_by: Optional[str] = Field(None, description="Uploader ID")
    is_nsfw: Optional[bool] = Field(None, description="NSFW filter")
    min_size: Optional[int] = Field(None, ge=0, description="Minimum file size in bytes")
    max_size: Optional[int] = Field(None, ge=0, description="Maximum file size in bytes")


class TransactionSearchRequest(SearchRequest):
    """Transaction search request with specific filters."""
    model_id: Optional[str] = Field(None, description="Model ID filter")
    transaction_type: Optional[str] = Field(None, description="Transaction type")
    status: Optional[str] = Field(None, description="Transaction status")
    min_amount: Optional[float] = Field(None, ge=0, description="Minimum amount")
    max_amount: Optional[float] = Field(None, ge=0, description="Maximum amount")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")


class SearchHit(BaseModel):
    """Individual search result."""
    id: str = Field(..., description="Document ID")
    score: float = Field(..., description="Relevance score")
    source: Dict[str, Any] = Field(..., description="Document data")
    highlight: Dict[str, List[str]] = Field(default_factory=dict, description="Highlighted snippets")


class SearchResultGroup(BaseModel):
    """Search results for a specific type."""
    total: int = Field(..., description="Total number of results")
    hits: List[SearchHit] = Field(..., description="Search results")
    aggregations: Optional[Dict[str, Any]] = Field(None, description="Faceted search aggregations")
    error: Optional[str] = Field(None, description="Error message if search failed")


class SearchResponse(BaseModel):
    """Combined search response."""
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total results across all types")
    results_by_type: Dict[str, Union[SearchResultGroup, Dict[str, Any]]] = Field(
        ..., description="Results grouped by type"
    )
    suggestions: Optional[List[str]] = Field(None, description="Search suggestions")


class SearchSuggestionResponse(BaseModel):
    """Search suggestion response."""
    query: str = Field(..., description="Original query")
    suggestions: List[str] = Field(..., description="Suggested completions")


class SavedSearchCreate(BaseModel):
    """Create saved search request."""
    name: str = Field(..., min_length=1, max_length=100, description="Search name")
    description: Optional[str] = Field(None, max_length=500, description="Search description")
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    search_type: SearchType = Field(..., description="Type of search")


class SavedSearchResponse(BaseModel):
    """Saved search response."""
    id: str = Field(..., description="Saved search ID")
    name: str = Field(..., description="Search name")
    description: Optional[str] = Field(None, description="Search description")
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    search_type: SearchType = Field(..., description="Type of search")
    user_id: str = Field(..., description="Owner user ID")
    agency_id: str = Field(..., description="Agency ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True