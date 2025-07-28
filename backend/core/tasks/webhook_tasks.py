"""
Webhook background tasks
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from core.logging import get_logger
from core.database import get_db
from core.webhooks.webhook_manager import webhook_manager
from core.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="retry_failed_webhooks",
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def retry_failed_webhooks_task():
    """
    Retry failed webhook deliveries
    """
    try:
        # Run async function in sync context
        asyncio.run(_retry_failed_webhooks())
        logger.info("Completed webhook retry task")
    except Exception as e:
        logger.error(f"Error in webhook retry task: {e}")
        raise


async def _retry_failed_webhooks():
    """
    Async implementation of webhook retry
    """
    async with get_db() as db:
        await webhook_manager.retry_failed_deliveries(db)


@celery_app.task(
    name="cleanup_old_webhook_deliveries",
    max_retries=3
)
def cleanup_old_webhook_deliveries(
    days_to_keep: int = 30
):
    """
    Clean up old webhook delivery records
    """
    try:
        asyncio.run(_cleanup_old_deliveries(days_to_keep))
        logger.info(f"Cleaned up webhook deliveries older than {days_to_keep} days")
    except Exception as e:
        logger.error(f"Error cleaning up webhook deliveries: {e}")
        raise


async def _cleanup_old_deliveries(days_to_keep: int):
    """
    Delete old webhook delivery records
    """
    from sqlalchemy import delete
    from core.webhooks.webhook_models import WebhookDelivery
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    async with get_db() as db:
        # Delete old delivery records
        stmt = delete(WebhookDelivery).where(
            WebhookDelivery.created_at < cutoff_date
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        logger.info(f"Deleted {result.rowcount} old webhook deliveries")


@celery_app.task(
    name="disable_failing_webhooks",
    max_retries=3
)
def disable_failing_webhooks(
    failure_threshold: float = 0.1,  # 10% success rate
    min_attempts: int = 10
):
    """
    Disable webhooks with high failure rates
    """
    try:
        asyncio.run(_disable_failing_webhooks(failure_threshold, min_attempts))
    except Exception as e:
        logger.error(f"Error disabling failing webhooks: {e}")
        raise


async def _disable_failing_webhooks(
    failure_threshold: float,
    min_attempts: int
):
    """
    Find and disable webhooks with high failure rates
    """
    from sqlalchemy import select, and_
    from core.webhooks.webhook_models import Webhook
    
    async with get_db() as db:
        # Find webhooks with poor success rates
        stmt = select(Webhook).where(
            and_(
                Webhook.is_active == True,
                Webhook.total_deliveries >= min_attempts
            )
        )
        
        result = await db.execute(stmt)
        webhooks = result.scalars().all()
        
        disabled_count = 0
        
        for webhook in webhooks:
            if webhook.total_deliveries > 0:
                success_rate = webhook.successful_deliveries / webhook.total_deliveries
                
                if success_rate < failure_threshold:
                    webhook.is_active = False
                    disabled_count += 1
                    
                    logger.warning(
                        f"Disabled webhook {webhook.id} due to low success rate: "
                        f"{success_rate:.1%} ({webhook.successful_deliveries}/{webhook.total_deliveries})"
                    )
        
        if disabled_count > 0:
            await db.commit()
            logger.info(f"Disabled {disabled_count} failing webhooks")


# Schedule periodic tasks
from celery.schedules import crontab

# Add to celery beat schedule
celery_app.conf.beat_schedule.update({
    'retry-failed-webhooks': {
        'task': 'retry_failed_webhooks',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-webhook-deliveries': {
        'task': 'cleanup_old_webhook_deliveries',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'kwargs': {'days_to_keep': 30}
    },
    'disable-failing-webhooks': {
        'task': 'disable_failing_webhooks',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        'kwargs': {
            'failure_threshold': 0.1,
            'min_attempts': 10
        }
    }
})


def send_webhook_event(
    agency_id: str,
    event: str,
    event_id: str,
    data: dict
):
    """
    Helper function to send webhook event from other tasks
    """
    from core.webhooks.webhook_models import WebhookEvent
    from uuid import UUID
    
    try:
        # Convert string event to enum
        webhook_event = WebhookEvent(event)
        
        # Trigger webhook
        asyncio.run(
            webhook_manager.trigger_event(
                agency_id=UUID(agency_id),
                event=webhook_event,
                event_id=event_id,
                data=data
            )
        )
    except Exception as e:
        logger.error(f"Error sending webhook event: {e}")
