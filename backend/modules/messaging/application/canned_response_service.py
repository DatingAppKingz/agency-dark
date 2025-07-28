"""
Canned response management service.
"""
import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func

from core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from modules.messaging.domain.models import CannedResponse
from modules.messaging.domain.schemas import (
    CannedResponseCreate, CannedResponseUpdate, CannedResponseResponse
)

logger = logging.getLogger(__name__)


class CannedResponseService:
    """Service for managing canned responses."""
    
    async def create_canned_response(
        self,
        data: CannedResponseCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> CannedResponseResponse:
        """Create a new canned response."""
        # Check for duplicate shortcut
        if data.shortcut:
            existing = await db.execute(
                select(CannedResponse).where(
                    CannedResponse.agency_id == agency_id,
                    CannedResponse.shortcut == data.shortcut
                )
            )
            if existing.scalar_one_or_none():
                raise BadRequestError(f"Shortcut '{data.shortcut}' already exists")
        
        # Create canned response
        canned_response = CannedResponse(
            agency_id=agency_id,
            user_id=None if data.is_agency_wide else user_id,
            title=data.title,
            content=data.content,
            shortcut=data.shortcut,
            category=data.category,
            tags=data.tags,
            auto_personalize=data.auto_personalize
        )
        
        db.add(canned_response)
        await db.commit()
        await db.refresh(canned_response)
        
        logger.info(f"Created canned response '{canned_response.title}'")
        return CannedResponseResponse.from_orm(canned_response)
    
    async def update_canned_response(
        self,
        response_id: UUID,
        data: CannedResponseUpdate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> CannedResponseResponse:
        """Update a canned response."""
        # Get canned response
        result = await db.execute(
            select(CannedResponse).where(
                CannedResponse.id == response_id,
                CannedResponse.agency_id == agency_id
            )
        )
        canned_response = result.scalar_one_or_none()
        
        if not canned_response:
            raise NotFoundError("Canned response not found")
        
        # Check ownership
        if canned_response.user_id and canned_response.user_id != user_id:
            raise ForbiddenError("Cannot edit another user's canned response")
        
        # Check for duplicate shortcut if updating
        if data.shortcut and data.shortcut != canned_response.shortcut:
            existing = await db.execute(
                select(CannedResponse).where(
                    CannedResponse.agency_id == agency_id,
                    CannedResponse.shortcut == data.shortcut,
                    CannedResponse.id != response_id
                )
            )
            if existing.scalar_one_or_none():
                raise BadRequestError(f"Shortcut '{data.shortcut}' already exists")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(canned_response, field, value)
        
        canned_response.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(canned_response)
        
        return CannedResponseResponse.from_orm(canned_response)
    
    async def delete_canned_response(
        self,
        response_id: UUID,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a canned response."""
        result = await db.execute(
            select(CannedResponse).where(
                CannedResponse.id == response_id,
                CannedResponse.agency_id == agency_id
            )
        )
        canned_response = result.scalar_one_or_none()
        
        if not canned_response:
            raise NotFoundError("Canned response not found")
        
        # Check ownership
        if canned_response.user_id and canned_response.user_id != user_id:
            raise ForbiddenError("Cannot delete another user's canned response")
        
        await db.delete(canned_response)
        await db.commit()
        
        logger.info(f"Deleted canned response '{canned_response.title}'")
        return True
    
    async def get_canned_response(
        self,
        response_id: UUID,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> CannedResponseResponse:
        """Get a canned response by ID."""
        result = await db.execute(
            select(CannedResponse).where(
                CannedResponse.id == response_id,
                CannedResponse.agency_id == agency_id,
                or_(
                    CannedResponse.user_id.is_(None),  # Agency-wide
                    CannedResponse.user_id == user_id
                )
            )
        )
        canned_response = result.scalar_one_or_none()
        
        if not canned_response:
            raise NotFoundError("Canned response not found")
        
        return CannedResponseResponse.from_orm(canned_response)
    
    async def list_canned_responses(
        self,
        agency_id: UUID,
        user_id: UUID,
        category: Optional[str] = None,
        search: Optional[str] = None,
        include_agency_wide: bool = True,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[CannedResponseResponse]:
        """List canned responses."""
        query = select(CannedResponse).where(
            CannedResponse.agency_id == agency_id,
            CannedResponse.is_active == True
        )
        
        # Filter by user access
        if include_agency_wide:
            query = query.where(
                or_(
                    CannedResponse.user_id.is_(None),
                    CannedResponse.user_id == user_id
                )
            )
        else:
            query = query.where(CannedResponse.user_id == user_id)
        
        # Apply filters
        if category:
            query = query.where(CannedResponse.category == category)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    CannedResponse.title.ilike(search_term),
                    CannedResponse.content.ilike(search_term),
                    CannedResponse.shortcut.ilike(search_term)
                )
            )
        
        # Order by usage
        query = query.order_by(
            CannedResponse.usage_count.desc(),
            CannedResponse.created_at.desc()
        )
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        responses = result.scalars().all()
        
        return [CannedResponseResponse.from_orm(r) for r in responses]
    
    async def get_by_shortcut(
        self,
        shortcut: str,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> Optional[CannedResponseResponse]:
        """Get a canned response by shortcut."""
        # Ensure shortcut starts with /
        if not shortcut.startswith('/'):
            shortcut = f'/{shortcut}'
        
        result = await db.execute(
            select(CannedResponse).where(
                CannedResponse.agency_id == agency_id,
                CannedResponse.shortcut == shortcut,
                CannedResponse.is_active == True,
                or_(
                    CannedResponse.user_id.is_(None),
                    CannedResponse.user_id == user_id
                )
            )
        )
        canned_response = result.scalar_one_or_none()
        
        if canned_response:
            # Increment usage
            await self.increment_usage(canned_response.id, agency_id, db)
            return CannedResponseResponse.from_orm(canned_response)
        
        return None
    
    async def increment_usage(
        self,
        response_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ):
        """Increment canned response usage count."""
        await db.execute(
            update(CannedResponse)
            .where(
                CannedResponse.id == response_id,
                CannedResponse.agency_id == agency_id
            )
            .values(
                usage_count=CannedResponse.usage_count + 1,
                last_used_at=datetime.utcnow()
            )
        )
        await db.commit()
    
    async def get_categories(
        self,
        agency_id: UUID,
        db: AsyncSession
    ) -> List[str]:
        """Get all unique categories."""
        result = await db.execute(
            select(func.distinct(CannedResponse.category))
            .where(
                CannedResponse.agency_id == agency_id,
                CannedResponse.category.isnot(None),
                CannedResponse.is_active == True
            )
        )
        categories = [row[0] for row in result if row[0]]
        return sorted(categories)
    
    async def personalize_content(
        self,
        content: str,
        fan_data: dict
    ) -> str:
        """Personalize canned response content with fan data."""
        personalized = content
        
        # Common replacements
        replacements = {
            "{{fan_name}}": fan_data.get("name", "there"),
            "{{fan_username}}": fan_data.get("username", ""),
            "{{model_name}}": fan_data.get("model_name", ""),
            "{{current_date}}": datetime.utcnow().strftime("%B %d, %Y"),
            "{{current_time}}": datetime.utcnow().strftime("%I:%M %p")
        }
        
        for placeholder, value in replacements.items():
            personalized = personalized.replace(placeholder, value)
        
        return personalized