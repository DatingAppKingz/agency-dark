"""Analytics service for chat insights and metrics."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, extract
from sqlalchemy.orm import selectinload
from decimal import Decimal
import json

from core.logger import get_logger
from core.redis import redis_manager
from models.chat import Conversation, Message, MessageType, MessageStatus, ConversationStatus
from models.user import User, UserRole
from models.model import Model

logger = get_logger(__name__)


class ChatAnalyticsService:
    """Service for generating chat analytics and insights."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache_ttl = 300  # 5 minutes cache
    
    async def get_conversation_metrics(
        self,
        conversation_id: int,
        user: User
    ) -> Dict[str, Any]:
        """Get detailed metrics for a specific conversation."""
        # Verify access
        conversation = await self._get_conversation_with_access(conversation_id, user)
        if not conversation:
            raise ValueError("Conversation not found or access denied")
        
        # Try cache first
        cache_key = f"analytics:conv:{conversation_id}"
        cached = await redis_manager.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Calculate metrics
        metrics = {
            'conversation_id': conversation_id,
            'basic_stats': await self._get_basic_conversation_stats(conversation_id),
            'engagement': await self._get_engagement_metrics(conversation_id),
            'financial': await self._get_financial_metrics(conversation_id),
            'response_times': await self._get_response_time_metrics(conversation_id),
            'content_breakdown': await self._get_content_breakdown(conversation_id),
            'activity_timeline': await self._get_activity_timeline(conversation_id, days=7)
        }
        
        # Cache results
        await redis_manager.set(cache_key, json.dumps(metrics, default=str), expire=self.cache_ttl)
        
        return metrics
    
    async def _get_basic_conversation_stats(self, conversation_id: int) -> Dict[str, Any]:
        """Get basic conversation statistics."""
        # Total messages
        total_messages = await self.db.scalar(
            select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                )
            )
        )
        
        # Messages by sender type
        sender_stats = await self.db.execute(
            select(
                Message.sender_type,
                func.count(Message.id).label('count')
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                )
            ).group_by(Message.sender_type)
        )
        
        sender_breakdown = {row.sender_type: row.count for row in sender_stats}
        
        # First and last message times
        time_stats = await self.db.execute(
            select(
                func.min(Message.created_at).label('first_message'),
                func.max(Message.created_at).label('last_message')
            ).where(Message.conversation_id == conversation_id)
        )
        
        time_row = time_stats.one()
        
        # Duration
        if time_row.first_message and time_row.last_message:
            first = datetime.fromisoformat(time_row.first_message)
            last = datetime.fromisoformat(time_row.last_message)
            duration_days = (last - first).days
        else:
            duration_days = 0
        
        return {
            'total_messages': total_messages,
            'messages_by_sender': sender_breakdown,
            'first_message_at': time_row.first_message,
            'last_message_at': time_row.last_message,
            'duration_days': duration_days,
            'avg_messages_per_day': total_messages / max(duration_days, 1)
        }
    
    async def _get_engagement_metrics(self, conversation_id: int) -> Dict[str, Any]:
        """Calculate engagement metrics."""
        # Response rate
        fan_messages = await self.db.scalar(
            select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_type == 'fan',
                    Message.is_deleted == False
                )
            )
        )
        
        our_messages = await self.db.scalar(
            select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_type.in_(['model', 'chatter']),
                    Message.is_deleted == False
                )
            )
        )
        
        response_rate = (our_messages / fan_messages * 100) if fan_messages > 0 else 0
        
        # Read rate
        read_messages = await self.db.scalar(
            select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_type == 'fan',
                    Message.status == MessageStatus.READ,
                    Message.is_deleted == False
                )
            )
        )
        
        read_rate = (read_messages / fan_messages * 100) if fan_messages > 0 else 100
        
        # Media sharing
        media_messages = await self.db.scalar(
            select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.type.in_([MessageType.IMAGE, MessageType.VIDEO, MessageType.AUDIO]),
                    Message.is_deleted == False
                )
            )
        )
        
        return {
            'response_rate': round(response_rate, 2),
            'read_rate': round(read_rate, 2),
            'total_media_shared': media_messages,
            'media_percentage': round((media_messages / max(fan_messages + our_messages, 1)) * 100, 2)
        }
    
    async def _get_financial_metrics(self, conversation_id: int) -> Dict[str, Any]:
        """Calculate financial metrics."""
        # Tips
        tips_result = await self.db.execute(
            select(
                func.count(Message.id).label('count'),
                func.sum(Message.amount).label('total'),
                func.avg(Message.amount).label('average')
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.type == MessageType.TIP,
                    Message.is_paid == True,
                    Message.is_deleted == False
                )
            )
        )
        
        tips = tips_result.one()
        
        # PPV
        ppv_result = await self.db.execute(
            select(
                func.count(Message.id).label('count'),
                func.sum(Message.amount).label('total'),
                func.avg(Message.amount).label('average'),
                func.sum(case((Message.is_paid == True, 1), else_=0)).label('purchased')
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.type == MessageType.PPV,
                    Message.is_deleted == False
                )
            )
        )
        
        ppv = ppv_result.one()
        
        # Conversion rate
        ppv_conversion = (ppv.purchased / ppv.count * 100) if ppv.count > 0 else 0
        
        return {
            'tips': {
                'count': tips.count or 0,
                'total': float(tips.total or 0),
                'average': float(tips.average or 0)
            },
            'ppv': {
                'count': ppv.count or 0,
                'purchased': ppv.purchased or 0,
                'total_revenue': float(ppv.total or 0),
                'average_price': float(ppv.average or 0),
                'conversion_rate': round(ppv_conversion, 2)
            },
            'total_revenue': float((tips.total or 0) + (ppv.total or 0))
        }
    
    async def _get_response_time_metrics(self, conversation_id: int) -> Dict[str, Any]:
        """Calculate response time metrics."""
        # Get all messages ordered by time
        messages = await self.db.execute(
            select(
                Message.id,
                Message.sender_type,
                Message.created_at
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                )
            ).order_by(Message.created_at)
        )
        
        response_times = []
        last_fan_message_time = None
        
        for msg in messages:
            if msg.sender_type == 'fan':
                last_fan_message_time = datetime.fromisoformat(msg.created_at)
            elif msg.sender_type in ['model', 'chatter'] and last_fan_message_time:
                response_time = datetime.fromisoformat(msg.created_at) - last_fan_message_time
                response_times.append(response_time.total_seconds())
                last_fan_message_time = None
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        return {
            'average_seconds': round(avg_response_time, 2),
            'minimum_seconds': round(min_response_time, 2),
            'maximum_seconds': round(max_response_time, 2),
            'average_formatted': self._format_duration(avg_response_time),
            'total_responses': len(response_times)
        }
    
    async def _get_content_breakdown(self, conversation_id: int) -> Dict[str, Any]:
        """Get breakdown of content types."""
        breakdown = await self.db.execute(
            select(
                Message.type,
                func.count(Message.id).label('count')
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                )
            ).group_by(Message.type)
        )
        
        return {
            row.type.value: row.count 
            for row in breakdown
        }
    
    async def _get_activity_timeline(self, conversation_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily activity timeline."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get daily message counts
        daily_stats = await self.db.execute(
            select(
                func.date(Message.created_at).label('date'),
                Message.sender_type,
                func.count(Message.id).label('count')
            ).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.created_at >= since.isoformat(),
                    Message.is_deleted == False
                )
            ).group_by(
                func.date(Message.created_at),
                Message.sender_type
            ).order_by(func.date(Message.created_at))
        )
        
        # Organize by date
        timeline = {}
        for row in daily_stats:
            date_str = row.date
            if date_str not in timeline:
                timeline[date_str] = {
                    'date': date_str,
                    'fan_messages': 0,
                    'our_messages': 0,
                    'total': 0
                }
            
            if row.sender_type == 'fan':
                timeline[date_str]['fan_messages'] = row.count
            elif row.sender_type in ['model', 'chatter']:
                timeline[date_str]['our_messages'] += row.count
            
            timeline[date_str]['total'] += row.count
        
        return list(timeline.values())
    
    async def get_model_analytics(
        self,
        model_id: int,
        user: User,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics for a model's conversations."""
        # Verify access
        if user.role == UserRole.MODEL:
            model = await self.db.scalar(
                select(Model).where(Model.user_id == user.id)
            )
            if not model or model.id != model_id:
                raise ValueError("Access denied")
        elif user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            raise ValueError("Access denied")
        
        since = datetime.utcnow() - timedelta(days=period_days)
        
        # Active conversations
        active_convs = await self.db.scalar(
            select(func.count(Conversation.id)).where(
                and_(
                    Conversation.model_id == model_id,
                    Conversation.status == ConversationStatus.ACTIVE,
                    Conversation.last_message_at >= since.isoformat()
                )
            )
        )
        
        # Total messages
        message_stats = await self.db.execute(
            select(
                func.count(Message.id).label('total'),
                func.sum(case((Message.sender_type == 'fan', 1), else_=0)).label('fan_messages'),
                func.sum(case((Message.sender_type.in_(['model', 'chatter']), 1), else_=0)).label('our_messages')
            ).select_from(Message).join(Conversation).where(
                and_(
                    Conversation.model_id == model_id,
                    Message.created_at >= since.isoformat(),
                    Message.is_deleted == False
                )
            )
        )
        
        msg_stats = message_stats.one()
        
        # Revenue
        revenue_stats = await self.db.execute(
            select(
                func.sum(Message.amount).label('total_revenue'),
                func.sum(case((Message.type == MessageType.TIP, Message.amount), else_=0)).label('tips_revenue'),
                func.sum(case((Message.type == MessageType.PPV, Message.amount), else_=0)).label('ppv_revenue')
            ).select_from(Message).join(Conversation).where(
                and_(
                    Conversation.model_id == model_id,
                    Message.created_at >= since.isoformat(),
                    Message.is_paid == True,
                    Message.is_deleted == False
                )
            )
        )
        
        rev_stats = revenue_stats.one()
        
        # Top fans by revenue
        top_fans = await self.db.execute(
            select(
                Conversation.fan_username,
                Conversation.fan_display_name,
                func.sum(Message.amount).label('total_spent')
            ).select_from(Message).join(Conversation).where(
                and_(
                    Conversation.model_id == model_id,
                    Message.is_paid == True,
                    Message.created_at >= since.isoformat()
                )
            ).group_by(
                Conversation.id,
                Conversation.fan_username,
                Conversation.fan_display_name
            ).order_by(func.sum(Message.amount).desc()).limit(10)
        )
        
        return {
            'period_days': period_days,
            'active_conversations': active_convs,
            'messages': {
                'total': msg_stats.total or 0,
                'from_fans': msg_stats.fan_messages or 0,
                'sent': msg_stats.our_messages or 0,
                'response_rate': round((msg_stats.our_messages / msg_stats.fan_messages * 100) if msg_stats.fan_messages > 0 else 0, 2)
            },
            'revenue': {
                'total': float(rev_stats.total_revenue or 0),
                'tips': float(rev_stats.tips_revenue or 0),
                'ppv': float(rev_stats.ppv_revenue or 0),
                'average_per_day': float((rev_stats.total_revenue or 0) / period_days)
            },
            'top_fans': [
                {
                    'username': fan.fan_username,
                    'display_name': fan.fan_display_name,
                    'total_spent': float(fan.total_spent)
                }
                for fan in top_fans
            ]
        }
    
    async def get_agency_analytics(
        self,
        agency_id: int,
        user: User,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics for an entire agency."""
        # Verify access
        if user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            raise ValueError("Access denied")
        
        if user.role == UserRole.AGENCY_OWNER and user.agency_id != agency_id:
            raise ValueError("Access denied")
        
        since = datetime.utcnow() - timedelta(days=period_days)
        
        # Active models
        active_models = await self.db.scalar(
            select(func.count(func.distinct(Conversation.model_id))).where(
                and_(
                    Conversation.agency_id == agency_id,
                    Conversation.last_message_at >= since.isoformat()
                )
            )
        )
        
        # Total conversations
        total_convs = await self.db.scalar(
            select(func.count(Conversation.id)).where(
                and_(
                    Conversation.agency_id == agency_id,
                    Conversation.status == ConversationStatus.ACTIVE
                )
            )
        )
        
        # Message volume
        message_volume = await self.db.execute(
            select(
                func.count(Message.id).label('total'),
                func.avg(func.count(Message.id)).over(
                    partition_by=func.date(Message.created_at)
                ).label('daily_average')
            ).select_from(Message).where(
                and_(
                    Message.agency_id == agency_id,
                    Message.created_at >= since.isoformat()
                )
            )
        )
        
        # Revenue by model
        model_revenue = await self.db.execute(
            select(
                Model.stage_name,
                func.sum(Message.amount).label('revenue'),
                func.count(func.distinct(Conversation.id)).label('conversations')
            ).select_from(Message).join(
                Conversation
            ).join(
                Model
            ).where(
                and_(
                    Conversation.agency_id == agency_id,
                    Message.is_paid == True,
                    Message.created_at >= since.isoformat()
                )
            ).group_by(Model.id, Model.stage_name).order_by(
                func.sum(Message.amount).desc()
            ).limit(10)
        )
        
        # Chatter performance
        chatter_stats = await self.db.execute(
            select(
                User.full_name,
                func.count(Message.id).label('messages_sent'),
                func.count(func.distinct(Message.conversation_id)).label('conversations_handled')
            ).select_from(Message).join(
                User, Message.sender_id == User.id
            ).where(
                and_(
                    Message.agency_id == agency_id,
                    Message.sender_type == 'chatter',
                    Message.created_at >= since.isoformat()
                )
            ).group_by(User.id, User.full_name).order_by(
                func.count(Message.id).desc()
            )
        )
        
        msg_vol = message_volume.first()
        
        return {
            'period_days': period_days,
            'active_models': active_models,
            'total_conversations': total_convs,
            'message_volume': {
                'total': msg_vol.total if msg_vol else 0,
                'daily_average': float(msg_vol.daily_average) if msg_vol else 0
            },
            'top_models_by_revenue': [
                {
                    'name': model.stage_name,
                    'revenue': float(model.revenue),
                    'conversations': model.conversations
                }
                for model in model_revenue
            ],
            'chatter_performance': [
                {
                    'name': chatter.full_name,
                    'messages_sent': chatter.messages_sent,
                    'conversations_handled': chatter.conversations_handled
                }
                for chatter in chatter_stats
            ]
        }
    
    async def generate_conversation_report(
        self,
        conversation_id: int,
        user: User
    ) -> Dict[str, Any]:
        """Generate a comprehensive conversation report."""
        metrics = await self.get_conversation_metrics(conversation_id, user)
        
        conversation = await self.db.get(Conversation, conversation_id)
        
        # Add conversation details
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'conversation': {
                'id': conversation.id,
                'fan_username': conversation.fan_username,
                'model_id': conversation.model_id,
                'status': conversation.status.value,
                'created_at': conversation.created_at.isoformat()
            },
            'metrics': metrics,
            'recommendations': await self._generate_recommendations(metrics)
        }
        
        return report
    
    async def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        # Response rate
        if metrics['engagement']['response_rate'] < 80:
            recommendations.append("Consider improving response rate to increase fan engagement")
        
        # Response time
        avg_response = metrics['response_times']['average_seconds']
        if avg_response > 3600:  # 1 hour
            recommendations.append("Response times are high. Consider assigning more chatters or using quick replies")
        
        # Revenue opportunities
        if metrics['financial']['tips']['count'] == 0:
            recommendations.append("No tips received. Consider encouraging tipping through engaging content")
        
        if metrics['financial']['ppv']['conversion_rate'] < 30:
            recommendations.append("PPV conversion rate is low. Consider improving preview content or pricing")
        
        # Content variety
        content = metrics['content_breakdown']
        if content.get('image', 0) + content.get('video', 0) == 0:
            recommendations.append("No media shared. Visual content typically increases engagement")
        
        return recommendations
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h {int((seconds % 3600) / 60)}m"
        else:
            return f"{int(seconds / 86400)}d {int((seconds % 86400) / 3600)}h"
    
    async def _get_conversation_with_access(self, conversation_id: int, user: User) -> Optional[Conversation]:
        """Get conversation with access check."""
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation:
            return None
        
        # Check access based on role
        if user.role == UserRole.ADMIN:
            return conversation
        elif user.role == UserRole.AGENCY_OWNER:
            if conversation.agency_id == user.agency_id:
                return conversation
        elif user.role == UserRole.MODEL:
            model = await self.db.scalar(
                select(Model).where(Model.user_id == user.id)
            )
            if model and conversation.model_id == model.id:
                return conversation
        elif user.role == UserRole.CHATTER:
            if conversation.assigned_chatter_id == user.id:
                return conversation
        
        return None