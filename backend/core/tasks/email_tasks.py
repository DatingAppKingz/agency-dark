"""
Email-related async tasks
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

from celery import shared_task
from celery.utils.log import get_task_logger

from core.config import settings
from .db_context import get_db_context
from models import User, EmailLog

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email(
    self,
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send email asynchronously
    
    Args:
        to_email: Recipient email
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        attachments: List of attachments [{filename, content, content_type}]
        cc: CC recipients
        bcc: BCC recipients
        reply_to: Reply-to address
        user_id: User ID for logging
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = getattr(settings, 'EMAIL_FROM', 'noreply@example.com')
        msg['To'] = to_email
        
        if cc:
            msg['Cc'] = ', '.join(cc)
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Add text parts
        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))
        
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
        with smtplib.SMTP(
            getattr(settings, 'SMTP_HOST', 'localhost'),
            getattr(settings, 'SMTP_PORT', 587)
        ) as server:
            if getattr(settings, 'SMTP_USE_TLS', True):
                server.starttls()
            
            if hasattr(settings, 'SMTP_USERNAME') and hasattr(settings, 'SMTP_PASSWORD'):
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            server.send_message(msg, to_addrs=recipients)
        
        # Log email
        # TODO: Fix async logging in sync task
        # # TODO: Fix async database access in sync task
 # async with get_db_context() as db:
        #     email_log = EmailLog(
        #         user_id=user_id,
        #         to_email=to_email,
        #         subject=subject,
        #         status='sent',
        #         sent_at=datetime.utcnow(),
        #         metadata={
        #             'cc': cc,
        #             'bcc': bcc,
        #             'has_attachments': bool(attachments),
        #             'task_id': self.request.id
        #         }
        #     )
        #     db.add(email_log)
        #     await db.commit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return {
            'status': 'sent',
            'to': to_email,
            'subject': subject,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        
        # Log failure
        try:
            # TODO: Fix async database access in sync task

            # async with get_db_context() as db:
                email_log = EmailLog(
                    user_id=user_id,
                    to_email=to_email,
                    subject=subject,
                    status='failed',
                    error_message=str(exc),
                    metadata={'task_id': self.request.id}
                )
                db.add(email_log)
                await db.commit()
        except Exception as log_exc:
            logger.error(f"Failed to log email failure: {log_exc}")
        
        # Retry
        raise self.retry(exc=exc)


@shared_task(bind=True)
def send_bulk_emails(
    self,
    recipients: List[Dict[str, Any]],
    template_id: str,
    variables: Optional[Dict[str, Any]] = None,
    sender_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send bulk emails using template
    
    Args:
        recipients: List of recipient dicts [{email, name, variables}]
        template_id: Email template ID
        variables: Global template variables
        sender_name: Override sender name
    """
    results = {
        'sent': [],
        'failed': [],
        'total': len(recipients)
    }
    
    for recipient in recipients:
        try:
            # Merge variables
            template_vars = {**(variables or {}), **(recipient.get('variables', {}))}
            
            # Get template and render (simplified)
            subject = f"Email from {sender_name or 'Agency'}"  # Would fetch from DB
            body = f"Hello {recipient.get('name', 'there')}!"  # Would render template
            
            # Send individual email
            send_email.delay(
                to_email=recipient['email'],
                subject=subject,
                body=body,
                user_id=recipient.get('user_id')
            )
            
            results['sent'].append(recipient['email'])
            
        except Exception as exc:
            logger.error(f"Failed to queue email for {recipient['email']}: {exc}")
            results['failed'].append({
                'email': recipient['email'],
                'error': str(exc)
            })
    
    return results


@shared_task
def send_notification_email(
    user_id: str,
    notification_type: str,
    data: Dict[str, Any]
) -> bool:
    """
    Send notification email to user
    
    Args:
        user_id: User ID
        notification_type: Type of notification
        data: Notification data
    """
    try:
        # TODO: Fix async database access in sync task

        # async with get_db_context() as db:
            # Get user
            user = await db.get(User, user_id)
            if not user or not user.email:
                logger.warning(f"User {user_id} not found or has no email")
                return False
            
            # Check user preferences
            if not user.email_notifications_enabled:
                logger.info(f"Email notifications disabled for user {user_id}")
                return False
            
            # Determine email content based on type
            templates = {
                'new_message': {
                    'subject': 'You have a new message',
                    'body': f"You received a new message from {data.get('sender_name', 'someone')}."
                },
                'payment_received': {
                    'subject': 'Payment received',
                    'body': f"You received a payment of ${data.get('amount', 0)}."
                },
                'subscription_expired': {
                    'subject': 'Subscription expired',
                    'body': 'Your subscription has expired. Please renew to continue.'
                },
                'report_ready': {
                    'subject': 'Your report is ready',
                    'body': f"Your {data.get('report_type', 'report')} is ready for download."
                }
            }
            
            template = templates.get(notification_type, {
                'subject': 'Notification',
                'body': 'You have a new notification.'
            })
            
            # Send email
            send_email.delay(
                to_email=user.email,
                subject=template['subject'],
                body=template['body'],
                user_id=user_id
            )
            
            return True
            
    except Exception as exc:
        logger.error(f"Failed to send notification email: {exc}")
        return False


@shared_task
def send_welcome_email(user_id: str) -> bool:
    """
    Send welcome email to new user
    """
    try:
        # TODO: Fix async database access in sync task

        # async with get_db_context() as db:
            user = await db.get(User, user_id)
            if not user:
                return False
            
            subject = "Welcome to Agency!"
            body = f"""
Hi {user.full_name or 'there'},

Welcome to Agency! We're excited to have you on board.

Here are some things you can do to get started:
- Complete your profile
- Connect your accounts
- Explore the dashboard

If you have any questions, feel free to reach out to our support team.

Best regards,
The Agency Team
"""
            
            send_email.delay(
                to_email=user.email,
                subject=subject,
                body=body,
                user_id=str(user.id)
            )
            
            return True
            
    except Exception as exc:
        logger.error(f"Failed to send welcome email: {exc}")
        return False


@shared_task
def cleanup_old_email_logs(days: int = 90) -> int:
    """
    Clean up old email logs
    
    Args:
        days: Keep logs from last N days
        
    Returns:
        Number of logs deleted
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # TODO: Fix async database access in sync task

        
        # async with get_db_context() as db:
            result = await db.execute(
                delete(EmailLog).where(EmailLog.created_at < cutoff_date)
            )
            await db.commit()
            
            count = result.rowcount
            logger.info(f"Deleted {count} old email logs")
            return count
            
    except Exception as exc:
        logger.error(f"Failed to cleanup email logs: {exc}")
        return 0