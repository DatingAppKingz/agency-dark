"""
Bulk messaging service for sending messages to multiple recipients.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

from core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from core.redis import redis_client
from modules.messaging.domain.models import (
    BulkMessage, BulkMessageRecipient, MessageTemplate,
    MessageStatus, MessagePriority
)
from modules.messaging.domain.schemas import (
    BulkMessageCreate, BulkMessageUpdate, BulkMessageResponse,
    BulkMessageStats, RecipientFilter, RecipientListResponse
)
from modules.messaging.application.template_service import TemplateService
from modules.onlyfans_wrapper.application.service import OnlyFansService
from modules.analytics.domain.models import Fan

logger = logging.getLogger(__name__)


class BulkMessageService:
    """Service for managing bulk message campaigns."""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.onlyfans_service = OnlyFansService()
        self.cache_prefix = "bulk_message:"
        self.rate_limit_key = "bulk_rate:"
    
    async def create_bulk_message(
        self,
        data: BulkMessageCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> BulkMessageResponse:
        """Create a new bulk message campaign."""
        # Validate template if provided
        content = data.content
        variables = []
        
        if data.template_id:
            template = await self.template_service.get_template(
                data.template_id, agency_id, db
            )
            if not template:
                raise NotFoundError("Template not found")
            
            content = template.content
            variables = template.variables
        
        # Create bulk message
        bulk_message = BulkMessage(
            agency_id=agency_id,
            model_id=data.model_id,
            created_by_id=user_id,
            template_id=data.template_id,
            campaign_name=data.campaign_name,
            subject=data.subject,
            content=content,
            scheduled_at=data.scheduled_at,
            time_zone=data.time_zone,
            priority=data.priority,
            recipient_filters=data.recipient_filters.dict(),
            personalize=data.personalize,
            track_opens=data.track_opens,
            track_clicks=data.track_clicks,
            messages_per_minute=data.messages_per_minute,
            status=MessageStatus.SCHEDULED if data.scheduled_at else MessageStatus.DRAFT
        )
        
        db.add(bulk_message)
        await db.flush()
        
        # Get recipients based on filters
        recipients = await self._get_filtered_recipients(
            data.model_id,
            data.recipient_filters,
            db
        )
        
        if data.send_test and data.test_recipient_ids:
            # Filter to only test recipients
            recipients = [r for r in recipients if r.id in data.test_recipient_ids]
        
        # Create recipient records
        bulk_message.total_recipients = len(recipients)
        
        for fan in recipients:
            personalized_content = content
            
            # Personalize content if enabled
            if data.personalize and variables:
                personalized_content = await self._personalize_content(
                    content, variables, fan, db
                )
            
            recipient = BulkMessageRecipient(
                bulk_message_id=bulk_message.id,
                fan_id=fan.id,
                personalized_content=personalized_content,
                status=MessageStatus.SCHEDULED
            )
            db.add(recipient)
        
        await db.commit()
        await db.refresh(bulk_message)
        
        # Schedule immediate sending if not scheduled
        if not data.scheduled_at:
            asyncio.create_task(
                self._process_bulk_message(bulk_message.id, db)
            )
        
        # Update template usage
        if data.template_id:
            await self.template_service.increment_usage(
                data.template_id, agency_id, db
            )
        
        return BulkMessageResponse.from_orm(bulk_message)
    
    async def update_bulk_message(
        self,
        message_id: UUID,
        data: BulkMessageUpdate,
        agency_id: UUID,
        db: AsyncSession
    ) -> BulkMessageResponse:
        """Update a bulk message campaign."""
        # Get bulk message
        result = await db.execute(
            select(BulkMessage).where(
                BulkMessage.id == message_id,
                BulkMessage.agency_id == agency_id
            )
        )
        bulk_message = result.scalar_one_or_none()
        
        if not bulk_message:
            raise NotFoundError("Bulk message not found")
        
        # Can only update if not started
        if bulk_message.status not in [MessageStatus.DRAFT, MessageStatus.SCHEDULED]:
            raise BadRequestError("Cannot update message that has started sending")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(bulk_message, field, value)
        
        # Update status if schedule changed
        if data.scheduled_at is not None:
            bulk_message.status = MessageStatus.SCHEDULED if data.scheduled_at else MessageStatus.DRAFT
        
        await db.commit()
        await db.refresh(bulk_message)
        
        return BulkMessageResponse.from_orm(bulk_message)
    
    async def cancel_bulk_message(
        self,
        message_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> BulkMessageResponse:
        """Cancel a bulk message campaign."""
        # Get bulk message
        result = await db.execute(
            select(BulkMessage).where(
                BulkMessage.id == message_id,
                BulkMessage.agency_id == agency_id
            )
        )
        bulk_message = result.scalar_one_or_none()
        
        if not bulk_message:
            raise NotFoundError("Bulk message not found")
        
        # Can only cancel if not completed
        if bulk_message.status in [MessageStatus.SENT, MessageStatus.CANCELLED]:
            raise BadRequestError("Cannot cancel completed message")
        
        # Update status
        bulk_message.status = MessageStatus.CANCELLED
        bulk_message.completed_at = datetime.utcnow()
        
        # Cancel unsent recipients
        await db.execute(
            update(BulkMessageRecipient)
            .where(
                BulkMessageRecipient.bulk_message_id == message_id,
                BulkMessageRecipient.status == MessageStatus.SCHEDULED
            )
            .values(status=MessageStatus.CANCELLED)
        )
        
        await db.commit()
        await db.refresh(bulk_message)
        
        # Clear from cache
        await self._clear_cache(message_id)
        
        return BulkMessageResponse.from_orm(bulk_message)
    
    async def get_bulk_message(
        self,
        message_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> BulkMessageResponse:
        """Get a bulk message by ID."""
        result = await db.execute(
            select(BulkMessage)
            .options(selectinload(BulkMessage.template))
            .where(
                BulkMessage.id == message_id,
                BulkMessage.agency_id == agency_id
            )
        )
        bulk_message = result.scalar_one_or_none()
        
        if not bulk_message:
            raise NotFoundError("Bulk message not found")
        
        return BulkMessageResponse.from_orm(bulk_message)
    
    async def list_bulk_messages(
        self,
        agency_id: UUID,
        model_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[BulkMessageResponse]:
        """List bulk messages with filtering."""
        query = select(BulkMessage).where(BulkMessage.agency_id == agency_id)
        
        if model_id:
            query = query.where(BulkMessage.model_id == model_id)
        
        if status:
            query = query.where(BulkMessage.status == status)
        
        query = query.order_by(BulkMessage.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [BulkMessageResponse.from_orm(msg) for msg in messages]
    
    async def get_message_stats(
        self,
        message_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> BulkMessageStats:
        """Get statistics for a bulk message."""
        # Get bulk message
        bulk_message = await self.get_bulk_message(message_id, agency_id, db)
        
        # Get recipient stats
        result = await db.execute(
            select(
                func.count(BulkMessageRecipient.id).label('total'),
                func.sum(func.cast(BulkMessageRecipient.status == MessageStatus.SENT, func.Integer)).label('sent'),
                func.sum(func.cast(BulkMessageRecipient.status == MessageStatus.FAILED, func.Integer)).label('failed'),
                func.sum(func.cast(BulkMessageRecipient.opened_at.isnot(None), func.Integer)).label('opened'),
                func.sum(func.cast(BulkMessageRecipient.clicked_at.isnot(None), func.Integer)).label('clicked')
            ).where(BulkMessageRecipient.bulk_message_id == message_id)
        )
        stats = result.first()
        
        total = stats.total or 0
        sent = stats.sent or 0
        failed = stats.failed or 0
        opened = stats.opened or 0
        clicked = stats.clicked or 0
        pending = total - sent - failed
        
        # Calculate rates
        open_rate = (opened / sent * 100) if sent > 0 else 0
        click_rate = (clicked / sent * 100) if sent > 0 else 0
        
        # Calculate average send time
        avg_send_time = None
        if bulk_message.started_at and sent > 0:
            elapsed = (datetime.utcnow() - bulk_message.started_at).total_seconds()
            avg_send_time = elapsed / sent
        
        # Estimate completion time
        estimated_completion = None
        if pending > 0 and avg_send_time:
            remaining_seconds = pending * avg_send_time
            estimated_completion = datetime.utcnow() + timedelta(seconds=remaining_seconds)
        
        return BulkMessageStats(
            total_recipients=total,
            sent_count=sent,
            failed_count=failed,
            pending_count=pending,
            open_rate=open_rate,
            click_rate=click_rate,
            avg_send_time_seconds=avg_send_time,
            estimated_completion_time=estimated_completion
        )
    
    async def get_recipients(
        self,
        message_id: UUID,
        agency_id: UUID,
        status_filter: Optional[MessageStatus] = None,
        skip: int = 0,
        limit: int = 50,
        db: AsyncSession = None
    ) -> RecipientListResponse:
        """Get recipients for a bulk message."""
        # Verify ownership
        bulk_message = await self.get_bulk_message(message_id, agency_id, db)
        
        # Build query
        query = select(BulkMessageRecipient).where(
            BulkMessageRecipient.bulk_message_id == message_id
        )
        
        if status_filter:
            query = query.where(BulkMessageRecipient.status == status_filter)
        
        # Get total count
        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Get paginated results
        query = query.options(selectinload(BulkMessageRecipient.fan))
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        recipients = result.scalars().all()
        
        # Build response
        recipient_list = []
        sent = failed = pending = 0
        
        for recipient in recipients:
            recipient_list.append({
                "fan_id": recipient.fan_id,
                "fan_name": recipient.fan.display_name or recipient.fan.username,
                "status": recipient.status,
                "sent_at": recipient.sent_at,
                "opened_at": recipient.opened_at,
                "clicked_at": recipient.clicked_at,
                "error_message": recipient.error_message
            })
            
            if recipient.status == MessageStatus.SENT:
                sent += 1
            elif recipient.status == MessageStatus.FAILED:
                failed += 1
            else:
                pending += 1
        
        return RecipientListResponse(
            recipients=recipient_list,
            total=total,
            sent=sent,
            failed=failed,
            pending=pending
        )
    
    async def _get_filtered_recipients(
        self,
        model_id: UUID,
        filters: RecipientFilter,
        db: AsyncSession
    ) -> List[Fan]:
        """Get fans based on filter criteria."""
        query = select(Fan).where(Fan.model_id == model_id)
        
        # Apply filters
        if filters.subscription_status:
            query = query.where(Fan.subscription_status.in_(filters.subscription_status))
        
        if filters.spent_min is not None:
            query = query.where(Fan.total_spent >= filters.spent_min)
        
        if filters.spent_max is not None:
            query = query.where(Fan.total_spent <= filters.spent_max)
        
        if filters.last_active_days:
            cutoff_date = datetime.utcnow() - timedelta(days=filters.last_active_days)
            query = query.where(Fan.last_activity > cutoff_date)
        
        if filters.tags:
            # Assuming tags are stored as JSON array
            for tag in filters.tags:
                query = query.where(Fan.tags.contains([tag]))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def _personalize_content(
        self,
        content: str,
        variables: List[str],
        fan: Fan,
        db: AsyncSession
    ) -> str:
        """Personalize content with fan-specific data."""
        personalized = content
        
        # Replace variables
        replacements = {
            "fan_name": fan.display_name or fan.username or "there",
            "fan_username": fan.username,
            "subscription_days": (datetime.utcnow() - fan.subscribed_at).days if fan.subscribed_at else 0,
            "total_spent": f"${fan.total_spent:.2f}" if fan.total_spent else "$0.00",
        }
        
        for var in variables:
            placeholder = f"{{{{{var}}}}}"
            if var in replacements:
                personalized = personalized.replace(placeholder, str(replacements[var]))
        
        return personalized
    
    async def _process_bulk_message(
        self,
        message_id: UUID,
        db: AsyncSession
    ):
        """Process and send a bulk message campaign."""
        try:
            # Update status to sending
            await db.execute(
                update(BulkMessage)
                .where(BulkMessage.id == message_id)
                .values(
                    status=MessageStatus.SENDING,
                    started_at=datetime.utcnow()
                )
            )
            await db.commit()
            
            # Get recipients to process
            result = await db.execute(
                select(BulkMessageRecipient)
                .options(selectinload(BulkMessageRecipient.fan))
                .where(
                    BulkMessageRecipient.bulk_message_id == message_id,
                    BulkMessageRecipient.status == MessageStatus.SCHEDULED
                )
            )
            recipients = result.scalars().all()
            
            # Get bulk message details
            msg_result = await db.execute(
                select(BulkMessage).where(BulkMessage.id == message_id)
            )
            bulk_message = msg_result.scalar_one()
            
            # Process recipients with rate limiting
            for recipient in recipients:
                try:
                    # Check rate limit
                    await self._check_rate_limit(
                        bulk_message.model_id,
                        bulk_message.messages_per_minute
                    )
                    
                    # Send message via platform
                    result = await self.onlyfans_service.send_message(
                        model_id=bulk_message.model_id,
                        fan_id=recipient.fan_id,
                        content=recipient.personalized_content,
                        media_urls=[]  # TODO: Add media support
                    )
                    
                    # Update recipient status
                    recipient.status = MessageStatus.SENT
                    recipient.sent_at = datetime.utcnow()
                    recipient.platform_message_id = result.get("message_id")
                    
                    # Update counters
                    bulk_message.sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to send to recipient {recipient.id}: {e}")
                    recipient.status = MessageStatus.FAILED
                    recipient.failed_at = datetime.utcnow()
                    recipient.error_message = str(e)
                    recipient.retry_count += 1
                    
                    bulk_message.failed_count += 1
                
                await db.commit()
            
            # Update final status
            if bulk_message.sent_count == bulk_message.total_recipients:
                bulk_message.status = MessageStatus.SENT
            elif bulk_message.failed_count == bulk_message.total_recipients:
                bulk_message.status = MessageStatus.FAILED
            else:
                bulk_message.status = MessageStatus.PARTIALLY_SENT
            
            bulk_message.completed_at = datetime.utcnow()
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error processing bulk message {message_id}: {e}")
            await db.execute(
                update(BulkMessage)
                .where(BulkMessage.id == message_id)
                .values(
                    status=MessageStatus.FAILED,
                    completed_at=datetime.utcnow()
                )
            )
            await db.commit()
    
    async def _check_rate_limit(
        self,
        model_id: UUID,
        messages_per_minute: int
    ):
        """Check and enforce rate limiting."""
        key = f"{self.rate_limit_key}{model_id}"
        current = await redis_client.get(key)
        
        if current and int(current) >= messages_per_minute:
            # Wait until next minute
            await asyncio.sleep(60)
        
        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        await pipe.execute()
    
    async def _clear_cache(self, message_id: UUID):
        """Clear cache for a bulk message."""
        pattern = f"{self.cache_prefix}{message_id}*"
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)