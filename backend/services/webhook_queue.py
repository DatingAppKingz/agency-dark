"""Async webhook processing queue service."""

import asyncio
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp

from core.logger import get_logger
from core.database import get_db
from models.webhook import Webhook, WebhookDelivery, WebhookStatus
from services.webhook_service import WebhookService
from services.webhook_session_manager import get_webhook_session_manager

logger = get_logger(__name__)


class QueuePriority(str, Enum):
    """Webhook queue priority levels."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class WebhookTask:
    """Webhook delivery task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: int = 0
    event: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: QueuePriority = QueuePriority.NORMAL
    attempt: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    next_retry_at: Optional[datetime] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30


class WebhookQueue:
    """In-memory priority queue for webhook tasks."""
    
    def __init__(self):
        self._high_priority: asyncio.Queue = asyncio.Queue()
        self._normal_priority: asyncio.Queue = asyncio.Queue()
        self._low_priority: asyncio.Queue = asyncio.Queue()
        self._processing: Dict[str, WebhookTask] = {}
    
    async def put(self, task: WebhookTask) -> None:
        """Add task to appropriate priority queue."""
        if task.priority == QueuePriority.HIGH:
            await self._high_priority.put(task)
        elif task.priority == QueuePriority.LOW:
            await self._low_priority.put(task)
        else:
            await self._normal_priority.put(task)
    
    async def get(self) -> WebhookTask:
        """Get next task from highest priority non-empty queue."""
        # Check queues in priority order
        if not self._high_priority.empty():
            task = await self._high_priority.get()
        elif not self._normal_priority.empty():
            task = await self._normal_priority.get()
        else:
            # Wait for any queue to have items
            done, pending = await asyncio.wait([
                asyncio.create_task(self._high_priority.get()),
                asyncio.create_task(self._normal_priority.get()),
                asyncio.create_task(self._low_priority.get())
            ], return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel pending tasks
            for t in pending:
                t.cancel()
            
            # Get result from completed task
            task = done.pop().result()
        
        # Track as processing
        self._processing[task.id] = task
        return task
    
    def complete(self, task_id: str) -> None:
        """Mark task as completed."""
        self._processing.pop(task_id, None)
    
    def size(self) -> Dict[str, int]:
        """Get queue sizes."""
        return {
            "high": self._high_priority.qsize(),
            "normal": self._normal_priority.qsize(),
            "low": self._low_priority.qsize(),
            "processing": len(self._processing)
        }


class WebhookProcessor:
    """Async webhook processor with retry and error handling."""
    
    def __init__(
        self,
        max_workers: int = 10,
        batch_size: int = 50
    ):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.queue = WebhookQueue()
        self.session_manager = get_webhook_session_manager()
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self) -> None:
        """Start webhook processor."""
        if self._running:
            return
        
        self._running = True
        self._session = aiohttp.ClientSession()
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        # Start retry checker
        asyncio.create_task(self._retry_checker())
        
        logger.info(f"Webhook processor started with {self.max_workers} workers")
    
    async def stop(self) -> None:
        """Stop webhook processor."""
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Close session
        if self._session:
            await self._session.close()
        
        logger.info("Webhook processor stopped")
    
    async def enqueue(
        self,
        webhook_id: int,
        event: str,
        payload: Dict[str, Any],
        priority: QueuePriority = QueuePriority.NORMAL
    ) -> str:
        """Enqueue webhook for delivery."""
        # Get webhook configuration
        async with self.session_manager.get_session() as db:
            result = await db.execute(
                select(Webhook).where(Webhook.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise ValueError(f"Webhook {webhook_id} not found")
        
        if not webhook.is_active or webhook.status != WebhookStatus.ACTIVE:
            logger.warning(f"Webhook {webhook_id} is not active")
            return ""
        
        # Create task
        task = WebhookTask(
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            priority=priority,
            max_attempts=webhook.max_retries,
            headers=webhook.headers or {},
            timeout_seconds=webhook.timeout_seconds
        )
        
            # Create delivery record
            delivery = WebhookDelivery(
                webhook_id=webhook_id,
                event=event,
                payload=payload,
                attempt_count=0
            )
            db.add(delivery)
            await db.commit()
        
            # Store delivery ID in task
            task.id = str(delivery.id)
        
        # Enqueue task
        await self.queue.put(task)
        
        logger.info(f"Enqueued webhook task {task.id} for event {event}")
        return task.id
    
    async def enqueue_batch(
        self,
        event: str,
        payload: Dict[str, Any],
        webhook_ids: Optional[List[int]] = None,
        priority: QueuePriority = QueuePriority.NORMAL
    ) -> List[str]:
        """Enqueue webhook for multiple recipients."""
        # Get target webhooks
        async with self.session_manager.get_session() as db:
            query = select(Webhook).where(
                and_(
                    Webhook.is_active == True,
                    Webhook.status == WebhookStatus.ACTIVE
                )
            )
            
            if webhook_ids:
                query = query.where(Webhook.id.in_(webhook_ids))
            
            result = await db.execute(query)
            webhooks = result.scalars().all()
        
        # Filter by event subscription
        target_webhooks = [
            w for w in webhooks
            if w.is_subscribed_to(event)
        ]
        
        # Enqueue for each webhook
        task_ids = []
        for webhook in target_webhooks:
            try:
                task_id = await self.enqueue(
                    webhook.id,
                    event,
                    payload,
                    priority
                )
                if task_id:
                    task_ids.append(task_id)
            except Exception as e:
                logger.error(f"Failed to enqueue webhook {webhook.id}: {e}")
        
        return task_ids
    
    async def _worker(self, worker_id: int) -> None:
        """Worker task to process webhook deliveries."""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get next task
                task = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=5.0
                )
                
                # Process task
                await self._deliver_webhook(task)
                
                # Mark as complete
                self.queue.complete(task.id)
                
            except asyncio.TimeoutError:
                # No tasks available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _deliver_webhook(self, task: WebhookTask) -> None:
        """Deliver webhook with retry logic."""
        # Get webhook and delivery records
        async with self.session_manager.get_session() as db:
            result = await db.execute(
                select(Webhook).where(Webhook.id == task.webhook_id)
            )
            webhook = result.scalar_one_or_none()
            
            if not webhook:
                logger.error(f"Webhook {task.webhook_id} not found")
                return
            
            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == int(task.id))
            )
            delivery = result.scalar_one_or_none()
            
            if not delivery:
                logger.error(f"Delivery record {task.id} not found")
                return
            
            # Create webhook service with this session
            webhook_service = WebhookService(db)
        
        # Update attempt count
        task.attempt += 1
        delivery.attempt_count = task.attempt
        
        try:
            # Prepare request
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AgencyDark/1.0",
                "X-Webhook-Event": task.event,
                "X-Webhook-Delivery": task.id,
                "X-Webhook-Timestamp": str(int(datetime.utcnow().timestamp()))
            }
            headers.update(task.headers)
            
            # Add signature if secret is configured
            if webhook.secret:
                payload_bytes = json.dumps(task.payload).encode()
                signature = webhook_service.generate_signature(
                    payload_bytes,
                    webhook.secret
                )
                headers["X-Webhook-Signature"] = signature
            
            # Send webhook
            start_time = datetime.utcnow()
            
            async with self._session.post(
                webhook.url,
                json=task.payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=task.timeout_seconds)
            ) as response:
                response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                # Update delivery record
                delivery.status_code = response.status
                delivery.response_time_ms = response_time_ms
                
                # Read response body (limited)
                try:
                    response_text = await response.text()
                    delivery.response_body = response_text[:2000]  # Limit stored response
                except:
                    delivery.response_body = None
                
                # Check if successful
                if 200 <= response.status < 300:
                    delivery.is_successful = True
                    webhook.successful_calls += 1
                    logger.info(
                        f"Webhook delivered successfully",
                        extra={
                            "webhook_id": webhook.id,
                            "event": task.event,
                            "status": response.status,
                            "duration_ms": response_time_ms
                        }
                    )
                else:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Network or timeout error
            delivery.is_successful = False
            delivery.error_message = str(e)[:500]
            webhook.failed_calls += 1
            webhook.last_error = str(e)[:500]
            
            logger.warning(
                f"Webhook delivery failed",
                extra={
                    "webhook_id": webhook.id,
                    "event": task.event,
                    "attempt": task.attempt,
                    "error": str(e)
                }
            )
            
            # Schedule retry if not exceeded
            if task.attempt < task.max_attempts:
                retry_delay = self._calculate_retry_delay(task.attempt)
                delivery.next_retry_at = (datetime.utcnow() + retry_delay).isoformat()
                
                # Re-enqueue for retry
                task.next_retry_at = datetime.utcnow() + retry_delay
                await self.queue.put(task)
        
        except Exception as e:
            # Unexpected error
            delivery.is_successful = False
            delivery.error_message = f"Unexpected error: {str(e)}"[:500]
            webhook.failed_calls += 1
            webhook.last_error = str(e)[:500]
            
            logger.error(
                f"Unexpected webhook delivery error",
                extra={
                    "webhook_id": webhook.id,
                    "event": task.event,
                    "error": str(e)
                },
                exc_info=True
            )
        
        finally:
            # Update webhook stats
            webhook.total_calls += 1
            webhook.last_called_at = datetime.utcnow().isoformat()
            
            # Check if webhook should be disabled due to failures
            if webhook.failed_calls > 10 and webhook.successful_calls == 0:
                webhook.status = WebhookStatus.FAILED
                logger.warning(f"Webhook {webhook.id} disabled due to repeated failures")
    
    def _calculate_retry_delay(self, attempt: int) -> timedelta:
        """Calculate exponential backoff delay."""
        # Exponential backoff: 1m, 2m, 4m, 8m, etc.
        delay_seconds = min(60 * (2 ** (attempt - 1)), 3600)  # Max 1 hour
        return timedelta(seconds=delay_seconds)
    
    async def _retry_checker(self) -> None:
        """Background task to check for webhooks ready to retry."""
        while self._running:
            try:
                # Check every minute
                await asyncio.sleep(60)
                
                # Find deliveries ready for retry
                async with self.session_manager.get_session() as db:
                    now = datetime.utcnow().isoformat()
                    result = await db.execute(
                        select(WebhookDelivery).where(
                            and_(
                                WebhookDelivery.is_successful == False,
                                WebhookDelivery.next_retry_at != None,
                                WebhookDelivery.next_retry_at <= now
                            )
                        ).limit(self.batch_size)
                    )
                    deliveries = result.scalars().all()
                    
                    # Re-enqueue for retry
                    for delivery in deliveries:
                        webhook = await db.get(Webhook, delivery.webhook_id)
                        if webhook and webhook.is_active:
                            task = WebhookTask(
                                id=str(delivery.id),
                                webhook_id=delivery.webhook_id,
                                event=delivery.event,
                                payload=delivery.payload,
                                priority=QueuePriority.LOW,  # Retries are lower priority
                                attempt=delivery.attempt_count,
                                max_attempts=webhook.max_retries,
                                headers=webhook.headers or {},
                                timeout_seconds=webhook.timeout_seconds
                            )
                            await self.queue.put(task)
                            
                            # Clear retry time
                            delivery.next_retry_at = None
                            await db.commit()
                
                if deliveries:
                    logger.info(f"Re-enqueued {len(deliveries)} webhooks for retry")
            
            except Exception as e:
                logger.error(f"Retry checker error: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            "queue_sizes": self.queue.size(),
            "workers": {
                "active": len(self._workers),
                "max": self.max_workers
            },
            "running": self._running
        }


# Global processor instance
_processor: Optional[WebhookProcessor] = None


async def get_webhook_processor() -> WebhookProcessor:
    """Get or create webhook processor instance."""
    global _processor
    
    if not _processor:
        _processor = WebhookProcessor()
        await _processor.start()
    
    return _processor


async def enqueue_webhook(
    event: str,
    payload: Dict[str, Any],
    webhook_ids: Optional[List[int]] = None,
    priority: QueuePriority = QueuePriority.NORMAL
) -> List[str]:
    """Enqueue webhook for delivery."""
    processor = await get_webhook_processor()
    return await processor.enqueue_batch(event, payload, webhook_ids, priority)


async def shutdown_processor() -> None:
    """Shutdown webhook processor."""
    global _processor
    
    if _processor:
        await _processor.stop()
        _processor = None