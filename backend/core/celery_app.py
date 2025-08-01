"""Celery configuration and app initialization."""

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from core.config import settings


# Create Celery app
celery_app = Celery(
    "agencydark",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.analytics",
        "tasks.notifications",
        "tasks.sync",
        "tasks.financial",
        "tasks.media_tasks",
        "tasks.export_tasks",
        "tasks.maintenance_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # Results expire after 1 hour
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    task_acks_late=True,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    
    # Queue configuration
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
        Queue("analytics", Exchange("analytics"), routing_key="analytics"),
        Queue("notifications", Exchange("notifications"), routing_key="notifications"),
        Queue("sync", Exchange("sync"), routing_key="sync"),
        Queue("financial", Exchange("financial"), routing_key="financial"),
        Queue("media", Exchange("media"), routing_key="media"),
        Queue("export", Exchange("export"), routing_key="export"),
        Queue("long_running", Exchange("long_running"), routing_key="long_running"),
        Queue("search", Exchange("search"), routing_key="search"),
        Queue("notifications", Exchange("notifications"), routing_key="notifications"),
    ),
    
    # Route tasks to specific queues
    task_routes={
        "tasks.analytics.*": {"queue": "analytics"},
        "tasks.notifications.*": {"queue": "notifications"},
        "tasks.sync.*": {"queue": "sync"},
        "tasks.financial.*": {"queue": "financial"},
        "tasks.media_tasks.*": {"queue": "media"},
        "tasks.export_tasks.*": {"queue": "export"},
        "tasks.maintenance_tasks.*": {"queue": "long_running"},
        "tasks.search_tasks.*": {"queue": "search"},
        "tasks.notification_tasks.*": {"queue": "notifications"},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Sync platform data every 6 hours
        "sync-platform-data": {
            "task": "tasks.sync.sync_all_models",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "sync"}
        },
        
        # Generate daily analytics
        "generate-daily-analytics": {
            "task": "tasks.analytics.generate_daily_analytics",
            "schedule": crontab(hour=2, minute=0),  # 2 AM UTC
            "options": {"queue": "analytics"}
        },
        
        # Process pending payouts
        "process-pending-payouts": {
            "task": "tasks.financial.process_pending_payouts",
            "schedule": crontab(hour=14, minute=0),  # 2 PM UTC
            "options": {"queue": "financial"}
        },
        
        # Send daily summary emails
        "send-daily-summaries": {
            "task": "tasks.notifications.send_daily_summaries",
            "schedule": crontab(hour=9, minute=0),  # 9 AM UTC
            "options": {"queue": "notifications"}
        },
        
        # Clean up old data
        "cleanup-old-data": {
            "task": "tasks.sync.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM UTC
            "options": {"queue": "default"}
        },
        
        # Monitor subscription expirations
        "check-subscription-expirations": {
            "task": "tasks.financial.check_subscription_expirations",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
            "options": {"queue": "financial"}
        },
        
        # Process scheduled notifications
        "process-scheduled-notifications": {
            "task": "tasks.notification_tasks.process_scheduled_notifications",
            "schedule": crontab(minute="*"),  # Every minute
            "options": {"queue": "notifications"}
        },
        
        # Send digest notifications
        "send-digest-notifications": {
            "task": "tasks.notification_tasks.send_digest_notifications",
            "schedule": crontab(hour=9, minute=0),  # 9 AM UTC daily
            "options": {"queue": "notifications"}
        },
        
        # Cleanup old notifications
        "cleanup-old-notifications": {
            "task": "tasks.notification_tasks.cleanup_old_notifications",
            "schedule": crontab(hour=3, minute=0),  # 3 AM UTC daily
            "options": {"queue": "notifications"}
        }
    }
)


# Task result backend configuration
celery_app.conf.result_backend_transport_options = {
    "master_name": "redis-master",
    "visibility_timeout": 3600,  # 1 hour
    "fanout_prefix": True,
    "fanout_patterns": True
}


def get_task_info(task_id: str) -> dict:
    """Get information about a task."""
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result,
        "traceback": result.traceback if result.failed() else None,
        "info": result.info
    }


def cancel_task(task_id: str) -> bool:
    """Cancel a running task."""
    result = celery_app.AsyncResult(task_id)
    result.revoke(terminate=True)
    return True


# Import task modules to register them
# This will be done when the actual task modules are created