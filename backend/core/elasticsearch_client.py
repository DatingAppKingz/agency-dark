"""Elasticsearch client configuration and helpers."""

from typing import Dict, List, Any, Optional
from elasticsearch import AsyncElasticsearch, helpers
from elasticsearch.exceptions import NotFoundError, ApiError as ElasticsearchException
import logging

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class ElasticsearchClient:
    """Async Elasticsearch client wrapper."""
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self.indices = {
            'models': 'agencydark_models',
            'messages': 'agencydark_messages',
            'users': 'agencydark_users',
            'media': 'agencydark_media',
            'transactions': 'agencydark_transactions',
            'content': 'agencydark_content'
        }
    
    async def initialize(self):
        """Initialize Elasticsearch connection."""
        try:
            self.client = AsyncElasticsearch(
                [settings.ELASTICSEARCH_URL],
                basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)
                if settings.ELASTICSEARCH_USER else None,
                verify_certs=settings.ELASTICSEARCH_VERIFY_CERTS,
                ssl_show_warn=False,
                retry_on_timeout=True,
                max_retries=3,
                timeout=30
            )
            
            # Test connection
            info = await self.client.info()
            logger.info(f"Connected to Elasticsearch {info['version']['number']}")
            
            # Create indices if they don't exist
            await self._create_indices()
            
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            raise
    
    async def close(self):
        """Close Elasticsearch connection."""
        if self.client:
            await self.client.close()
    
    async def _create_indices(self):
        """Create indices with proper mappings."""
        # Models index
        await self._create_index('models', {
            "properties": {
                "id": {"type": "keyword"},
                "platform_id": {"type": "keyword"},
                "username": {"type": "keyword"},
                "display_name": {"type": "text", "analyzer": "standard"},
                "bio": {"type": "text", "analyzer": "standard"},
                "platform": {"type": "keyword"},
                "agency_id": {"type": "keyword"},
                "is_active": {"type": "boolean"},
                "tags": {"type": "keyword"},
                "stats": {
                    "properties": {
                        "total_fans": {"type": "integer"},
                        "total_revenue": {"type": "float"},
                        "message_count": {"type": "integer"}
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"}
            }
        })
        
        # Messages index
        await self._create_index('messages', {
            "properties": {
                "id": {"type": "keyword"},
                "model_id": {"type": "keyword"},
                "fan_id": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "standard"},
                "platform": {"type": "keyword"},
                "is_from_fan": {"type": "boolean"},
                "has_media": {"type": "boolean"},
                "tip_amount": {"type": "float"},
                "sentiment": {"type": "keyword"},
                "created_at": {"type": "date"}
            }
        })
        
        # Users index
        await self._create_index('users', {
            "properties": {
                "id": {"type": "keyword"},
                "email": {"type": "keyword"},
                "full_name": {"type": "text", "analyzer": "standard"},
                "role": {"type": "keyword"},
                "agency_id": {"type": "keyword"},
                "is_active": {"type": "boolean"},
                "created_at": {"type": "date"},
                "last_login": {"type": "date"}
            }
        })
        
        # Media index
        await self._create_index('media', {
            "properties": {
                "id": {"type": "keyword"},
                "filename": {"type": "text", "analyzer": "standard"},
                "original_filename": {"type": "text", "analyzer": "standard"},
                "title": {"type": "text", "analyzer": "standard"},
                "description": {"type": "text", "analyzer": "standard"},
                "tags": {"type": "keyword"},
                "media_type": {"type": "keyword"},
                "mime_type": {"type": "keyword"},
                "file_size": {"type": "long"},
                "agency_id": {"type": "keyword"},
                "model_id": {"type": "keyword"},
                "uploaded_by": {"type": "keyword"},
                "visibility": {"type": "keyword"},
                "is_nsfw": {"type": "boolean"},
                "view_count": {"type": "integer"},
                "created_at": {"type": "date"}
            }
        })
        
        # Transactions index
        await self._create_index('transactions', {
            "properties": {
                "id": {"type": "keyword"},
                "model_id": {"type": "keyword"},
                "fan_id": {"type": "keyword"},
                "type": {"type": "keyword"},
                "amount": {"type": "float"},
                "currency": {"type": "keyword"},
                "status": {"type": "keyword"},
                "platform": {"type": "keyword"},
                "description": {"type": "text"},
                "created_at": {"type": "date"}
            }
        })
        
        # Content index (for full-text search across all content)
        await self._create_index('content', {
            "properties": {
                "id": {"type": "keyword"},
                "type": {"type": "keyword"},  # model, message, media, etc.
                "title": {"type": "text", "analyzer": "standard"},
                "content": {"type": "text", "analyzer": "standard"},
                "tags": {"type": "keyword"},
                "agency_id": {"type": "keyword"},
                "created_at": {"type": "date"},
                "suggest": {
                    "type": "completion",
                    "analyzer": "simple",
                    "preserve_separators": True,
                    "preserve_position_increments": True,
                    "max_input_length": 50
                }
            }
        })
    
    async def _create_index(self, index_name: str, mappings: Dict[str, Any]):
        """Create an index with mappings if it doesn't exist."""
        index = self.indices[index_name]
        try:
            exists = await self.client.indices.exists(index=index)
            if not exists:
                await self.client.indices.create(
                    index=index,
                    body={
                        "settings": {
                            "number_of_shards": 1,
                            "number_of_replicas": 1,
                            "analysis": {
                                "analyzer": {
                                    "autocomplete": {
                                        "tokenizer": "autocomplete",
                                        "filter": ["lowercase"]
                                    },
                                    "autocomplete_search": {
                                        "tokenizer": "lowercase"
                                    }
                                },
                                "tokenizer": {
                                    "autocomplete": {
                                        "type": "edge_ngram",
                                        "min_gram": 2,
                                        "max_gram": 10,
                                        "token_chars": ["letter", "digit"]
                                    }
                                }
                            }
                        },
                        "mappings": mappings
                    }
                )
                logger.info(f"Created index: {index}")
        except Exception as e:
            logger.error(f"Error creating index {index}: {e}")
    
    async def index_document(self, index_name: str, doc_id: str, document: Dict[str, Any]):
        """Index a single document."""
        try:
            index = self.indices.get(index_name)
            if not index:
                raise ValueError(f"Unknown index: {index_name}")
            
            await self.client.index(
                index=index,
                id=doc_id,
                body=document,
                refresh='wait_for'
            )
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            raise
    
    async def bulk_index(self, index_name: str, documents: List[Dict[str, Any]]):
        """Bulk index multiple documents."""
        try:
            index = self.indices.get(index_name)
            if not index:
                raise ValueError(f"Unknown index: {index_name}")
            
            actions = [
                {
                    "_index": index,
                    "_id": doc.get("id"),
                    "_source": doc
                }
                for doc in documents
            ]
            
            success, failed = await helpers.async_bulk(
                self.client,
                actions,
                chunk_size=500,
                raise_on_error=False
            )
            
            if failed:
                logger.error(f"Failed to index {len(failed)} documents")
            
            return success, failed
            
        except Exception as e:
            logger.error(f"Error in bulk indexing: {e}")
            raise
    
    async def search(
        self,
        index_name: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 20,
        from_: int = 0,
        sort: Optional[List[Dict[str, Any]]] = None,
        highlight: bool = True
    ) -> Dict[str, Any]:
        """
        Search documents with query and filters.
        
        Args:
            index_name: Index to search in
            query: Search query string
            filters: Additional filters (e.g., {"agency_id": "123"})
            size: Number of results to return
            from_: Offset for pagination
            sort: Sort criteria
            highlight: Whether to highlight matching terms
        
        Returns:
            Search results with hits and aggregations
        """
        try:
            index = self.indices.get(index_name)
            if not index:
                raise ValueError(f"Unknown index: {index_name}")
            
            # Build query
            must_clauses = []
            
            # Add search query
            if query:
                must_clauses.append({
                    "multi_match": {
                        "query": query,
                        "fields": self._get_search_fields(index_name),
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                })
            
            # Add filters
            filter_clauses = []
            if filters:
                for field, value in filters.items():
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {field: value}})
                    else:
                        filter_clauses.append({"term": {field: value}})
            
            # Construct final query
            search_query = {
                "bool": {
                    "must": must_clauses if must_clauses else {"match_all": {}},
                    "filter": filter_clauses
                }
            }
            
            # Build search body
            body = {
                "query": search_query,
                "size": size,
                "from": from_
            }
            
            # Add sorting
            if sort:
                body["sort"] = sort
            else:
                body["sort"] = [{"_score": "desc"}, {"created_at": "desc"}]
            
            # Add highlighting
            if highlight and query:
                body["highlight"] = {
                    "fields": {
                        "*": {
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 150,
                            "number_of_fragments": 3
                        }
                    }
                }
            
            # Add aggregations for faceted search
            body["aggs"] = self._get_aggregations(index_name)
            
            # Execute search
            response = await self.client.search(
                index=index,
                body=body
            )
            
            return {
                "total": response["hits"]["total"]["value"],
                "hits": [
                    {
                        "id": hit["_id"],
                        "score": hit["_score"],
                        "source": hit["_source"],
                        "highlight": hit.get("highlight", {})
                    }
                    for hit in response["hits"]["hits"]
                ],
                "aggregations": response.get("aggregations", {})
            }
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            raise
    
    async def suggest(self, query: str, size: int = 5) -> List[str]:
        """Get search suggestions based on query."""
        try:
            body = {
                "suggest": {
                    "text": query,
                    "completion": {
                        "field": "suggest",
                        "size": size,
                        "skip_duplicates": True,
                        "fuzzy": {
                            "fuzziness": "AUTO"
                        }
                    }
                }
            }
            
            response = await self.client.search(
                index=self.indices['content'],
                body=body
            )
            
            suggestions = []
            for option in response["suggest"]["completion"][0]["options"]:
                suggestions.append(option["text"])
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return []
    
    async def delete_document(self, index_name: str, doc_id: str):
        """Delete a document from index."""
        try:
            index = self.indices.get(index_name)
            if not index:
                raise ValueError(f"Unknown index: {index_name}")
            
            await self.client.delete(
                index=index,
                id=doc_id,
                refresh='wait_for'
            )
        except NotFoundError:
            logger.warning(f"Document {doc_id} not found in {index_name}")
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise
    
    async def update_document(self, index_name: str, doc_id: str, updates: Dict[str, Any]):
        """Update a document in index."""
        try:
            index = self.indices.get(index_name)
            if not index:
                raise ValueError(f"Unknown index: {index_name}")
            
            await self.client.update(
                index=index,
                id=doc_id,
                body={"doc": updates},
                refresh='wait_for'
            )
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            raise
    
    def _get_search_fields(self, index_name: str) -> List[str]:
        """Get searchable fields for an index."""
        fields_map = {
            'models': ["username^3", "display_name^2", "bio"],
            'messages': ["content"],
            'users': ["email^2", "full_name^3"],
            'media': ["filename^2", "original_filename^2", "title^3", "description", "tags"],
            'transactions': ["description"],
            'content': ["title^3", "content", "tags^2"]
        }
        return fields_map.get(index_name, ["*"])
    
    def _get_aggregations(self, index_name: str) -> Dict[str, Any]:
        """Get aggregations for faceted search."""
        aggs_map = {
            'models': {
                "platforms": {"terms": {"field": "platform"}},
                "active_status": {"terms": {"field": "is_active"}}
            },
            'messages': {
                "platforms": {"terms": {"field": "platform"}},
                "has_media": {"terms": {"field": "has_media"}},
                "date_histogram": {
                    "date_histogram": {
                        "field": "created_at",
                        "calendar_interval": "day"
                    }
                }
            },
            'users': {
                "roles": {"terms": {"field": "role"}},
                "active_status": {"terms": {"field": "is_active"}}
            },
            'media': {
                "media_types": {"terms": {"field": "media_type"}},
                "visibility": {"terms": {"field": "visibility"}},
                "tags": {"terms": {"field": "tags", "size": 20}}
            },
            'transactions': {
                "types": {"terms": {"field": "type"}},
                "status": {"terms": {"field": "status"}},
                "platforms": {"terms": {"field": "platform"}}
            },
            'content': {
                "types": {"terms": {"field": "type"}},
                "tags": {"terms": {"field": "tags", "size": 20}}
            }
        }
        return aggs_map.get(index_name, {})


# Global instance
es_client = ElasticsearchClient()


async def get_elasticsearch_client() -> ElasticsearchClient:
    """Get Elasticsearch client instance."""
    return es_client