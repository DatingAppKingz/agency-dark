"""
OnlyFans webhook handlers and event processing
"""
from typing import Dict, Any
from datetime import datetime
import logging
import hmac
import hashlib

from core.external_api.webhooks import HMACWebhookHandler, WebhookEvent
from core.database import AsyncSession
from sqlalchemy import select

from ..domain.schemas import (
    OnlyFansFan, OnlyFansMessage, OnlyFansTransaction,
    OnlyFansPost, OnlyFansNotification
)
from core.domain.models import User, Transaction, Fan
from modules.analytics.domain.models import AnalyticsEvent


logger = logging.getLogger(__name__)


class OnlyFansWebhookHandler(HMACWebhookHandler):
    """Webhook handler for OnlyFans events"""
    
    def __init__(self, webhook_secret: str):
        super().__init__(
            api_name="onlyfans",
            signature_header="x-onlyfans-signature",
            hash_algorithm="sha256"
        )
        self.webhook_secret = webhook_secret
        
    def parse_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse OnlyFans webhook payload"""
        return WebhookEvent(
            id=payload.get('id', 'unknown'),
            type=payload.get('type', 'unknown'),
            timestamp=datetime.fromisoformat(
                payload.get('created_at', datetime.utcnow().isoformat())
            ),
            data=payload.get('data', {})
        )
        
    async def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify OnlyFans webhook signature"""
        # OnlyFans uses HMAC-SHA256 with the raw payload
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)


class OnlyFansWebhookEventHandler:
    """Handler for OnlyFans webhook events"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def handle_subscription_create(self, event: WebhookEvent):
        """Handle subscription.create event"""
        data = event.data
        
        # Create or update fan record
        result = await self.db.execute(
            select(Fan).where(
                Fan.onlyfans_user_id == data.get('user_id'),
                Fan.model_id == data.get('creator_id')
            )
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            fan = Fan(
                onlyfans_user_id=data.get('user_id'),
                model_id=data.get('creator_id'),
                username=data.get('username'),
                display_name=data.get('display_name'),
                subscription_status='active',
                subscription_price=float(data.get('price', 0)),
                subscribed_at=event.timestamp
            )
            self.db.add(fan)
        else:
            fan.subscription_status = 'active'
            fan.subscription_price = float(data.get('price', 0))
            fan.subscribed_at = event.timestamp
            
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_created",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "price": float(data.get('price', 0)),
                "subscription_type": data.get('subscription_type', 'monthly'),
                "platform": "onlyfans"
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed subscription create for fan {data.get('user_id')}")
        
    async def handle_subscription_renew(self, event: WebhookEvent):
        """Handle subscription.renew event"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="subscription_renewal",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "subscription_id": data.get('subscription_id'),
                "platform": "onlyfans"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_renewed",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD')
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed subscription renewal for fan {data.get('user_id')}")
        
    async def handle_subscription_cancel(self, event: WebhookEvent):
        """Handle subscription.cancel event"""
        data = event.data
        
        # Update fan record
        result = await self.db.execute(
            select(Fan).where(
                Fan.onlyfans_user_id == data.get('user_id'),
                Fan.model_id == data.get('creator_id')
            )
        )
        fan = result.scalar_one_or_none()
        
        if fan:
            fan.subscription_status = 'cancelled'
            fan.cancelled_at = event.timestamp
            
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="subscription_cancelled",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "reason": data.get('reason'),
                "will_renew": data.get('will_renew', False)
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed subscription cancellation for fan {data.get('user_id')}")
        
    async def handle_tip(self, event: WebhookEvent):
        """Handle tip event"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="tip",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "message": data.get('message'),
                "platform": "onlyfans"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="tip_received",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD'),
                "has_message": bool(data.get('message'))
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed tip from fan {data.get('user_id')}")
        
    async def handle_message_purchase(self, event: WebhookEvent):
        """Handle message.purchase event (PPV message)"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="ppv_purchase",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "message_id": data.get('message_id'),
                "platform": "onlyfans",
                "content_type": "message"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="ppv_purchased",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "message_id": data.get('message_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD')
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed PPV message purchase from fan {data.get('user_id')}")
        
    async def handle_post_purchase(self, event: WebhookEvent):
        """Handle post.purchase event (PPV post)"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="ppv_purchase",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "post_id": data.get('post_id'),
                "platform": "onlyfans",
                "content_type": "post"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="content_purchased",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "post_id": data.get('post_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD'),
                "content_type": "post"
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed PPV post purchase from fan {data.get('user_id')}")
        
    async def handle_stream_tip(self, event: WebhookEvent):
        """Handle stream.tip event"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="stream_tip",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "stream_id": data.get('stream_id'),
                "message": data.get('message'),
                "platform": "onlyfans"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="stream_tip_received",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "stream_id": data.get('stream_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD')
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed stream tip from fan {data.get('user_id')}")
        
    async def handle_referral_transaction(self, event: WebhookEvent):
        """Handle referral.transaction event"""
        data = event.data
        
        # Create transaction record
        transaction = Transaction(
            user_id=data.get('referee_id'),  # The person who earned the referral
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            type="referral_earning",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "referrer_id": data.get('referrer_id'),
                "referred_user_id": data.get('referred_user_id'),
                "platform": "onlyfans"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="referral_earned",
            user_id=data.get('referee_id'),
            metadata={
                "referrer_id": data.get('referrer_id'),
                "referred_user_id": data.get('referred_user_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD')
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed referral transaction for {data.get('referee_id')}")
        
    async def handle_chargeback(self, event: WebhookEvent):
        """Handle chargeback event"""
        data = event.data
        
        # Create negative transaction record
        transaction = Transaction(
            user_id=data.get('creator_id'),
            amount=-float(data.get('amount', 0)),  # Negative amount
            currency=data.get('currency', 'USD'),
            type="chargeback",
            status="completed",
            external_id=data.get('transaction_id'),
            metadata={
                "original_transaction_id": data.get('original_transaction_id'),
                "fan_id": data.get('user_id'),
                "reason": data.get('reason'),
                "platform": "onlyfans"
            }
        )
        
        self.db.add(transaction)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="chargeback_received",
            user_id=data.get('creator_id'),
            metadata={
                "fan_id": data.get('user_id'),
                "amount": float(data.get('amount', 0)),
                "currency": data.get('currency', 'USD'),
                "reason": data.get('reason')
            },
            timestamp=event.timestamp
        )
        
        self.db.add(analytics_event)
        await self.db.commit()
        
        logger.info(f"Processed chargeback from fan {data.get('user_id')}")


def get_event_handler_mapping(db: AsyncSession) -> Dict[str, Any]:
    """Get mapping of event types to handler methods"""
    handler = OnlyFansWebhookEventHandler(db)
    
    return {
        "subscription.create": handler.handle_subscription_create,
        "subscription.renew": handler.handle_subscription_renew,
        "subscription.cancel": handler.handle_subscription_cancel,
        "tip": handler.handle_tip,
        "message.purchase": handler.handle_message_purchase,
        "post.purchase": handler.handle_post_purchase,
        "stream.tip": handler.handle_stream_tip,
        "referral.transaction": handler.handle_referral_transaction,
        "chargeback": handler.handle_chargeback
    }