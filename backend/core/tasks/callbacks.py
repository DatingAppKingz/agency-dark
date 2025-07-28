"""
Celery task callbacks for monitoring and alerting
"""
import json
from datetime import datetime
from typing import Any

from celery.utils.log import get_task_logger

from core.redis import redis_client
from core.logging import logger as app_logger

logger = get_task_logger(__name__)


def on_task_success(task_name: str, task_id: str, result: Any):
    """
    Called when a task completes successfully
    """
    try:
        # Log success
        logger.info(f"Task {task_name} ({task_id}) completed successfully")
        
        # Update metrics
        import asyncio
        asyncio.run(_update_task_metrics(task_name, 'success'))
        
        # Store result in cache for monitoring
        asyncio.run(_store_task_result(task_id, {
            'status': 'success',
            'task_name': task_name,
            'result': result,
            'completed_at': datetime.utcnow().isoformat()
        }))
        
    except Exception as exc:
        logger.error(f"Error in task success callback: {exc}")


def on_task_failure(task_name: str, task_id: str, exc: Exception, einfo: Any):
    """
    Called when a task fails
    """
    try:
        # Log failure
        logger.error(f"Task {task_name} ({task_id}) failed: {exc}")
        logger.error(f"Traceback: {einfo}")
        
        # Update metrics
        import asyncio
        asyncio.run(_update_task_metrics(task_name, 'failure'))
        
        # Store failure info
        asyncio.run(_store_task_result(task_id, {
            'status': 'failed',
            'task_name': task_name,
            'error': str(exc),
            'traceback': str(einfo),
            'failed_at': datetime.utcnow().isoformat()
        }))
        
        # Send alerts for critical tasks
        critical_tasks = [
            'sync_onlyfans_data',
            'sync_inflow_transactions',
            'sync_stripe_data',
            'process_scheduled_payouts'
        ]
        
        if task_name in critical_tasks:
            asyncio.run(_send_failure_alert(task_name, task_id, exc))
        
    except Exception as callback_exc:
        logger.error(f"Error in task failure callback: {callback_exc}")


def on_task_retry(task_name: str, task_id: str, exc: Exception, einfo: Any):
    """
    Called when a task is retried
    """
    try:
        # Log retry
        logger.warning(f"Task {task_name} ({task_id}) retrying due to: {exc}")
        
        # Update metrics
        import asyncio
        asyncio.run(_update_task_metrics(task_name, 'retry'))
        
    except Exception as callback_exc:
        logger.error(f"Error in task retry callback: {callback_exc}")


async def _update_task_metrics(task_name: str, status: str):
    """
    Update task execution metrics
    """
    try:
        # Increment counter
        metric_key = f"task_metrics:{task_name}:{status}"
        await redis_client.incr(metric_key)
        
        # Set expiry to 7 days
        await redis_client.expire(metric_key, 604800)
        
        # Update last execution time
        last_exec_key = f"task_last_execution:{task_name}"
        await redis_client.set(
            last_exec_key,
            json.dumps({
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            })
        )
        
    except Exception as exc:
        logger.error(f"Failed to update task metrics: {exc}")


async def _store_task_result(task_id: str, result_data: dict):
    """
    Store task result for monitoring
    """
    try:
        result_key = f"task_result:{task_id}"
        await redis_client.setex(
            result_key,
            86400,  # 24 hours
            json.dumps(result_data)
        )
    except Exception as exc:
        logger.error(f"Failed to store task result: {exc}")


async def _send_failure_alert(task_name: str, task_id: str, exc: Exception):
    """
    Send alert for critical task failure
    """
    try:
        # Store alert in Redis for monitoring service to pick up
        alert_key = f"task_alerts:{datetime.utcnow().strftime('%Y%m%d')}"
        alert_data = {
            'task_name': task_name,
            'task_id': task_id,
            'error': str(exc),
            'timestamp': datetime.utcnow().isoformat(),
            'severity': 'critical'
        }
        
        await redis_client.lpush(alert_key, json.dumps(alert_data))
        await redis_client.expire(alert_key, 86400)  # 24 hours
        
        # Log to application logger for immediate visibility
        app_logger.critical(
            f"CRITICAL TASK FAILURE: {task_name} ({task_id}) - {exc}",
            extra={
                'task_name': task_name,
                'task_id': task_id,
                'error': str(exc)
            }
        )
        
        # In production, you would also:
        # - Send email/SMS alerts
        # - Post to monitoring webhook
        # - Create incident ticket
        
    except Exception as alert_exc:
        logger.error(f"Failed to send failure alert: {alert_exc}")