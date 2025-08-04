"""Email queue service for reliable email delivery."""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.email import EmailMessage, get_email_service
from core.logger import get_logger
from models.email_queue import EmailQueue, EmailStatus, EmailPriority, EmailLog
from core.celery_app import celery_app

logger = get_logger(__name__)


class EmailQueueService:
    """Service for managing email queue."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = get_email_service()
    
    async def enqueue(
        self,
        to: List[str],
        subject: str,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        priority: EmailPriority = EmailPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        user_id: Optional[int] = None,
        related_object_type: Optional[str] = None,
        related_object_id: Optional[int] = None,
        **kwargs
    ) -> EmailQueue:
        """Add email to queue."""
        try:
            # Create queue entry
            email_queue = EmailQueue(
                to_emails=to,
                subject=subject,
                template_id=template_id,
                template_data=template_data,
                html_content=html_content,
                text_content=text_content,
                priority=priority,
                scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
                user_id=user_id,
                related_object_type=related_object_type,
                related_object_id=related_object_id,
                status=EmailStatus.PENDING,
                **kwargs
            )
            
            self.db.add(email_queue)
            await self.db.commit()
            await self.db.refresh(email_queue)
            
            # Schedule for immediate processing if not scheduled
            if not scheduled_at:
                send_email_task.delay(email_queue.id)
            
            logger.info(f"Email queued: {email_queue.id} - {subject}")
            return email_queue
            
        except Exception as e:
            logger.error(f"Failed to enqueue email: {str(e)}")
            await self.db.rollback()
            raise
    
    async def process_queue(self, batch_size: int = 100) -> Dict[str, Any]:
        """Process pending emails in queue."""
        results = {
            'processed': 0,
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # Get pending emails ordered by priority and creation time
            query = select(EmailQueue).where(
                and_(
                    EmailQueue.status == EmailStatus.PENDING,
                    or_(
                        EmailQueue.scheduled_at.is_(None),
                        EmailQueue.scheduled_at <= datetime.utcnow().isoformat()
                    )
                )
            ).order_by(
                EmailQueue.priority.desc(),
                EmailQueue.created_at.asc()
            ).limit(batch_size)
            
            emails = await self.db.scalars(query)
            email_list = list(emails)
            
            for email in email_list:
                try:
                    await self.send_email(email)
                    results['sent'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'email_id': email.id,
                        'error': str(e)
                    })
                
                results['processed'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Queue processing error: {str(e)}")
            results['errors'].append({'error': str(e)})
            return results
    
    async def send_email(self, email_queue: EmailQueue) -> bool:
        """Send a single email from queue."""
        try:
            # Update status to processing
            email_queue.status = EmailStatus.PROCESSING
            email_queue.attempts += 1
            await self.db.commit()
            
            # Create email message
            message = EmailMessage(
                to=email_queue.to_emails,
                subject=email_queue.subject,
                template_id=email_queue.template_id,
                template_data=email_queue.template_data,
                html_content=email_queue.html_content,
                text_content=email_queue.text_content,
                cc=email_queue.cc_emails,
                bcc=email_queue.bcc_emails,
                reply_to=email_queue.reply_to,
                attachments=email_queue.attachments,
                metadata=email_queue.metadata
            )
            
            # Send email
            result = await self.email_service.send(message)
            
            if result.get('success'):
                # Mark as sent
                email_queue.status = EmailStatus.SENT
                email_queue.sent_at = datetime.utcnow().isoformat()
                email_queue.provider_message_id = result.get('message_id')
                email_queue.provider_response = result
                
                # Log success
                await self._log_email_event(
                    email_queue,
                    'sent',
                    {'message_id': result.get('message_id')}
                )
                
                logger.info(f"Email sent: {email_queue.id}")
                
            else:
                # Handle failure
                await self._handle_send_failure(email_queue, result.get('error'))
            
            await self.db.commit()
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Email send error: {str(e)}")
            await self._handle_send_failure(email_queue, str(e))
            await self.db.commit()
            return False
    
    async def _handle_send_failure(
        self, 
        email_queue: EmailQueue, 
        error: str
    ) -> None:
        """Handle email send failure."""
        email_queue.last_error = error
        email_queue.error_count += 1
        
        if email_queue.attempts >= email_queue.max_attempts:
            # Max attempts reached, mark as failed
            email_queue.status = EmailStatus.FAILED
            
            # Log failure
            await self._log_email_event(
                email_queue,
                'failed',
                {'error': error, 'attempts': email_queue.attempts}
            )
            
            logger.error(f"Email failed after {email_queue.attempts} attempts: {email_queue.id}")
            
        else:
            # Schedule retry
            email_queue.status = EmailStatus.PENDING
            
            # Exponential backoff for retries
            retry_delay = min(300, 60 * (2 ** (email_queue.attempts - 1)))
            email_queue.next_retry_at = (
                datetime.utcnow() + timedelta(seconds=retry_delay)
            ).isoformat()
            
            logger.warning(f"Email retry scheduled: {email_queue.id} (attempt {email_queue.attempts})")
    
    async def _log_email_event(
        self,
        email_queue: EmailQueue,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log email event."""
        try:
            for email in email_queue.to_emails:
                log = EmailLog(
                    email_queue_id=email_queue.id,
                    to_email=email,
                    subject=email_queue.subject,
                    event_type=event_type,
                    event_data=event_data,
                    event_timestamp=datetime.utcnow().isoformat(),
                    provider=email_queue.provider,
                    user_id=email_queue.user_id
                )
                self.db.add(log)
            
        except Exception as e:
            logger.error(f"Failed to log email event: {str(e)}")
    
    async def retry_failed_emails(self) -> Dict[str, Any]:
        """Retry failed emails that are eligible."""
        results = {
            'retried': 0,
            'errors': []
        }
        
        try:
            # Get emails ready for retry
            query = select(EmailQueue).where(
                and_(
                    EmailQueue.status == EmailStatus.PENDING,
                    EmailQueue.next_retry_at.isnot(None),
                    EmailQueue.next_retry_at <= datetime.utcnow().isoformat()
                )
            )
            
            emails = await self.db.scalars(query)
            
            for email in emails:
                try:
                    await self.send_email(email)
                    results['retried'] += 1
                except Exception as e:
                    results['errors'].append({
                        'email_id': email.id,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Retry processing error: {str(e)}")
            results['errors'].append({'error': str(e)})
            return results
    
    async def cancel_email(self, email_id: int) -> bool:
        """Cancel a pending email."""
        try:
            email = await self.db.get(EmailQueue, email_id)
            if not email:
                return False
            
            if email.status in [EmailStatus.PENDING, EmailStatus.PROCESSING]:
                email.status = EmailStatus.CANCELLED
                await self.db.commit()
                
                logger.info(f"Email cancelled: {email_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel email: {str(e)}")
            await self.db.rollback()
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get email queue statistics."""
        try:
            # Count by status
            status_counts = await self.db.execute(
                select(
                    EmailQueue.status,
                    func.count(EmailQueue.id).label('count')
                ).group_by(EmailQueue.status)
            )
            
            stats = {
                'by_status': {
                    row.status: row.count
                    for row in status_counts
                },
                'total': sum(row.count for row in status_counts),
                'pending': 0,
                'processing': 0,
                'sent_today': 0,
                'failed_today': 0
            }
            
            # Get today's stats
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            
            sent_today = await self.db.scalar(
                select(func.count(EmailQueue.id)).where(
                    and_(
                        EmailQueue.status == EmailStatus.SENT,
                        EmailQueue.sent_at >= today_start
                    )
                )
            )
            
            failed_today = await self.db.scalar(
                select(func.count(EmailQueue.id)).where(
                    and_(
                        EmailQueue.status == EmailStatus.FAILED,
                        EmailQueue.updated_at >= today_start
                    )
                )
            )
            
            stats['sent_today'] = sent_today or 0
            stats['failed_today'] = failed_today or 0
            stats['pending'] = stats['by_status'].get(EmailStatus.PENDING, 0)
            stats['processing'] = stats['by_status'].get(EmailStatus.PROCESSING, 0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {str(e)}")
            return {}


# Celery tasks
@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, email_queue_id: int):
    """Celery task to send email."""
    async def _send():
        async with get_db() as db:
            service = EmailQueueService(db)
            email = await db.get(EmailQueue, email_queue_id)
            if email:
                await service.send_email(email)
    
    try:
        asyncio.run(_send())
    except Exception as e:
        logger.error(f"Celery email task error: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task
def process_email_queue():
    """Celery task to process email queue."""
    async def _process():
        async with get_db() as db:
            service = EmailQueueService(db)
            await service.process_queue()
    
    asyncio.run(_process())


@celery_app.task
def retry_failed_emails():
    """Celery task to retry failed emails."""
    async def _retry():
        async with get_db() as db:
            service = EmailQueueService(db)
            await service.retry_failed_emails()
    
    asyncio.run(_retry())