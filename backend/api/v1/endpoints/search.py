"""Advanced search endpoints using Elasticsearch."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
from core.rbac import check_permission
from services.search_service import SearchService
from models.user import User
from schemas.search import (
    SearchRequest,
    SearchResponse,
    ModelSearchRequest,
    MessageSearchRequest,
    MediaSearchRequest,
    TransactionSearchRequest,
    SearchSuggestionResponse,
    SavedSearchCreate,
    SavedSearchResponse
)
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/all", response_model=SearchResponse)
async def search_all(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Search across all content types.
    
    Searches in:
    - Models (username, display name, bio)
    - Messages (content)
    - Media (filename, title, description, tags)
    - Transactions (description)
    - Users (name, email)
    
    Returns combined results with facets for filtering.
    """
    # Check permission
    check_permission(current_user, "search", "read")
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Perform search
    results = await search_service.search_all(
        query=request.query,
        agency_id=str(current_user.agency_id),
        filters=request.filters,
        size=request.size,
        offset=request.offset
    )
    
    # Track search query in background
    background_tasks.add_task(
        search_service.save_search_query,
        str(current_user.id),
        str(current_user.agency_id),
        request.query,
        results["total_results"]
    )
    
    return SearchResponse(**results)


@router.post("/models", response_model=Dict[str, Any])
async def search_models(
    request: ModelSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search models with advanced filters.
    
    Searchable fields:
    - Username
    - Display name
    - Bio
    
    Filters:
    - Platform
    - Active status
    - Revenue range
    - Fan count range
    """
    # Check permission
    check_permission(current_user, "models", "read")
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Build filters
    filters = {}
    if request.platform:
        filters["platform"] = request.platform
    if request.is_active is not None:
        filters["is_active"] = request.is_active
    
    # Perform search
    results = await search_service.search_models(
        query=request.query,
        agency_id=str(current_user.agency_id),
        filters=filters,
        sort_by=request.sort_by,
        size=request.size,
        offset=request.offset
    )
    
    return results


@router.post("/messages", response_model=Dict[str, Any])
async def search_messages(
    request: MessageSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search messages with advanced filters.
    
    Searchable fields:
    - Message content
    
    Filters:
    - Model ID
    - Fan ID
    - Date range
    - Has media
    - Sentiment
    """
    # Check permission
    check_permission(current_user, "messages", "read")
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Perform search
    results = await search_service.search_messages(
        query=request.query,
        agency_id=str(current_user.agency_id),
        model_id=str(request.model_id) if request.model_id else None,
        fan_id=str(request.fan_id) if request.fan_id else None,
        date_from=request.date_from,
        date_to=request.date_to,
        has_media=request.has_media,
        sentiment=request.sentiment,
        size=request.size,
        offset=request.offset
    )
    
    return results


@router.post("/media", response_model=Dict[str, Any])
async def search_media(
    request: MediaSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search media files with filters.
    
    Searchable fields:
    - Filename
    - Title
    - Description
    - Tags
    
    Filters:
    - Media type
    - Tags
    - Uploaded by
    - NSFW status
    - File size range
    """
    # Check permission
    check_permission(current_user, "media", "read")
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Perform search
    results = await search_service.search_media(
        query=request.query,
        agency_id=str(current_user.agency_id),
        media_type=request.media_type,
        tags=request.tags,
        uploaded_by=str(request.uploaded_by) if request.uploaded_by else None,
        is_nsfw=request.is_nsfw,
        min_size=request.min_size,
        max_size=request.max_size,
        size=request.size,
        offset=request.offset
    )
    
    return results


@router.post("/transactions", response_model=Dict[str, Any])
async def search_transactions(
    request: TransactionSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search transactions with filters.
    
    Searchable fields:
    - Description
    
    Filters:
    - Model ID
    - Transaction type
    - Status
    - Amount range
    - Date range
    """
    # Check permission
    check_permission(current_user, "transactions", "read")
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Perform search
    results = await search_service.search_transactions(
        query=request.query,
        agency_id=str(current_user.agency_id),
        model_id=str(request.model_id) if request.model_id else None,
        transaction_type=request.transaction_type,
        status=request.status,
        min_amount=request.min_amount,
        max_amount=request.max_amount,
        date_from=request.date_from,
        date_to=request.date_to,
        size=request.size,
        offset=request.offset
    )
    
    return results


@router.get("/suggestions", response_model=SearchSuggestionResponse)
async def get_search_suggestions(
    query: str = Query(..., min_length=2),
    context: Optional[str] = Query(None, regex="^(models|messages|media|transactions)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get search suggestions based on partial query.
    
    Returns autocomplete suggestions based on:
    - Previous searches
    - Existing content
    - Popular searches
    """
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Get suggestions
    suggestions = await search_service.get_search_suggestions(query, context)
    
    return SearchSuggestionResponse(
        query=query,
        suggestions=suggestions
    )


@router.get("/popular", response_model=List[Dict[str, Any]])
async def get_popular_searches(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get popular searches for the agency."""
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Get popular searches
    popular = await search_service.get_popular_searches(
        agency_id=str(current_user.agency_id),
        limit=limit
    )
    
    return popular


@router.post("/saved", response_model=SavedSearchResponse)
async def save_search(
    search_data: SavedSearchCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save a search query for later use.
    
    Allows users to save complex searches with filters.
    """
    # Create saved search
    from models.saved_search import SavedSearch
    
    saved_search = SavedSearch(
        name=search_data.name,
        description=search_data.description,
        query=search_data.query,
        filters=search_data.filters,
        search_type=search_data.search_type,
        user_id=current_user.id,
        agency_id=current_user.agency_id
    )
    
    db.add(saved_search)
    await db.commit()
    await db.refresh(saved_search)
    
    return SavedSearchResponse.from_orm(saved_search)


@router.get("/saved", response_model=List[SavedSearchResponse])
async def list_saved_searches(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's saved searches."""
    from sqlalchemy import select
    from models.saved_search import SavedSearch
    
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.user_id == current_user.id
        ).order_by(SavedSearch.created_at.desc())
    )
    
    saved_searches = result.scalars().all()
    
    return [SavedSearchResponse.from_orm(s) for s in saved_searches]


@router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved search."""
    from models.saved_search import SavedSearch
    
    saved_search = await db.get(SavedSearch, search_id)
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    if saved_search.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete search you don't own"
        )
    
    await db.delete(saved_search)
    await db.commit()
    
    return {"message": "Saved search deleted successfully"}


@router.post("/reindex")
async def reindex_agency_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Reindex all agency data in Elasticsearch.
    
    Admin only endpoint to rebuild search indices.
    """
    # Check permission (admin only)
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Initialize search service
    search_service = SearchService(db)
    await search_service.initialize()
    
    # Start reindex in background
    background_tasks.add_task(
        search_service.reindex_agency_data,
        str(current_user.agency_id)
    )
    
    return {
        "message": "Reindexing started",
        "agency_id": str(current_user.agency_id)
    }