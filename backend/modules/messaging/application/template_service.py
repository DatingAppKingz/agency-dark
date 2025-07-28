"""
Template management service for message templates.
"""
import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func

from core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from modules.messaging.domain.models import MessageTemplate, TemplateCategory
from modules.messaging.domain.schemas import (
    MessageTemplateCreate, MessageTemplateUpdate, MessageTemplateResponse
)

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing message templates."""
    
    def __init__(self):
        self.variable_pattern = re.compile(r'\{\{(\w+)\}\}')
    
    async def create_template(
        self,
        data: MessageTemplateCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> MessageTemplateResponse:
        """Create a new message template."""
        # Check for duplicate name
        existing = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.agency_id == agency_id,
                MessageTemplate.name == data.name
            )
        )
        if existing.scalar_one_or_none():
            raise BadRequestError(f"Template with name '{data.name}' already exists")
        
        # Extract variables from content
        variables = self._extract_variables(data.content)
        
        # Create template
        template = MessageTemplate(
            agency_id=agency_id,
            created_by_id=user_id,
            name=data.name,
            category=data.category,
            subject=data.subject,
            content=data.content,
            variables=variables,
            tags=data.tags,
            is_global=data.is_global
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Created template '{template.name}' for agency {agency_id}")
        return MessageTemplateResponse.from_orm(template)
    
    async def update_template(
        self,
        template_id: UUID,
        data: MessageTemplateUpdate,
        agency_id: UUID,
        db: AsyncSession
    ) -> MessageTemplateResponse:
        """Update an existing template."""
        # Get template
        result = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.id == template_id,
                MessageTemplate.agency_id == agency_id
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundError("Template not found")
        
        # Check for duplicate name if updating
        if data.name and data.name != template.name:
            existing = await db.execute(
                select(MessageTemplate).where(
                    MessageTemplate.agency_id == agency_id,
                    MessageTemplate.name == data.name,
                    MessageTemplate.id != template_id
                )
            )
            if existing.scalar_one_or_none():
                raise BadRequestError(f"Template with name '{data.name}' already exists")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        
        # Re-extract variables if content updated
        if 'content' in update_data:
            update_data['variables'] = self._extract_variables(update_data['content'])
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(template)
        
        return MessageTemplateResponse.from_orm(template)
    
    async def delete_template(
        self,
        template_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a template."""
        result = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.id == template_id,
                MessageTemplate.agency_id == agency_id
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundError("Template not found")
        
        await db.delete(template)
        await db.commit()
        
        logger.info(f"Deleted template '{template.name}' from agency {agency_id}")
        return True
    
    async def get_template(
        self,
        template_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> MessageTemplateResponse:
        """Get a template by ID."""
        result = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.id == template_id,
                MessageTemplate.agency_id == agency_id
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundError("Template not found")
        
        return MessageTemplateResponse.from_orm(template)
    
    async def list_templates(
        self,
        agency_id: UUID,
        user_id: Optional[UUID] = None,
        category: Optional[TemplateCategory] = None,
        is_global: Optional[bool] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[MessageTemplateResponse]:
        """List templates with filtering."""
        query = select(MessageTemplate).where(
            MessageTemplate.agency_id == agency_id,
            MessageTemplate.is_active == True
        )
        
        # Filter by user access
        if user_id:
            query = query.where(
                or_(
                    MessageTemplate.is_global == True,
                    MessageTemplate.created_by_id == user_id
                )
            )
        
        # Apply filters
        if category:
            query = query.where(MessageTemplate.category == category)
        
        if is_global is not None:
            query = query.where(MessageTemplate.is_global == is_global)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    MessageTemplate.name.ilike(search_term),
                    MessageTemplate.content.ilike(search_term),
                    MessageTemplate.subject.ilike(search_term)
                )
            )
        
        if tags:
            for tag in tags:
                query = query.where(MessageTemplate.tags.contains([tag]))
        
        # Order by usage
        query = query.order_by(
            MessageTemplate.usage_count.desc(),
            MessageTemplate.created_at.desc()
        )
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return [MessageTemplateResponse.from_orm(t) for t in templates]
    
    async def get_popular_templates(
        self,
        agency_id: UUID,
        category: Optional[TemplateCategory] = None,
        limit: int = 10,
        db: AsyncSession = None
    ) -> List[MessageTemplateResponse]:
        """Get most popular templates by usage."""
        query = select(MessageTemplate).where(
            MessageTemplate.agency_id == agency_id,
            MessageTemplate.is_active == True,
            MessageTemplate.usage_count > 0
        )
        
        if category:
            query = query.where(MessageTemplate.category == category)
        
        query = query.order_by(MessageTemplate.usage_count.desc())
        query = query.limit(limit)
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return [MessageTemplateResponse.from_orm(t) for t in templates]
    
    async def duplicate_template(
        self,
        template_id: UUID,
        new_name: str,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> MessageTemplateResponse:
        """Duplicate an existing template."""
        # Get original template
        original = await self.get_template(template_id, agency_id, db)
        
        # Create duplicate
        duplicate_data = MessageTemplateCreate(
            name=new_name,
            category=original.category,
            subject=original.subject,
            content=original.content,
            tags=original.tags,
            is_global=False  # Duplicates are personal by default
        )
        
        return await self.create_template(duplicate_data, agency_id, user_id, db)
    
    async def increment_usage(
        self,
        template_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ):
        """Increment template usage count."""
        await db.execute(
            update(MessageTemplate)
            .where(
                MessageTemplate.id == template_id,
                MessageTemplate.agency_id == agency_id
            )
            .values(
                usage_count=MessageTemplate.usage_count + 1,
                last_used_at=datetime.utcnow()
            )
        )
        await db.commit()
    
    async def validate_template_content(
        self,
        content: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate template content and test variable substitution."""
        # Extract variables
        found_variables = self._extract_variables(content)
        
        # Test substitution if variables provided
        test_content = content
        if variables:
            for var, value in variables.items():
                placeholder = f"{{{{{var}}}}}"
                test_content = test_content.replace(placeholder, str(value))
        
        # Check for unmatched variables
        remaining_vars = self._extract_variables(test_content)
        
        return {
            "valid": len(remaining_vars) == 0 if variables else True,
            "found_variables": found_variables,
            "missing_values": remaining_vars,
            "test_output": test_content if variables else None
        }
    
    def _extract_variables(self, content: str) -> List[str]:
        """Extract variable names from template content."""
        matches = self.variable_pattern.findall(content)
        return list(set(matches))  # Remove duplicates
    
    async def get_template_analytics(
        self,
        agency_id: UUID,
        days: int = 30,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get analytics for template usage."""
        # Get usage stats
        result = await db.execute(
            select(
                func.count(MessageTemplate.id).label('total_templates'),
                func.sum(MessageTemplate.usage_count).label('total_usage'),
                func.avg(MessageTemplate.usage_count).label('avg_usage')
            ).where(
                MessageTemplate.agency_id == agency_id,
                MessageTemplate.is_active == True
            )
        )
        stats = result.first()
        
        # Get category breakdown
        category_result = await db.execute(
            select(
                MessageTemplate.category,
                func.count(MessageTemplate.id).label('count'),
                func.sum(MessageTemplate.usage_count).label('usage')
            ).where(
                MessageTemplate.agency_id == agency_id,
                MessageTemplate.is_active == True
            ).group_by(MessageTemplate.category)
        )
        category_stats = category_result.all()
        
        # Get top tags
        # This is simplified - in production you'd want a proper tag aggregation
        tag_result = await db.execute(
            select(MessageTemplate.tags).where(
                MessageTemplate.agency_id == agency_id,
                MessageTemplate.is_active == True
            )
        )
        all_tags = []
        for row in tag_result:
            if row.tags:
                all_tags.extend(row.tags)
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_templates": stats.total_templates or 0,
            "total_usage": stats.total_usage or 0,
            "average_usage": float(stats.avg_usage or 0),
            "category_breakdown": [
                {
                    "category": cat.category,
                    "count": cat.count,
                    "usage": cat.usage or 0
                }
                for cat in category_stats
            ],
            "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags]
        }