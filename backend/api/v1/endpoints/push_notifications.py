"""
Push Notification API endpoints
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.database import get_db
from core.security import get_current_user
from core.domain.models import User, UserRole
from modules.notifications.push_service import push_service
from modules.notifications.models import PushSubscription, NotificationPreferences

router = APIRouter(prefix="/push", tags=["push-notifications"])


class PushSubscriptionRequest(BaseModel):
    """Push subscription request"""
    token: str = Field(..., description="FCM/APNS token")
    platform: str = Field(..., pattern="^(ios|android|web)$")
    device_info: Optional[Dict[str, Any]] = None


class PushNotificationRequest(BaseModel):
    """Push notification request"""
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    priority: str = Field("normal", pattern="^(normal|high)$")


class BulkPushRequest(BaseModel):
    """Bulk push notification request"""
    user_ids: List[UUID]
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None


class NotificationPreferencesUpdate(BaseModel):
    """Notification preferences update"""
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    notification_types: Optional[Dict[str, bool]] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    max_daily_notifications: Optional[int] = Field(None, ge=0, le=100)


@router.post("/subscribe")
async def subscribe_to_push(
    request: PushSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Subscribe device to push notifications"""
    subscription = await push_service.subscribe_to_push(
        db=db,
        user_id=current_user.id,
        token=request.token,
        platform=request.platform,
        device_info=request.device_info
    )
    
    return {
        "success": True,
        "subscription_id": str(subscription.id),
        "platform": subscription.platform
    }


@router.post("/unsubscribe")
async def unsubscribe_from_push(
    token: str = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe device from push notifications"""
    success = await push_service.unsubscribe_from_push(
        db=db,
        user_id=current_user.id,
        token=token
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return {"success": True, "message": "Unsubscribed successfully"}


@router.get("/subscriptions")
async def get_push_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's push subscriptions"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == current_user.id
        )
    )
    subscriptions = result.scalars().all()
    
    return {
        "subscriptions": [
            {
                "id": str(sub.id),
                "platform": sub.platform,
                "device_info": sub.device_info,
                "is_active": sub.is_active,
                "created_at": sub.created_at,
                "last_used": sub.last_used
            }
            for sub in subscriptions
        ]
    }


@router.post("/send")
async def send_push_notification(
    user_id: UUID,
    notification: PushNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send push notification to a user (admin only)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify user exists and belongs to agency
    from sqlalchemy import select
    target_user = await db.get(User, user_id)
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and target_user.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Cannot send notifications to users outside your agency")
    
    result = await push_service.send_push_notification(
        db=db,
        user_id=user_id,
        title=notification.title,
        body=notification.body,
        data=notification.data,
        image_url=notification.image_url,
        action_url=notification.action_url,
        priority=notification.priority
    )
    
    return result


@router.post("/send-bulk")
async def send_bulk_push(
    request: BulkPushRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send push notification to multiple users (admin only)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify all users belong to agency
    if current_user.role != UserRole.SUPER_ADMIN:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.id.in_(request.user_ids))
        )
        users = result.scalars().all()
        
        for user in users:
            if user.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"User {user.id} does not belong to your agency"
                )
    
    result = await push_service.send_bulk_push(
        db=db,
        user_ids=request.user_ids,
        title=request.title,
        body=request.body,
        data=request.data,
        image_url=request.image_url,
        action_url=request.action_url
    )
    
    return result


@router.post("/topic/{topic}")
async def send_topic_notification(
    topic: str,
    notification: PushNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send notification to a topic (super admin only)"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can send topic notifications")
    
    result = await push_service.send_topic_notification(
        topic=topic,
        title=notification.title,
        body=notification.body,
        data=notification.data,
        image_url=notification.image_url
    )
    
    return result


@router.get("/preferences")
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notification preferences"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        # Return default preferences
        return {
            "push_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
            "in_app_enabled": True,
            "notification_types": {
                "messages": True,
                "tips": True,
                "subscriptions": True,
                "content": True,
                "promotions": True,
                "system": True
            },
            "quiet_hours_enabled": False,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "timezone": "UTC",
            "max_daily_notifications": 50
        }
    
    return {
        "push_enabled": prefs.push_enabled,
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "in_app_enabled": prefs.in_app_enabled,
        "notification_types": prefs.notification_types,
        "quiet_hours_enabled": prefs.quiet_hours_enabled,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "timezone": prefs.timezone,
        "max_daily_notifications": prefs.max_daily_notifications
    }


@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's notification preferences"""
    updated_prefs = await push_service.update_preferences(
        db=db,
        user_id=current_user.id,
        preferences=preferences.dict(exclude_unset=True)
    )
    
    return {
        "success": True,
        "preferences": {
            "push_enabled": updated_prefs.push_enabled,
            "email_enabled": updated_prefs.email_enabled,
            "sms_enabled": updated_prefs.sms_enabled,
            "in_app_enabled": updated_prefs.in_app_enabled,
            "notification_types": updated_prefs.notification_types,
            "quiet_hours_enabled": updated_prefs.quiet_hours_enabled,
            "quiet_hours_start": updated_prefs.quiet_hours_start,
            "quiet_hours_end": updated_prefs.quiet_hours_end,
            "timezone": updated_prefs.timezone,
            "max_daily_notifications": updated_prefs.max_daily_notifications
        }
    }


@router.delete("/cleanup")
async def cleanup_inactive_tokens(
    days_inactive: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clean up inactive push tokens (admin only)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    count = await push_service.cleanup_inactive_tokens(db, days_inactive)
    
    return {
        "success": True,
        "removed": count,
        "message": f"Removed {count} inactive tokens"
    }