"""
Celery tasks for messaging module.

Handles background processing of messages, scheduling, and analytics.
"""
import logging
from datetime import datetime, timedelta
from uuid import UUID
from celery import shared_task
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.tasks import celery_app
from modules.messaging.domain.models import MessageSchedule, BulkMessage, MessageStatus
from modules.messaging.application.scheduling_service import SchedulingService
from modules.messaging.application.bulk_message_service import BulkMessageService

logger = logging.getLogger(__name__)


@shared_task
async def send_scheduled_message(schedule_id: str):
    """Send a scheduled message."""
    async with AsyncSessionLocal() as db:
        try:
            # Get scheduled message
            result = await db.execute(
                select(MessageSchedule).where(MessageSchedule.id == schedule_id)
            )
            scheduled_msg = result.scalar_one_or_none()
            
            if not scheduled_msg:
                logger.error(f"Scheduled message {schedule_id} not found")
                return
            
            if scheduled_msg.status != MessageStatus.SCHEDULED:
                logger.info(f"Scheduled message {schedule_id} already processed")
                return
            
            # Send the message
            service = SchedulingService()
            await service._send_scheduled_message(scheduled_msg, db)
            
        except Exception as e:
            logger.error(f"Error sending scheduled message {schedule_id}: {e}")
            raise


@shared_task
async def process_bulk_message(bulk_message_id: str):
    """Process a bulk message campaign."""
    async with AsyncSessionLocal() as db:
        try:
            service = BulkMessageService()
            await service._process_bulk_message(bulk_message_id, db)
            
        except Exception as e:
            logger.error(f"Error processing bulk message {bulk_message_id}: {e}")
            raise


@shared_task
async def process_scheduled_messages():
    """Process all due scheduled messages (runs every minute)."""
    async with AsyncSessionLocal() as db:
        try:
            service = SchedulingService()
            await service.process_scheduled_messages(db)
            
        except Exception as e:
            logger.error(f"Error processing scheduled messages: {e}")


@shared_task
async def process_scheduled_bulk_messages():
    """Process scheduled bulk message campaigns."""
    async with AsyncSessionLocal() as db:
        try:
            # Get scheduled bulk messages that are due
            now = datetime.utcnow()
            result = await db.execute(
                select(BulkMessage).where(
                    BulkMessage.status == MessageStatus.SCHEDULED,
                    BulkMessage.scheduled_at <= now
                )
            )
            bulk_messages = result.scalars().all()
            
            logger.info(f"Processing {len(bulk_messages)} scheduled bulk messages")
            
            # Start processing each campaign
            service = BulkMessageService()
            for bulk_msg in bulk_messages:
                await service._process_bulk_message(bulk_msg.id, db)
                
        except Exception as e:
            logger.error(f"Error processing scheduled bulk messages: {e}")


@shared_task
async def cleanup_old_messages(days: int = 90):
    """Clean up old sent messages."""
    async with AsyncSessionLocal() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old scheduled messages
            from sqlalchemy import delete
            result = await db.execute(
                delete(MessageSchedule).where(
                    MessageSchedule.status.in_([MessageStatus.SENT, MessageStatus.FAILED]),
                    MessageSchedule.created_at < cutoff_date
                )
            )
            
            logger.info(f"Deleted {result.rowcount} old scheduled messages")
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error cleaning up old messages: {e}")


@shared_task
async def update_message_analytics():
    """Update message analytics and tracking data."""
    async with AsyncSessionLocal() as db:
        try:
            # This would integrate with platform webhooks to update:
            # - Open rates
            # - Click rates
            # - Delivery status
            # - etc.
            
            logger.info("Message analytics updated")
            
        except Exception as e:
            logger.error(f"Error updating message analytics: {e}")


# Celery beat schedule
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'process-scheduled-messages': {
        'task': 'modules.messaging.tasks.process_scheduled_messages',
        'schedule': 60.0,  # Every minute
    },
    'process-scheduled-bulk-messages': {
        'task': 'modules.messaging.tasks.process_scheduled_bulk_messages',
        'schedule': 60.0,  # Every minute
    },
    'cleanup-old-messages': {
        'task': 'modules.messaging.tasks.cleanup_old_messages',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'update-message-analytics': {
        'task': 'modules.messaging.tasks.update_message_analytics',
        'schedule': 300.0,  # Every 5 minutes
    },
}