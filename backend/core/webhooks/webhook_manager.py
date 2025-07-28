"""
Webhook management system
"""
import secrets
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.database import get_db
from .webhook_models import (
    Webhook, WebhookDelivery, WebhookEvent, 
    WebhookStatus, DeliveryStatus, WebhookPayload,
    WebhookDeadLetter
)
from .webhook_sender import WebhookSender

logger = get_logger(__name__)


class WebhookManager:
    """Manage webhooks and deliveries"""
    
    def __init__(self):
        self.sender = WebhookSender()
        self._event_handlers: Dict[WebhookEvent, List[callable]] = {}
        
    async def create_webhook(
        self,
        agency_id: UUID,
        url: str,
        events: List[WebhookEvent],
        description: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        db: AsyncSession = None
    ) -> Webhook:
        """Create a new webhook"""
        if db is None:
            async with get_db() as db:
                return await self._create_webhook(
                    agency_id, url, events, description, custom_headers, db
                )
        else:
            return await self._create_webhook(
                agency_id, url, events, description, custom_headers, db
            )
    
    async def _create_webhook(
        self,
        agency_id: UUID,
        url: str,
        events: List[WebhookEvent],
        description: Optional[str],
        custom_headers: Optional[Dict[str, str]],
        db: AsyncSession
    ) -> Webhook:
        """Internal method to create webhook"""
        # Generate secret for signing
        secret = secrets.token_urlsafe(32)
        
        webhook = Webhook(
            agency_id=str(agency_id),
            url=url,
            secret=secret,
            events=[e.value for e in events],
            description=description,
            custom_headers=custom_headers or {}
        )
        
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        
        logger.info(f"Created webhook {webhook.id} for agency {agency_id}")
        
        return webhook
    
    async def update_webhook(
        self,
        webhook_id: str,
        updates: Dict[str, Any],
        db: AsyncSession
    ) -> Webhook:
        """Update webhook configuration"""
        webhook = await db.get(Webhook, webhook_id)
        if not webhook:
            raise ValueError(f"Webhook {webhook_id} not found")
        
        for key, value in updates.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        webhook.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(webhook)
        
        return webhook
    
    async def delete_webhook(
        self,
        webhook_id: str,
        db: AsyncSession
    ) -> bool:
        """Delete a webhook"""
        webhook = await db.get(Webhook, webhook_id)
        if not webhook:
            return False
        
        await db.delete(webhook)
        await db.commit()
        
        logger.info(f"Deleted webhook {webhook_id}")
        
        return True
    
    async def get_webhooks_for_event(
        self,
        agency_id: UUID,
        event: WebhookEvent,
        db: AsyncSession
    ) -> List[Webhook]:
        """Get all active webhooks for an event"""
        query = select(Webhook).where(
            and_(
                Webhook.agency_id == str(agency_id),
                Webhook.is_active == True,
                Webhook.events.contains([event.value])
            )
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def trigger_event(
        self,
        agency_id: UUID,
        event: WebhookEvent,
        event_id: str,
        data: Dict[str, Any],
        db: AsyncSession = None
    ):
        """Trigger webhook event for all subscribed webhooks"""
        if db is None:
            async with get_db() as db:
                await self._trigger_event(agency_id, event, event_id, data, db)
        else:
            await self._trigger_event(agency_id, event, event_id, data, db)
    
    async def _trigger_event(
        self,
        agency_id: UUID,
        event: WebhookEvent,
        event_id: str,
        data: Dict[str, Any],
        db: AsyncSession
    ):
        """Internal method to trigger event"""
        # Get webhooks for this event
        webhooks = await self.get_webhooks_for_event(agency_id, event, db)
        
        if not webhooks:
            return
        
        # Create payload
        payload = WebhookPayload(
            event=event,
            event_id=event_id,
            data=data
        )
        
        # Create delivery records and send
        tasks = []
        for webhook in webhooks:
            delivery = await self._create_delivery(
                webhook, event, event_id, payload.dict(), db
            )
            
            # Queue async delivery
            task = asyncio.create_task(
                self._deliver_webhook(webhook, delivery, payload, db)
            )
            tasks.append(task)
        
        # Don't wait for deliveries to complete
        # They will run in the background
        
        logger.info(
            f"Triggered {len(webhooks)} webhooks for event {event.value} "
            f"(agency: {agency_id}, event_id: {event_id})"
        )
    
    async def _create_delivery(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        event_id: str,
        payload: Dict[str, Any],
        db: AsyncSession
    ) -> WebhookDelivery:
        """Create delivery record"""
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event.value,
            event_id=event_id,
            request_body=payload,
            status=DeliveryStatus.PENDING.value
        )
        
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)
        
        return delivery
    
    async def _deliver_webhook(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery,
        payload: WebhookPayload,
        db: AsyncSession
    ):
        """Deliver webhook with retries"""
        max_attempts = webhook.max_retries + 1 if webhook.retry_enabled else 1
        
        for attempt in range(max_attempts):
            try:
                # Update attempt count
                delivery.attempts = attempt + 1
                
                # Send webhook
                response = await self.sender.send(
                    webhook=webhook,
                    payload=payload.dict(),
                    timeout=webhook.timeout_seconds
                )
                
                # Update delivery record
                delivery.status = DeliveryStatus.SUCCESS.value
                delivery.response_status_code = response.status_code
                delivery.response_headers = dict(response.headers)
                delivery.response_body = response.text[:1000]  # Limit response size
                delivery.response_time_ms = response.elapsed_ms
                delivery.delivered_at = datetime.utcnow()
                
                # Update webhook statistics
                webhook.total_deliveries += 1
                webhook.successful_deliveries += 1
                webhook.last_delivery_at = datetime.utcnow()
                webhook.last_success_at = datetime.utcnow()
                
                await db.commit()
                
                logger.info(
                    f"Successfully delivered webhook {webhook.id} "
                    f"(event: {delivery.event_type}, attempt: {attempt + 1})"
                )
                
                break
                
            except Exception as e:
                logger.error(
                    f"Failed to deliver webhook {webhook.id} "
                    f"(attempt {attempt + 1}/{max_attempts}): {e}"
                )
                
                delivery.error_message = str(e)
                
                if attempt < max_attempts - 1:
                    # Calculate next retry time with exponential backoff
                    delay = min(2 ** attempt * 60, 3600)  # Max 1 hour
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                    delivery.status = DeliveryStatus.RETRYING.value
                else:
                    # Final failure
                    delivery.status = DeliveryStatus.FAILED.value
                    
                    # Update webhook statistics
                    webhook.total_deliveries += 1
                    webhook.failed_deliveries += 1
                    webhook.last_delivery_at = datetime.utcnow()
                    webhook.last_failure_at = datetime.utcnow()
                    
                    # Disable webhook after too many failures
                    if webhook.failed_deliveries > 10 and \
                       webhook.successful_deliveries < webhook.failed_deliveries * 0.1:
                        webhook.is_active = False
                        logger.warning(
                            f"Disabled webhook {webhook.id} due to high failure rate"
                        )
                
                await db.commit()
                
                # Move to dead letter queue after final failure
                if attempt == max_attempts - 1:
                    await self.move_to_dead_letter_queue(
                        delivery=delivery,
                        webhook=webhook,
                        payload=payload.dict(),
                        error_summary=str(e),
                        db=db
                    )
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
    
    async def retry_failed_deliveries(self, db: AsyncSession):
        """Retry failed webhook deliveries"""
        # Get deliveries that need retry
        query = select(WebhookDelivery).where(
            and_(
                WebhookDelivery.status == DeliveryStatus.RETRYING.value,
                WebhookDelivery.next_retry_at <= datetime.utcnow()
            )
        )
        
        result = await db.execute(query)
        deliveries = result.scalars().all()
        
        for delivery in deliveries:
            webhook = await db.get(Webhook, delivery.webhook_id)
            if webhook and webhook.is_active:
                # Retry delivery
                payload = WebhookPayload(
                    event=WebhookEvent(delivery.event_type),
                    event_id=delivery.event_id,
                    timestamp=delivery.created_at,
                    data=delivery.request_body.get("data", {})
                )
                
                await self._deliver_webhook(webhook, delivery, payload, db)
    
    async def get_webhook_deliveries(
        self,
        webhook_id: str,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession
    ) -> List[WebhookDelivery]:
        """Get delivery history for a webhook"""
        query = (
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    def generate_signature(self, webhook: Webhook, payload: str) -> str:
        """Generate HMAC signature for webhook payload"""
        signature = hmac.new(
            webhook.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def verify_signature(
        self,
        webhook: Webhook,
        payload: str,
        signature: str
    ) -> bool:
        """Verify webhook signature"""
        expected = self.generate_signature(webhook, payload)
        return hmac.compare_digest(expected, signature)
    
    # Event handler registration for custom processing
    def register_event_handler(
        self,
        event: WebhookEvent,
        handler: callable
    ):
        """Register custom event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        
        self._event_handlers[event].append(handler)
    
    async def process_event_handlers(
        self,
        event: WebhookEvent,
        data: Dict[str, Any]
    ):
        """Process registered event handlers"""
        handlers = self._event_handlers.get(event, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, data)
                else:
                    handler(event, data)
            except Exception as e:
                logger.error(f"Error in event handler for {event.value}: {e}")
    
    async def move_to_dead_letter_queue(
        self,
        delivery: WebhookDelivery,
        webhook: Webhook,
        payload: Dict[str, Any],
        error_summary: str,
        db: AsyncSession
    ) -> WebhookDeadLetter:
        """
        Move failed delivery to dead letter queue
        """
        # Create dead letter entry
        dead_letter = WebhookDeadLetter(
            webhook_id=webhook.id,
            delivery_id=delivery.id,
            event_type=delivery.event_type,
            event_id=delivery.event_id,
            payload=payload,
            final_status_code=delivery.response_status_code,
            total_attempts=delivery.attempts,
            first_attempt_at=delivery.created_at,
            last_attempt_at=datetime.utcnow(),
            error_summary=error_summary,
            expires_at=datetime.utcnow() + timedelta(days=90)  # Keep for 90 days
        )
        
        db.add(dead_letter)
        
        # Update delivery status
        delivery.status = DeliveryStatus.FAILED.value
        
        await db.commit()
        await db.refresh(dead_letter)
        
        logger.warning(
            f"Moved webhook delivery {delivery.id} to dead letter queue. "
            f"Event: {delivery.event_type}, Error: {error_summary}"
        )
        
        return dead_letter
    
    async def reprocess_dead_letter(
        self,
        dead_letter_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Attempt to reprocess a dead letter webhook
        """
        dead_letter = await db.get(WebhookDeadLetter, dead_letter_id)
        if not dead_letter:
            raise ValueError(f"Dead letter {dead_letter_id} not found")
        
        if dead_letter.is_reprocessed:
            raise ValueError(f"Dead letter {dead_letter_id} has already been reprocessed")
        
        webhook = await db.get(Webhook, dead_letter.webhook_id)
        if not webhook or not webhook.is_active:
            raise ValueError("Webhook is not active")
        
        try:
            # Create new delivery
            delivery = await self._create_delivery(
                webhook=webhook,
                event=WebhookEvent(dead_letter.event_type),
                event_id=dead_letter.event_id,
                payload=dead_letter.payload,
                db=db
            )
            
            # Attempt delivery
            response = await self.sender.send_with_retry(
                webhook=webhook,
                payload=dead_letter.payload,
                delivery=delivery
            )
            
            # Mark as reprocessed
            dead_letter.is_reprocessed = True
            dead_letter.reprocessed_at = datetime.utcnow()
            
            await db.commit()
            
            logger.info(f"Successfully reprocessed dead letter {dead_letter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reprocess dead letter {dead_letter_id}: {e}")
            return False
    
    async def get_dead_letters(
        self,
        agency_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession = None
    ) -> List[WebhookDeadLetter]:
        """
        Get dead letter entries
        """
        if db is None:
            async with get_db() as db:
                return await self._get_dead_letters(agency_id, limit, offset, db)
        else:
            return await self._get_dead_letters(agency_id, limit, offset, db)
    
    async def _get_dead_letters(
        self,
        agency_id: Optional[UUID],
        limit: int,
        offset: int,
        db: AsyncSession
    ) -> List[WebhookDeadLetter]:
        """Internal method to get dead letters"""
        stmt = select(WebhookDeadLetter).join(Webhook)
        
        if agency_id:
            stmt = stmt.where(Webhook.agency_id == str(agency_id))
        
        stmt = stmt.order_by(WebhookDeadLetter.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        return result.scalars().all()


# Global webhook manager instance
webhook_manager = WebhookManager()