"""
Dead letter queue implementation for failed tasks
"""
import json
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

from celery import Task, current_app
from celery.utils.log import get_task_logger
from sqlalchemy import select, and_, desc

from core.database import get_db_context
from core.redis import redis_client
from core.models import Task as TaskModel

logger = get_task_logger(__name__)


class DeadLetterReason(Enum):
    """Reasons for moving tasks to dead letter queue"""
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    PERMANENT_FAILURE = "permanent_failure"
    INVALID_DATA = "invalid_data"
    UNRECOVERABLE_ERROR = "unrecoverable_error"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


class DeadLetterEntry:
    """Represents an entry in the dead letter queue"""
    
    def __init__(
        self,
        task_id: str,
        task_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        reason: DeadLetterReason,
        error: str,
        traceback: str,
        attempts: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.args = args
        self.kwargs = kwargs
        self.reason = reason
        self.error = error
        self.traceback = traceback
        self.attempts = attempts
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'reason': self.reason.value,
            'error': self.error,
            'traceback': self.traceback,
            'attempts': self.attempts,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeadLetterEntry':
        """Create from dictionary"""
        entry = cls(
            task_id=data['task_id'],
            task_name=data['task_name'],
            args=data['args'],
            kwargs=data['kwargs'],
            reason=DeadLetterReason(data['reason']),
            error=data['error'],
            traceback=data['traceback'],
            attempts=data['attempts'],
            metadata=data.get('metadata', {})
        )
        entry.created_at = datetime.fromisoformat(data['created_at'])
        return entry


class DeadLetterQueue:
    """Manages dead letter queue for failed tasks"""
    
    def __init__(self, queue_name: str = "dead_letter"):
        self.queue_name = queue_name
        self.redis_key_prefix = f"dlq:{queue_name}"
        self.retention_days = 30  # Keep dead letters for 30 days
    
    async def add(
        self,
        task: Task,
        exc: Exception,
        reason: DeadLetterReason,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a failed task to the dead letter queue
        """
        # Create dead letter entry
        entry = DeadLetterEntry(
            task_id=task.request.id,
            task_name=task.name,
            args=task.request.args,
            kwargs=task.request.kwargs,
            reason=reason,
            error=str(exc),
            traceback=traceback.format_exc(),
            attempts=task.request.retries + 1,
            metadata=metadata or {}
        )
        
        # Store in Redis
        entry_key = f"{self.redis_key_prefix}:entry:{entry.task_id}"
        await redis_client.setex(
            entry_key,
            self.retention_days * 86400,
            json.dumps(entry.to_dict())
        )
        
        # Add to queue list
        queue_key = f"{self.redis_key_prefix}:queue"
        await redis_client.lpush(queue_key, entry.task_id)
        
        # Store metadata for searching
        metadata_key = f"{self.redis_key_prefix}:metadata:{entry.task_id}"
        await redis_client.hset(
            metadata_key,
            mapping={
                'task_name': entry.task_name,
                'reason': entry.reason.value,
                'created_at': entry.created_at.isoformat(),
                'error_type': type(exc).__name__
            }
        )
        await redis_client.expire(metadata_key, self.retention_days * 86400)
        
        # Update metrics
        await self._update_metrics(entry)
        
        # Log the dead letter
        logger.error(
            f"Task {entry.task_name} ({entry.task_id}) moved to dead letter queue. "
            f"Reason: {reason.value}, Error: {str(exc)}"
        )
        
        # Send alert for critical tasks
        if task.name in self._get_critical_tasks():
            await self._send_alert(entry)
        
        return entry.task_id
    
    async def get(self, task_id: str) -> Optional[DeadLetterEntry]:
        """
        Get a dead letter entry by task ID
        """
        entry_key = f"{self.redis_key_prefix}:entry:{task_id}"
        data = await redis_client.get(entry_key)
        
        if data:
            return DeadLetterEntry.from_dict(json.loads(data))
        return None
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        task_name: Optional[str] = None,
        reason: Optional[DeadLetterReason] = None
    ) -> List[DeadLetterEntry]:
        """
        List dead letter entries with filtering
        """
        entries = []
        
        # Get all task IDs from queue
        queue_key = f"{self.redis_key_prefix}:queue"
        task_ids = await redis_client.lrange(queue_key, 0, -1)
        
        for task_id in task_ids[offset:offset + limit]:
            # Get metadata for filtering
            metadata_key = f"{self.redis_key_prefix}:metadata:{task_id}"
            metadata = await redis_client.hgetall(metadata_key)
            
            # Apply filters
            if task_name and metadata.get('task_name') != task_name:
                continue
            if reason and metadata.get('reason') != reason.value:
                continue
            
            # Get full entry
            entry = await self.get(task_id)
            if entry:
                entries.append(entry)
        
        return entries
    
    async def retry(self, task_id: str, delay: Optional[int] = None) -> bool:
        """
        Retry a task from the dead letter queue
        """
        entry = await self.get(task_id)
        if not entry:
            logger.error(f"Dead letter entry {task_id} not found")
            return False
        
        try:
            # Get the task
            task = current_app.tasks.get(entry.task_name)
            if not task:
                logger.error(f"Task {entry.task_name} not found")
                return False
            
            # Update metadata
            entry.metadata['retried_from_dlq'] = True
            entry.metadata['retry_timestamp'] = datetime.utcnow().isoformat()
            
            # Apply the task with delay if specified
            if delay:
                task.apply_async(
                    args=entry.args,
                    kwargs=entry.kwargs,
                    countdown=delay,
                    task_id=f"{entry.task_id}_retry"
                )
            else:
                task.apply_async(
                    args=entry.args,
                    kwargs=entry.kwargs,
                    task_id=f"{entry.task_id}_retry"
                )
            
            # Remove from dead letter queue
            await self.remove(task_id)
            
            logger.info(f"Successfully retried task {entry.task_name} ({task_id}) from DLQ")
            return True
            
        except Exception as exc:
            logger.error(f"Failed to retry task {task_id} from DLQ: {exc}")
            return False
    
    async def remove(self, task_id: str) -> bool:
        """
        Remove a task from the dead letter queue
        """
        # Remove entry
        entry_key = f"{self.redis_key_prefix}:entry:{task_id}"
        await redis_client.delete(entry_key)
        
        # Remove from queue list
        queue_key = f"{self.redis_key_prefix}:queue"
        await redis_client.lrem(queue_key, 0, task_id)
        
        # Remove metadata
        metadata_key = f"{self.redis_key_prefix}:metadata:{task_id}"
        await redis_client.delete(metadata_key)
        
        return True
    
    async def purge(
        self,
        older_than: Optional[timedelta] = None,
        task_name: Optional[str] = None
    ) -> int:
        """
        Purge old entries from the dead letter queue
        """
        count = 0
        cutoff_date = datetime.utcnow() - (older_than or timedelta(days=self.retention_days))
        
        # Get all entries
        entries = await self.list(limit=10000)  # Large limit for purging
        
        for entry in entries:
            # Check if should purge
            if entry.created_at < cutoff_date:
                if not task_name or entry.task_name == task_name:
                    await self.remove(entry.task_id)
                    count += 1
        
        logger.info(f"Purged {count} entries from dead letter queue")
        return count
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get dead letter queue metrics
        """
        queue_key = f"{self.redis_key_prefix}:queue"
        queue_size = await redis_client.llen(queue_key)
        
        # Get metrics by reason
        metrics_key = f"{self.redis_key_prefix}:metrics"
        raw_metrics = await redis_client.hgetall(metrics_key)
        
        metrics = {
            'queue_size': queue_size,
            'by_reason': {},
            'by_task': {},
            'recent_errors': []
        }
        
        # Parse metrics
        for key, value in raw_metrics.items():
            if key.startswith('reason:'):
                reason = key.replace('reason:', '')
                metrics['by_reason'][reason] = int(value)
            elif key.startswith('task:'):
                task = key.replace('task:', '')
                metrics['by_task'][task] = int(value)
        
        # Get recent errors
        recent_entries = await self.list(limit=10)
        metrics['recent_errors'] = [
            {
                'task_id': entry.task_id,
                'task_name': entry.task_name,
                'reason': entry.reason.value,
                'error': entry.error[:100],  # First 100 chars
                'created_at': entry.created_at.isoformat()
            }
            for entry in recent_entries
        ]
        
        return metrics
    
    async def _update_metrics(self, entry: DeadLetterEntry):
        """
        Update dead letter queue metrics
        """
        metrics_key = f"{self.redis_key_prefix}:metrics"
        
        # Increment counters
        await redis_client.hincrby(metrics_key, f"reason:{entry.reason.value}", 1)
        await redis_client.hincrby(metrics_key, f"task:{entry.task_name}", 1)
        
        # Set expiry
        await redis_client.expire(metrics_key, 86400 * 7)  # 7 days
    
    def _get_critical_tasks(self) -> List[str]:
        """
        Get list of critical tasks that require immediate alerts
        """
        return [
            'process_payment',
            'send_payout',
            'sync_critical_data',
            'process_subscription',
            'handle_chargeback'
        ]
    
    async def _send_alert(self, entry: DeadLetterEntry):
        """
        Send alert for critical task failure
        """
        alert_key = f"dlq:alerts:{datetime.utcnow().strftime('%Y%m%d')}"
        alert_data = {
            'task_id': entry.task_id,
            'task_name': entry.task_name,
            'reason': entry.reason.value,
            'error': entry.error,
            'attempts': entry.attempts,
            'timestamp': entry.created_at.isoformat(),
            'severity': 'critical'
        }
        
        await redis_client.lpush(alert_key, json.dumps(alert_data))
        await redis_client.expire(alert_key, 86400)  # 24 hours
        
        logger.critical(
            f"CRITICAL TASK FAILURE: {entry.task_name} moved to DLQ after {entry.attempts} attempts"
        )


# Global dead letter queue instance
dead_letter_queue = DeadLetterQueue()


# Enhanced Task class with DLQ support
class TaskWithDLQ(Task):
    """Task class that automatically uses dead letter queue"""
    
    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        super().on_failure(exc, task_id, args, kwargs, einfo)
        
        # Check if should go to DLQ
        if self.request.retries >= self.max_retries:
            # Determine reason
            reason = self._determine_dlq_reason(exc)
            
            # Add to dead letter queue
            import asyncio
            asyncio.run(
                dead_letter_queue.add(
                    task=self,
                    exc=exc,
                    reason=reason,
                    metadata={
                        'final_retry': True,
                        'total_attempts': self.request.retries + 1
                    }
                )
            )
    
    def _determine_dlq_reason(self, exc: Exception) -> DeadLetterReason:
        """Determine the reason for moving to DLQ"""
        exc_type = type(exc).__name__
        exc_msg = str(exc).lower()
        
        # Check for specific error types
        if 'validation' in exc_msg or 'invalid' in exc_msg:
            return DeadLetterReason.INVALID_DATA
        
        if any(keyword in exc_msg for keyword in ['permanent', 'unrecoverable', 'fatal']):
            return DeadLetterReason.PERMANENT_FAILURE
        
        if any(keyword in exc_msg for keyword in ['manual', 'intervention', 'review']):
            return DeadLetterReason.MANUAL_INTERVENTION_REQUIRED
        
        if self.request.retries >= self.max_retries:
            return DeadLetterReason.MAX_RETRIES_EXCEEDED
        
        return DeadLetterReason.UNRECOVERABLE_ERROR


# API endpoints for DLQ management
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/api/v1/dead-letter-queue", tags=["dead-letter-queue"])


@router.get("/entries")
async def list_dead_letter_entries(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    task_name: Optional[str] = None,
    reason: Optional[str] = None
):
    """List entries in the dead letter queue"""
    reason_enum = DeadLetterReason(reason) if reason else None
    entries = await dead_letter_queue.list(
        limit=limit,
        offset=offset,
        task_name=task_name,
        reason=reason_enum
    )
    
    return {
        "entries": [entry.to_dict() for entry in entries],
        "total": len(entries)
    }


@router.get("/entries/{task_id}")
async def get_dead_letter_entry(task_id: str):
    """Get a specific dead letter entry"""
    entry = await dead_letter_queue.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return entry.to_dict()


@router.post("/entries/{task_id}/retry")
async def retry_dead_letter_task(
    task_id: str,
    delay: Optional[int] = Query(None, description="Delay in seconds before retry")
):
    """Retry a task from the dead letter queue"""
    success = await dead_letter_queue.retry(task_id, delay)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to retry task")
    
    return {"status": "success", "message": f"Task {task_id} scheduled for retry"}


@router.delete("/entries/{task_id}")
async def remove_dead_letter_entry(task_id: str):
    """Remove an entry from the dead letter queue"""
    success = await dead_letter_queue.remove(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {"status": "success", "message": f"Entry {task_id} removed"}


@router.get("/metrics")
async def get_dead_letter_metrics():
    """Get dead letter queue metrics"""
    return await dead_letter_queue.get_metrics()


@router.post("/purge")
async def purge_dead_letter_queue(
    older_than_days: Optional[int] = Query(None, description="Purge entries older than N days"),
    task_name: Optional[str] = None
):
    """Purge old entries from the dead letter queue"""
    older_than = timedelta(days=older_than_days) if older_than_days else None
    count = await dead_letter_queue.purge(older_than=older_than, task_name=task_name)
    
    return {
        "status": "success",
        "message": f"Purged {count} entries from dead letter queue"
    }