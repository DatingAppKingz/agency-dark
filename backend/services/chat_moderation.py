"""Chat moderation service for content filtering and safety."""

import re
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from collections import defaultdict

from core.logger import get_logger
from core.redis import redis_manager
from models.chat import Message, Conversation, ConversationStatus
from models.user import User, UserRole
from services.email_notifications import EmailNotificationService

logger = get_logger(__name__)


class ChatModerationService:
    """Service for moderating chat content."""
    
    # Spam patterns
    SPAM_PATTERNS = [
        r'(?i)(buy|get|click).{0,20}(now|here|today)',
        r'(?i)(limited|exclusive).{0,20}(offer|deal)',
        r'(?i)congratulations.{0,20}(won|winner)',
        r'(?i)(viagra|cialis|pills)',
        r'(?i)(crypto|bitcoin).{0,20}(profit|earn)',
        r'https?://bit\.ly/\w+',  # Shortened URLs
        r'(?i)whatsapp\.me',
        r'(?i)t\.me/\w+',  # Telegram links
    ]
    
    # Prohibited content patterns
    PROHIBITED_PATTERNS = [
        r'(?i)(suicide|kill myself)',
        r'(?i)(minor|underage|child)',
        r'(?i)(drugs|cocaine|heroin)',
        r'(?i)(revenge porn)',
    ]
    
    # Rate limiting thresholds
    RATE_LIMITS = {
        'messages_per_minute': 10,
        'messages_per_hour': 100,
        'identical_messages': 3,
        'links_per_hour': 20,
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailNotificationService(db)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.spam_regex = [re.compile(pattern) for pattern in self.SPAM_PATTERNS]
        self.prohibited_regex = [re.compile(pattern) for pattern in self.PROHIBITED_PATTERNS]
        self.url_regex = re.compile(r'https?://[^\s]+')
        self.email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.phone_regex = re.compile(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}')
    
    async def moderate_message(
        self,
        message: Message,
        user: User
    ) -> Dict[str, Any]:
        """Moderate a message before sending."""
        moderation_result = {
            'allowed': True,
            'reasons': [],
            'severity': 'none',
            'actions': []
        }
        
        # Skip moderation for system messages
        if message.sender_type == 'system':
            return moderation_result
        
        # Check rate limits
        rate_limit_check = await self._check_rate_limits(user.id, message.content)
        if not rate_limit_check['allowed']:
            moderation_result['allowed'] = False
            moderation_result['reasons'].append(rate_limit_check['reason'])
            moderation_result['severity'] = 'warning'
            moderation_result['actions'].append('rate_limited')
        
        # Check for spam
        if self._is_spam(message.content):
            moderation_result['allowed'] = False
            moderation_result['reasons'].append('Spam content detected')
            moderation_result['severity'] = 'warning'
            moderation_result['actions'].append('flag_spam')
        
        # Check for prohibited content
        prohibited_check = self._check_prohibited_content(message.content)
        if prohibited_check['found']:
            moderation_result['allowed'] = False
            moderation_result['reasons'].append(f"Prohibited content: {prohibited_check['type']}")
            moderation_result['severity'] = 'severe'
            moderation_result['actions'].extend(['block', 'notify_admin'])
        
        # Check for personal information
        pii_check = self._check_pii(message.content)
        if pii_check['found']:
            moderation_result['reasons'].append(f"Personal information detected: {pii_check['types']}")
            moderation_result['severity'] = 'warning' if moderation_result['severity'] == 'none' else moderation_result['severity']
            moderation_result['actions'].append('flag_pii')
        
        # Apply actions if message is not allowed
        if not moderation_result['allowed']:
            await self._apply_moderation_actions(message, user, moderation_result)
        
        return moderation_result
    
    async def _check_rate_limits(self, user_id: int, content: str) -> Dict[str, Any]:
        """Check if user is exceeding rate limits."""
        now = datetime.utcnow()
        
        # Messages per minute
        minute_key = f"rate:msg_minute:{user_id}:{now.minute}"
        minute_count = await redis_manager.incr(minute_key)
        await redis_manager.expire(minute_key, 60)
        
        if minute_count > self.RATE_LIMITS['messages_per_minute']:
            return {
                'allowed': False,
                'reason': f"Too many messages per minute (limit: {self.RATE_LIMITS['messages_per_minute']})"
            }
        
        # Messages per hour
        hour_key = f"rate:msg_hour:{user_id}:{now.hour}"
        hour_count = await redis_manager.incr(hour_key)
        await redis_manager.expire(hour_key, 3600)
        
        if hour_count > self.RATE_LIMITS['messages_per_hour']:
            return {
                'allowed': False,
                'reason': f"Too many messages per hour (limit: {self.RATE_LIMITS['messages_per_hour']})"
            }
        
        # Check for identical messages
        content_hash = hash(content.lower().strip())
        identical_key = f"rate:identical:{user_id}:{content_hash}"
        identical_count = await redis_manager.incr(identical_key)
        await redis_manager.expire(identical_key, 300)  # 5 minutes
        
        if identical_count > self.RATE_LIMITS['identical_messages']:
            return {
                'allowed': False,
                'reason': "Sending too many identical messages"
            }
        
        # Check link rate
        if self.url_regex.search(content):
            link_key = f"rate:links:{user_id}:{now.hour}"
            link_count = await redis_manager.incr(link_key)
            await redis_manager.expire(link_key, 3600)
            
            if link_count > self.RATE_LIMITS['links_per_hour']:
                return {
                    'allowed': False,
                    'reason': f"Too many links per hour (limit: {self.RATE_LIMITS['links_per_hour']})"
                }
        
        return {'allowed': True}
    
    def _is_spam(self, content: str) -> bool:
        """Check if content matches spam patterns."""
        for pattern in self.spam_regex:
            if pattern.search(content):
                return True
        
        # Check for excessive caps
        if len(content) > 10:
            caps_ratio = sum(1 for c in content if c.isupper()) / len(content)
            if caps_ratio > 0.7:
                return True
        
        # Check for excessive repetition
        words = content.lower().split()
        if len(words) > 5:
            word_counts = defaultdict(int)
            for word in words:
                word_counts[word] += 1
            
            max_repetition = max(word_counts.values())
            if max_repetition > len(words) * 0.4:
                return True
        
        return False
    
    def _check_prohibited_content(self, content: str) -> Dict[str, Any]:
        """Check for prohibited content."""
        for pattern in self.prohibited_regex:
            match = pattern.search(content)
            if match:
                return {
                    'found': True,
                    'type': match.group(0),
                    'pattern': pattern.pattern
                }
        
        return {'found': False}
    
    def _check_pii(self, content: str) -> Dict[str, Any]:
        """Check for personal information."""
        pii_types = []
        
        if self.email_regex.search(content):
            pii_types.append('email')
        
        if self.phone_regex.search(content):
            pii_types.append('phone')
        
        # Check for social security numbers (US)
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, content):
            pii_types.append('ssn')
        
        # Check for credit card patterns
        cc_pattern = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
        if re.search(cc_pattern, content):
            pii_types.append('credit_card')
        
        return {
            'found': len(pii_types) > 0,
            'types': ', '.join(pii_types)
        }
    
    async def _apply_moderation_actions(
        self,
        message: Message,
        user: User,
        moderation_result: Dict[str, Any]
    ):
        """Apply moderation actions."""
        # Flag the message
        message.is_flagged = True
        message.flagged_reason = '; '.join(moderation_result['reasons'])
        
        # Log moderation event
        logger.warning(
            f"Message moderated - User: {user.id}, "
            f"Reasons: {moderation_result['reasons']}, "
            f"Actions: {moderation_result['actions']}"
        )
        
        # Increment user violation counter
        violation_key = f"violations:{user.id}"
        violations = await redis_manager.incr(violation_key)
        await redis_manager.expire(violation_key, 86400 * 7)  # 7 days
        
        # Apply progressive actions based on violations
        if violations >= 10:
            # Suspend user
            user.is_active = False
            moderation_result['actions'].append('account_suspended')
        elif violations >= 5:
            # Temporary restriction
            restriction_key = f"restricted:{user.id}"
            await redis_manager.set(restriction_key, "1", expire=3600)  # 1 hour
            moderation_result['actions'].append('temporary_restriction')
        
        # Notify admins for severe violations
        if moderation_result['severity'] == 'severe':
            await self._notify_admins(message, user, moderation_result)
    
    async def _notify_admins(
        self,
        message: Message,
        user: User,
        moderation_result: Dict[str, Any]
    ):
        """Notify admins of severe violations."""
        # Get admin users
        admins = await self.db.execute(
            select(User).where(
                User.role.in_([UserRole.ADMIN, UserRole.AGENCY_OWNER])
            )
        )
        
        for admin in admins.scalars():
            # Send email notification
            await self.email_service.send_moderation_alert(
                admin=admin,
                violator=user,
                message_content=message.content[:200],  # Truncate for safety
                reasons=moderation_result['reasons'],
                actions_taken=moderation_result['actions']
            )
    
    async def review_flagged_messages(
        self,
        reviewer: User,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get flagged messages for review."""
        if reviewer.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            raise ValueError("Insufficient permissions")
        
        stmt = select(Message).where(
            and_(
                Message.is_flagged == True,
                Message.is_deleted == False
            )
        ).order_by(Message.created_at.desc()).limit(limit)
        
        if reviewer.role == UserRole.AGENCY_OWNER:
            # Limit to agency messages
            stmt = stmt.where(Message.agency_id == reviewer.agency_id)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        return [
            {
                'id': msg.id,
                'conversation_id': msg.conversation_id,
                'sender_id': msg.sender_id,
                'content': msg.content,
                'flagged_reason': msg.flagged_reason,
                'created_at': msg.created_at.isoformat()
            }
            for msg in messages
        ]
    
    async def approve_message(self, message_id: int, reviewer: User):
        """Approve a flagged message."""
        message = await self.db.get(Message, message_id)
        if not message or not message.is_flagged:
            raise ValueError("Message not found or not flagged")
        
        message.is_flagged = False
        message.flagged_reason = None
        
        # Log approval
        logger.info(f"Message {message_id} approved by {reviewer.id}")
        
        await self.db.commit()
    
    async def delete_flagged_message(self, message_id: int, reviewer: User):
        """Delete a flagged message."""
        message = await self.db.get(Message, message_id)
        if not message:
            raise ValueError("Message not found")
        
        message.is_deleted = True
        
        # Log deletion
        logger.info(f"Message {message_id} deleted by {reviewer.id}")
        
        await self.db.commit()
    
    async def block_conversation(
        self,
        conversation_id: int,
        blocked_by: User,
        reason: str
    ):
        """Block a conversation."""
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        conversation.status = ConversationStatus.BLOCKED
        
        if not conversation.conversation_metadata:
            conversation.conversation_metadata = {}
        
        conversation.conversation_metadata['blocked_by'] = blocked_by.id
        conversation.conversation_metadata['blocked_at'] = datetime.utcnow().isoformat()
        conversation.conversation_metadata['block_reason'] = reason
        
        await self.db.commit()
        
        logger.info(f"Conversation {conversation_id} blocked by {blocked_by.id}")
    
    async def get_moderation_stats(
        self,
        agency_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get moderation statistics."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Base query
        base_query = select(Message).where(
            Message.created_at >= since.isoformat()
        )
        
        if agency_id:
            base_query = base_query.where(Message.agency_id == agency_id)
        
        # Total messages
        total_result = await self.db.execute(
            select(func.count(Message.id)).select_from(base_query.subquery())
        )
        total_messages = total_result.scalar()
        
        # Flagged messages
        flagged_result = await self.db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.created_at >= since.isoformat(),
                    Message.is_flagged == True
                )
            )
        )
        flagged_messages = flagged_result.scalar()
        
        # Deleted messages
        deleted_result = await self.db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.created_at >= since.isoformat(),
                    Message.is_deleted == True
                )
            )
        )
        deleted_messages = deleted_result.scalar()
        
        # Blocked conversations
        blocked_result = await self.db.execute(
            select(func.count(Conversation.id)).where(
                and_(
                    Conversation.status == ConversationStatus.BLOCKED,
                    Conversation.updated_at >= since
                )
            )
        )
        blocked_conversations = blocked_result.scalar()
        
        return {
            'period_days': days,
            'total_messages': total_messages,
            'flagged_messages': flagged_messages,
            'deleted_messages': deleted_messages,
            'blocked_conversations': blocked_conversations,
            'flag_rate': (flagged_messages / total_messages * 100) if total_messages > 0 else 0,
            'deletion_rate': (deleted_messages / total_messages * 100) if total_messages > 0 else 0
        }