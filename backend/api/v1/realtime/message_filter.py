"""
Message filtering service for real-time WebSocket communications.
"""
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.filters.websocket_filter import WebSocketMessageFilter
from core.logger import get_logger
from models.user import User, UserRole
from models.model import Model
from models.model_assignment import ModelAssignment
from models.chat import Conversation

logger = get_logger(__name__)


class RealtimeMessageFilterService:
    """Service for filtering real-time messages with database integration."""
    
    def __init__(self):
        # Cache for performance
        self.conversation_access_cache: Dict[str, Set[str]] = {}  # conversation_id -> set of user_ids
        self.model_assignment_cache: Dict[str, Set[str]] = {}  # chatter_id -> set of model_ids
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
    
    async def filter_message_for_users(
        self, 
        message: Dict[str, Any], 
        message_type: str,
        user_contexts: List[Dict[str, Any]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Filter a message for multiple users based on their permissions.
        
        Args:
            message: The message to filter
            message_type: Type of message
            user_contexts: List of user contexts to filter for
            
        Returns:
            Dict mapping user_id to filtered message (or None if filtered out)
        """
        results = {}
        
        for user_context in user_contexts:
            user_id = user_context.get("user_id")
            filter = WebSocketMessageFilter(user_context)
            
            # Apply filtering with database checks
            if message_type == "chat_message":
                filtered = await self._filter_chat_message_with_db(message, user_context)
            elif message_type == "presence":
                filtered = await self._filter_presence_with_db(message, user_context)
            else:
                filtered = await filter.filter_message(message, message_type)
            
            results[user_id] = filtered
        
        return results
    
    async def get_conversation_participants(self, conversation_id: int) -> Set[str]:
        """Get all users who should receive messages for a conversation."""
        # Check cache first
        cache_key = f"conv:{conversation_id}"
        if self._is_cache_valid(cache_key):
            return self.conversation_access_cache.get(cache_key, set())
        
        participants = set()
        
        async with AsyncSessionLocal() as db:
            # Get conversation details
            conversation = await db.get(Conversation, conversation_id)
            if not conversation:
                return participants
            
            # Add model
            if conversation.model_id:
                model = await db.get(Model, conversation.model_id)
                if model and model.user_id:
                    participants.add(str(model.user_id))
            
            # Add assigned chatter
            if conversation.assigned_chatter_id:
                participants.add(str(conversation.assigned_chatter_id))
            
            # Add agency admins
            agency_admins = await self._get_agency_admins(db, conversation.agency_id)
            participants.update(agency_admins)
            
            # Add super admins
            super_admins = await self._get_super_admins(db)
            participants.update(super_admins)
        
        # Cache the result
        self.conversation_access_cache[cache_key] = participants
        self.cache_timestamps[cache_key] = datetime.utcnow()
        
        return participants
    
    async def get_users_for_agency_broadcast(self, agency_id: str) -> Set[str]:
        """Get all users who should receive agency-wide broadcasts."""
        users = set()
        
        async with AsyncSessionLocal() as db:
            # Get all users in agency
            result = await db.execute(
                select(User.id).where(
                    User.agency_id == agency_id,
                    User.is_active == True
                )
            )
            agency_users = [str(row[0]) for row in result.fetchall()]
            users.update(agency_users)
            
            # Add super admins
            super_admins = await self._get_super_admins(db)
            users.update(super_admins)
        
        return users
    
    async def validate_message_recipient(
        self, 
        sender_context: Dict[str, Any],
        recipient_id: str,
        message_type: str
    ) -> bool:
        """Validate if sender can send message to recipient."""
        sender_id = sender_context.get("user_id")
        sender_role = sender_context.get("role")
        sender_agency = sender_context.get("agency_id")
        
        # Super admins can message anyone
        if sender_context.get("is_super_admin"):
            return True
        
        async with AsyncSessionLocal() as db:
            # Get recipient info
            recipient = await db.get(User, recipient_id)
            if not recipient or not recipient.is_active:
                return False
            
            # Check agency match (except for super admins)
            if recipient.role != UserRole.SUPER_ADMIN:
                if str(recipient.agency_id) != str(sender_agency):
                    logger.warning(
                        f"Cross-agency message blocked: {sender_id} -> {recipient_id}"
                    )
                    return False
            
            # Role-based validation
            if sender_role == UserRole.MODEL:
                # Models can message assigned chatters and agency admins
                if recipient.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                    return True
                elif recipient.role == UserRole.CHATTER:
                    return await self._is_model_assigned_to_chatter(
                        db, sender_id, recipient_id
                    )
            
            elif sender_role == UserRole.CHATTER:
                # Chatters can message assigned models and agency admins
                if recipient.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                    return True
                elif recipient.role == UserRole.MODEL:
                    return await self._is_chatter_assigned_to_model(
                        db, sender_id, recipient_id
                    )
            
            elif sender_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Agency admins can message anyone in their agency
                return True
            
            elif sender_role == UserRole.AGENCY_STAFF:
                # Staff can only message admins
                return recipient.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]
        
        return False
    
    async def filter_message_history(
        self, 
        messages: List[Dict[str, Any]], 
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter historical messages based on user permissions."""
        filter = WebSocketMessageFilter(user_context)
        filtered_messages = []
        
        for message in messages:
            filtered = await filter.filter_message(message, "chat_message")
            if filtered:
                filtered_messages.append(filtered)
        
        return filtered_messages
    
    # Private helper methods
    
    async def _filter_chat_message_with_db(
        self, 
        message: Dict[str, Any], 
        user_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Filter chat message with database checks."""
        conversation_id = message.get("conversation_id")
        user_id = user_context.get("user_id")
        role = user_context.get("role")
        
        # Get conversation participants
        participants = await self.get_conversation_participants(conversation_id)
        
        # Check if user is a participant
        if user_id in participants:
            return message
        
        # Additional checks for specific roles
        if role == UserRole.CHATTER:
            # Double-check chatter assignment
            if await self._verify_chatter_assignment(user_id, conversation_id):
                return message
        
        logger.debug(
            f"Message filtered out for user {user_id} in conversation {conversation_id}"
        )
        return None
    
    async def _filter_presence_with_db(
        self, 
        presence: Dict[str, Any], 
        user_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Filter presence with database checks for assignments."""
        target_user_id = presence.get("user_id")
        user_id = user_context.get("user_id")
        role = user_context.get("role")
        
        # Check if we need to verify assignment
        if role == UserRole.CHATTER:
            # Check if chatter can see this model's presence
            cache_key = f"chatter:{user_id}"
            if self._is_cache_valid(cache_key):
                assigned_models = self.model_assignment_cache.get(cache_key, set())
                if target_user_id not in assigned_models:
                    return None
            else:
                # Fetch from database
                if not await self._is_chatter_assigned_to_user(user_id, target_user_id):
                    return None
        
        elif role == UserRole.MODEL:
            # Check if model can see this chatter's presence
            if not await self._is_model_assigned_to_chatter_direct(target_user_id, user_id):
                return None
        
        # Use base filter for other checks
        filter = WebSocketMessageFilter(user_context)
        return await filter.filter_message(presence, "presence")
    
    async def _get_agency_admins(self, db: AsyncSession, agency_id: str) -> Set[str]:
        """Get all admin users for an agency."""
        result = await db.execute(
            select(User.id).where(
                User.agency_id == agency_id,
                User.role.in_([UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]),
                User.is_active == True
            )
        )
        return {str(row[0]) for row in result.fetchall()}
    
    async def _get_super_admins(self, db: AsyncSession) -> Set[str]:
        """Get all super admin users."""
        result = await db.execute(
            select(User.id).where(
                User.role == UserRole.SUPER_ADMIN,
                User.is_active == True
            )
        )
        return {str(row[0]) for row in result.fetchall()}
    
    async def _is_chatter_assigned_to_model(
        self, 
        db: AsyncSession, 
        chatter_id: str, 
        model_user_id: str
    ) -> bool:
        """Check if chatter is assigned to a model."""
        # Get model ID from user ID
        result = await db.execute(
            select(Model.id).where(Model.user_id == model_user_id)
        )
        model_id = result.scalar_one_or_none()
        
        if not model_id:
            return False
        
        # Check assignment
        result = await db.execute(
            select(ModelAssignment).where(
                ModelAssignment.chatter_id == chatter_id,
                ModelAssignment.model_id == model_id,
                ModelAssignment.is_active == True
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def _is_model_assigned_to_chatter(
        self, 
        db: AsyncSession, 
        model_user_id: str, 
        chatter_id: str
    ) -> bool:
        """Check if model has the specified chatter assigned."""
        # Get model ID from user ID
        result = await db.execute(
            select(Model.id).where(Model.user_id == model_user_id)
        )
        model_id = result.scalar_one_or_none()
        
        if not model_id:
            return False
        
        # Check assignment
        result = await db.execute(
            select(ModelAssignment).where(
                ModelAssignment.model_id == model_id,
                ModelAssignment.chatter_id == chatter_id,
                ModelAssignment.is_active == True
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def _verify_chatter_assignment(self, chatter_id: str, conversation_id: int) -> bool:
        """Verify chatter is assigned to conversation."""
        async with AsyncSessionLocal() as db:
            conversation = await db.get(Conversation, conversation_id)
            if not conversation:
                return False
            
            # Check direct assignment
            if str(conversation.assigned_chatter_id) == chatter_id:
                return True
            
            # Check model assignment
            if conversation.model_id:
                result = await db.execute(
                    select(ModelAssignment).where(
                        ModelAssignment.model_id == conversation.model_id,
                        ModelAssignment.chatter_id == chatter_id,
                        ModelAssignment.is_active == True
                    )
                )
                return result.scalar_one_or_none() is not None
        
        return False
    
    async def _is_chatter_assigned_to_user(self, chatter_id: str, user_id: str) -> bool:
        """Check if chatter is assigned to a user (who is a model)."""
        async with AsyncSessionLocal() as db:
            # Get model ID from user ID
            result = await db.execute(
                select(Model.id).where(Model.user_id == user_id)
            )
            model_id = result.scalar_one_or_none()
            
            if not model_id:
                return False
            
            # Check assignment
            result = await db.execute(
                select(ModelAssignment).where(
                    ModelAssignment.chatter_id == chatter_id,
                    ModelAssignment.model_id == model_id,
                    ModelAssignment.is_active == True
                )
            )
            assigned = result.scalar_one_or_none() is not None
            
            # Update cache
            cache_key = f"chatter:{chatter_id}"
            if cache_key not in self.model_assignment_cache:
                self.model_assignment_cache[cache_key] = set()
            
            if assigned:
                self.model_assignment_cache[cache_key].add(user_id)
            
            self.cache_timestamps[cache_key] = datetime.utcnow()
            
            return assigned
    
    async def _is_model_assigned_to_chatter_direct(self, chatter_id: str, model_user_id: str) -> bool:
        """Direct check if model has chatter assigned."""
        return await self._is_chatter_assigned_to_user(chatter_id, model_user_id)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = (datetime.utcnow() - self.cache_timestamps[cache_key]).total_seconds()
        return age < self.cache_ttl
    
    def clear_cache(self):
        """Clear all caches."""
        self.conversation_access_cache.clear()
        self.model_assignment_cache.clear()
        self.cache_timestamps.clear()
    
    def clear_conversation_cache(self, conversation_id: int):
        """Clear cache for a specific conversation."""
        cache_key = f"conv:{conversation_id}"
        self.conversation_access_cache.pop(cache_key, None)
        self.cache_timestamps.pop(cache_key, None)
    
    def clear_assignment_cache(self, chatter_id: str):
        """Clear assignment cache for a chatter."""
        cache_key = f"chatter:{chatter_id}"
        self.model_assignment_cache.pop(cache_key, None)
        self.cache_timestamps.pop(cache_key, None)


# Global message filter service
message_filter_service = RealtimeMessageFilterService()