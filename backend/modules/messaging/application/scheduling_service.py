"""
Message scheduling service for scheduled and recurring messages.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pytz
from uuid import UUID
import asyncio
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

from core.exceptions import BadRequestError, NotFoundError
from core.redis import redis_client
from core.tasks import celery_app
from modules.messaging.domain.models import (
    MessageSchedule, BulkMessage, MessageStatus
)
from modules.messaging.domain.schemas import (
    MessageScheduleCreate, MessageScheduleUpdate, MessageScheduleResponse
)
from modules.onlyfans_wrapper.application.service import OnlyFansService

logger = logging.getLogger(__name__)


class SchedulingService:
    """Service for managing scheduled messages."""
    
    def __init__(self):
        self.onlyfans_service = OnlyFansService()
        self.cache_prefix = "msg_schedule:"
        self.scheduler_lock = "scheduler_lock"
    
    async def create_scheduled_message(
        self,
        data: MessageScheduleCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> MessageScheduleResponse:
        """Create a new scheduled message."""
        # Validate timezone
        try:
            tz = pytz.timezone(data.time_zone)
        except:
            raise BadRequestError(f"Invalid timezone: {data.time_zone}")
        
        # Convert scheduled time to UTC
        local_time = tz.localize(data.scheduled_for.replace(tzinfo=None))
        utc_time = local_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Validate recurrence pattern if provided
        if data.is_recurring and data.recurrence_pattern:
            self._validate_recurrence_pattern(data.recurrence_pattern)
        
        # Create scheduled message
        scheduled_msg = MessageSchedule(
            agency_id=agency_id,
            model_id=data.model_id,
            fan_id=data.fan_id,
            created_by_id=user_id,
            content=data.content,
            media_urls=data.media_urls,
            scheduled_for=utc_time,
            time_zone=data.time_zone,
            platform=data.platform,
            is_recurring=data.is_recurring,
            recurrence_pattern=data.recurrence_pattern,
            recurrence_end_date=data.recurrence_end_date,
            status=MessageStatus.SCHEDULED
        )
        
        db.add(scheduled_msg)
        await db.commit()
        await db.refresh(scheduled_msg)
        
        # Schedule the task
        await self._schedule_message_task(scheduled_msg)
        
        logger.info(f"Created scheduled message {scheduled_msg.id} for {utc_time}")
        return MessageScheduleResponse.from_orm(scheduled_msg)
    
    async def update_scheduled_message(
        self,
        schedule_id: UUID,
        data: MessageScheduleUpdate,
        agency_id: UUID,
        db: AsyncSession
    ) -> MessageScheduleResponse:
        """Update a scheduled message."""
        # Get scheduled message
        result = await db.execute(
            select(MessageSchedule).where(
                MessageSchedule.id == schedule_id,
                MessageSchedule.agency_id == agency_id
            )
        )
        scheduled_msg = result.scalar_one_or_none()
        
        if not scheduled_msg:
            raise NotFoundError("Scheduled message not found")
        
        # Can only update if not sent
        if scheduled_msg.status != MessageStatus.SCHEDULED:
            raise BadRequestError("Cannot update message that has been sent")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        
        # Handle timezone conversion for scheduled_for
        if 'scheduled_for' in update_data and data.scheduled_for:
            tz = pytz.timezone(scheduled_msg.time_zone)
            if 'time_zone' in update_data:
                tz = pytz.timezone(data.time_zone)
            
            local_time = tz.localize(data.scheduled_for.replace(tzinfo=None))
            update_data['scheduled_for'] = local_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Validate recurrence if updated
        if 'recurrence_pattern' in update_data and update_data['recurrence_pattern']:
            self._validate_recurrence_pattern(update_data['recurrence_pattern'])
        
        for field, value in update_data.items():
            setattr(scheduled_msg, field, value)
        
        await db.commit()
        await db.refresh(scheduled_msg)
        
        # Reschedule the task
        await self._cancel_scheduled_task(schedule_id)
        await self._schedule_message_task(scheduled_msg)
        
        return MessageScheduleResponse.from_orm(scheduled_msg)
    
    async def cancel_scheduled_message(
        self,
        schedule_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Cancel a scheduled message."""
        # Get scheduled message
        result = await db.execute(
            select(MessageSchedule).where(
                MessageSchedule.id == schedule_id,
                MessageSchedule.agency_id == agency_id
            )
        )
        scheduled_msg = result.scalar_one_or_none()
        
        if not scheduled_msg:
            raise NotFoundError("Scheduled message not found")
        
        if scheduled_msg.status != MessageStatus.SCHEDULED:
            raise BadRequestError("Message has already been processed")
        
        # Update status
        scheduled_msg.status = MessageStatus.CANCELLED
        await db.commit()
        
        # Cancel scheduled task
        await self._cancel_scheduled_task(schedule_id)
        
        logger.info(f"Cancelled scheduled message {schedule_id}")
        return True
    
    async def get_scheduled_message(
        self,
        schedule_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> MessageScheduleResponse:
        """Get a scheduled message by ID."""
        result = await db.execute(
            select(MessageSchedule).where(
                MessageSchedule.id == schedule_id,
                MessageSchedule.agency_id == agency_id
            )
        )
        scheduled_msg = result.scalar_one_or_none()
        
        if not scheduled_msg:
            raise NotFoundError("Scheduled message not found")
        
        return MessageScheduleResponse.from_orm(scheduled_msg)
    
    async def list_scheduled_messages(
        self,
        agency_id: UUID,
        model_id: Optional[UUID] = None,
        fan_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[MessageScheduleResponse]:
        """List scheduled messages with filtering."""
        query = select(MessageSchedule).where(MessageSchedule.agency_id == agency_id)
        
        # Apply filters
        if model_id:
            query = query.where(MessageSchedule.model_id == model_id)
        
        if fan_id:
            query = query.where(MessageSchedule.fan_id == fan_id)
        
        if status:
            query = query.where(MessageSchedule.status == status)
        
        if date_from:
            query = query.where(MessageSchedule.scheduled_for >= date_from)
        
        if date_to:
            query = query.where(MessageSchedule.scheduled_for <= date_to)
        
        # Order by scheduled time
        query = query.order_by(MessageSchedule.scheduled_for.asc())
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [MessageScheduleResponse.from_orm(msg) for msg in messages]
    
    async def get_calendar_view(
        self,
        agency_id: UUID,
        model_id: UUID,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get calendar view of scheduled messages."""
        # Get scheduled messages in date range
        messages = await self.list_scheduled_messages(
            agency_id=agency_id,
            model_id=model_id,
            date_from=start_date,
            date_to=end_date,
            limit=1000,  # Higher limit for calendar
            db=db
        )
        
        # Get bulk messages in range
        bulk_result = await db.execute(
            select(BulkMessage).where(
                BulkMessage.agency_id == agency_id,
                BulkMessage.model_id == model_id,
                BulkMessage.scheduled_at >= start_date,
                BulkMessage.scheduled_at <= end_date,
                BulkMessage.status.in_([MessageStatus.SCHEDULED, MessageStatus.SENT])
            )
        )
        bulk_messages = bulk_result.scalars().all()
        
        # Organize by date
        calendar = {}
        
        # Add individual scheduled messages
        for msg in messages:
            date_key = msg.scheduled_for.date().isoformat()
            if date_key not in calendar:
                calendar[date_key] = []
            
            calendar[date_key].append({
                "type": "scheduled",
                "id": str(msg.id),
                "time": msg.scheduled_for.time().isoformat(),
                "fan_id": str(msg.fan_id),
                "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                "status": msg.status,
                "is_recurring": msg.is_recurring
            })
        
        # Add bulk messages
        for bulk in bulk_messages:
            if bulk.scheduled_at:
                date_key = bulk.scheduled_at.date().isoformat()
                if date_key not in calendar:
                    calendar[date_key] = []
                
                calendar[date_key].append({
                    "type": "bulk",
                    "id": str(bulk.id),
                    "time": bulk.scheduled_at.time().isoformat(),
                    "campaign_name": bulk.campaign_name,
                    "recipient_count": bulk.total_recipients,
                    "status": bulk.status
                })
        
        # Sort events by time within each day
        for date_key in calendar:
            calendar[date_key].sort(key=lambda x: x['time'])
        
        return calendar
    
    async def process_scheduled_messages(self, db: AsyncSession):
        """Process due scheduled messages (called by scheduler)."""
        # Acquire distributed lock
        lock_acquired = await redis_client.set(
            self.scheduler_lock,
            "1",
            nx=True,
            ex=300  # 5 minute lock
        )
        
        if not lock_acquired:
            logger.debug("Scheduler already running on another instance")
            return
        
        try:
            # Get messages due for sending
            now = datetime.utcnow()
            result = await db.execute(
                select(MessageSchedule).where(
                    MessageSchedule.status == MessageStatus.SCHEDULED,
                    MessageSchedule.scheduled_for <= now
                ).limit(100)  # Process in batches
            )
            due_messages = result.scalars().all()
            
            logger.info(f"Processing {len(due_messages)} scheduled messages")
            
            # Process each message
            for msg in due_messages:
                await self._send_scheduled_message(msg, db)
            
            # Process recurring messages
            await self._process_recurring_messages(db)
            
        finally:
            # Release lock
            await redis_client.delete(self.scheduler_lock)
    
    async def _send_scheduled_message(
        self,
        scheduled_msg: MessageSchedule,
        db: AsyncSession
    ):
        """Send a scheduled message."""
        try:
            # Send via platform
            result = await self.onlyfans_service.send_message(
                model_id=scheduled_msg.model_id,
                fan_id=scheduled_msg.fan_id,
                content=scheduled_msg.content,
                media_urls=scheduled_msg.media_urls
            )
            
            # Update status
            scheduled_msg.status = MessageStatus.SENT
            scheduled_msg.sent_at = datetime.utcnow()
            scheduled_msg.platform_message_id = result.get("message_id")
            
            logger.info(f"Sent scheduled message {scheduled_msg.id}")
            
        except Exception as e:
            logger.error(f"Failed to send scheduled message {scheduled_msg.id}: {e}")
            scheduled_msg.status = MessageStatus.FAILED
            scheduled_msg.error_message = str(e)
        
        await db.commit()
    
    async def _process_recurring_messages(self, db: AsyncSession):
        """Process recurring messages and create next occurrences."""
        # Get sent recurring messages
        result = await db.execute(
            select(MessageSchedule).where(
                MessageSchedule.is_recurring == True,
                MessageSchedule.status == MessageStatus.SENT,
                or_(
                    MessageSchedule.recurrence_end_date.is_(None),
                    MessageSchedule.recurrence_end_date > datetime.utcnow()
                )
            )
        )
        recurring_messages = result.scalars().all()
        
        for msg in recurring_messages:
            # Calculate next occurrence
            next_time = self._calculate_next_occurrence(
                msg.scheduled_for,
                msg.recurrence_pattern
            )
            
            if next_time and (not msg.recurrence_end_date or next_time < msg.recurrence_end_date):
                # Create new scheduled message
                new_msg = MessageSchedule(
                    agency_id=msg.agency_id,
                    model_id=msg.model_id,
                    fan_id=msg.fan_id,
                    created_by_id=msg.created_by_id,
                    content=msg.content,
                    media_urls=msg.media_urls,
                    scheduled_for=next_time,
                    time_zone=msg.time_zone,
                    platform=msg.platform,
                    is_recurring=True,
                    recurrence_pattern=msg.recurrence_pattern,
                    recurrence_end_date=msg.recurrence_end_date,
                    status=MessageStatus.SCHEDULED
                )
                db.add(new_msg)
        
        await db.commit()
    
    def _validate_recurrence_pattern(self, pattern: Dict[str, Any]):
        """Validate recurrence pattern."""
        required_fields = ['type', 'interval']
        for field in required_fields:
            if field not in pattern:
                raise BadRequestError(f"Missing required field in recurrence pattern: {field}")
        
        valid_types = ['daily', 'weekly', 'monthly', 'cron']
        if pattern['type'] not in valid_types:
            raise BadRequestError(f"Invalid recurrence type: {pattern['type']}")
        
        if pattern['type'] == 'cron' and 'cron_expression' not in pattern:
            raise BadRequestError("Cron expression required for cron type recurrence")
        
        if pattern['type'] == 'weekly' and 'days_of_week' not in pattern:
            raise BadRequestError("days_of_week required for weekly recurrence")
    
    def _calculate_next_occurrence(
        self,
        last_time: datetime,
        pattern: Dict[str, Any]
    ) -> Optional[datetime]:
        """Calculate next occurrence based on recurrence pattern."""
        if not pattern:
            return None
        
        recurrence_type = pattern.get('type')
        interval = pattern.get('interval', 1)
        
        if recurrence_type == 'daily':
            return last_time + timedelta(days=interval)
        
        elif recurrence_type == 'weekly':
            days_of_week = pattern.get('days_of_week', [])
            if not days_of_week:
                return last_time + timedelta(weeks=interval)
            
            # Find next occurrence on specified days
            current_day = last_time.weekday()
            for i in range(1, 8):
                next_day = (current_day + i) % 7
                if next_day in days_of_week:
                    return last_time + timedelta(days=i)
        
        elif recurrence_type == 'monthly':
            # Simple monthly - same day of month
            next_month = last_time.month + interval
            year = last_time.year + (next_month - 1) // 12
            month = ((next_month - 1) % 12) + 1
            
            try:
                return last_time.replace(year=year, month=month)
            except ValueError:
                # Handle end of month cases
                return last_time.replace(year=year, month=month, day=1) + timedelta(days=30)
        
        elif recurrence_type == 'cron':
            cron_expr = pattern.get('cron_expression')
            if cron_expr:
                cron = croniter(cron_expr, last_time)
                return cron.get_next(datetime)
        
        return None
    
    async def _schedule_message_task(self, scheduled_msg: MessageSchedule):
        """Schedule a message task with Celery."""
        # Calculate delay
        delay = (scheduled_msg.scheduled_for - datetime.utcnow()).total_seconds()
        
        if delay > 0:
            # Schedule with Celery
            from modules.messaging.tasks import send_scheduled_message
            task = send_scheduled_message.apply_async(
                args=[str(scheduled_msg.id)],
                countdown=delay
            )
            
            # Store task ID for cancellation
            await redis_client.set(
                f"{self.cache_prefix}task:{scheduled_msg.id}",
                task.id,
                ex=int(delay) + 3600  # Expire after delay + 1 hour
            )
    
    async def _cancel_scheduled_task(self, schedule_id: UUID):
        """Cancel a scheduled task."""
        # Get task ID from cache
        task_id = await redis_client.get(f"{self.cache_prefix}task:{schedule_id}")
        
        if task_id:
            # Cancel Celery task
            celery_app.control.revoke(task_id, terminate=True)
            
            # Clear from cache
            await redis_client.delete(f"{self.cache_prefix}task:{schedule_id}")