"""
Push Notification Service

Handles push notifications for mobile and web clients.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from firebase_admin import messaging
import httpx

from core.domain.models import User, Agency
from .models import PushSubscription, NotificationPreferences

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for managing push notifications"""
    
    def __init__(self):
        self.fcm_initialized = False
        self._init_fcm()
    
    def _init_fcm(self):
        """Initialize Firebase Cloud Messaging"""
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            # Initialize Firebase Admin SDK
            cred = credentials.Certificate('path/to/serviceAccountKey.json')
            firebase_admin.initialize_app(cred)
            self.fcm_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize FCM: {e}")
            self.fcm_initialized = False
    
    async def subscribe_to_push(
        self,
        db: AsyncSession,
        user_id: UUID,
        token: str,
        platform: str,
        device_info: Optional[Dict[str, Any]] = None
    ) -> PushSubscription:
        """Subscribe a device to push notifications"""
        # Check if subscription exists
        result = await db.execute(
            select(PushSubscription).where(
                and_(
                    PushSubscription.user_id == user_id,
                    PushSubscription.token == token
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            # Update existing subscription
            subscription.platform = platform
            subscription.device_info = device_info or {}
            subscription.is_active = True
            subscription.updated_at = datetime.utcnow()
        else:
            # Create new subscription
            subscription = PushSubscription(
                user_id=user_id,
                token=token,
                platform=platform,
                device_info=device_info or {},
                is_active=True
            )
            db.add(subscription)
        
        await db.commit()
        await db.refresh(subscription)
        
        return subscription
    
    async def unsubscribe_from_push(
        self,
        db: AsyncSession,
        user_id: UUID,
        token: str
    ) -> bool:
        """Unsubscribe a device from push notifications"""
        result = await db.execute(
            select(PushSubscription).where(
                and_(
                    PushSubscription.user_id == user_id,
                    PushSubscription.token == token
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.is_active = False
            subscription.updated_at = datetime.utcnow()
            await db.commit()
            return True
        
        return False
    
    async def send_push_notification(
        self,
        db: AsyncSession,
        user_id: UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send push notification to a user"""
        # Get user's active push subscriptions
        result = await db.execute(
            select(PushSubscription).where(
                and_(
                    PushSubscription.user_id == user_id,
                    PushSubscription.is_active == True
                )
            )
        )
        subscriptions = result.scalars().all()
        
        if not subscriptions:
            return {
                "success": False,
                "error": "No active push subscriptions found"
            }
        
        # Check user preferences
        prefs = await self._get_user_preferences(db, user_id)
        if not prefs.push_enabled:
            return {
                "success": False,
                "error": "Push notifications disabled by user"
            }
        
        # Send to all active devices
        results = []
        for subscription in subscriptions:
            result = await self._send_to_device(
                token=subscription.token,
                platform=subscription.platform,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                action_url=action_url,
                priority=priority
            )
            results.append(result)
        
        # Return summary
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        return {
            "success": successful > 0,
            "sent": successful,
            "failed": failed,
            "results": results
        }
    
    async def send_bulk_push(
        self,
        db: AsyncSession,
        user_ids: List[UUID],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send push notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            result = await self.send_push_notification(
                db=db,
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                action_url=action_url
            )
            results.append({
                "user_id": str(user_id),
                "result": result
            })
        
        # Summary
        successful = sum(1 for r in results if r["result"].get("success"))
        
        return {
            "success": successful > 0,
            "total": len(user_ids),
            "sent": successful,
            "failed": len(user_ids) - successful,
            "results": results
        }
    
    async def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to all devices subscribed to a topic"""
        if not self.fcm_initialized:
            return {
                "success": False,
                "error": "FCM not initialized"
            }
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
                image=image_url
            ),
            data=data or {},
            topic=topic
        )
        
        try:
            response = messaging.send(message)
            return {
                "success": True,
                "message_id": response
            }
        except Exception as e:
            logger.error(f"Failed to send topic notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_to_device(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send notification to a specific device"""
        if platform in ["ios", "android", "web"] and self.fcm_initialized:
            # Use FCM for mobile and web
            return await self._send_fcm(
                token=token,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                action_url=action_url,
                priority=priority
            )
        else:
            # Fallback or other platforms
            logger.warning(f"Unsupported platform: {platform}")
            return {
                "success": False,
                "error": f"Unsupported platform: {platform}"
            }
    
    async def _send_fcm(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send notification via Firebase Cloud Messaging"""
        if not self.fcm_initialized:
            return {
                "success": False,
                "error": "FCM not initialized"
            }
        
        # Prepare data payload
        payload = data or {}
        if action_url:
            payload["action_url"] = action_url
        
        # Build message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
                image=image_url
            ),
            data={k: str(v) for k, v in payload.items()},  # FCM requires string values
            token=token,
            android=messaging.AndroidConfig(
                priority="high" if priority == "high" else "normal"
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        content_available=True,
                        sound="default"
                    )
                )
            )
        )
        
        try:
            response = messaging.send(message)
            return {
                "success": True,
                "message_id": response
            }
        except messaging.UnregisteredError:
            # Token is invalid, mark as inactive
            logger.warning(f"Invalid FCM token: {token}")
            return {
                "success": False,
                "error": "Invalid token",
                "should_remove": True
            }
        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_user_preferences(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> NotificationPreferences:
        """Get user's notification preferences"""
        result = await db.execute(
            select(NotificationPreferences).where(
                NotificationPreferences.user_id == user_id
            )
        )
        prefs = result.scalar_one_or_none()
        
        if not prefs:
            # Create default preferences
            prefs = NotificationPreferences(
                user_id=user_id,
                push_enabled=True,
                email_enabled=True,
                sms_enabled=False,
                notification_types={
                    "messages": True,
                    "tips": True,
                    "subscriptions": True,
                    "content": True,
                    "system": True
                }
            )
            db.add(prefs)
            await db.commit()
            await db.refresh(prefs)
        
        return prefs
    
    async def update_preferences(
        self,
        db: AsyncSession,
        user_id: UUID,
        preferences: Dict[str, Any]
    ) -> NotificationPreferences:
        """Update user's notification preferences"""
        prefs = await self._get_user_preferences(db, user_id)
        
        for key, value in preferences.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        
        prefs.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(prefs)
        
        return prefs
    
    async def cleanup_inactive_tokens(
        self,
        db: AsyncSession,
        days_inactive: int = 30
    ) -> int:
        """Remove inactive push tokens"""
        cutoff = datetime.utcnow() - timedelta(days=days_inactive)
        
        result = await db.execute(
            select(PushSubscription).where(
                and_(
                    PushSubscription.is_active == False,
                    PushSubscription.updated_at < cutoff
                )
            )
        )
        subscriptions = result.scalars().all()
        
        count = len(subscriptions)
        for sub in subscriptions:
            await db.delete(sub)
        
        await db.commit()
        
        return count


# Global push service instance
push_service = PushNotificationService()