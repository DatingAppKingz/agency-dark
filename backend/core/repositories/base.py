"""
Base repository with automatic agency filtering.
"""
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from models.base import Base
from models.user_simple import User
from core.filters.agency_filter import get_filter_for_model, AgencyFilter
import logging

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with automatic agency-based filtering."""
    
    def __init__(
        self, 
        model: Type[ModelType], 
        db: AsyncSession,
        current_user: Optional[User] = None,
        bypass_filters: bool = False
    ):
        self.model = model
        self.db = db
        self.current_user = current_user
        self.bypass_filters = bypass_filters
        self._filter = None
        
        if current_user and not bypass_filters:
            self._filter = get_filter_for_model(model, current_user, db)
    
    def _apply_filters(self, query: Select) -> Select:
        """Apply agency filters to a query if applicable."""
        if self.bypass_filters or not self._filter:
            return query
        
        # Check if filter has async method
        if hasattr(self._filter, 'apply_filter_async'):
            # This will need to be handled in async context
            logger.warning(
                f"Filter for {self.model.__name__} requires async context. "
                "Use apply_filters_async() instead."
            )
            return query
        
        return self._filter.apply_filter(query, self.model)
    
    async def apply_filters_async(self, query: Select) -> Select:
        """Apply agency filters that require async operations."""
        if self.bypass_filters or not self._filter:
            return query
        
        # Use async filter method if available
        if hasattr(self._filter, 'apply_filter_async'):
            return await self._filter.apply_filter_async(query)
        
        # Otherwise use sync method
        return self._filter.apply_filter(query, self.model)
    
    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Get a single record by ID with agency filtering."""
        query = select(self.model).where(self.model.id == id)
        query = await self.apply_filters_async(query)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[List[Any]] = None
    ) -> List[ModelType]:
        """Get all records with agency filtering and pagination."""
        query = select(self.model)
        
        # Apply custom filters
        if filters:
            for filter_condition in filters:
                query = query.where(filter_condition)
        
        # Apply agency filters
        query = await self.apply_filters_async(query)
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count(self, filters: Optional[List[Any]] = None) -> int:
        """Count records with agency filtering."""
        query = select(func.count()).select_from(self.model)
        
        # Apply custom filters
        if filters:
            for filter_condition in filters:
                query = query.where(filter_condition)
        
        # Apply agency filters
        query = await self.apply_filters_async(query)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record with automatic agency assignment."""
        # Auto-assign agency_id if model has it and user has agency
        if (
            hasattr(self.model, 'agency_id') and 
            self.current_user and 
            self.current_user.agency_id and
            'agency_id' not in kwargs
        ):
            kwargs['agency_id'] = self.current_user.agency_id
        
        db_obj = self.model(**kwargs)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def update(self, id: Any, **kwargs) -> Optional[ModelType]:
        """Update a record with agency filtering."""
        db_obj = await self.get_by_id(id)
        if not db_obj:
            return None
        
        for field, value in kwargs.items():
            setattr(db_obj, field, value)
        
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: Any) -> bool:
        """Delete a record with agency filtering."""
        db_obj = await self.get_by_id(id)
        if not db_obj:
            return False
        
        await self.db.delete(db_obj)
        await self.db.commit()
        return True
    
    async def exists(self, **kwargs) -> bool:
        """Check if a record exists with agency filtering."""
        query = select(self.model)
        
        for field, value in kwargs.items():
            query = query.where(getattr(self.model, field) == value)
        
        query = await self.apply_filters_async(query)
        query = query.limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    def with_user(self, user: User) -> "BaseRepository":
        """Create a new repository instance with a different user context."""
        return self.__class__(
            model=self.model,
            db=self.db,
            current_user=user,
            bypass_filters=self.bypass_filters
        )
    
    def without_filters(self) -> "BaseRepository":
        """Create a new repository instance without filters (for system operations)."""
        return self.__class__(
            model=self.model,
            db=self.db,
            current_user=self.current_user,
            bypass_filters=True
        )