"""Notification service for handling email, SMS, and push notifications."""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from twilio.rest import Client as TwilioClient
from jinja2 import Template, Environment, meta
import pytz

from core.config import settings
from core.logger import get_logger
from models.notification import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationEvent, NotificationType, NotificationStatus,
    NotificationPriority
)
from models.user import User
from schemas.notification import NotificationCreate, BulkNotificationCreate

logger = get_logger(__name__)


class NotificationService:
    """Service for managing notifications."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_tls = settings.SMTP_TLS
        self.email_from = settings.EMAIL_FROM
        
        # Initialize Twilio client for SMS
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            self.twilio_phone_number = settings.TWILIO_PHONE_NUMBER
        else:
            self.twilio_client = None
            
        # Jinja2 environment for templates
        self.jinja_env = Environment(autoescape=True)
    
    async def create_notification(
        self,
        notification_data: NotificationCreate,
        agency_id: str,
        send_immediately: bool = True
    ) -> Notification:
        """Create a new notification."""
        try:
            # If user_id is provided, get user details
            user = None
            if notification_data.user_id:
                user = await self.db.get(User, notification_data.user_id)
                if not user:
                    raise ValueError(f"User {notification_data.user_id} not found")
                
                # Check user preferences
                preferences = await self._get_user_preferences(user.id)
                if not await self._should_send_notification(
                    preferences,
                    notification_data.type,
                    notification_data.metadata
                ):
                    logger.info(f"Notification skipped due to user preferences: {user.id}")
                    return None
            
            # Create notification record
            notification = Notification(
                type=notification_data.type,
                status=NotificationStatus.PENDING,
                priority=notification_data.priority,
                user_id=user.id if user else None,
                email=notification_data.email or (user.email if user else None),
                phone=notification_data.phone or (user.phone if user else None),
                subject=notification_data.subject,
                content=notification_data.content,
                html_content=notification_data.html_content,
                template_id=notification_data.template_id,
                template_data=notification_data.template_data,
                metadata=notification_data.metadata,
                tags=notification_data.tags,
                scheduled_at=notification_data.scheduled_at,
                callback_url=notification_data.callback_url,
                agency_id=agency_id
            )
            
            # Process template if provided
            if notification_data.template_id:
                await self._process_template(notification)
            
            self.db.add(notification)
            await self.db.commit()
            await self.db.refresh(notification)
            
            # Send immediately if requested and not scheduled
            if send_immediately and not notification_data.scheduled_at:
                # Queue for sending via Celery
                from tasks.notification_tasks import send_notification
                send_notification.delay(str(notification.id))
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            await self.db.rollback()
            raise
    
    async def send_notification(self, notification_id: str) -> bool:
        """Send a notification."""
        try:
            notification = await self.db.get(Notification, notification_id)
            if not notification:
                logger.error(f"Notification {notification_id} not found")
                return False
            
            # Check if already sent
            if notification.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED]:
                logger.info(f"Notification {notification_id} already sent")
                return True
            
            # Check retry limit
            if notification.retry_count >= notification.max_retries:
                notification.status = NotificationStatus.FAILED
                notification.error_message = "Max retries exceeded"
                await self.db.commit()
                return False
            
            # Send based on type
            success = False
            if notification.type == NotificationType.EMAIL:
                success = await self._send_email(notification)
            elif notification.type == NotificationType.SMS:
                success = await self._send_sms(notification)
            elif notification.type == NotificationType.PUSH:
                success = await self._send_push(notification)
            elif notification.type == NotificationType.IN_APP:
                success = await self._send_in_app(notification)
            elif notification.type == NotificationType.WEBHOOK:
                success = await self._send_webhook(notification)
            
            # Update notification status
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                await self._create_event(notification.id, "sent")
            else:
                notification.status = NotificationStatus.FAILED
                notification.retry_count += 1
                
                # Schedule retry if within limits
                if notification.retry_count < notification.max_retries:
                    retry_delay = 60 * (2 ** notification.retry_count)  # Exponential backoff
                    from tasks.notification_tasks import send_notification
                    send_notification.apply_async(
                        args=[str(notification.id)],
                        countdown=retry_delay
                    )
            
            await self.db.commit()
            return success
            
        except Exception as e:
            logger.error(f"Error sending notification {notification_id}: {e}")
            if notification:
                notification.error_message = str(e)
                notification.retry_count += 1
                await self.db.commit()
            return False
    
    async def _send_email(self, notification: Notification) -> bool:
        """Send email notification."""
        try:
            if not notification.email:
                logger.error(f"No email address for notification {notification.id}")
                return False
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = notification.subject or "Notification from AgencyDark"
            message['From'] = self.email_from
            message['To'] = notification.email
            
            # Add text part
            text_part = MIMEText(notification.content, 'plain')
            message.attach(text_part)
            
            # Add HTML part if available
            if notification.html_content:
                html_part = MIMEText(notification.html_content, 'html')
                message.attach(html_part)
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=self.smtp_tls
            ) as smtp:
                if self.smtp_user and self.smtp_password:
                    await smtp.login(self.smtp_user, self.smtp_password)
                
                response = await smtp.send_message(message)
                
                # Store external ID (message ID from SMTP server)
                if response:
                    notification.external_id = response
                
                logger.info(f"Email sent successfully to {notification.email}")
                return True
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            notification.error_message = str(e)
            return False
    
    async def _send_sms(self, notification: Notification) -> bool:
        """Send SMS notification."""
        try:
            if not self.twilio_client:
                logger.error("Twilio client not configured")
                return False
            
            if not notification.phone:
                logger.error(f"No phone number for notification {notification.id}")
                return False
            
            # Send SMS
            message = self.twilio_client.messages.create(
                body=notification.content,
                from_=self.twilio_phone_number,
                to=notification.phone
            )
            
            # Store external ID
            notification.external_id = message.sid
            
            logger.info(f"SMS sent successfully to {notification.phone}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            notification.error_message = str(e)
            return False
    
    async def _send_push(self, notification: Notification) -> bool:
        """Send push notification."""
        try:
            # TODO: Implement push notification logic
            # This would integrate with services like Firebase Cloud Messaging
            # or Apple Push Notification Service
            
            logger.info(f"Push notification queued for {notification.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            notification.error_message = str(e)
            return False
    
    async def _send_in_app(self, notification: Notification) -> bool:
        """Send in-app notification."""
        try:
            # Send via WebSocket to connected clients
            from core.websocket import manager
            
            if notification.user_id:
                await manager.send_notification(
                    str(notification.user_id),
                    {
                        "id": str(notification.id),
                        "type": "notification",
                        "priority": notification.priority,
                        "subject": notification.subject,
                        "content": notification.content,
                        "metadata": notification.metadata,
                        "created_at": notification.created_at.isoformat()
                    }
                )
            
            logger.info(f"In-app notification sent to user {notification.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending in-app notification: {e}")
            notification.error_message = str(e)
            return False
    
    async def _send_webhook(self, notification: Notification) -> bool:
        """Send webhook notification."""
        try:
            if not notification.callback_url:
                logger.error(f"No callback URL for notification {notification.id}")
                return False
            
            import aiohttp
            
            payload = {
                "id": str(notification.id),
                "type": notification.type,
                "priority": notification.priority,
                "subject": notification.subject,
                "content": notification.content,
                "metadata": notification.metadata,
                "created_at": notification.created_at.isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    notification.callback_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status < 300:
                        logger.info(f"Webhook sent successfully to {notification.callback_url}")
                        return True
                    else:
                        notification.error_message = f"Webhook returned status {response.status}"
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            notification.error_message = str(e)
            return False
    
    async def _process_template(self, notification: Notification) -> None:
        """Process notification template."""
        if not notification.template_id:
            return
        
        template = await self.db.get(NotificationTemplate, notification.template_id)
        if not template:
            logger.error(f"Template {notification.template_id} not found")
            return
        
        # Prepare template data
        template_data = notification.template_data or {}
        
        # Add default variables
        if notification.user_id:
            user = await self.db.get(User, notification.user_id)
            if user:
                template_data.setdefault('user_name', user.full_name)
                template_data.setdefault('user_email', user.email)
        
        # Render subject
        if template.subject_template and not notification.subject:
            subject_template = self.jinja_env.from_string(template.subject_template)
            notification.subject = subject_template.render(**template_data)
        
        # Render content
        if template.content_template:
            content_template = self.jinja_env.from_string(template.content_template)
            notification.content = content_template.render(**template_data)
        
        # Render HTML content
        if template.html_template and not notification.html_content:
            html_template = self.jinja_env.from_string(template.html_template)
            notification.html_content = html_template.render(**template_data)
    
    async def _get_user_preferences(self, user_id: str) -> Optional[NotificationPreference]:
        """Get user notification preferences."""
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    
    async def _should_send_notification(
        self,
        preferences: Optional[NotificationPreference],
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if notification should be sent based on preferences."""
        if not preferences:
            return True  # No preferences = send all
        
        # Check channel preference
        if notification_type == NotificationType.EMAIL and not preferences.email_enabled:
            return False
        elif notification_type == NotificationType.SMS and not preferences.sms_enabled:
            return False
        elif notification_type == NotificationType.PUSH and not preferences.push_enabled:
            return False
        elif notification_type == NotificationType.IN_APP and not preferences.in_app_enabled:
            return False
        
        # Check category preference
        if metadata and 'category' in metadata:
            category = metadata['category']
            if category in preferences.categories and not preferences.categories[category]:
                return False
        
        # Check quiet hours
        if preferences.quiet_hours_enabled and preferences.quiet_hours_start and preferences.quiet_hours_end:
            tz = pytz.timezone(preferences.timezone)
            now = datetime.now(tz)
            current_time = now.strftime('%H:%M')
            
            # Simple comparison (doesn't handle overnight quiet hours)
            if preferences.quiet_hours_start <= current_time <= preferences.quiet_hours_end:
                return False
        
        return True
    
    async def _create_event(
        self,
        notification_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create notification event."""
        event = NotificationEvent(
            notification_id=notification_id,
            event_type=event_type,
            event_data=event_data
        )
        self.db.add(event)
    
    async def create_bulk_notifications(
        self,
        bulk_data: BulkNotificationCreate,
        agency_id: str
    ) -> Dict[str, Any]:
        """Create bulk notifications."""
        try:
            # Gather recipients
            recipients = []
            
            # Add users by ID
            if bulk_data.user_ids:
                for user_id in bulk_data.user_ids:
                    user = await self.db.get(User, user_id)
                    if user:
                        recipients.append({
                            'user_id': user.id,
                            'email': user.email,
                            'phone': user.phone
                        })
            
            # Add direct emails
            if bulk_data.emails and bulk_data.type == NotificationType.EMAIL:
                for email in bulk_data.emails:
                    recipients.append({
                        'user_id': None,
                        'email': email,
                        'phone': None
                    })
            
            # Add direct phones
            if bulk_data.phones and bulk_data.type == NotificationType.SMS:
                for phone in bulk_data.phones:
                    recipients.append({
                        'user_id': None,
                        'email': None,
                        'phone': phone
                    })
            
            # Add users by filters
            if bulk_data.user_filters:
                query = select(User).where(User.agency_id == agency_id)
                
                # Apply filters
                if 'is_active' in bulk_data.user_filters:
                    query = query.where(User.is_active == bulk_data.user_filters['is_active'])
                if 'role' in bulk_data.user_filters:
                    query = query.where(User.role == bulk_data.user_filters['role'])
                
                result = await self.db.execute(query)
                users = result.scalars().all()
                
                for user in users:
                    recipients.append({
                        'user_id': user.id,
                        'email': user.email,
                        'phone': user.phone
                    })
            
            # Create notifications
            notifications_created = 0
            for recipient in recipients:
                notification_data = NotificationCreate(
                    type=bulk_data.type,
                    priority=bulk_data.priority,
                    subject=bulk_data.subject,
                    content=bulk_data.content,
                    html_content=bulk_data.html_content,
                    template_id=bulk_data.template_id,
                    template_data=bulk_data.template_data,
                    user_id=recipient['user_id'],
                    email=recipient['email'],
                    phone=recipient['phone'],
                    metadata=bulk_data.metadata,
                    tags=bulk_data.tags,
                    scheduled_at=bulk_data.scheduled_at
                )
                
                notification = await self.create_notification(
                    notification_data,
                    agency_id,
                    send_immediately=False
                )
                
                if notification:
                    notifications_created += 1
            
            # Queue bulk send task
            from tasks.notification_tasks import send_bulk_notifications
            task = send_bulk_notifications.delay(
                agency_id,
                bulk_data.scheduled_at.isoformat() if bulk_data.scheduled_at else None
            )
            
            return {
                'total_recipients': len(recipients),
                'notifications_created': notifications_created,
                'task_id': task.id,
                'estimated_time': notifications_created * 2  # 2 seconds per notification estimate
            }
            
        except Exception as e:
            logger.error(f"Error creating bulk notifications: {e}")
            await self.db.rollback()
            raise
    
    async def mark_as_delivered(self, notification_id: str, external_id: Optional[str] = None) -> None:
        """Mark notification as delivered."""
        notification = await self.db.get(Notification, notification_id)
        if notification:
            notification.status = NotificationStatus.DELIVERED
            notification.delivered_at = datetime.utcnow()
            if external_id:
                notification.external_id = external_id
            await self._create_event(notification_id, "delivered")
            await self.db.commit()
    
    async def mark_as_opened(self, notification_id: str, ip_address: Optional[str] = None) -> None:
        """Mark notification as opened."""
        notification = await self.db.get(Notification, notification_id)
        if notification:
            notification.status = NotificationStatus.OPENED
            notification.opened_at = datetime.utcnow()
            await self._create_event(
                notification_id,
                "opened",
                {"ip_address": ip_address} if ip_address else None
            )
            await self.db.commit()
    
    async def mark_as_clicked(self, notification_id: str, link: Optional[str] = None) -> None:
        """Mark notification as clicked."""
        notification = await self.db.get(Notification, notification_id)
        if notification:
            notification.status = NotificationStatus.CLICKED
            notification.clicked_at = datetime.utcnow()
            await self._create_event(
                notification_id,
                "clicked",
                {"link": link} if link else None
            )
            await self.db.commit()
    
    async def get_notification_stats(
        self,
        agency_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get notification statistics."""
        query = select(Notification).where(Notification.agency_id == agency_id)
        
        if start_date:
            query = query.where(Notification.created_at >= start_date)
        if end_date:
            query = query.where(Notification.created_at <= end_date)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        # Calculate stats
        stats = {
            'total_sent': 0,
            'total_delivered': 0,
            'total_opened': 0,
            'total_clicked': 0,
            'total_failed': 0,
            'total_bounced': 0,
            'by_type': {},
            'by_priority': {}
        }
        
        for notification in notifications:
            if notification.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED,
                                     NotificationStatus.OPENED, NotificationStatus.CLICKED]:
                stats['total_sent'] += 1
            
            if notification.status in [NotificationStatus.DELIVERED, NotificationStatus.OPENED,
                                     NotificationStatus.CLICKED]:
                stats['total_delivered'] += 1
            
            if notification.status in [NotificationStatus.OPENED, NotificationStatus.CLICKED]:
                stats['total_opened'] += 1
            
            if notification.status == NotificationStatus.CLICKED:
                stats['total_clicked'] += 1
            
            if notification.status == NotificationStatus.FAILED:
                stats['total_failed'] += 1
            
            if notification.status == NotificationStatus.BOUNCED:
                stats['total_bounced'] += 1
            
            # By type
            type_key = notification.type.value
            if type_key not in stats['by_type']:
                stats['by_type'][type_key] = {
                    'sent': 0, 'delivered': 0, 'opened': 0, 'clicked': 0, 'failed': 0
                }
            
            if notification.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED,
                                     NotificationStatus.OPENED, NotificationStatus.CLICKED]:
                stats['by_type'][type_key]['sent'] += 1
            
            # By priority
            priority_key = notification.priority.value
            stats['by_priority'][priority_key] = stats['by_priority'].get(priority_key, 0) + 1
        
        # Calculate rates
        stats['delivery_rate'] = (stats['total_delivered'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0
        stats['open_rate'] = (stats['total_opened'] / stats['total_delivered'] * 100) if stats['total_delivered'] > 0 else 0
        stats['click_rate'] = (stats['total_clicked'] / stats['total_opened'] * 100) if stats['total_opened'] > 0 else 0
        
        return stats