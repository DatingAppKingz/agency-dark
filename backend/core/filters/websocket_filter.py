"""
WebSocket-specific filters for real-time message filtering and data isolation.
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import logging

from models.user import UserRole
from core.filters.agency_filter import AgencyFilter
from core.logger import get_logger

logger = get_logger(__name__)


class WebSocketMessageFilter:
    """Filter WebSocket messages based on user role and agency."""
    
    def __init__(self, user_context: Dict[str, Any]):
        self.user_context = user_context
        self.user_id = user_context.get("user_id")
        self.role = user_context.get("role")
        self.agency_id = user_context.get("agency_id")
        self.is_super_admin = user_context.get("is_super_admin", False)
        self.permissions = user_context.get("permissions", [])
    
    async def filter_message(self, message: Dict[str, Any], message_type: str) -> Optional[Dict[str, Any]]:
        """
        Filter a message based on user's permissions and role.
        
        Args:
            message: The message to filter
            message_type: Type of message (chat_message, notification, presence, etc.)
            
        Returns:
            Filtered message or None if user shouldn't see it
        """
        # Super admins see everything
        if self.is_super_admin:
            return message
        
        # Route to specific filter based on message type
        if message_type == "chat_message":
            return await self._filter_chat_message(message)
        elif message_type == "notification":
            return await self._filter_notification(message)
        elif message_type == "presence":
            return await self._filter_presence(message)
        elif message_type == "conversation_update":
            return await self._filter_conversation_update(message)
        elif message_type == "user_status":
            return await self._filter_user_status(message)
        else:
            # Unknown message type - filter conservatively
            logger.warning(f"Unknown message type: {message_type}")
            return await self._apply_default_filter(message)
    
    async def _filter_chat_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter chat messages based on conversation access."""
        conversation_id = message.get("conversation_id")
        sender_id = message.get("sender_id")
        agency_id = message.get("agency_id")
        
        # Check agency match first
        if not self._check_agency_access(agency_id):
            logger.debug(f"User {self.user_id} blocked from message in agency {agency_id}")
            return None
        
        # Role-specific filtering
        if self.role == UserRole.MODEL:
            # Models see messages in their conversations only
            # This would need to check if the model is in the conversation
            return message if self._is_model_in_conversation(conversation_id) else None
        
        elif self.role == UserRole.CHATTER:
            # Chatters see messages in assigned conversations only
            return message if self._is_chatter_assigned(conversation_id) else None
        
        elif self.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Agency admins see all messages in their agency
            return message
        
        else:
            # Other roles don't see chat messages
            return None
    
    async def _filter_notification(self, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter notifications based on relevance to user."""
        target_user_id = notification.get("target_user_id")
        target_agency_id = notification.get("target_agency_id")
        notification_type = notification.get("type")
        
        # Personal notifications
        if target_user_id and target_user_id == self.user_id:
            return notification
        
        # Agency-wide notifications
        if target_agency_id and target_agency_id == self.agency_id:
            # Check if user has permission to see this notification type
            if self._has_notification_permission(notification_type):
                return notification
        
        # System notifications for admins
        if notification_type == "system" and self.role in [
            UserRole.SUPER_ADMIN, 
            UserRole.AGENCY_OWNER, 
            UserRole.AGENCY_ADMIN
        ]:
            return notification
        
        return None
    
    async def _filter_presence(self, presence: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter presence updates based on visibility rules."""
        user_id = presence.get("user_id")
        user_role = presence.get("user_role")
        user_agency_id = presence.get("agency_id")
        
        # Super admins see all presence
        if self.is_super_admin:
            return presence
        
        # Check agency match for non-super admins
        if user_agency_id and user_agency_id != self.agency_id:
            return None
        
        # Role-based presence visibility
        if self.role == UserRole.MODEL:
            # Models see chatters assigned to them and agency admins
            if user_role in [UserRole.CHATTER, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                return presence
        
        elif self.role == UserRole.CHATTER:
            # Chatters see assigned models and agency admins
            if user_role in [UserRole.MODEL, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Additional check needed for model assignment
                return presence
        
        elif self.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Agency admins see all users in their agency
            return presence
        
        elif self.role == UserRole.AGENCY_STAFF:
            # Staff see limited presence (admins only)
            if user_role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                return presence
        
        return None
    
    async def _filter_conversation_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter conversation updates based on access."""
        conversation_id = update.get("conversation_id")
        agency_id = update.get("agency_id")
        
        # Check agency access
        if not self._check_agency_access(agency_id):
            return None
        
        # Check conversation access based on role
        if self.role == UserRole.MODEL:
            return update if self._is_model_in_conversation(conversation_id) else None
        elif self.role == UserRole.CHATTER:
            return update if self._is_chatter_assigned(conversation_id) else None
        elif self.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return update
        
        return None
    
    async def _filter_user_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter user status updates."""
        user_id = status.get("user_id")
        user_agency_id = status.get("agency_id")
        
        # Self status always visible
        if user_id == self.user_id:
            return status
        
        # Agency-based filtering
        if not self._check_agency_access(user_agency_id):
            return None
        
        # Sensitive fields removal for non-admins
        if self.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Remove sensitive fields
            filtered_status = status.copy()
            sensitive_fields = ["ip_address", "last_activity", "device_info"]
            for field in sensitive_fields:
                filtered_status.pop(field, None)
            return filtered_status
        
        return status
    
    async def _apply_default_filter(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply default conservative filtering for unknown message types."""
        # Check for agency_id field
        agency_id = message.get("agency_id")
        if agency_id and not self._check_agency_access(agency_id):
            return None
        
        # Check for user_id field (personal messages)
        target_user_id = message.get("target_user_id") or message.get("user_id")
        if target_user_id and target_user_id == self.user_id:
            return message
        
        # For unknown types, only admins see them
        if self.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return message
        
        return None
    
    def _check_agency_access(self, message_agency_id: Optional[str]) -> bool:
        """Check if user has access to content from a specific agency."""
        if self.is_super_admin:
            return True
        
        if not message_agency_id:
            # No agency specified - could be system message
            return self.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]
        
        return str(message_agency_id) == str(self.agency_id)
    
    def _is_model_in_conversation(self, conversation_id: str) -> bool:
        """Check if current user (model) is in the conversation."""
        # This would need to be implemented with actual database check
        # For now, return True as placeholder
        # TODO: Implement actual check
        return True
    
    def _is_chatter_assigned(self, conversation_id: str) -> bool:
        """Check if current user (chatter) is assigned to the conversation."""
        # This would need to be implemented with actual database check
        # For now, return True as placeholder
        # TODO: Implement actual check
        return True
    
    def _has_notification_permission(self, notification_type: str) -> bool:
        """Check if user has permission to see a notification type."""
        notification_permissions = {
            "new_message": [UserRole.MODEL, UserRole.CHATTER, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "new_fan": [UserRole.MODEL, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "payment": [UserRole.MODEL, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "assignment": [UserRole.CHATTER, UserRole.MODEL],
            "system": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "analytics": [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_STAFF]
        }
        
        allowed_roles = notification_permissions.get(notification_type, [])
        return self.role in allowed_roles


class WebSocketRoomFilter:
    """Filter room memberships and room-based broadcasts."""
    
    def __init__(self):
        self.room_memberships: Dict[str, Set[str]] = {}  # room_id -> set of user_ids
    
    async def can_join_room(self, user_context: Dict[str, Any], room_id: str, room_type: str) -> bool:
        """Check if user can join a specific room."""
        user_id = user_context.get("user_id")
        role = user_context.get("role")
        agency_id = user_context.get("agency_id")
        
        # Parse room ID
        if ":" in room_id:
            room_type, room_value = room_id.split(":", 1)
        else:
            room_value = room_id
        
        # Super admins can join any room
        if user_context.get("is_super_admin"):
            return True
        
        # Room type specific checks
        if room_type == "agency":
            return room_value == agency_id
        
        elif room_type == "user":
            return room_value == user_id
        
        elif room_type == "role":
            return room_value == role
        
        elif room_type == "conversation":
            # Need database check for conversation access
            return await self._check_conversation_access(user_context, room_value)
        
        elif room_type == "model":
            # Models join their own room, chatters need assignment
            if role == UserRole.MODEL:
                # Need to check if user is the model
                return await self._check_model_room_access(user_context, room_value)
            elif role == UserRole.CHATTER:
                # Need to check assignment
                return await self._check_chatter_model_access(user_context, room_value)
            elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Admins can monitor their agency's models
                return True  # With additional agency check
        
        return False
    
    async def filter_room_members(
        self, 
        room_id: str, 
        members: List[str], 
        requester_context: Dict[str, Any]
    ) -> List[str]:
        """Filter room members list based on who's asking."""
        role = requester_context.get("role")
        agency_id = requester_context.get("agency_id")
        
        # Super admins see all members
        if requester_context.get("is_super_admin"):
            return members
        
        # For agency rooms, filter by agency
        if room_id.startswith("agency:"):
            # Only show members from same agency
            # This would need actual user data to filter properly
            return members
        
        # For conversation rooms, show based on role
        if room_id.startswith("conversation:"):
            if role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                return members
            elif role in [UserRole.MODEL, UserRole.CHATTER]:
                # Only show relevant members (model, assigned chatter, admins)
                # This would need filtering based on actual roles
                return members[:3]  # Placeholder
        
        return members
    
    async def _check_conversation_access(self, user_context: Dict[str, Any], conversation_id: str) -> bool:
        """Check if user has access to a conversation."""
        # TODO: Implement with actual database check
        return True
    
    async def _check_model_room_access(self, user_context: Dict[str, Any], model_id: str) -> bool:
        """Check if user can access a model's room."""
        # TODO: Implement with actual database check
        return True
    
    async def _check_chatter_model_access(self, user_context: Dict[str, Any], model_id: str) -> bool:
        """Check if chatter is assigned to model."""
        # TODO: Implement with actual database check
        return True


class WebSocketPresenceFilter:
    """Filter presence information based on visibility rules."""
    
    def __init__(self):
        self.presence_data: Dict[str, Dict[str, Any]] = {}
    
    def filter_online_users(
        self, 
        all_users: List[Dict[str, Any]], 
        requester_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter online users list based on requester's permissions."""
        role = requester_context.get("role")
        agency_id = requester_context.get("agency_id")
        user_id = requester_context.get("user_id")
        
        # Super admins see everyone
        if requester_context.get("is_super_admin"):
            return all_users
        
        filtered_users = []
        
        for user in all_users:
            # Skip users from other agencies
            if user.get("agency_id") != agency_id:
                continue
            
            # Apply role-based filtering
            if role == UserRole.MODEL:
                # Models see chatters assigned to them and admins
                if user.get("role") in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                    filtered_users.append(user)
                elif user.get("role") == UserRole.CHATTER:
                    # Check if chatter is assigned (placeholder)
                    if self._is_chatter_assigned_to_model(user.get("id"), user_id):
                        filtered_users.append(user)
            
            elif role == UserRole.CHATTER:
                # Chatters see assigned models and admins
                if user.get("role") in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                    filtered_users.append(user)
                elif user.get("role") == UserRole.MODEL:
                    # Check if assigned to model (placeholder)
                    if self._is_chatter_assigned_to_model(user_id, user.get("id")):
                        filtered_users.append(user)
            
            elif role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                # Agency admins see all agency users
                filtered_users.append(user)
            
            elif role == UserRole.AGENCY_STAFF:
                # Staff see only admins
                if user.get("role") in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                    filtered_users.append(user)
        
        return filtered_users
    
    def _is_chatter_assigned_to_model(self, chatter_id: str, model_id: str) -> bool:
        """Check if chatter is assigned to model."""
        # TODO: Implement with actual assignment check
        return True


# Global filter instances
websocket_room_filter = WebSocketRoomFilter()
websocket_presence_filter = WebSocketPresenceFilter()