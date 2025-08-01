"""Notification processing background tasks."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import jinja2
from twilio.rest import Client as TwilioClient
import httpx

from core.database_sync import get_db_sync
from core.logger import get_logger
from core.config import settings
from models.user import User
from models.notification import Notification, NotificationType, NotificationChannel
from models.agency import Agency
from models.model import Model

logger = get_logger(__name__)


class NotificationTask(Task):
    """Base task for notification operations."""
    _db = None
    _email_templates = None
    _twilio_client = None
    
    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            self._db = get_db_sync()
        return self._db
    
    @property
    def email_templates(self) -> jinja2.Environment:
        if self._email_templates is None:
            self._email_templates = jinja2.Environment(
                loader=jinja2.FileSystemLoader('templates/emails')
            )
        return self._email_templates
    
    @property
    def twilio_client(self) -> Optional[TwilioClient]:
        if self._twilio_client is None and settings.TWILIO_ACCOUNT_SID:
            self._twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
        return self._twilio_client


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_email')
def send_email(
    self,
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, Any],
    attachments: Optional[List[Dict[str, Any]]] = None
):
    """
    Send email notification.
    
    Args:
        to_email: Recipient email
        subject: Email subject
        template_name: Email template name
        context: Template context variables
        attachments: List of attachments with 'filename' and 'content'
    """
    try:
        logger.info(f"Sending email to {to_email}: {subject}")
        
        # Render email template
        template = self.email_templates.get_template(f"{template_name}.html")
        html_content = template.render(**context)
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Add plain text version (optional)
        try:
            text_template = self.email_templates.get_template(f"{template_name}.txt")
            text_content = text_template.render(**context)
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
        except:
            # No text template available
            pass
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment["filename"]}"'
                )
                msg.attach(part)
        
        # Send email
        asyncio.run(self._send_email_async(msg))
        
        logger.info(f"Email sent successfully to {to_email}")
        
        return {
            "success": True,
            "to": to_email,
            "subject": subject
        }
        
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return {"success": False, "error": str(e)}
    
    async def _send_email_async(self, message: MIMEMultipart):
        """Send email asynchronously."""
        async with aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            use_tls=settings.SMTP_TLS
        ) as smtp:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            await smtp.send_message(message)


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_sms')
def send_sms(self, to_phone: str, message: str):
    """
    Send SMS notification via Twilio.
    
    Args:
        to_phone: Recipient phone number (E.164 format)
        message: SMS message content
    """
    try:
        if not self.twilio_client:
            logger.error("Twilio not configured")
            return {"success": False, "error": "SMS service not configured"}
        
        logger.info(f"Sending SMS to {to_phone}")
        
        # Send SMS
        message = self.twilio_client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        
        logger.info(f"SMS sent successfully: {message.sid}")
        
        return {
            "success": True,
            "message_sid": message.sid,
            "to": to_phone
        }
        
    except Exception as e:
        logger.error(f"Error sending SMS to {to_phone}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_push_notification')
def send_push_notification(
    self,
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
):
    """
    Send push notification to user's devices.
    
    Args:
        user_id: User ID
        title: Notification title
        body: Notification body
        data: Additional data payload
    """
    try:
        logger.info(f"Sending push notification to user {user_id}")
        
        # Get user's push tokens
        push_tokens = asyncio.run(self._get_user_push_tokens(user_id))
        
        if not push_tokens:
            logger.warning(f"No push tokens found for user {user_id}")
            return {"success": False, "error": "No push tokens found"}
        
        sent_count = 0
        
        for token in push_tokens:
            if token['provider'] == 'fcm':
                success = self._send_fcm_notification(token['token'], title, body, data)
            elif token['provider'] == 'apns':
                success = self._send_apns_notification(token['token'], title, body, data)
            else:
                continue
            
            if success:
                sent_count += 1
        
        logger.info(f"Push notifications sent to {sent_count} devices")
        
        return {
            "success": True,
            "sent_count": sent_count,
            "total_tokens": len(push_tokens)
        }
        
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_user_push_tokens(self, user_id: str) -> List[Dict[str, str]]:
        """Get user's push notification tokens."""
        # Implement token retrieval from database
        # This is a placeholder
        return []
    
    def _send_fcm_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send Firebase Cloud Messaging notification."""
        try:
            # Implement FCM sending logic
            # Using firebase-admin SDK
            return True
        except Exception as e:
            logger.error(f"FCM error: {e}")
            return False
    
    def _send_apns_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send Apple Push Notification Service notification."""
        try:
            # Implement APNS sending logic
            # Using apns2 library
            return True
        except Exception as e:
            logger.error(f"APNS error: {e}")
            return False


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_webhook')
def send_webhook(
    self,
    url: str,
    event_type: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    retry_count: int = 0
):
    """
    Send webhook notification.
    
    Args:
        url: Webhook URL
        event_type: Event type
        payload: Event payload
        headers: Additional headers
        retry_count: Current retry attempt
    """
    try:
        logger.info(f"Sending webhook to {url}: {event_type}")
        
        # Prepare webhook data
        webhook_data = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        
        # Prepare headers
        request_headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Timestamp": webhook_data["timestamp"]
        }
        
        if headers:
            request_headers.update(headers)
        
        # Add signature if secret is configured
        if hasattr(settings, 'WEBHOOK_SECRET'):
            import hmac
            import hashlib
            signature = hmac.new(
                settings.WEBHOOK_SECRET.encode(),
                json.dumps(webhook_data).encode(),
                hashlib.sha256
            ).hexdigest()
            request_headers["X-Webhook-Signature"] = signature
        
        # Send webhook
        response = asyncio.run(self._send_webhook_request(
            url,
            webhook_data,
            request_headers
        ))
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Webhook sent successfully to {url}")
            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.text[:500]  # First 500 chars
            }
        else:
            raise Exception(f"Webhook failed with status {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error sending webhook to {url}: {e}")
        
        # Retry logic
        if retry_count < 3:
            # Exponential backoff
            countdown = (2 ** retry_count) * 60  # 1, 2, 4 minutes
            send_webhook.apply_async(
                args=[url, event_type, payload, headers, retry_count + 1],
                countdown=countdown
            )
            return {"success": False, "error": str(e), "retrying": True}
        
        return {"success": False, "error": str(e), "retrying": False}
    
    async def _send_webhook_request(
        self,
        url: str,
        data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> httpx.Response:
        """Send webhook HTTP request."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            import json
            response = await client.post(
                url,
                json=data,
                headers=headers
            )
            return response


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.process_notification_queue')
def process_notification_queue(self):
    """
    Process queued notifications.
    
    Runs every minute to process pending notifications.
    """
    try:
        logger.info("Processing notification queue")
        
        # Get pending notifications
        notifications = asyncio.run(self._get_pending_notifications())
        
        processed_count = 0
        
        for notification in notifications:
            # Mark as processing
            asyncio.run(self._update_notification_status(
                notification.id,
                'processing'
            ))
            
            # Send based on channel
            if notification.channel == NotificationChannel.EMAIL:
                result = send_email.apply_async(
                    args=[
                        notification.recipient_email,
                        notification.subject,
                        notification.template,
                        notification.context
                    ]
                )
            elif notification.channel == NotificationChannel.SMS:
                result = send_sms.apply_async(
                    args=[
                        notification.recipient_phone,
                        notification.content
                    ]
                )
            elif notification.channel == NotificationChannel.PUSH:
                result = send_push_notification.apply_async(
                    args=[
                        notification.user_id,
                        notification.title,
                        notification.content,
                        notification.data
                    ]
                )
            elif notification.channel == NotificationChannel.IN_APP:
                # In-app notifications are handled differently
                asyncio.run(self._deliver_in_app_notification(notification))
                result = None
            else:
                continue
            
            # Update status
            if result:
                asyncio.run(self._update_notification_status(
                    notification.id,
                    'sent',
                    task_id=result.id
                ))
            
            processed_count += 1
        
        logger.info(f"Processed {processed_count} notifications")
        
        return {
            "success": True,
            "processed_count": processed_count
        }
        
    except Exception as e:
        logger.error(f"Error processing notification queue: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_pending_notifications(self) -> List[Notification]:
        """Get pending notifications."""
        async with self.db as session:
            result = await session.execute(
                select(Notification).where(
                    and_(
                        Notification.status == 'pending',
                        or_(
                            Notification.scheduled_at <= datetime.utcnow(),
                            Notification.scheduled_at.is_(None)
                        )
                    )
                ).limit(100)
            )
            return result.scalars().all()
    
    async def _update_notification_status(
        self,
        notification_id: str,
        status: str,
        task_id: Optional[str] = None
    ):
        """Update notification status."""
        async with self.db as session:
            notification = await session.get(Notification, notification_id)
            if notification:
                notification.status = status
                notification.sent_at = datetime.utcnow() if status == 'sent' else None
                if task_id:
                    notification.task_id = task_id
                await session.commit()
    
    async def _deliver_in_app_notification(self, notification: Notification):
        """Deliver in-app notification."""
        # Mark as delivered
        notification.status = 'delivered'
        notification.delivered_at = datetime.utcnow()
        
        # Send via WebSocket if user is online
        # This would integrate with the real-time system
        pass


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_daily_summaries')
def send_daily_summaries(self):
    """
    Send daily summary emails to agencies.
    
    Runs daily at 9 AM to send performance summaries.
    """
    try:
        logger.info("Sending daily summary emails")
        
        # Get active agencies
        agencies = asyncio.run(self._get_active_agencies())
        
        sent_count = 0
        
        for agency in agencies:
            # Get agency admins
            admins = asyncio.run(self._get_agency_admins(agency.id))
            
            # Generate summary data
            summary_data = asyncio.run(self._generate_daily_summary(agency.id))
            
            # Send to each admin
            for admin in admins:
                if admin.notification_preferences.get('daily_summary', True):
                    send_email.delay(
                        admin.email,
                        f"Daily Summary - {agency.name}",
                        'daily_summary',
                        {
                            'agency': agency,
                            'user': admin,
                            'summary': summary_data
                        }
                    )
                    sent_count += 1
        
        logger.info(f"Sent {sent_count} daily summary emails")
        
        return {
            "success": True,
            "sent_count": sent_count
        }
        
    except Exception as e:
        logger.error(f"Error sending daily summaries: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_active_agencies(self) -> List[Agency]:
        """Get active agencies."""
        async with self.db as session:
            result = await session.execute(
                select(Agency).where(Agency.is_active == True)
            )
            return result.scalars().all()
    
    async def _get_agency_admins(self, agency_id: str) -> List[User]:
        """Get agency admin users."""
        async with self.db as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.agency_id == agency_id,
                        User.role.in_(['agency_admin', 'super_admin']),
                        User.is_active == True
                    )
                )
            )
            return result.scalars().all()
    
    async def _generate_daily_summary(self, agency_id: str) -> Dict[str, Any]:
        """Generate daily summary data."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # This is a placeholder - implement actual summary generation
        return {
            'date': yesterday.date().isoformat(),
            'metrics': {
                'total_revenue': 0,
                'new_fans': 0,
                'messages_sent': 0,
                'active_models': 0
            },
            'top_performers': [],
            'alerts': []
        }


@shared_task(bind=True, base=NotificationTask, name='tasks.notification_tasks.send_alert')
def send_alert(
    self,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    agency_id: Optional[str] = None,
    user_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
):
    """
    Send alert notification.
    
    Args:
        alert_type: Type of alert (security, performance, business)
        severity: Alert severity (info, warning, error, critical)
        title: Alert title
        message: Alert message
        agency_id: Target agency (optional)
        user_id: Target user (optional)
        data: Additional alert data
    """
    try:
        logger.info(f"Sending {severity} alert: {title}")
        
        # Determine recipients
        recipients = asyncio.run(self._get_alert_recipients(
            alert_type,
            severity,
            agency_id,
            user_id
        ))
        
        if not recipients:
            logger.warning("No recipients found for alert")
            return {"success": False, "error": "No recipients"}
        
        sent_count = 0
        
        for recipient in recipients:
            # Send based on severity and preferences
            channels = self._get_alert_channels(severity, recipient)
            
            for channel in channels:
                if channel == 'email':
                    send_email.delay(
                        recipient.email,
                        f"[{severity.upper()}] {title}",
                        'alert',
                        {
                            'alert_type': alert_type,
                            'severity': severity,
                            'title': title,
                            'message': message,
                            'data': data
                        }
                    )
                elif channel == 'sms' and recipient.phone_number:
                    send_sms.delay(
                        recipient.phone_number,
                        f"{title}: {message[:140]}"
                    )
                elif channel == 'push':
                    send_push_notification.delay(
                        str(recipient.id),
                        title,
                        message,
                        {
                            'alert_type': alert_type,
                            'severity': severity,
                            **data or {}
                        }
                    )
                
                sent_count += 1
        
        # Store alert in database
        asyncio.run(self._store_alert(
            alert_type,
            severity,
            title,
            message,
            agency_id,
            data
        ))
        
        logger.info(f"Alert sent to {sent_count} recipients")
        
        return {
            "success": True,
            "sent_count": sent_count
        }
        
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_alert_recipients(
        self,
        alert_type: str,
        severity: str,
        agency_id: Optional[str],
        user_id: Optional[str]
    ) -> List[User]:
        """Get alert recipients based on type and severity."""
        async with self.db as session:
            if user_id:
                # Specific user
                user = await session.get(User, user_id)
                return [user] if user else []
            
            # Get users based on alert type and severity
            query = select(User).where(User.is_active == True)
            
            if agency_id:
                query = query.where(User.agency_id == agency_id)
            
            # For critical alerts, notify admins
            if severity == 'critical':
                query = query.where(User.role.in_(['agency_admin', 'super_admin']))
            
            result = await session.execute(query)
            return result.scalars().all()
    
    def _get_alert_channels(self, severity: str, user: User) -> List[str]:
        """Determine alert channels based on severity."""
        channels = ['email']  # Always send email
        
        if severity in ['error', 'critical']:
            # High severity - use all channels
            channels.extend(['sms', 'push'])
        elif severity == 'warning':
            # Medium severity - email and push
            channels.append('push')
        
        # Filter based on user preferences
        preferences = user.notification_preferences or {}
        return [
            ch for ch in channels
            if preferences.get(f'alert_{ch}', True)
        ]
    
    async def _store_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        agency_id: Optional[str],
        data: Optional[Dict[str, Any]]
    ):
        """Store alert in database for history."""
        # Implement alert storage
        pass