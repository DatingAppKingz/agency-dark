"""
Messaging-specific permission service for controlling messaging features.

This service manages messaging permissions including bulk messaging,
automation, template management, and conversation access control.
"""
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import json
import re

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, MessagePermission
)
from core.security.feature_permissions.service import feature_permission_service
from core.logger import get_logger
from core.exceptions import PermissionDeniedError, QuotaExceededError
from core.redis import redis_client


logger = get_logger(__name__)


class MessagingPermissionService:
    """Service for managing messaging-specific permissions."""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes
        self.rate_window = 3600  # 1 hour
    
    async def can_send_message(
        self,
        db: AsyncSession,
        user: User,
        message_type: str = "individual",
        recipient_count: int = 1,
        chat_id: Optional[str] = None,
        is_automated: bool = False
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if user can send a message.
        
        Returns:
            Tuple of (allowed, denial_reason, limits)
        """
        # Determine action based on message type
        if message_type == "bulk" or recipient_count > 1:
            action = "send_bulk"
        else:
            action = "send_message"
        
        # Prepare context
        context = {
            "message_type": message_type,
            "recipient_count": recipient_count,
            "chat_id": chat_id,
            "is_automated": is_automated
        }
        
        # Check basic feature permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.MESSAGING, action, chat_id, context
        )
        
        if not allowed:
            return False, reason, None
        
        # Get messaging permissions
        permissions = await self._get_messaging_permissions(db, user)
        
        if not permissions:
            return False, "No messaging permissions configured", None
        
        # Check specific permissions
        limits = await self._get_messaging_limits(permissions)
        
        # Check bulk recipient limit
        if action == "send_bulk" and limits["max_bulk_recipients"]:
            if recipient_count > limits["max_bulk_recipients"]:
                return False, f"Recipient count exceeds limit of {limits['max_bulk_recipients']}", limits
        
        # Check automation permission
        if is_automated and not limits["can_use_automation"]:
            return False, "No permission to use automation", limits
        
        # Check rate limits
        if limits["max_messages_per_hour"]:
            current_usage = await self._get_message_usage(db, user)
            if current_usage >= limits["max_messages_per_hour"]:
                return False, f"Message rate limit exceeded ({current_usage}/{limits['max_messages_per_hour']} per hour)", limits
        
        # Check conversation access
        if chat_id and not limits["can_access_all_conversations"]:
            if not await self._can_access_conversation(db, user, chat_id):
                return False, "No permission to access this conversation", limits
        
        return True, None, limits
    
    async def _get_messaging_permissions(
        self,
        db: AsyncSession,
        user: User
    ) -> List[FeaturePermission]:
        """Get messaging permissions for user."""
        return await feature_permission_service.get_user_permissions(
            db, user, FeatureType.MESSAGING
        )
    
    async def _get_messaging_limits(
        self,
        permissions: List[FeaturePermission]
    ) -> Dict[str, Any]:
        """Extract messaging limits from permissions."""
        limits = {
            "allowed_actions": set(),
            "max_bulk_recipients": None,
            "max_messages_per_hour": None,
            "can_use_automation": False,
            "can_access_all_conversations": False,
            "can_edit_templates": False,
            "can_approve_scheduled": False,
            "can_export_chats": False,
            "requires_approval_for_bulk": False
        }
        
        for perm in permissions:
            # Collect allowed message permissions
            if perm.message_permissions:
                for mp in perm.message_permissions:
                    if mp in [p.value for p in MessagePermission]:
                        limits["allowed_actions"].add(mp)
            
            # Get max values
            if perm.max_bulk_recipients:
                if limits["max_bulk_recipients"] is None or perm.max_bulk_recipients > limits["max_bulk_recipients"]:
                    limits["max_bulk_recipients"] = perm.max_bulk_recipients
            
            if perm.max_messages_per_hour:
                if limits["max_messages_per_hour"] is None or perm.max_messages_per_hour > limits["max_messages_per_hour"]:
                    limits["max_messages_per_hour"] = perm.max_messages_per_hour
            
            # Check boolean permissions
            if perm.can_use_automation:
                limits["can_use_automation"] = True
            
            if perm.can_access_all_conversations:
                limits["can_access_all_conversations"] = True
        
        # Map specific permissions
        if MessagePermission.EDIT_TEMPLATES.value in limits["allowed_actions"]:
            limits["can_edit_templates"] = True
        
        if MessagePermission.APPROVE_SCHEDULED.value in limits["allowed_actions"]:
            limits["can_approve_scheduled"] = True
        
        if MessagePermission.EXPORT_CHATS.value in limits["allowed_actions"]:
            limits["can_export_chats"] = True
        
        return limits
    
    async def _get_message_usage(
        self,
        db: AsyncSession,
        user: User
    ) -> int:
        """Get message count in current rate window."""
        # Check cache
        cache_key = f"message_usage:{user.id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return int(cached)
        
        # Query from usage logs
        since = datetime.utcnow() - timedelta(seconds=self.rate_window)
        
        # In production, would query actual message table
        # For now, return mock value
        count = 0
        
        # Cache result
        ttl = self.rate_window - int((datetime.utcnow() - since).total_seconds())
        if ttl > 0:
            await redis_client.setex(cache_key, ttl, str(count))
        
        return count
    
    async def _can_access_conversation(
        self,
        db: AsyncSession,
        user: User,
        chat_id: str
    ) -> bool:
        """Check if user can access a specific conversation."""
        # Check cache
        cache_key = f"chat_access:{user.id}:{chat_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached == "1"
        
        # Check access rules based on role
        can_access = False
        
        if user.role == UserRole.MODEL:
            # Models can access their own chats
            # Would query chat table to check ownership
            can_access = True  # Simplified
        
        elif user.role == UserRole.CHATTER:
            # Chatters can access assigned model chats
            # Would query assignment table
            can_access = True  # Simplified
        
        elif user.role in [UserRole.MANAGER, UserRole.ADMIN]:
            # Managers and admins can access agency chats
            can_access = True
        
        # Cache result
        await redis_client.setex(cache_key, self.cache_ttl, "1" if can_access else "0")
        
        return can_access
    
    async def can_manage_templates(
        self,
        db: AsyncSession,
        user: User,
        action: str = "view"
    ) -> Tuple[bool, Optional[str]]:
        """Check if user can manage message templates."""
        # Map action to permission
        if action in ["create", "edit", "delete"]:
            required_action = "edit_template"
        else:
            required_action = "view_templates"
        
        # Check permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.MESSAGING, required_action
        )
        
        return allowed, reason
    
    async def create_message_template(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        content: str,
        category: str,
        variables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a message template with permission check."""
        # Check permission
        allowed, reason = await self.can_manage_templates(db, user, "create")
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot create template: {reason}")
        
        # Validate template content
        if not self._validate_template_content(content):
            raise ValueError("Invalid template content")
        
        # Extract variables if not provided
        if variables is None:
            variables = self._extract_template_variables(content)
        
        # Create template (in production would save to database)
        template = {
            "id": f"template_{user.id}_{datetime.utcnow().timestamp()}",
            "name": name,
            "content": content,
            "category": category,
            "variables": variables,
            "created_by": str(user.id),
            "created_at": datetime.utcnow().isoformat(),
            "agency_id": str(user.agency_id) if user.agency_id else None
        }
        
        # Cache template
        cache_key = f"message_template:{template['id']}"
        await redis_client.setex(cache_key, 86400, json.dumps(template))
        
        return template
    
    def _validate_template_content(self, content: str) -> bool:
        """Validate template content for safety."""
        # Check for malicious patterns
        forbidden_patterns = [
            r'<script',
            r'javascript:',
            r'on\w+\s*=',  # onclick, onload, etc.
            r'data:text/html'
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        
        # Check length
        if len(content) > 10000:  # 10KB limit
            return False
        
        return True
    
    def _extract_template_variables(self, content: str) -> List[str]:
        """Extract variable placeholders from template."""
        # Find {{variable}} patterns
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)
        return list(set(matches))
    
    async def schedule_message(
        self,
        db: AsyncSession,
        user: User,
        message_data: Dict[str, Any],
        scheduled_time: datetime,
        recipient_count: int = 1
    ) -> Dict[str, Any]:
        """Schedule a message for future sending."""
        # Check permission to send
        allowed, reason, limits = await self.can_send_message(
            db, user,
            message_type="bulk" if recipient_count > 1 else "individual",
            recipient_count=recipient_count
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot schedule message: {reason}")
        
        # Check if scheduling requires approval
        requires_approval = False
        if recipient_count > 10:  # Arbitrary threshold
            # Check if user can approve their own scheduled messages
            can_approve, _ = await feature_permission_service.check_feature_permission(
                db, user, FeatureType.MESSAGING, "approve_scheduled"
            )
            requires_approval = not can_approve
        
        # Create scheduled message (in production would save to database)
        scheduled = {
            "id": f"scheduled_{user.id}_{datetime.utcnow().timestamp()}",
            "message_data": message_data,
            "scheduled_time": scheduled_time.isoformat(),
            "recipient_count": recipient_count,
            "created_by": str(user.id),
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending_approval" if requires_approval else "scheduled",
            "requires_approval": requires_approval
        }
        
        # Cache scheduled message
        cache_key = f"scheduled_message:{scheduled['id']}"
        await redis_client.setex(
            cache_key,
            int((scheduled_time - datetime.utcnow()).total_seconds()) + 3600,
            json.dumps(scheduled)
        )
        
        return scheduled
    
    async def approve_scheduled_message(
        self,
        db: AsyncSession,
        user: User,
        scheduled_id: str
    ) -> bool:
        """Approve a scheduled message."""
        # Check permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.MESSAGING, "approve_scheduled"
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot approve scheduled messages: {reason}")
        
        # Get scheduled message
        cache_key = f"scheduled_message:{scheduled_id}"
        scheduled_data = await redis_client.get(cache_key)
        
        if not scheduled_data:
            raise ValueError("Scheduled message not found")
        
        scheduled = json.loads(scheduled_data)
        
        # Update status
        scheduled["status"] = "scheduled"
        scheduled["approved_by"] = str(user.id)
        scheduled["approved_at"] = datetime.utcnow().isoformat()
        
        # Update cache
        ttl = await redis_client.ttl(cache_key)
        if ttl > 0:
            await redis_client.setex(cache_key, ttl, json.dumps(scheduled))
        
        return True
    
    async def get_conversation_history(
        self,
        db: AsyncSession,
        user: User,
        chat_id: str,
        limit: int = 100,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """Get conversation history with permission check."""
        # Check permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.MESSAGING, "view_history", chat_id
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot view conversation history: {reason}")
        
        # Check conversation access
        permissions = await self._get_messaging_permissions(db, user)
        limits = await self._get_messaging_limits(permissions)
        
        if not limits["can_access_all_conversations"]:
            if not await self._can_access_conversation(db, user, chat_id):
                raise PermissionDeniedError("No permission to access this conversation")
        
        # In production, would query message table
        # Return mock data
        messages = []
        
        # Filter metadata if not permitted
        if not include_metadata and messages:
            for msg in messages:
                msg.pop("metadata", None)
                msg.pop("internal_notes", None)
        
        return messages
    
    async def export_chat_history(
        self,
        db: AsyncSession,
        user: User,
        chat_ids: List[str],
        format: str = "json",
        date_range: Optional[Dict[str, datetime]] = None
    ) -> Dict[str, Any]:
        """Export chat history with permission check."""
        # Check export permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.MESSAGING, "export_chats"
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot export chats: {reason}")
        
        # Check access to each chat
        permissions = await self._get_messaging_permissions(db, user)
        limits = await self._get_messaging_limits(permissions)
        
        accessible_chats = []
        for chat_id in chat_ids:
            if limits["can_access_all_conversations"] or await self._can_access_conversation(db, user, chat_id):
                accessible_chats.append(chat_id)
        
        if not accessible_chats:
            raise PermissionDeniedError("No accessible chats to export")
        
        # Create export job (in production would queue for processing)
        export_job = {
            "id": f"export_{user.id}_{datetime.utcnow().timestamp()}",
            "chat_ids": accessible_chats,
            "format": format,
            "date_range": date_range,
            "requested_by": str(user.id),
            "requested_at": datetime.utcnow().isoformat(),
            "status": "processing"
        }
        
        return export_job
    
    async def get_messaging_stats(
        self,
        db: AsyncSession,
        user: User
    ) -> Dict[str, Any]:
        """Get user's messaging statistics and limits."""
        # Get permissions and limits
        permissions = await self._get_messaging_permissions(db, user)
        limits = await self._get_messaging_limits(permissions)
        
        # Get current usage
        current_usage = await self._get_message_usage(db, user)
        
        # Get quota usage
        daily_quota, daily_limit = await feature_permission_service.check_quota_usage(
            db, user, permissions[0] if permissions else None, "daily"
        )
        
        return {
            "limits": {
                "max_bulk_recipients": limits["max_bulk_recipients"],
                "max_messages_per_hour": limits["max_messages_per_hour"],
                "can_use_automation": limits["can_use_automation"],
                "can_access_all_conversations": limits["can_access_all_conversations"]
            },
            "usage": {
                "messages_this_hour": current_usage,
                "messages_today": daily_quota,
                "daily_limit": daily_limit
            },
            "permissions": list(limits["allowed_actions"])
        }


# Global instance
messaging_permission_service = MessagingPermissionService()