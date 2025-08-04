"""Advanced pagination service for efficient data loading."""

from typing import TypeVar, Generic, List, Optional, Dict, Any, Type, Union
from datetime import datetime
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from pydantic import BaseModel, Field
import base64
import json

from core.logger import get_logger
from core.database import Base

logger = get_logger(__name__)

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    limit: int = Field(default=50, ge=1, le=100)
    cursor: Optional[str] = None
    direction: str = Field(default="next", pattern="^(next|prev)$")


class PageInfo(BaseModel):
    """Pagination metadata."""
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]
    total_count: Optional[int] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    edges: List[Dict[str, Any]]
    page_info: PageInfo
    
    class Config:
        arbitrary_types_allowed = True


class CursorPagination:
    """Cursor-based pagination implementation."""
    
    @staticmethod
    def encode_cursor(data: Dict[str, Any]) -> str:
        """Encode cursor data to string."""
        json_str = json.dumps(data, default=str)
        return base64.urlsafe_b64encode(json_str.encode()).decode()
    
    @staticmethod
    def decode_cursor(cursor: str) -> Dict[str, Any]:
        """Decode cursor string to data."""
        try:
            json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Invalid cursor: {e}")
            return {}
    
    @classmethod
    async def paginate(
        cls,
        db: AsyncSession,
        query: Select,
        model: Type[Base],
        order_by: str,
        params: PaginationParams,
        additional_filters: Optional[List] = None,
        unique_field: str = "id"
    ) -> PaginatedResponse:
        """
        Perform cursor-based pagination on a query.
        
        Args:
            db: Database session
            query: Base query to paginate
            model: SQLAlchemy model
            order_by: Field to order by
            params: Pagination parameters
            additional_filters: Additional WHERE clauses
            unique_field: Unique field for stable ordering
        
        Returns:
            PaginatedResponse with edges and page info
        """
        # Parse order field and direction
        if order_by.startswith("-"):
            order_field = order_by[1:]
            order_desc = True
        else:
            order_field = order_by
            order_desc = False
        
        # Apply additional filters
        if additional_filters:
            for filter_clause in additional_filters:
                query = query.where(filter_clause)
        
        # Apply cursor filter if provided
        if params.cursor:
            cursor_data = cls.decode_cursor(params.cursor)
            if cursor_data:
                cursor_value = cursor_data.get(order_field)
                cursor_id = cursor_data.get(unique_field)
                
                if cursor_value is not None:
                    order_attr = getattr(model, order_field)
                    unique_attr = getattr(model, unique_field)
                    
                    if params.direction == "next":
                        if order_desc:
                            # For DESC order, next means less than cursor
                            query = query.where(
                                or_(
                                    order_attr < cursor_value,
                                    and_(
                                        order_attr == cursor_value,
                                        unique_attr > cursor_id
                                    )
                                )
                            )
                        else:
                            # For ASC order, next means greater than cursor
                            query = query.where(
                                or_(
                                    order_attr > cursor_value,
                                    and_(
                                        order_attr == cursor_value,
                                        unique_attr > cursor_id
                                    )
                                )
                            )
                    else:  # prev
                        if order_desc:
                            # For DESC order, prev means greater than cursor
                            query = query.where(
                                or_(
                                    order_attr > cursor_value,
                                    and_(
                                        order_attr == cursor_value,
                                        unique_attr < cursor_id
                                    )
                                )
                            )
                        else:
                            # For ASC order, prev means less than cursor
                            query = query.where(
                                or_(
                                    order_attr < cursor_value,
                                    and_(
                                        order_attr == cursor_value,
                                        unique_attr < cursor_id
                                    )
                                )
                            )
        
        # Apply ordering
        order_attr = getattr(model, order_field)
        unique_attr = getattr(model, unique_field)
        
        if order_desc:
            query = query.order_by(desc(order_attr), asc(unique_attr))
        else:
            query = query.order_by(asc(order_attr), asc(unique_attr))
        
        # Fetch one extra to determine if there's a next page
        query = query.limit(params.limit + 1)
        
        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Determine pagination info
        has_next = len(items) > params.limit
        if has_next:
            items = items[:-1]  # Remove extra item
        
        # For previous page detection, we need to check if there are items before the first one
        has_prev = False
        if items and params.cursor:
            # This is a simplified check - in production, you'd run a count query
            has_prev = True
        
        # Create edges with cursors
        edges = []
        for item in items:
            cursor_data = {
                order_field: getattr(item, order_field),
                unique_field: getattr(item, unique_field)
            }
            edges.append({
                "node": item,
                "cursor": cls.encode_cursor(cursor_data)
            })
        
        # Page info
        page_info = PageInfo(
            has_next_page=has_next,
            has_previous_page=has_prev,
            start_cursor=edges[0]["cursor"] if edges else None,
            end_cursor=edges[-1]["cursor"] if edges else None
        )
        
        return PaginatedResponse(edges=edges, page_info=page_info)


class OffsetPagination:
    """Traditional offset-based pagination (less efficient for large datasets)."""
    
    @classmethod
    async def paginate(
        cls,
        db: AsyncSession,
        query: Select,
        page: int = 1,
        per_page: int = 50,
        include_total: bool = True
    ) -> Dict[str, Any]:
        """
        Perform offset-based pagination.
        
        Args:
            db: Database session
            query: Query to paginate
            page: Page number (1-based)
            per_page: Items per page
            include_total: Whether to include total count
        
        Returns:
            Dict with items, pagination metadata
        """
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get items
        paginated_query = query.offset(offset).limit(per_page)
        result = await db.execute(paginated_query)
        items = result.scalars().all()
        
        # Get total count if requested
        total = None
        total_pages = None
        if include_total:
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            total_pages = (total + per_page - 1) // per_page
        
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages if total_pages else len(items) == per_page,
            "has_prev": page > 1
        }


class PaginationService:
    """Main pagination service with caching and optimization."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cursor_pagination = CursorPagination()
        self.offset_pagination = OffsetPagination()
    
    async def paginate_cursor(
        self,
        model: Type[Base],
        order_by: str = "-created_at",
        filters: Optional[Dict[str, Any]] = None,
        params: Optional[PaginationParams] = None,
        includes: Optional[List[str]] = None
    ) -> PaginatedResponse:
        """
        Paginate using cursor-based pagination.
        
        Args:
            model: Model to query
            order_by: Field to order by (prefix with - for DESC)
            filters: Filter conditions
            params: Pagination parameters
            includes: Relationships to eager load
        
        Returns:
            PaginatedResponse
        """
        if params is None:
            params = PaginationParams()
        
        # Build base query
        query = select(model)
        
        # Apply filters
        filter_clauses = []
        if filters:
            for field, value in filters.items():
                if hasattr(model, field):
                    attr = getattr(model, field)
                    if isinstance(value, list):
                        filter_clauses.append(attr.in_(value))
                    elif isinstance(value, dict):
                        # Handle complex filters like {"gte": 100, "lte": 500}
                        for op, val in value.items():
                            if op == "gte":
                                filter_clauses.append(attr >= val)
                            elif op == "lte":
                                filter_clauses.append(attr <= val)
                            elif op == "gt":
                                filter_clauses.append(attr > val)
                            elif op == "lt":
                                filter_clauses.append(attr < val)
                            elif op == "ne":
                                filter_clauses.append(attr != val)
                            elif op == "like":
                                filter_clauses.append(attr.like(f"%{val}%"))
                            elif op == "ilike":
                                filter_clauses.append(attr.ilike(f"%{val}%"))
                    else:
                        filter_clauses.append(attr == value)
        
        # Apply eager loading
        if includes:
            from core.query_optimization import QueryOptimizer
            query = QueryOptimizer.optimize_query(
                query,
                model.__name__,
                "custom" if len(includes) > 2 else "default"
            )
        
        return await self.cursor_pagination.paginate(
            db=self.db,
            query=query,
            model=model,
            order_by=order_by,
            params=params,
            additional_filters=filter_clauses
        )
    
    async def paginate_offset(
        self,
        model: Type[Base],
        page: int = 1,
        per_page: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        include_total: bool = True
    ) -> Dict[str, Any]:
        """
        Paginate using offset-based pagination.
        
        Args:
            model: Model to query
            page: Page number
            per_page: Items per page
            filters: Filter conditions
            order_by: Order by field
            include_total: Include total count
        
        Returns:
            Dict with pagination data
        """
        # Build query
        query = select(model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(model, field):
                    query = query.where(getattr(model, field) == value)
        
        # Apply ordering
        if order_by:
            if order_by.startswith("-"):
                query = query.order_by(desc(getattr(model, order_by[1:])))
            else:
                query = query.order_by(asc(getattr(model, order_by)))
        
        return await self.offset_pagination.paginate(
            db=self.db,
            query=query,
            page=page,
            per_page=per_page,
            include_total=include_total
        )


# Helper functions for common pagination scenarios
async def paginate_messages(
    db: AsyncSession,
    conversation_id: int,
    params: PaginationParams
) -> PaginatedResponse:
    """Paginate messages in a conversation."""
    from models.chat import Message
    
    service = PaginationService(db)
    return await service.paginate_cursor(
        model=Message,
        order_by="-created_at",
        filters={"conversation_id": conversation_id, "is_deleted": False},
        params=params,
        includes=["sender"]
    )


async def paginate_conversations(
    db: AsyncSession,
    model_id: Optional[int] = None,
    status: Optional[str] = None,
    params: Optional[PaginationParams] = None
) -> PaginatedResponse:
    """Paginate conversations with filters."""
    from models.chat import Conversation
    
    filters = {}
    if model_id:
        filters["model_id"] = model_id
    if status:
        filters["status"] = status
    
    service = PaginationService(db)
    return await service.paginate_cursor(
        model=Conversation,
        order_by="-last_message_at",
        filters=filters,
        params=params or PaginationParams(),
        includes=["model", "assigned_chatter"]
    )


async def paginate_transactions(
    db: AsyncSession,
    model_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    params: Optional[PaginationParams] = None
) -> PaginatedResponse:
    """Paginate financial transactions."""
    from models.financial import Transaction
    
    filters = {}
    if model_id:
        filters["model_id"] = model_id
    if date_from and date_to:
        filters["created_at"] = {"gte": date_from.isoformat(), "lte": date_to.isoformat()}
    
    service = PaginationService(db)
    return await service.paginate_cursor(
        model=Transaction,
        order_by="-created_at",
        filters=filters,
        params=params or PaginationParams(),
        includes=["model"]
    )