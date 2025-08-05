"""
User repository with role-specific filtering.
"""
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_simple import User, UserRole
from models.model_assignment import ModelAssignment
from core.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with enhanced filtering."""
    
    def __init__(self, db: AsyncSession, current_user: Optional[User] = None):
        super().__init__(User, db, current_user)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email with agency filtering."""
        query = select(User).where(User.email == email)
        query = await self.apply_filters_async(query)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """Get users by role with agency filtering."""
        return await self.get_all(
            skip=skip,
            limit=limit,
            filters=[User.role == role.value]
        )
    
    async def get_models_for_chatter(self, chatter_id: str) -> List[User]:
        """Get all models assigned to a chatter."""
        if not self.current_user or self.current_user.role != UserRole.CHATTER.value:
            return []
        
        # Get assigned model user IDs
        query = select(ModelAssignment.model_id).where(
            and_(
                ModelAssignment.chatter_id == chatter_id,
                ModelAssignment.is_active == True
            )
        )
        result = await self.db.execute(query)
        model_ids = [row[0] for row in result.fetchall()]
        
        if not model_ids:
            return []
        
        # Get the model users
        query = select(User).where(
            and_(
                User.id.in_(model_ids),
                User.role == UserRole.MODEL.value,
                User.is_active == True
            )
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_chatters_for_model(self, model_id: str) -> List[User]:
        """Get all chatters assigned to a model."""
        # Check permissions
        if self.current_user:
            if self.current_user.role == UserRole.MODEL.value and str(self.current_user.id) != model_id:
                return []  # Models can only see their own chatters
            elif self.current_user.role not in [
                UserRole.SUPER_ADMIN.value,
                UserRole.AGENCY_OWNER.value,
                UserRole.AGENCY_ADMIN.value,
                UserRole.MODEL.value
            ]:
                return []  # Others can't see chatter assignments
        
        # Get assigned chatter IDs
        query = select(ModelAssignment.chatter_id).where(
            and_(
                ModelAssignment.model_id == model_id,
                ModelAssignment.is_active == True
            )
        )
        result = await self.db.execute(query)
        chatter_ids = [row[0] for row in result.fetchall()]
        
        if not chatter_ids:
            return []
        
        # Get the chatter users
        query = select(User).where(
            and_(
                User.id.in_(chatter_ids),
                User.role == UserRole.CHATTER.value,
                User.is_active == True
            )
        )
        
        # Apply agency filter for non-super admins
        if self.current_user and self.current_user.role != UserRole.SUPER_ADMIN.value:
            query = query.where(User.agency_id == self.current_user.agency_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def search_users(
        self, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[User]:
        """Search users by name or email with agency filtering."""
        search_pattern = f"%{search_term}%"
        
        return await self.get_all(
            skip=skip,
            limit=limit,
            filters=[
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern)
                )
            ]
        )