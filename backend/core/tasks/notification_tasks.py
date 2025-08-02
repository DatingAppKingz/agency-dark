"""
Notification tasks for push notifications and alerts
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from celery import shared_task, group
from celery.utils.log import get_task_logger
from sqlalchemy import select, and_, or_

from .db_context import get_db_context
from models import User, Notification, Device, ModelProfile
from core.push_notifications import PushNotificationService
from .email_tasks import send_notification_email

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification(
    self,
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    priority: str = 'normal'
) -> Dict[str, Any]:
    """
    Send push notification to user's devices
    
    Args:
        user_id: User ID
        title: Notification title
        body: Notification body
        data: Additional data payload
        priority: Notification priority (normal, high)
    """
    try:
        async def _send():
            async with get_db_context() as db:
                # Get user's devices
                result = await db.execute(
                    select(Device).where(
                        and_(
                            Device.user_id == user_id,
                            Device.is_active == True,
                            Device.push_token.isnot(None)
                        )
                    )
                )
                devices = result.scalars().all()
                
                if not devices:
                    logger.info(f"No active devices found for user {user_id}")
                    return {
                        'status': 'no_devices',
                        'user_id': user_id
                    }
                
                # Initialize push service
                push_service = PushNotificationService()
                
                results = {
                    'sent': [],
                    'failed': [],
                    'total': len(devices)
                }
                
                # Send to each device
                for device in devices:
                    try:
                        result = await push_service.send_notification(
                            device_token=device.push_token,
                            title=title,
                            body=body,
                            data=data,
                            priority=priority,
                            platform=device.platform
                        )
                        
                        if result['success']:
                            results['sent'].append({
                                'device_id': str(device.id),
                                'platform': device.platform
                            })
                        else:
                            results['failed'].append({
                                'device_id': str(device.id),
                                'platform': device.platform,
                                'error': result.get('error')
                            })
                            
                            # Mark device as inactive if token is invalid
                            if result.get('error') == 'invalid_token':
                                device.is_active = False
                        
                    except Exception as exc:
                        logger.error(f"Failed to send to device {device.id}: {exc}")
                        results['failed'].append({
                            'device_id': str(device.id),
                            'error': str(exc)
                        })
                
                # Create notification record
                notification = Notification(
                    user_id=user_id,
                    title=title,
                    body=body,
                    type='push',
                    data=data,
                    sent_at=datetime.utcnow() if results['sent'] else None,
                    status='sent' if results['sent'] else 'failed',
                    metadata={
                        'devices_sent': len(results['sent']),
                        'devices_failed': len(results['failed'])
                    }
                )
                db.add(notification)
                
                await db.commit()
                
                logger.info(f"Push notification sent to {len(results['sent'])} devices for user {user_id}")
                return results
        
        # Run async function
        import asyncio
        return asyncio.run(_send())
        
    except Exception as exc:
        logger.error(f"Failed to send push notification: {exc}")
        raise self.retry(exc=exc)


@shared_task
def send_bulk_notification(
    user_ids: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send notification to multiple users
    """
    # Create group of tasks
    job = group(
        send_push_notification.s(user_id, title, body, data)
        for user_id in user_ids
    )
    
    # Execute group
    result = job.apply_async()
    
    return {
        'status': 'queued',
        'user_count': len(user_ids),
        'group_id': result.id
    }


@shared_task
def notify_new_message(
    user_id: str,
    sender_name: str,
    message_preview: str,
    conversation_id: str
) -> Dict[str, Any]:
    """
    Notify user of new message
    """
    try:
        async def _notify():
            async with get_db_context() as db:
                # Get user preferences
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return {'status': 'user_not_found'}
                
                results = {}
                
                # Send push notification if enabled
                if user.push_notifications_enabled:
                    push_result = send_push_notification.delay(
                        user_id=user_id,
                        title=f"New message from {sender_name}",
                        body=message_preview[:100],
                        data={
                            'type': 'new_message',
                            'conversation_id': conversation_id,
                            'sender_name': sender_name
                        },
                        priority='high'
                    )
                    results['push_task_id'] = push_result.id
                
                # Send email notification if enabled
                if user.email_notifications_enabled:
                    email_result = send_notification_email.delay(
                        user_id=user_id,
                        notification_type='new_message',
                        data={
                            'sender_name': sender_name,
                            'message_preview': message_preview,
                            'conversation_id': conversation_id
                        }
                    )
                    results['email_task_id'] = email_result.id
                
                return results
        
        # Run async function
        import asyncio
        return asyncio.run(_notify())
        
    except Exception as exc:
        logger.error(f"Failed to notify new message: {exc}")
        raise


@shared_task
def notify_payment_received(
    model_id: str,
    amount: float,
    currency: str,
    fan_name: str,
    payment_type: str
) -> Dict[str, Any]:
    """
    Notify model of payment received
    """
    try:
        async def _notify():
            async with get_db_context() as db:
                # Get model profile
                result = await db.execute(
                    select(ModelProfile).where(ModelProfile.id == model_id)
                )
                model = result.scalar_one_or_none()
                
                if not model or not model.user_id:
                    return {'status': 'model_not_found'}
                
                # Format amount
                amount_str = f"{currency} {amount:,.2f}"
                
                # Send notification
                return send_push_notification.delay(
                    user_id=str(model.user_id),
                    title="Payment Received! 💰",
                    body=f"You received a {payment_type} of {amount_str} from {fan_name}",
                    data={
                        'type': 'payment_received',
                        'amount': amount,
                        'currency': currency,
                        'fan_name': fan_name,
                        'payment_type': payment_type
                    },
                    priority='high'
                ).get()
        
        # Run async function
        import asyncio
        return asyncio.run(_notify())
        
    except Exception as exc:
        logger.error(f"Failed to notify payment: {exc}")
        raise


@shared_task
def notify_milestone_reached(
    model_id: str,
    milestone_type: str,
    value: Any
) -> Dict[str, Any]:
    """
    Notify model of milestone reached
    """
    milestones = {
        'revenue_1k': {
            'title': '🎉 $1,000 Revenue Milestone!',
            'body': 'Congratulations! You\'ve earned over $1,000!'
        },
        'revenue_10k': {
            'title': '🚀 $10,000 Revenue Milestone!',
            'body': 'Amazing! You\'ve earned over $10,000!'
        },
        'fans_100': {
            'title': '👥 100 Fans Milestone!',
            'body': 'You now have over 100 active fans!'
        },
        'fans_1000': {
            'title': '🌟 1,000 Fans Milestone!',
            'body': 'Incredible! You have over 1,000 active fans!'
        }
    }
    
    if milestone_type not in milestones:
        logger.warning(f"Unknown milestone type: {milestone_type}")
        return {'status': 'unknown_milestone'}
    
    milestone = milestones[milestone_type]
    
    try:
        async def _notify():
            async with get_db_context() as db:
                # Get model profile
                result = await db.execute(
                    select(ModelProfile).where(ModelProfile.id == model_id)
                )
                model = result.scalar_one_or_none()
                
                if not model or not model.user_id:
                    return {'status': 'model_not_found'}
                
                # Send notification
                return send_push_notification.delay(
                    user_id=str(model.user_id),
                    title=milestone['title'],
                    body=milestone['body'],
                    data={
                        'type': 'milestone_reached',
                        'milestone_type': milestone_type,
                        'value': value
                    },
                    priority='normal'
                ).get()
        
        # Run async function
        import asyncio
        return asyncio.run(_notify())
        
    except Exception as exc:
        logger.error(f"Failed to notify milestone: {exc}")
        raise


@shared_task
def check_and_send_reminders() -> Dict[str, Any]:
    """
    Check and send various reminders
    """
    try:
        results = {
            'reminders_sent': 0,
            'types': {}
        }
        
        async def _check():
            async with get_db_context() as db:
                now = datetime.utcnow()
                
                # Check for models who haven't posted in 3 days
                three_days_ago = now - timedelta(days=3)
                inactive_models = await db.execute(
                    select(ModelProfile).where(
                        and_(
                            ModelProfile.is_active == True,
                            ModelProfile.last_content_posted < three_days_ago
                        )
                    )
                )
                
                for model in inactive_models.scalars():
                    if model.user_id:
                        send_push_notification.delay(
                            user_id=str(model.user_id),
                            title="Time to engage your fans! 📸",
                            body="Your fans miss you! Share some new content to keep them engaged.",
                            data={'type': 'content_reminder'}
                        )
                        results['reminders_sent'] += 1
                
                results['types']['content_reminders'] = results['reminders_sent']
                
                # Add other reminder types here...
                
                return results
        
        # Run async function
        import asyncio
        result = asyncio.run(_check())
        
        logger.info(f"Sent {result['reminders_sent']} reminders")
        return result
        
    except Exception as exc:
        logger.error(f"Failed to check reminders: {exc}")
        raise


@shared_task
def cleanup_old_notifications(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old notification records
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                result = await db.execute(
                    delete(Notification).where(
                        Notification.created_at < cutoff_date
                    )
                )
                
                await db.commit()
                
                count = result.rowcount
                logger.info(f"Cleaned up {count} old notifications")
                
                return {
                    'notifications_deleted': count,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Notification cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }