"""Notification tasks for sending emails, SMS, and push notifications."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import shared_task, group
from sqlalchemy import select, and_
import asyncio

from core.database_sync import get_db_sync
from core.logger import get_logger
from models.notification import Notification, NotificationStatus, NotificationType
from models.user import User
from services.notification_service import NotificationService

logger = get_logger(__name__)


@shared_task(bind=True, name='tasks.notification_tasks.send_notification')
def send_notification(self, notification_id: str):
    """Send a single notification."""
    try:
        with get_db_sync() as db:
            # Create async event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run async notification sending
                result = loop.run_until_complete(
                    _send_notification_async(db, notification_id)
                )
                
                if result:
                    logger.info(f"Successfully sent notification {notification_id}")
                else:
                    logger.error(f"Failed to send notification {notification_id}")
                
                return result
                
            finally:
                loop.close()
                
    except Exception as e:
        logger.error(f"Error in send_notification task: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.notification_tasks.send_email')
def send_email(self, to_email: str, subject: str, content: str, html_content: Optional[str] = None, 
               template_name: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
    """Send a simple email notification."""
    try:
        with get_db_sync() as db:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Create notification
                from schemas.notification import NotificationCreate
                notification_data = NotificationCreate(
                    type=NotificationType.EMAIL,
                    email=to_email,
                    subject=subject,
                    content=content,
                    html_content=html_content,
                    template_data=context
                )
                
                # Get first agency (for simple email sending)
                from models.agency import Agency
                agency = db.query(Agency).first()
                if not agency:
                    logger.error("No agency found for email sending")
                    return False
                
                # Send email
                result = loop.run_until_complete(
                    _create_and_send_notification_async(
                        db, notification_data, str(agency.id)
                    )
                )
                
                return result
                
            finally:
                loop.close()
                
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.notification_tasks.send_sms')
def send_sms(self, to_phone: str, content: str):
    """Send a simple SMS notification."""
    try:
        with get_db_sync() as db:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Create notification
                from schemas.notification import NotificationCreate
                notification_data = NotificationCreate(
                    type=NotificationType.SMS,
                    phone=to_phone,
                    content=content
                )
                
                # Get first agency
                from models.agency import Agency
                agency = db.query(Agency).first()
                if not agency:
                    logger.error("No agency found for SMS sending")
                    return False
                
                # Send SMS
                result = loop.run_until_complete(
                    _create_and_send_notification_async(
                        db, notification_data, str(agency.id)
                    )
                )
                
                return result
                
            finally:
                loop.close()
                
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.notification_tasks.send_bulk_notifications')
def send_bulk_notifications(self, agency_id: str, scheduled_at: Optional[str] = None):
    """Send bulk notifications for an agency."""
    try:
        with get_db_sync() as db:
            # Get pending notifications for agency
            query = db.query(Notification).filter(
                and_(
                    Notification.agency_id == agency_id,
                    Notification.status == NotificationStatus.PENDING
                )
            )
            
            # Filter by scheduled time if provided
            if scheduled_at:
                scheduled_time = datetime.fromisoformat(scheduled_at)
                query = query.filter(Notification.scheduled_at <= scheduled_time)
            else:
                query = query.filter(Notification.scheduled_at.is_(None))
            
            notifications = query.all()
            
            if not notifications:
                logger.info(f"No pending notifications for agency {agency_id}")
                return {'sent': 0, 'failed': 0}
            
            # Create tasks for each notification
            tasks = []
            for notification in notifications:
                tasks.append(send_notification.s(str(notification.id)))
            
            # Execute all tasks
            job = group(tasks)
            result = job.apply_async()
            
            logger.info(f"Queued {len(notifications)} notifications for agency {agency_id}")
            
            return {
                'queued': len(notifications),
                'task_group_id': result.id
            }
            
    except Exception as e:
        logger.error(f"Error in bulk notification task: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, name='tasks.notification_tasks.process_scheduled_notifications')
def process_scheduled_notifications(self):
    """Process scheduled notifications that are due."""
    try:
        with get_db_sync() as db:
            # Find due scheduled notifications
            now = datetime.utcnow()
            notifications = db.query(Notification).filter(
                and_(
                    Notification.status == NotificationStatus.PENDING,
                    Notification.scheduled_at <= now
                )
            ).limit(100).all()
            
            if not notifications:
                return {'processed': 0}
            
            # Send each notification
            sent_count = 0
            for notification in notifications:
                send_notification.delay(str(notification.id))
                sent_count += 1
            
            logger.info(f"Processed {sent_count} scheduled notifications")
            
            return {'processed': sent_count}
            
    except Exception as e:
        logger.error(f"Error processing scheduled notifications: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.notification_tasks.send_digest_notifications')
def send_digest_notifications(self):
    """Send digest notifications to users."""
    try:
        with get_db_sync() as db:
            # Get users with digest enabled
            from models.notification import NotificationPreference
            
            # Daily digests
            daily_users = db.query(User).join(NotificationPreference).filter(
                and_(
                    NotificationPreference.digest_enabled == True,
                    NotificationPreference.digest_frequency == 'daily'
                )
            ).all()
            
            for user in daily_users:
                _create_digest_notification(db, user, 'daily')
            
            # Weekly digests (only on Mondays)
            if datetime.utcnow().weekday() == 0:
                weekly_users = db.query(User).join(NotificationPreference).filter(
                    and_(
                        NotificationPreference.digest_enabled == True,
                        NotificationPreference.digest_frequency == 'weekly'
                    )
                ).all()
                
                for user in weekly_users:
                    _create_digest_notification(db, user, 'weekly')
            
            # Monthly digests (only on 1st of month)
            if datetime.utcnow().day == 1:
                monthly_users = db.query(User).join(NotificationPreference).filter(
                    and_(
                        NotificationPreference.digest_enabled == True,
                        NotificationPreference.digest_frequency == 'monthly'
                    )
                ).all()
                
                for user in monthly_users:
                    _create_digest_notification(db, user, 'monthly')
            
            return {'daily': len(daily_users)}
            
    except Exception as e:
        logger.error(f"Error sending digest notifications: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, name='tasks.notification_tasks.cleanup_old_notifications')
def cleanup_old_notifications(self, days: int = 90):
    """Clean up old notifications."""
    try:
        with get_db_sync() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old notifications
            deleted = db.query(Notification).filter(
                Notification.created_at < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info(f"Deleted {deleted} notifications older than {days} days")
            
            return {'deleted': deleted}
            
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, name='tasks.notification_tasks.send_webhook_notification')
def send_webhook_notification(self, url: str, payload: Dict[str, Any], 
                            headers: Optional[Dict[str, str]] = None):
    """Send a webhook notification."""
    try:
        import requests
        
        response = requests.post(
            url,
            json=payload,
            headers=headers or {},
            timeout=30
        )
        
        if response.status_code < 300:
            logger.info(f"Webhook sent successfully to {url}")
            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.text[:500]  # First 500 chars
            }
        else:
            logger.error(f"Webhook failed with status {response.status_code}")
            return {
                'success': False,
                'status_code': response.status_code,
                'error': response.text[:500]
            }
            
    except Exception as e:
        logger.error(f"Error sending webhook: {e}")
        raise self.retry(exc=e, countdown=60)


# Helper functions
async def _send_notification_async(db, notification_id: str) -> bool:
    """Async helper to send notification."""
    service = NotificationService(db)
    return await service.send_notification(notification_id)


async def _create_and_send_notification_async(db, notification_data, agency_id: str) -> bool:
    """Async helper to create and send notification."""
    service = NotificationService(db)
    notification = await service.create_notification(
        notification_data,
        agency_id,
        send_immediately=False
    )
    if notification:
        return await service.send_notification(str(notification.id))
    return False


def _create_digest_notification(db, user: User, frequency: str):
    """Create a digest notification for a user."""
    try:
        # Get recent activity based on frequency
        if frequency == 'daily':
            since = datetime.utcnow() - timedelta(days=1)
        elif frequency == 'weekly':
            since = datetime.utcnow() - timedelta(days=7)
        else:  # monthly
            since = datetime.utcnow() - timedelta(days=30)
        
        # TODO: Gather activity data (messages, transactions, etc.)
        
        # Create digest notification
        from schemas.notification import NotificationCreate
        notification_data = NotificationCreate(
            type=NotificationType.EMAIL,
            user_id=str(user.id),
            subject=f"Your {frequency} activity digest",
            content=f"Here's your {frequency} summary...",
            metadata={'category': 'digest', 'frequency': frequency}
        )
        
        # Queue notification
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(
                _create_and_send_notification_async(
                    db, notification_data, str(user.agency_id)
                )
            )
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error creating digest for user {user.id}: {e}")