"""Advanced search service using Elasticsearch."""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.elasticsearch_client import get_elasticsearch_client
from core.logger import get_logger
from models.model import Model
from models.message import Message
from models.user import User
from models.media import Media
from models.transaction import Transaction

logger = get_logger(__name__)


class SearchService:
    """Service for advanced search functionality."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.es_client = None
    
    async def initialize(self):
        """Initialize search service."""
        self.es_client = await get_elasticsearch_client()
    
    async def search_all(
        self,
        query: str,
        agency_id: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search across all content types.
        
        Args:
            query: Search query
            agency_id: Agency ID for filtering
            filters: Additional filters
            size: Number of results per type
            offset: Pagination offset
        
        Returns:
            Combined search results from all indices
        """
        try:
            # Add agency filter
            all_filters = {"agency_id": agency_id}
            if filters:
                all_filters.update(filters)
            
            # Search in parallel across all indices
            import asyncio
            
            tasks = []
            indices = ['models', 'messages', 'users', 'media', 'transactions']
            
            for index in indices:
                task = self.es_client.search(
                    index_name=index,
                    query=query,
                    filters=all_filters,
                    size=size,
                    from_=offset
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            combined_results = {
                "query": query,
                "total_results": 0,
                "results_by_type": {}
            }
            
            for index, result in zip(indices, results):
                if isinstance(result, Exception):
                    logger.error(f"Search error in {index}: {result}")
                    combined_results["results_by_type"][index] = {
                        "error": str(result),
                        "hits": []
                    }
                else:
                    combined_results["results_by_type"][index] = result
                    combined_results["total_results"] += result.get("total", 0)
            
            # Get search suggestions if no results
            if combined_results["total_results"] == 0:
                suggestions = await self.es_client.suggest(query)
                combined_results["suggestions"] = suggestions
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Error in search_all: {e}")
            raise
    
    async def search_models(
        self,
        query: str,
        agency_id: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        size: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search models with advanced filters."""
        try:
            # Add agency filter
            search_filters = {"agency_id": agency_id}
            if filters:
                search_filters.update(filters)
            
            # Determine sort
            sort = None
            if sort_by == "revenue":
                sort = [{"stats.total_revenue": "desc"}]
            elif sort_by == "fans":
                sort = [{"stats.total_fans": "desc"}]
            elif sort_by == "recent":
                sort = [{"created_at": "desc"}]
            
            # Search
            results = await self.es_client.search(
                index_name='models',
                query=query,
                filters=search_filters,
                size=size,
                from_=offset,
                sort=sort
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching models: {e}")
            raise
    
    async def search_messages(
        self,
        query: str,
        agency_id: str,
        model_id: Optional[str] = None,
        fan_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        has_media: Optional[bool] = None,
        sentiment: Optional[str] = None,
        size: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search messages with advanced filters."""
        try:
            # Build filters
            filters = {"agency_id": agency_id}
            
            if model_id:
                filters["model_id"] = model_id
            if fan_id:
                filters["fan_id"] = fan_id
            if has_media is not None:
                filters["has_media"] = has_media
            if sentiment:
                filters["sentiment"] = sentiment
            
            # Date range filter
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter["gte"] = date_from.isoformat()
                if date_to:
                    date_filter["lte"] = date_to.isoformat()
                filters["created_at"] = {"range": date_filter}
            
            # Search
            results = await self.es_client.search(
                index_name='messages',
                query=query,
                filters=filters,
                size=size,
                from_=offset,
                sort=[{"created_at": "desc"}]
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            raise
    
    async def search_media(
        self,
        query: str,
        agency_id: str,
        media_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        uploaded_by: Optional[str] = None,
        is_nsfw: Optional[bool] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        size: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search media files with filters."""
        try:
            # Build filters
            filters = {"agency_id": agency_id}
            
            if media_type:
                filters["media_type"] = media_type
            if tags:
                filters["tags"] = tags
            if uploaded_by:
                filters["uploaded_by"] = uploaded_by
            if is_nsfw is not None:
                filters["is_nsfw"] = is_nsfw
            
            # Size range filter
            if min_size or max_size:
                size_filter = {}
                if min_size:
                    size_filter["gte"] = min_size
                if max_size:
                    size_filter["lte"] = max_size
                filters["file_size"] = {"range": size_filter}
            
            # Search
            results = await self.es_client.search(
                index_name='media',
                query=query,
                filters=filters,
                size=size,
                from_=offset,
                sort=[{"created_at": "desc"}]
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching media: {e}")
            raise
    
    async def search_transactions(
        self,
        query: str,
        agency_id: str,
        model_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        status: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        size: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search transactions with filters."""
        try:
            # Build filters
            filters = {"agency_id": agency_id}
            
            if model_id:
                filters["model_id"] = model_id
            if transaction_type:
                filters["type"] = transaction_type
            if status:
                filters["status"] = status
            
            # Amount range filter
            if min_amount or max_amount:
                amount_filter = {}
                if min_amount:
                    amount_filter["gte"] = min_amount
                if max_amount:
                    amount_filter["lte"] = max_amount
                filters["amount"] = {"range": amount_filter}
            
            # Date range filter
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter["gte"] = date_from.isoformat()
                if date_to:
                    date_filter["lte"] = date_to.isoformat()
                filters["created_at"] = {"range": date_filter}
            
            # Search
            results = await self.es_client.search(
                index_name='transactions',
                query=query,
                filters=filters,
                size=size,
                from_=offset,
                sort=[{"created_at": "desc"}]
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching transactions: {e}")
            raise
    
    async def get_search_suggestions(
        self,
        query: str,
        context: Optional[str] = None
    ) -> List[str]:
        """Get search suggestions based on partial query."""
        try:
            suggestions = await self.es_client.suggest(query, size=10)
            
            # Filter suggestions by context if provided
            if context and suggestions:
                # Implement context-aware filtering
                pass
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return []
    
    async def get_popular_searches(
        self,
        agency_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get popular searches for the agency."""
        # This would typically be tracked separately
        # For now, return empty list
        return []
    
    async def save_search_query(
        self,
        user_id: str,
        agency_id: str,
        query: str,
        results_count: int
    ):
        """Save search query for analytics and suggestions."""
        try:
            # Index search query for future suggestions
            await self.es_client.index_document(
                'content',
                f"search_{user_id}_{datetime.utcnow().timestamp()}",
                {
                    "id": f"search_{datetime.utcnow().isoformat()}",
                    "type": "search_query",
                    "content": query,
                    "agency_id": agency_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "results_count": results_count,
                    "suggest": {
                        "input": query.split(),
                        "weight": results_count + 1
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error saving search query: {e}")
    
    # Index synchronization methods
    
    async def index_model(self, model: Model):
        """Index a model in Elasticsearch."""
        try:
            doc = {
                "id": str(model.id),
                "platform_id": model.platform_id,
                "username": model.username,
                "display_name": model.display_name,
                "bio": model.bio,
                "platform": model.platform,
                "agency_id": str(model.agency_id),
                "is_active": model.is_active,
                "tags": model.tags or [],
                "stats": {
                    "total_fans": model.total_fans or 0,
                    "total_revenue": float(model.total_revenue) if model.total_revenue else 0,
                    "message_count": model.message_count or 0
                },
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat() if model.updated_at else None
            }
            
            await self.es_client.index_document('models', str(model.id), doc)
            
            # Also index in content for global search
            await self.es_client.index_document('content', f"model_{model.id}", {
                "id": str(model.id),
                "type": "model",
                "title": model.display_name or model.username,
                "content": model.bio or "",
                "tags": model.tags or [],
                "agency_id": str(model.agency_id),
                "created_at": model.created_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error indexing model: {e}")
    
    async def index_message(self, message: Message):
        """Index a message in Elasticsearch."""
        try:
            doc = {
                "id": str(message.id),
                "model_id": str(message.model_id),
                "fan_id": str(message.fan_id),
                "content": message.content,
                "platform": message.platform,
                "is_from_fan": message.is_from_fan,
                "has_media": message.has_media,
                "tip_amount": float(message.tip_amount) if message.tip_amount else 0,
                "sentiment": message.sentiment,
                "created_at": message.created_at.isoformat()
            }
            
            await self.es_client.index_document('messages', str(message.id), doc)
            
        except Exception as e:
            logger.error(f"Error indexing message: {e}")
    
    async def index_media(self, media: Media):
        """Index media in Elasticsearch."""
        try:
            doc = {
                "id": str(media.id),
                "filename": media.filename,
                "original_filename": media.original_filename,
                "title": media.title,
                "description": media.description,
                "tags": media.tags or [],
                "media_type": media.media_type.value,
                "mime_type": media.mime_type,
                "file_size": media.file_size,
                "agency_id": str(media.agency_id),
                "model_id": str(media.model_id) if media.model_id else None,
                "uploaded_by": str(media.uploaded_by),
                "visibility": media.visibility.value,
                "is_nsfw": media.is_nsfw,
                "view_count": media.view_count,
                "created_at": media.created_at.isoformat()
            }
            
            await self.es_client.index_document('media', str(media.id), doc)
            
            # Also index in content for global search
            await self.es_client.index_document('content', f"media_{media.id}", {
                "id": str(media.id),
                "type": "media",
                "title": media.title or media.original_filename,
                "content": media.description or "",
                "tags": media.tags or [],
                "agency_id": str(media.agency_id),
                "created_at": media.created_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error indexing media: {e}")
    
    async def delete_from_index(self, index_name: str, doc_id: str):
        """Delete document from index."""
        try:
            await self.es_client.delete_document(index_name, doc_id)
            
            # Also delete from content index
            if index_name in ['models', 'media']:
                await self.es_client.delete_document('content', f"{index_name[:-1]}_{doc_id}")
                
        except Exception as e:
            logger.error(f"Error deleting from index: {e}")
    
    async def reindex_agency_data(self, agency_id: str):
        """Reindex all data for an agency."""
        try:
            logger.info(f"Starting reindex for agency {agency_id}")
            
            # Reindex models
            models = await self.db.execute(
                select(Model).where(Model.agency_id == agency_id)
            )
            for model in models.scalars():
                await self.index_model(model)
            
            # Reindex media
            media_items = await self.db.execute(
                select(Media).where(Media.agency_id == agency_id)
            )
            for media in media_items.scalars():
                await self.index_media(media)
            
            logger.info(f"Completed reindex for agency {agency_id}")
            
        except Exception as e:
            logger.error(f"Error reindexing agency data: {e}")
            raise