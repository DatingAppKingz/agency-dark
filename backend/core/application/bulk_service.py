"""Bulk operations service for processing multiple items efficiently."""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from datetime import datetime
import asyncio

from models.user import User
from models.chat import Conversation, Message
from models.model import Model
from models.agency import Agency
from core.exceptions import ValidationError, NotFoundError, PermissionError
from core.redis import redis_manager
from core.celery_app import celery_app as celery


class BulkService:
    """Service for handling bulk operations."""
    
    @staticmethod
    async def send_bulk_messages(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send messages to multiple conversations."""
        # Validate user permissions
        user = await db.get(User, user_id)
        if not user or user.agency_id != agency_id:
            raise PermissionError("User not authorized for this agency")
        
        # Extract data
        conversation_ids = message_data.get("conversation_ids", [])
        content = message_data.get("content")
        media_urls = message_data.get("media_urls", [])
        scheduled_at = message_data.get("scheduled_at")
        
        if not conversation_ids:
            raise ValidationError("No conversation IDs provided")
        if not content and not media_urls:
            raise ValidationError("Message must have content or media")
        
        # Verify conversations exist and belong to agency
        stmt = select(Conversation).where(
            and_(
                Conversation.id.in_(conversation_ids),
                Conversation.agency_id == agency_id
            )
        )
        result = await db.execute(stmt)
        conversations = result.scalars().all()
        
        if len(conversations) != len(conversation_ids):
            raise NotFoundError("Some conversations not found or not authorized")
        
        # If scheduled, create celery task
        if scheduled_at:
            task = celery.send_task(
                "tasks.send_bulk_messages",
                args=[conversation_ids, content, media_urls, user_id],
                eta=scheduled_at
            )
            
            return {
                "status": "scheduled",
                "task_id": task.id,
                "scheduled_at": scheduled_at,
                "conversation_count": len(conversation_ids)
            }
        
        # Send messages immediately
        created_messages = []
        failed_conversations = []
        
        for conversation in conversations:
            try:
                message = Message(
                    conversation_id=conversation.id,
                    sender_id=user_id,
                    sender_type="chatter",
                    content=content,
                    media_urls=media_urls,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.add(message)
                created_messages.append(message)
                
                # Update conversation last message time
                conversation.last_message_at = datetime.utcnow()
                
            except Exception as e:
                failed_conversations.append({
                    "conversation_id": conversation.id,
                    "error": str(e)
                })
        
        await db.commit()
        
        # Clear relevant caches
        for conv_id in conversation_ids:
            await redis_manager.delete(f"conversation:{conv_id}")
        
        return {
            "status": "completed",
            "sent_count": len(created_messages),
            "failed_count": len(failed_conversations),
            "failed_conversations": failed_conversations,
            "message_ids": [m.id for m in created_messages]
        }
    
    @staticmethod
    async def bulk_tag_conversations(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        tag_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add or remove tags from multiple conversations."""
        # Validate user permissions
        user = await db.get(User, user_id)
        if not user or user.agency_id != agency_id:
            raise PermissionError("User not authorized for this agency")
        
        conversation_ids = tag_data.get("conversation_ids", [])
        add_tags = tag_data.get("add_tags", [])
        remove_tags = tag_data.get("remove_tags", [])
        
        if not conversation_ids:
            raise ValidationError("No conversation IDs provided")
        if not add_tags and not remove_tags:
            raise ValidationError("No tags to add or remove")
        
        # Get conversations
        stmt = select(Conversation).where(
            and_(
                Conversation.id.in_(conversation_ids),
                Conversation.agency_id == agency_id
            )
        )
        result = await db.execute(stmt)
        conversations = result.scalars().all()
        
        if len(conversations) != len(conversation_ids):
            raise NotFoundError("Some conversations not found or not authorized")
        
        updated_count = 0
        failed_updates = []
        
        for conversation in conversations:
            try:
                current_tags = conversation.tags or []
                
                # Add new tags
                for tag in add_tags:
                    if tag not in current_tags:
                        current_tags.append(tag)
                
                # Remove tags
                for tag in remove_tags:
                    if tag in current_tags:
                        current_tags.remove(tag)
                
                conversation.tags = current_tags
                updated_count += 1
                
            except Exception as e:
                failed_updates.append({
                    "conversation_id": conversation.id,
                    "error": str(e)
                })
        
        await db.commit()
        
        # Clear caches
        for conv_id in conversation_ids:
            await redis_manager.delete(f"conversation:{conv_id}")
        
        return {
            "status": "completed",
            "updated_count": updated_count,
            "failed_count": len(failed_updates),
            "failed_updates": failed_updates
        }
    
    @staticmethod
    async def bulk_update_conversation_status(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        status_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update status for multiple conversations."""
        # Validate user permissions
        user = await db.get(User, user_id)
        if not user or user.agency_id != agency_id:
            raise PermissionError("User not authorized for this agency")
        
        conversation_ids = status_data.get("conversation_ids", [])
        new_status = status_data.get("status")
        priority = status_data.get("priority")
        
        if not conversation_ids:
            raise ValidationError("No conversation IDs provided")
        if not new_status and priority is None:
            raise ValidationError("No status or priority to update")
        
        # Build update statement
        update_values = {}
        if new_status:
            update_values["status"] = new_status
        if priority is not None:
            update_values["priority"] = priority
        update_values["updated_at"] = datetime.utcnow()
        
        stmt = update(Conversation).where(
            and_(
                Conversation.id.in_(conversation_ids),
                Conversation.agency_id == agency_id
            )
        ).values(**update_values)
        
        result = await db.execute(stmt)
        await db.commit()
        
        # Clear caches
        for conv_id in conversation_ids:
            await redis_manager.delete(f"conversation:{conv_id}")
        
        return {
            "status": "completed",
            "updated_count": result.rowcount
        }
    
    @staticmethod
    async def bulk_assign_conversations(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        assign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assign multiple conversations to chatters."""
        # Validate user permissions
        user = await db.get(User, user_id)
        if not user or user.agency_id != agency_id:
            raise PermissionError("User not authorized for this agency")
        
        conversation_ids = assign_data.get("conversation_ids", [])
        chatter_id = assign_data.get("chatter_id")
        
        if not conversation_ids:
            raise ValidationError("No conversation IDs provided")
        if not chatter_id:
            raise ValidationError("No chatter ID provided")
        
        # Verify chatter exists and belongs to agency
        chatter = await db.get(User, chatter_id)
        if not chatter or chatter.agency_id != agency_id or chatter.role != "chatter":
            raise NotFoundError("Chatter not found or not authorized")
        
        # Update conversations
        stmt = update(Conversation).where(
            and_(
                Conversation.id.in_(conversation_ids),
                Conversation.agency_id == agency_id
            )
        ).values(
            assigned_chatter_id=chatter_id,
            updated_at=datetime.utcnow()
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        # Clear caches
        for conv_id in conversation_ids:
            await redis_manager.delete(f"conversation:{conv_id}")
        
        return {
            "status": "completed",
            "assigned_count": result.rowcount,
            "chatter_id": chatter_id
        }
    
    @staticmethod
    async def bulk_delete_messages(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        delete_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delete multiple messages."""
        # Validate user permissions
        user = await db.get(User, user_id)
        if not user or user.agency_id != agency_id or user.role not in ["admin", "manager"]:
            raise PermissionError("User not authorized for bulk deletion")
        
        message_ids = delete_data.get("message_ids", [])
        
        if not message_ids:
            raise ValidationError("No message IDs provided")
        
        # Get messages and verify they belong to agency conversations
        stmt = select(Message).join(Conversation).where(
            and_(
                Message.id.in_(message_ids),
                Conversation.agency_id == agency_id
            )
        )
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        if len(messages) != len(message_ids):
            raise NotFoundError("Some messages not found or not authorized")
        
        # Delete messages
        for message in messages:
            await db.delete(message)
        
        await db.commit()
        
        # Clear conversation caches
        conversation_ids = list(set([m.conversation_id for m in messages]))
        for conv_id in conversation_ids:
            await redis_manager.delete(f"conversation:{conv_id}")
        
        return {
            "status": "completed",
            "deleted_count": len(messages),
            "affected_conversations": len(conversation_ids)
        }
    
    @staticmethod
    async def get_bulk_operation_status(
        db: AsyncSession,
        task_id: str
    ) -> Dict[str, Any]:
        """Get status of a bulk operation task."""
        # Get task status from Celery
        from celery.result import AsyncResult
        
        task = AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": task.state,
            "result": task.result if task.state == "SUCCESS" else None,
            "error": str(task.info) if task.state == "FAILURE" else None
        }