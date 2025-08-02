"""
Mobile push notification endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime
import json

from core.database import get_db
from core.auth import get_current_user
from core.logging import get_logger
from models.user import User

router = APIRouter(prefix="/mobile/notifications", tags=["mobile-notifications"])
logger = get_logger(__name__)


class NotificationPreferences(BaseModel):
    """Notification preferences"""
    new_messages: bool = True
    new_fans: bool = True
    payments: bool = True
    daily_summary: bool = True
    marketing: bool = False
    sound_enabled: bool = True
    vibration_enabled: bool = True
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None    # HH:MM format


class PushNotification(BaseModel):
    """Push notification model"""
    title: str
    body: str
    data: Optional[dict] = None
    badge: Optional[int] = None
    sound: Optional[str] = "default"
    priority: str = "high"
    category: Optional[str] = None
    thread_id: Optional[str] = None
    image_url: Optional[str] = None


class NotificationHistory(BaseModel):
    """Notification history item"""
    id: str
    title: str
    body: str
    category: str
    sent_at: datetime
    read: bool
    data: Optional[dict]


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's notification preferences
    """
    # Get preferences from user settings or database
    # For now, return defaults
    preferences = NotificationPreferences()
    
    # Load from user settings if available
    if hasattr(current_user, 'settings') and current_user.settings:
        prefs = current_user.settings.get('notifications', {})
        preferences = NotificationPreferences(**prefs)
    
    return preferences


@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user's notification preferences
    """
    # Update user settings
    if not hasattr(current_user, 'settings'):
        current_user.settings = {}
    
    current_user.settings['notifications'] = preferences.dict()
    
    # Save to database
    db.add(current_user)
    await db.commit()
    
    return {"message": "Preferences updated successfully"}


@router.post("/test")
async def send_test_notification(
    device_id: str,
    notification: PushNotification,
    current_user: User = Depends(get_current_user)
):
    """
    Send a test push notification
    """
    # Send test notification
    await _send_push_notification(
        user_id=current_user.id,
        device_id=device_id,
        notification=notification
    )
    
    return {"message": "Test notification sent"}


@router.get("/history", response_model=List[NotificationHistory])
async def get_notification_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notification history
    """
    # This would fetch from a notifications table
    # For now, return mock data
    
    history = []
    
    # Mock notification history
    categories = ["message", "payment", "fan", "summary"]
    for i in range(5):
        history.append(NotificationHistory(
            id=f"notif_{i}",
            title="New Message" if i % 2 == 0 else "Payment Received",
            body="You have a new message from Fan123" if i % 2 == 0 else "$50.00 payment received",
            category=categories[i % len(categories)],
            sent_at=datetime.utcnow(),
            read=i < 2,
            data={"fan_id": "123", "amount": 50} if i % 2 == 1 else None
        ))
    
    return history


@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a notification as read
    """
    # Update notification status in database
    # ... implementation ...
    
    return {"message": "Notification marked as read"}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark all notifications as read
    """
    # Update all notifications for user
    # ... implementation ...
    
    return {"message": "All notifications marked as read"}


@router.delete("/clear")
async def clear_notifications(
    older_than_days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear old notifications
    """
    # Delete notifications older than specified days
    # ... implementation ...
    
    return {"message": f"Cleared notifications older than {older_than_days} days"}


# Notification service functions
async def send_new_message_notification(
    user_id: UUID,
    fan_username: str,
    message_preview: str,
    model_id: UUID,
    fan_id: UUID,
    db: AsyncSession
):
    """
    Send notification for new message
    """
    notification = PushNotification(
        title=f"New message from {fan_username}",
        body=message_preview[:100] + "..." if len(message_preview) > 100 else message_preview,
        data={
            "type": "new_message",
            "model_id": str(model_id),
            "fan_id": str(fan_id)
        },
        category="message",
        thread_id=str(fan_id),
        sound="message.wav"
    )
    
    await _send_notification_to_user(user_id, notification, db)


async def send_payment_notification(
    user_id: UUID,
    amount: float,
    fan_username: str,
    payment_type: str,
    model_id: UUID,
    db: AsyncSession
):
    """
    Send notification for payment received
    """
    notification = PushNotification(
        title="Payment Received! 💰",
        body=f"${amount:.2f} from {fan_username} ({payment_type})",
        data={
            "type": "payment",
            "amount": amount,
            "model_id": str(model_id),
            "payment_type": payment_type
        },
        category="payment",
        sound="payment.wav"
    )
    
    await _send_notification_to_user(user_id, notification, db)


async def send_new_fan_notification(
    user_id: UUID,
    fan_username: str,
    model_id: UUID,
    fan_id: UUID,
    db: AsyncSession
):
    """
    Send notification for new fan
    """
    notification = PushNotification(
        title="New Fan! 🎉",
        body=f"{fan_username} just subscribed",
        data={
            "type": "new_fan",
            "model_id": str(model_id),
            "fan_id": str(fan_id)
        },
        category="fan",
        sound="success.wav"
    )
    
    await _send_notification_to_user(user_id, notification, db)


async def send_daily_summary_notification(
    user_id: UUID,
    revenue: float,
    new_fans: int,
    messages: int,
    model_id: UUID,
    db: AsyncSession
):
    """
    Send daily summary notification
    """
    notification = PushNotification(
        title="Daily Summary 📊",
        body=f"Revenue: ${revenue:.2f} | New fans: {new_fans} | Messages: {messages}",
        data={
            "type": "daily_summary",
            "model_id": str(model_id),
            "revenue": revenue,
            "new_fans": new_fans,
            "messages": messages
        },
        category="summary"
    )
    
    await _send_notification_to_user(user_id, notification, db)


async def _send_notification_to_user(
    user_id: UUID,
    notification: PushNotification,
    db: AsyncSession
):
    """
    Send notification to all user devices
    """
    # Get user's notification preferences
    user = await db.get(User, user_id)
    if not user:
        return
    
    # Check preferences
    prefs = user.settings.get('notifications', {}) if hasattr(user, 'settings') else {}
    
    # Check if this type of notification is enabled
    category_enabled = {
        "message": prefs.get("new_messages", True),
        "payment": prefs.get("payments", True),
        "fan": prefs.get("new_fans", True),
        "summary": prefs.get("daily_summary", True)
    }
    
    if not category_enabled.get(notification.category, True):
        return
    
    # Check quiet hours
    if _is_quiet_hours(prefs.get("quiet_hours_start"), prefs.get("quiet_hours_end")):
        return
    
    # Get user devices
    from core.auth.session_manager import session_manager
    devices = await session_manager.get_user_devices(user_id)
    
    # Send to each device with push token
    for device in devices:
        if device.get("push_token"):
            await _send_push_notification(
                user_id=user_id,
                device_id=device["device_id"],
                notification=notification,
                push_token=device["push_token"]
            )
    
    # Store in notification history
    await _store_notification_history(user_id, notification, db)


async def _send_push_notification(
    user_id: UUID,
    device_id: str,
    notification: PushNotification,
    push_token: Optional[str] = None
):
    """
    Send push notification to specific device
    """
    # This would integrate with push notification services
    # like Firebase Cloud Messaging (FCM) or Apple Push Notification Service (APNS)
    
    logger.info(
        f"Sending push notification to user {user_id}, device {device_id}: "
        f"{notification.title}"
    )
    
    # Implementation would depend on the push service
    # For FCM:
    # await fcm_client.send(push_token, notification.dict())
    
    # For APNS:
    # await apns_client.send(push_token, notification.dict())
    
    pass


async def _store_notification_history(
    user_id: UUID,
    notification: PushNotification,
    db: AsyncSession
):
    """
    Store notification in history
    """
    # This would store in a notifications table
    # For tracking and allowing users to view past notifications
    pass


def _is_quiet_hours(start_time: Optional[str], end_time: Optional[str]) -> bool:
    """
    Check if current time is within quiet hours
    """
    if not start_time or not end_time:
        return False
    
    from datetime import datetime, time
    
    now = datetime.now().time()
    
    # Parse times (HH:MM format)
    start_hour, start_min = map(int, start_time.split(':'))
    end_hour, end_min = map(int, end_time.split(':'))
    
    start = time(start_hour, start_min)
    end = time(end_hour, end_min)
    
    # Handle overnight quiet hours
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end