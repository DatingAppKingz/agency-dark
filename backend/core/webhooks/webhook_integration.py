"""
Webhook integration helper for triggering events from services
"""
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import asyncio

from core.logging import get_logger
from core.database import get_db
from .webhook_models import WebhookEvent
from .webhook_manager import webhook_manager

logger = get_logger(__name__)


class WebhookIntegration:
    """Helper class for webhook integrations"""
    
    @staticmethod
    async def message_received(
        agency_id: UUID,
        message_id: str,
        model_id: UUID,
        fan_id: UUID,
        content: str,
        sender: str,
        created_at: datetime,
        media_count: int = 0,
        price: Optional[float] = None
    ):
        """Trigger webhook for message received event"""
        data = {
            "message_id": str(message_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "content": content[:500],  # Limit content length
            "sender": sender,
            "created_at": created_at.isoformat(),
            "media_count": media_count,
            "has_media": media_count > 0
        }
        
        if price is not None:
            data["price"] = price
            data["is_paid_message"] = True
        else:
            data["is_paid_message"] = False
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MESSAGE_RECEIVED,
            event_id=str(message_id),
            data=data
        )
    
    @staticmethod
    async def message_sent(
        agency_id: UUID,
        message_id: str,
        model_id: UUID,
        fan_id: UUID,
        content: str,
        created_at: datetime,
        media_count: int = 0
    ):
        """Trigger webhook for message sent event"""
        data = {
            "message_id": str(message_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "content": content[:500],
            "sender": "model",
            "created_at": created_at.isoformat(),
            "media_count": media_count,
            "has_media": media_count > 0
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MESSAGE_SENT,
            event_id=str(message_id),
            data=data
        )
    
    @staticmethod
    async def message_read(
        agency_id: UUID,
        message_id: str,
        model_id: UUID,
        fan_id: UUID,
        read_at: datetime
    ):
        """Trigger webhook for message read event"""
        data = {
            "message_id": str(message_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "read_at": read_at.isoformat()
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MESSAGE_READ,
            event_id=str(message_id),
            data=data
        )
    
    @staticmethod
    async def payment_received(
        agency_id: UUID,
        payment_id: str,
        model_id: UUID,
        fan_id: UUID,
        amount: float,
        currency: str,
        payment_type: str,
        status: str,
        created_at: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Trigger webhook for payment received event"""
        data = {
            "payment_id": str(payment_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "amount": amount,
            "currency": currency,
            "payment_type": payment_type,
            "status": status,
            "created_at": created_at.isoformat()
        }
        
        if metadata:
            data["metadata"] = metadata
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.PAYMENT_RECEIVED,
            event_id=str(payment_id),
            data=data
        )
    
    @staticmethod
    async def payment_failed(
        agency_id: UUID,
        payment_id: str,
        model_id: UUID,
        fan_id: UUID,
        amount: float,
        currency: str,
        error_message: str,
        failed_at: datetime
    ):
        """Trigger webhook for payment failed event"""
        data = {
            "payment_id": str(payment_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "amount": amount,
            "currency": currency,
            "error_message": error_message,
            "failed_at": failed_at.isoformat()
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.PAYMENT_FAILED,
            event_id=str(payment_id),
            data=data
        )
    
    @staticmethod
    async def payment_refunded(
        agency_id: UUID,
        payment_id: str,
        refund_id: str,
        model_id: UUID,
        fan_id: UUID,
        amount: float,
        currency: str,
        reason: str,
        refunded_at: datetime
    ):
        """Trigger webhook for payment refunded event"""
        data = {
            "payment_id": str(payment_id),
            "refund_id": str(refund_id),
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "amount": amount,
            "currency": currency,
            "reason": reason,
            "refunded_at": refunded_at.isoformat()
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.PAYMENT_REFUNDED,
            event_id=str(refund_id),
            data=data
        )
    
    @staticmethod
    async def fan_subscribed(
        agency_id: UUID,
        fan_id: UUID,
        model_id: UUID,
        username: str,
        subscription_type: str,
        price: float,
        subscribed_at: datetime,
        profile_data: Optional[Dict[str, Any]] = None
    ):
        """Trigger webhook for new fan subscription"""
        data = {
            "fan_id": str(fan_id),
            "model_id": str(model_id),
            "username": username,
            "subscription_type": subscription_type,
            "price": price,
            "subscribed_at": subscribed_at.isoformat()
        }
        
        if profile_data:
            data["profile"] = profile_data
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.FAN_SUBSCRIBED,
            event_id=str(fan_id),
            data=data
        )
    
    @staticmethod
    async def fan_unsubscribed(
        agency_id: UUID,
        fan_id: UUID,
        model_id: UUID,
        username: str,
        unsubscribed_at: datetime,
        total_spent: float,
        subscription_duration_days: int
    ):
        """Trigger webhook for fan unsubscription"""
        data = {
            "fan_id": str(fan_id),
            "model_id": str(model_id),
            "username": username,
            "unsubscribed_at": unsubscribed_at.isoformat(),
            "total_spent": total_spent,
            "subscription_duration_days": subscription_duration_days
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.FAN_UNSUBSCRIBED,
            event_id=str(fan_id),
            data=data
        )
    
    @staticmethod
    async def fan_updated(
        agency_id: UUID,
        fan_id: UUID,
        model_id: UUID,
        username: str,
        changes: Dict[str, Any],
        updated_at: datetime
    ):
        """Trigger webhook for fan profile update"""
        data = {
            "fan_id": str(fan_id),
            "model_id": str(model_id),
            "username": username,
            "changes": changes,
            "updated_at": updated_at.isoformat()
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.FAN_UPDATED,
            event_id=str(fan_id),
            data=data
        )
    
    @staticmethod
    async def model_online(
        agency_id: UUID,
        model_id: UUID,
        username: str,
        online_at: datetime
    ):
        """Trigger webhook for model going online"""
        data = {
            "model_id": str(model_id),
            "username": username,
            "online_at": online_at.isoformat(),
            "status": "online"
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MODEL_ONLINE,
            event_id=str(model_id),
            data=data
        )
    
    @staticmethod
    async def model_offline(
        agency_id: UUID,
        model_id: UUID,
        username: str,
        offline_at: datetime,
        session_duration_minutes: int
    ):
        """Trigger webhook for model going offline"""
        data = {
            "model_id": str(model_id),
            "username": username,
            "offline_at": offline_at.isoformat(),
            "status": "offline",
            "session_duration_minutes": session_duration_minutes
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MODEL_OFFLINE,
            event_id=str(model_id),
            data=data
        )
    
    @staticmethod
    async def model_updated(
        agency_id: UUID,
        model_id: UUID,
        username: str,
        changes: Dict[str, Any],
        updated_at: datetime
    ):
        """Trigger webhook for model profile update"""
        data = {
            "model_id": str(model_id),
            "username": username,
            "changes": changes,
            "updated_at": updated_at.isoformat()
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MODEL_UPDATED,
            event_id=str(model_id),
            data=data
        )
    
    @staticmethod
    async def daily_summary(
        agency_id: UUID,
        model_id: UUID,
        date: str,
        revenue: float,
        new_fans: int,
        total_messages: int,
        engagement_rate: float,
        top_fans: List[Dict[str, Any]],
        summary_data: Dict[str, Any]
    ):
        """Trigger webhook for daily analytics summary"""
        data = {
            "model_id": str(model_id),
            "date": date,
            "revenue": revenue,
            "new_fans": new_fans,
            "total_messages": total_messages,
            "engagement_rate": engagement_rate,
            "top_fans": top_fans,
            "summary": summary_data
        }
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.DAILY_SUMMARY,
            event_id=f"{model_id}_{date}",
            data=data
        )
    
    @staticmethod
    async def milestone_reached(
        agency_id: UUID,
        model_id: UUID,
        milestone_type: str,
        milestone_value: Any,
        previous_value: Any,
        reached_at: datetime,
        details: Optional[Dict[str, Any]] = None
    ):
        """Trigger webhook for milestone achievement"""
        data = {
            "model_id": str(model_id),
            "milestone_type": milestone_type,
            "milestone_value": milestone_value,
            "previous_value": previous_value,
            "reached_at": reached_at.isoformat()
        }
        
        if details:
            data["details"] = details
        
        await webhook_manager.trigger_event(
            agency_id=agency_id,
            event=WebhookEvent.MILESTONE_REACHED,
            event_id=f"{model_id}_{milestone_type}_{milestone_value}",
            data=data
        )


# Create global instance
webhook_integration = WebhookIntegration()
