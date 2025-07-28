"""
Response optimization utilities for API performance
"""
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import orjson
from pydantic import BaseModel
from sqlalchemy.orm import Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base
from core.performance.cache_manager import cache_manager, CacheKeyBuilder


class ResponseOptimizer:
    """Optimize API responses for better performance"""
    
    @staticmethod
    def optimize_json_response(
        data: Any,
        include_fields: Optional[Set[str]] = None,
        exclude_fields: Optional[Set[str]] = None
    ) -> bytes:
        """
        Optimize JSON response using orjson
        
        Args:
            data: Data to serialize
            include_fields: Fields to include (whitelist)
            exclude_fields: Fields to exclude (blacklist)
            
        Returns:
            Optimized JSON bytes
        """
        # Apply field filtering
        if include_fields or exclude_fields:
            data = ResponseOptimizer._filter_fields(
                data,
                include_fields,
                exclude_fields
            )
        
        # Use orjson for fast serialization
        return orjson.dumps(
            data,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY,
            default=ResponseOptimizer._json_encoder
        )
    
    @staticmethod
    def _filter_fields(
        data: Any,
        include_fields: Optional[Set[str]] = None,
        exclude_fields: Optional[Set[str]] = None
    ) -> Any:
        """Filter fields from response data"""
        if isinstance(data, dict):
            result = {}
            
            for key, value in data.items():
                # Skip excluded fields
                if exclude_fields and key in exclude_fields:
                    continue
                
                # Include only specified fields
                if include_fields and key not in include_fields:
                    continue
                
                # Recursively filter nested data
                result[key] = ResponseOptimizer._filter_fields(
                    value,
                    include_fields,
                    exclude_fields
                )
            
            return result
        
        elif isinstance(data, list):
            return [
                ResponseOptimizer._filter_fields(item, include_fields, exclude_fields)
                for item in data
            ]
        
        return data
    
    @staticmethod
    def _json_encoder(obj: Any) -> Any:
        """Custom JSON encoder for complex types"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, BaseModel):
            return obj.dict()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @staticmethod
    async def paginate_response(
        query: Query,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100,
        cache_key: Optional[str] = None,
        cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """
        Create paginated response with caching
        
        Args:
            query: SQLAlchemy query
            page: Page number
            per_page: Items per page
            max_per_page: Maximum items per page
            cache_key: Optional cache key
            cache_ttl: Cache TTL in seconds
            
        Returns:
            Paginated response dict
        """
        # Check cache first
        if cache_key:
            cached = await cache_manager.get(cache_key)
            if cached:
                return cached
        
        # Ensure per_page doesn't exceed maximum
        per_page = min(per_page, max_per_page)
        
        # Calculate pagination
        offset = (page - 1) * per_page
        
        # Get total count
        total = await query.count()
        
        # Get items
        items = await query.limit(per_page).offset(offset).all()
        
        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1
        
        response = {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev,
                "next_page": page + 1 if has_next else None,
                "prev_page": page - 1 if has_prev else None
            }
        }
        
        # Cache the response
        if cache_key:
            await cache_manager.set(cache_key, response, cache_ttl)
        
        return response
    
    @staticmethod
    def create_sparse_fieldset(
        data: Union[Dict, List[Dict]],
        fields: List[str]
    ) -> Union[Dict, List[Dict]]:
        """
        Create sparse fieldset response (JSON:API style)
        
        Args:
            data: Response data
            fields: List of fields to include
            
        Returns:
            Filtered data with only requested fields
        """
        if isinstance(data, list):
            return [
                {field: item.get(field) for field in fields if field in item}
                for item in data
            ]
        else:
            return {field: data.get(field) for field in fields if field in data}
    
    @staticmethod
    async def create_cached_list_response(
        db: AsyncSession,
        model: Base,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 20,
        sort_by: Optional[str] = None,
        cache_namespace: str = "list"
    ) -> Dict[str, Any]:
        """
        Create cached list response with automatic cache key generation
        
        Args:
            db: Database session
            model: SQLAlchemy model
            filters: Query filters
            page: Page number
            per_page: Items per page
            sort_by: Sort field
            cache_namespace: Cache namespace
            
        Returns:
            Cached list response
        """
        # Generate cache key
        cache_key = CacheKeyBuilder.list_key(
            entity_type=model.__tablename__,
            filters=filters,
            page=page,
            per_page=per_page
        )
        
        if sort_by:
            cache_key += f":sort={sort_by}"
        
        # Check cache
        cached = await cache_manager.get(cache_key, cache_namespace)
        if cached:
            return cached
        
        # Build query
        query = db.query(model)
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(model, field):
                column = getattr(model, field)
                if isinstance(value, list):
                    query = query.filter(column.in_(value))
                else:
                    query = query.filter(column == value)
        
        # Apply sorting
        if sort_by and hasattr(model, sort_by):
            column = getattr(model, sort_by)
            query = query.order_by(column)
        
        # Create paginated response
        response = await ResponseOptimizer.paginate_response(
            query=query,
            page=page,
            per_page=per_page
        )
        
        # Cache the response
        await cache_manager.set(cache_key, response, 300, cache_namespace)
        
        return response


class ResponseFormatter:
    """Format responses for consistency and optimization"""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "Success",
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Format success response"""
        response = {
            "success": True,
            "message": message
        }
        
        if data is not None:
            response["data"] = data
        
        if meta:
            response["meta"] = meta
        
        return response
    
    @staticmethod
    def error(
        message: str,
        code: Optional[str] = None,
        details: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Format error response"""
        response = {
            "success": False,
            "message": message
        }
        
        if code:
            response["code"] = code
        
        if details:
            response["details"] = details
        
        return response
    
    @staticmethod
    def paginated(
        items: List[Any],
        page: int,
        per_page: int,
        total: int,
        message: str = "Success"
    ) -> Dict[str, Any]:
        """Format paginated response"""
        total_pages = (total + per_page - 1) // per_page
        
        return {
            "success": True,
            "message": message,
            "data": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    
    @staticmethod
    def batch(
        results: List[Dict[str, Any]],
        succeeded: int,
        failed: int,
        message: str = "Batch operation completed"
    ) -> Dict[str, Any]:
        """Format batch operation response"""
        return {
            "success": True,
            "message": message,
            "data": {
                "results": results,
                "summary": {
                    "total": succeeded + failed,
                    "succeeded": succeeded,
                    "failed": failed
                }
            }
        }