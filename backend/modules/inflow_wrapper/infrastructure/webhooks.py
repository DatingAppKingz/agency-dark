"""
Inflow webhook event handlers
"""
from typing import Dict, Any
from datetime import datetime
import logging

from core.external_api.webhooks import WebhookEvent
from core.database import AsyncSession
from sqlalchemy import select

from ..domain.schemas import (
    InflowUser, InflowSubscription, InflowMessage,
    InflowTransaction, InflowContent
)
from core.domain.models import User, Transaction
from modules.analytics.domain.models import AnalyticsEvent


logger = logging.getLogger(__name__)


class InflowWebhookEventHandler:
    """Handler for Inflow webhook events"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def handle_user_updated(self, event: WebhookEvent):
        """Handle user.updated event"""
        user_data = InflowUser(**event.data)
        
        # Update user in our database
        result = await self.db.execute(
            select(User).where(User.external_id == user_data.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.username = user_data.username
            user.display_name = user_data.display_name
            user.email = user_data.email
            user.updated_at = datetime.utcnow()
            
            await self.db.commit()
            logger.info(f"Updated user {user.id} from webhook")
            
    async def handle_subscription_created(self, event: WebhookEvent):
        """Handle subscription.created event"""
        sub_data = InflowSubscription(**event.data)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_created",
            user_id=sub_data.subscriber_id,
            metadata={
                "creator_id": sub_data.creator_id,
                "subscription_id": sub_data.id,
                "tier": sub_data.tier,
                "price": float(sub_data.price) if sub_data.price else 0,
                "start_date": sub_data.start_date.isoformat() if sub_data.start_date else None
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded new subscription {sub_data.id}")
        
    async def handle_subscription_cancelled(self, event: WebhookEvent):
        """Handle subscription.cancelled event"""
        sub_data = InflowSubscription(**event.data)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_cancelled",
            user_id=sub_data.subscriber_id,
            metadata={
                "creator_id": sub_data.creator_id,
                "subscription_id": sub_data.id,
                "cancelled_at": sub_data.cancelled_at.isoformat() if sub_data.cancelled_at else None,
                "reason": event.data.get("cancellation_reason")
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded subscription cancellation {sub_data.id}")
        
    async def handle_subscription_renewed(self, event: WebhookEvent):
        """Handle subscription.renewed event"""
        sub_data = InflowSubscription(**event.data)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_renewed",
            user_id=sub_data.subscriber_id,
            metadata={
                "creator_id": sub_data.creator_id,
                "subscription_id": sub_data.id,
                "renewal_date": event.timestamp.isoformat(),
                "price": float(sub_data.price) if sub_data.price else 0
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded subscription renewal {sub_data.id}")
        
    async def handle_message_sent(self, event: WebhookEvent):
        """Handle message.sent event"""
        msg_data = InflowMessage(**event.data)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="message_sent",
            user_id=msg_data.sender_id,
            metadata={
                "message_id": msg_data.id,
                "recipient_id": msg_data.recipient_id,
                "conversation_id": msg_data.conversation_id,
                "is_ppv": msg_data.is_ppv,
                "price": float(msg_data.price) if msg_data.price else None
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded message sent {msg_data.id}")
        
    async def handle_message_purchased(self, event: WebhookEvent):
        """Handle message.purchased event (PPV message bought)"""
        msg_data = InflowMessage(**event.data)
        purchase_data = event.data.get("purchase", {})
        
        # Create transaction record
        transaction = Transaction(
            user_id=purchase_data.get("buyer_id"),
            amount=float(purchase_data.get("amount", 0)),
            currency=purchase_data.get("currency", "USD"),
            type="ppv_purchase",
            status="completed",
            external_id=purchase_data.get("transaction_id"),
            metadata={
                "message_id": msg_data.id,
                "seller_id": msg_data.sender_id,
                "content_type": "message"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="ppv_purchased",
            user_id=purchase_data.get("buyer_id"),
            metadata={
                "message_id": msg_data.id,
                "seller_id": msg_data.sender_id,
                "amount": float(purchase_data.get("amount", 0)),
                "currency": purchase_data.get("currency", "USD")
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded PPV purchase for message {msg_data.id}")
        
    async def handle_transaction_completed(self, event: WebhookEvent):
        """Handle transaction.completed event"""
        trans_data = InflowTransaction(**event.data)
        
        # Check if transaction already exists
        result = await self.db.execute(
            select(Transaction).where(Transaction.external_id == trans_data.id)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            # Create new transaction
            transaction = Transaction(
                user_id=trans_data.user_id,
                amount=float(trans_data.amount),
                currency=trans_data.currency,
                type=trans_data.type,
                status="completed",
                external_id=trans_data.id,
                metadata={
                    "platform": "inflow",
                    "description": trans_data.description,
                    "category": trans_data.metadata.get("category") if trans_data.metadata else None
                }
            )
            
            self.db.add(transaction)
            await self.db.commit()
            
            logger.info(f"Created transaction {transaction.id} from webhook")
            
    async def handle_content_created(self, event: WebhookEvent):
        """Handle content.created event"""
        content_data = InflowContent(**event.data)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="content_created",
            user_id=content_data.creator_id,
            metadata={
                "content_id": content_data.id,
                "content_type": content_data.content_type,
                "title": content_data.title,
                "is_ppv": content_data.is_ppv,
                "price": float(content_data.price) if content_data.price else None
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded content creation {content_data.id}")
        
    async def handle_content_purchased(self, event: WebhookEvent):
        """Handle content.purchased event"""
        content_data = InflowContent(**event.data)
        purchase_data = event.data.get("purchase", {})
        
        # Create transaction record
        transaction = Transaction(
            user_id=purchase_data.get("buyer_id"),
            amount=float(purchase_data.get("amount", 0)),
            currency=purchase_data.get("currency", "USD"),
            type="content_purchase",
            status="completed",
            external_id=purchase_data.get("transaction_id"),
            metadata={
                "content_id": content_data.id,
                "seller_id": content_data.creator_id,
                "content_type": content_data.content_type,
                "title": content_data.title
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="content_purchased",
            user_id=purchase_data.get("buyer_id"),
            metadata={
                "content_id": content_data.id,
                "seller_id": content_data.creator_id,
                "amount": float(purchase_data.get("amount", 0)),
                "currency": purchase_data.get("currency", "USD"),
                "content_type": content_data.content_type
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded content purchase {content_data.id}")
        
    async def handle_tip_received(self, event: WebhookEvent):
        """Handle tip.received event"""
        tip_data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=tip_data.get("recipient_id"),
            amount=float(tip_data.get("amount", 0)),
            currency=tip_data.get("currency", "USD"),
            type="tip_received",
            status="completed",
            external_id=tip_data.get("transaction_id"),
            metadata={
                "tipper_id": tip_data.get("tipper_id"),
                "message": tip_data.get("message"),
                "platform": "inflow"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="tip_received",
            user_id=tip_data.get("recipient_id"),
            metadata={
                "tipper_id": tip_data.get("tipper_id"),
                "amount": float(tip_data.get("amount", 0)),
                "currency": tip_data.get("currency", "USD"),
                "message": tip_data.get("message")
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded tip received {tip_data.get('transaction_id')}")
        
    async def handle_stream_started(self, event: WebhookEvent):
        """Handle stream.started event"""
        stream_data = event.data
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="stream_started",
            user_id=stream_data.get("creator_id"),
            metadata={
                "stream_id": stream_data.get("stream_id"),
                "title": stream_data.get("title"),
                "scheduled_start": stream_data.get("scheduled_start"),
                "actual_start": event.timestamp.isoformat()
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded stream start {stream_data.get('stream_id')}")
        
    async def handle_stream_ended(self, event: WebhookEvent):
        """Handle stream.ended event"""
        stream_data = event.data
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="stream_ended",
            user_id=stream_data.get("creator_id"),
            metadata={
                "stream_id": stream_data.get("stream_id"),
                "duration_seconds": stream_data.get("duration"),
                "viewer_count": stream_data.get("viewer_count"),
                "revenue": stream_data.get("revenue"),
                "tips_received": stream_data.get("tips_received")
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Recorded stream end {stream_data.get('stream_id')}")


def get_event_handler_mapping(db: AsyncSession) -> Dict[str, Any]:
    """Get mapping of event types to handler methods"""
    handler = InflowWebhookEventHandler(db)
    
    return {
        "user.updated": handler.handle_user_updated,
        "subscription.created": handler.handle_subscription_created,
        "subscription.cancelled": handler.handle_subscription_cancelled,
        "subscription.renewed": handler.handle_subscription_renewed,
        "message.sent": handler.handle_message_sent,
        "message.purchased": handler.handle_message_purchased,
        "transaction.completed": handler.handle_transaction_completed,
        "content.created": handler.handle_content_created,
        "content.purchased": handler.handle_content_purchased,
        "tip.received": handler.handle_tip_received,
        "stream.started": handler.handle_stream_started,
        "stream.ended": handler.handle_stream_ended
    }