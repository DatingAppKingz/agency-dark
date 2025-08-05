"""
Agency-based query filters for automatic data scoping.
"""
from typing import Optional, Type, Any
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Query
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_simple import User, UserRole
from models.base import Base
import logging

logger = logging.getLogger(__name__)


class AgencyFilter:
    """Base class for applying agency-based filters to queries."""
    
    def __init__(self, current_user: User):
        self.current_user = current_user
        self.user_role = current_user.role if current_user else None
        self.agency_id = current_user.agency_id if current_user else None
    
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.user_role == UserRole.SUPER_ADMIN.value
    
    def is_agency_admin(self) -> bool:
        """Check if user is an agency admin or owner."""
        return self.user_role in [
            UserRole.AGENCY_OWNER.value,
            UserRole.AGENCY_ADMIN.value
        ]
    
    def is_model(self) -> bool:
        """Check if user is a model."""
        return self.user_role == UserRole.MODEL.value
    
    def is_chatter(self) -> bool:
        """Check if user is a chatter."""
        return self.user_role == UserRole.CHATTER.value
    
    def apply_filter(self, query: Select, model_class: Type[Base]) -> Select:
        """
        Apply agency-based filtering to a query.
        
        Args:
            query: The SQLAlchemy select query
            model_class: The model class being queried
            
        Returns:
            The filtered query
        """
        # Super admins see everything
        if self.is_super_admin():
            return query
        
        # Check if model has agency_id field
        if not hasattr(model_class, 'agency_id'):
            logger.warning(
                f"Model {model_class.__name__} does not have agency_id field. "
                "No agency filtering applied."
            )
            return query
        
        # Apply agency filter for non-super admins
        if self.agency_id:
            return query.where(model_class.agency_id == self.agency_id)
        else:
            # User has no agency - return empty result
            logger.warning(
                f"User {self.current_user.email} has no agency_id. "
                "Returning empty query."
            )
            return query.where(model_class.id == None)  # Will return no results


class UserFilter(AgencyFilter):
    """Filter for User model with role-specific logic."""
    
    def apply_filter(self, query: Select, model_class: Type[Base] = None) -> Select:
        """Apply user-specific filtering."""
        from models.user_simple import User
        
        # Super admins see all users
        if self.is_super_admin():
            return query
        
        # Agency admins see users in their agency
        if self.is_agency_admin() and self.agency_id:
            return query.where(User.agency_id == self.agency_id)
        
        # Models see only themselves
        if self.is_model():
            return query.where(User.id == self.current_user.id)
        
        # Chatters see themselves and assigned models
        if self.is_chatter():
            # This will be enhanced when we implement chatter-model filtering
            return query.where(User.id == self.current_user.id)
        
        # Agency members see only themselves
        return query.where(User.id == self.current_user.id)


class ModelFilter(AgencyFilter):
    """Filter for Model profiles with role-specific logic."""
    
    def __init__(self, current_user: User, db: AsyncSession):
        super().__init__(current_user)
        self.db = db
    
    async def apply_filter_async(self, query: Select) -> Select:
        """Apply model-specific filtering with async support for assignments."""
        from models.model import Model
        from models.model_assignment import ModelAssignment
        
        # Super admins see all models
        if self.is_super_admin():
            return query
        
        # Agency admins see models in their agency
        if self.is_agency_admin() and self.agency_id:
            return query.where(Model.agency_id == self.agency_id)
        
        # Models see only themselves
        if self.is_model():
            return query.where(Model.user_id == self.current_user.id)
        
        # Chatters see only assigned models
        if self.is_chatter():
            # Get assigned model IDs
            assignments_query = select(ModelAssignment.model_id).where(
                and_(
                    ModelAssignment.chatter_id == self.current_user.id,
                    ModelAssignment.is_active == True
                )
            )
            result = await self.db.execute(assignments_query)
            assigned_model_ids = [row[0] for row in result.fetchall()]
            
            if assigned_model_ids:
                return query.where(Model.user_id.in_(assigned_model_ids))
            else:
                # No assignments - return empty result
                return query.where(Model.id == None)
        
        # Others see nothing
        return query.where(Model.id == None)


class TransactionFilter(AgencyFilter):
    """Filter for financial transactions."""
    
    def apply_filter(self, query: Select) -> Select:
        """Apply transaction-specific filtering."""
        from models.financial import Transaction
        
        # Super admins see all transactions
        if self.is_super_admin():
            return query
        
        # Agency admins see agency transactions
        if self.is_agency_admin() and self.agency_id:
            # Transactions don't have direct agency_id, need to join with model
            from models.model import Model
            return query.join(Model, Transaction.model_id == Model.id).where(
                Model.agency_id == self.agency_id
            )
        
        # Models see only their transactions
        if self.is_model():
            from models.model import Model
            return query.join(Model, Transaction.model_id == Model.id).where(
                Model.user_id == self.current_user.id
            )
        
        # Others see nothing
        return query.where(Transaction.id == None)


class ChatFilter(AgencyFilter):
    """Filter for chat conversations."""
    
    def __init__(self, current_user: User, db: AsyncSession):
        super().__init__(current_user)
        self.db = db
    
    async def apply_filter_async(self, query: Select) -> Select:
        """Apply chat-specific filtering."""
        from models.chat import Conversation
        from models.model_assignment import ModelAssignment
        
        # Super admins see all chats
        if self.is_super_admin():
            return query
        
        # Agency admins see agency chats
        if self.is_agency_admin() and self.agency_id:
            from models.model import Model
            return query.join(Model, Conversation.model_id == Model.id).where(
                Model.agency_id == self.agency_id
            )
        
        # Models see their own chats
        if self.is_model():
            from models.model import Model
            return query.join(Model, Conversation.model_id == Model.id).where(
                Model.user_id == self.current_user.id
            )
        
        # Chatters see chats for assigned models
        if self.is_chatter():
            # Get assigned model IDs
            assignments_query = select(ModelAssignment.model_id).where(
                and_(
                    ModelAssignment.chatter_id == self.current_user.id,
                    ModelAssignment.is_active == True
                )
            )
            result = await self.db.execute(assignments_query)
            assigned_model_ids = [row[0] for row in result.fetchall()]
            
            if assigned_model_ids:
                return query.where(Conversation.model_id.in_(assigned_model_ids))
            else:
                return query.where(Conversation.id == None)
        
        # Others see nothing
        return query.where(Conversation.id == None)


def get_filter_for_model(model_class: Type[Base], current_user: User, db: AsyncSession = None) -> AgencyFilter:
    """
    Get the appropriate filter for a model class.
    
    Args:
        model_class: The SQLAlchemy model class
        current_user: The current user
        db: Database session (required for some filters)
        
    Returns:
        The appropriate filter instance
    """
    from models.user_simple import User
    from models.model import Model
    from models.financial import Transaction
    from models.chat import Conversation
    
    filter_map = {
        User: UserFilter,
        Model: lambda u: ModelFilter(u, db),
        Transaction: TransactionFilter,
        Conversation: lambda u: ChatFilter(u, db)
    }
    
    filter_class = filter_map.get(model_class, AgencyFilter)
    
    if callable(filter_class):
        return filter_class(current_user)
    else:
        return filter_class(current_user)