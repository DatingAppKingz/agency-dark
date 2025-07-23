"""
Message queuing system for offline chatters.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import asyncio

from backend.core.redis import redis_client
from backend.core.database import AsyncSessionLocal
from backend.core.domain.models import User, Message, Fan


logger = logging.getLogger(__name__)


class MessageQueue:
    """Manages message queuing for offline chatters."""
    
    QUEUE_KEY_PREFIX = "message_queue:"
    QUEUE_EXPIRY_DAYS = 7  # Keep messages for 7 days
    MAX_QUEUE_SIZE = 1000  # Max messages per user
    
    async def queue_message(
        self,
        user_id: str,
        message_data: Dict[str, Any]
    ) -> bool:
        """
        Queue a message for an offline user.
        
        Args:
            user_id: ID of the user to queue message for
            message_data: Message information to queue
            
        Returns:
            True if queued successfully
        """
        try:
            queue_key = f"{self.QUEUE_KEY_PREFIX}{user_id}"
            
            # Add timestamp
            message_data['queued_at'] = datetime.utcnow().isoformat()
            
            # Add to queue (using list)
            await redis_client.lpush(queue_key, json.dumps(message_data))
            
            # Trim queue to max size (keep most recent)
            await redis_client.ltrim(queue_key, 0, self.MAX_QUEUE_SIZE - 1)
            
            # Set expiry
            await redis_client.expire(
                queue_key,
                self.QUEUE_EXPIRY_DAYS * 24 * 3600
            )
            
            logger.info(f"Queued message for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue message: {e}")
            return False
    
    async def get_queued_messages(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get queued messages for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of queued messages
        """
        try:
            queue_key = f"{self.QUEUE_KEY_PREFIX}{user_id}"
            
            # Get messages from queue
            if limit:
                messages = await redis_client.lrange(queue_key, 0, limit - 1)
            else:
                messages = await redis_client.lrange(queue_key, 0, -1)
            
            # Parse messages
            parsed_messages = []
            for msg in messages:
                try:
                    parsed = json.loads(msg)
                    parsed_messages.append(parsed)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse queued message: {msg}")
                    continue
            
            return parsed_messages
            
        except Exception as e:
            logger.error(f"Failed to get queued messages: {e}")
            return []
    
    async def clear_queued_messages(
        self,
        user_id: str
    ) -> bool:
        """
        Clear all queued messages for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if cleared successfully
        """
        try:
            queue_key = f"{self.QUEUE_KEY_PREFIX}{user_id}"
            await redis_client.delete(queue_key)
            logger.info(f"Cleared message queue for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear message queue: {e}")
            return False
    
    async def queue_fan_message(
        self,
        fan_id: str,
        model_id: str,
        message_type: str,
        content: Dict[str, Any]
    ):
        """
        Queue a fan message for all offline chatters who might handle it.
        
        Args:
            fan_id: ID of the fan
            model_id: ID of the model
            message_type: Type of message (new_message, tip, etc.)
            content: Message content
        """
        async with AsyncSessionLocal() as db:
            # Get fan details
            fan = await db.get(Fan, fan_id)
            if not fan:
                return
            
            # Check if fan is claimed
            from backend.modules.chat.application.claim_manager import ClaimManager
            claim_manager = ClaimManager()
            claim_status = await claim_manager.check_claim_status(fan_id)
            
            # Prepare message data
            message_data = {
                'type': message_type,
                'fan_id': fan_id,
                'fan_username': fan.username,
                'model_id': model_id,
                'content': content,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if claim_status['is_claimed']:
                # Queue only for the claiming chatter
                await self.queue_message(
                    claim_status['chatter_id'],
                    message_data
                )
            else:
                # Queue for all chatters in the agency
                # Get all chatters for this model's agency
                from sqlalchemy import select, and_
                from backend.core.domain.models import UserRole, ModelProfile
                
                model = await db.get(ModelProfile, model_id)
                if not model:
                    return
                
                result = await db.execute(
                    select(User).where(
                        and_(
                            User.agency_id == model.agency_id,
                            User.role == UserRole.CHATTER,
                            User.is_active == True
                        )
                    )
                )
                chatters = result.scalars().all()
                
                # Queue for each chatter
                for chatter in chatters:
                    await self.queue_message(
                        str(chatter.id),
                        message_data
                    )
    
    async def process_priority_queue(self):
        """
        Process priority messages (tips, new subscribers, etc.).
        This would be called periodically to ensure important messages
        are delivered promptly.
        """
        # TODO: Implement priority queue processing
        # This could involve checking for high-value fans,
        # urgent messages, etc. and ensuring they're handled
        pass
    
    async def get_queue_stats(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Args:
            user_id: Specific user ID or None for all users
            
        Returns:
            Queue statistics
        """
        if user_id:
            queue_key = f"{self.QUEUE_KEY_PREFIX}{user_id}"
            queue_length = await redis_client.llen(queue_key)
            
            return {
                'user_id': user_id,
                'queue_length': queue_length,
                'oldest_message': None  # TODO: Get oldest message timestamp
            }
        else:
            # Get stats for all queues
            # This would require scanning Redis keys
            return {
                'total_queues': 0,
                'total_messages': 0
            }