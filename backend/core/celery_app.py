"""
Celery application configuration for async task processing
"""
import os
from celery import Celery
from kombu import Exchange, Queue
from celery.schedules import crontab
from datetime import timedelta

from core.config import settings

# Create Celery instance
celery_app = Celery(
    "agency_app",
    broker=getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=[
        'core.tasks.email_tasks',
        'core.tasks.sync_tasks',
        'core.tasks.analytics_tasks',
        'core.tasks.cleanup_tasks',
        'core.tasks.ml_tasks',
        'core.tasks.report_tasks',
        'core.tasks.notification_tasks'
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Result backend settings
    result_expires=86400,  # Results expire after 1 day
    result_persistent=True,
    result_compression='gzip',
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    worker_send_task_events=True,
    
    # Queue configuration
    task_default_queue='default',
    task_default_exchange='default',
    task_default_exchange_type='direct',
    task_default_routing_key='default',
    
    # Error handling
    task_annotations={
        '*': {
            'rate_limit': '100/m',
            'time_limit': 300,
            'soft_time_limit': 270
        }
    }
)

# Define queues with different priorities
celery_app.conf.task_routes = {
    'core.tasks.email_tasks.*': {'queue': 'email', 'priority': 6},
    'core.tasks.sync_tasks.*': {'queue': 'sync', 'priority': 4},
    'core.tasks.analytics_tasks.*': {'queue': 'analytics', 'priority': 3},
    'core.tasks.ml_tasks.*': {'queue': 'ml', 'priority': 2},
    'core.tasks.report_tasks.*': {'queue': 'reports', 'priority': 5},
    'core.tasks.cleanup_tasks.*': {'queue': 'cleanup', 'priority': 1},
    'core.tasks.notification_tasks.*': {'queue': 'notifications', 'priority': 7}
}

# Queue definitions
celery_app.conf.task_queues = (
    Queue('default', Exchange('default'), routing_key='default', priority=5),
    Queue('email', Exchange('email'), routing_key='email', priority=6),
    Queue('sync', Exchange('sync'), routing_key='sync', priority=4),
    Queue('analytics', Exchange('analytics'), routing_key='analytics', priority=3),
    Queue('ml', Exchange('ml'), routing_key='ml', priority=2),
    Queue('reports', Exchange('reports'), routing_key='reports', priority=5),
    Queue('cleanup', Exchange('cleanup'), routing_key='cleanup', priority=1),
    Queue('notifications', Exchange('notifications'), routing_key='notifications', priority=7),
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Data cleanup tasks
    'cleanup-expired-sessions': {
        'task': 'core.tasks.cleanup_tasks.cleanup_expired_sessions',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {'queue': 'cleanup'}
    },
    'cleanup-old-audit-logs': {
        'task': 'core.tasks.cleanup_tasks.cleanup_old_audit_logs',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
        'options': {'queue': 'cleanup'}
    },
    'cleanup-temp-files': {
        'task': 'core.tasks.cleanup_tasks.cleanup_temp_files',
        'schedule': timedelta(hours=1),  # Every hour
        'options': {'queue': 'cleanup'}
    },
    
    # Sync operations
    'sync-onlyfans-data': {
        'task': 'core.tasks.sync_tasks.sync_onlyfans_data',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'queue': 'sync'}
    },
    'sync-inflow-transactions': {
        'task': 'core.tasks.sync_tasks.sync_inflow_transactions',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'sync'}
    },
    'sync-stripe-data': {
        'task': 'core.tasks.sync_tasks.sync_stripe_data',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
        'options': {'queue': 'sync'}
    },
    
    # Report generation
    'generate-daily-reports': {
        'task': 'core.tasks.report_tasks.generate_daily_reports',
        'schedule': crontab(minute=0, hour=6),  # Daily at 6 AM
        'options': {'queue': 'reports'}
    },
    'generate-weekly-reports': {
        'task': 'core.tasks.report_tasks.generate_weekly_reports',
        'schedule': crontab(minute=0, hour=6, day_of_week=1),  # Mondays at 6 AM
        'options': {'queue': 'reports'}
    },
    'generate-monthly-reports': {
        'task': 'core.tasks.report_tasks.generate_monthly_reports',
        'schedule': crontab(minute=0, hour=6, day_of_month=1),  # First of month at 6 AM
        'options': {'queue': 'reports'}
    },
    
    # ML model retraining
    'retrain-revenue-forecast-model': {
        'task': 'core.tasks.ml_tasks.retrain_revenue_forecast_model',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),  # Sundays at 3 AM
        'options': {'queue': 'ml'}
    },
    'retrain-churn-prediction-model': {
        'task': 'core.tasks.ml_tasks.retrain_churn_prediction_model',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),  # Sundays at 4 AM
        'options': {'queue': 'ml'}
    },
    'update-content-recommendations': {
        'task': 'core.tasks.ml_tasks.update_content_recommendations',
        'schedule': timedelta(hours=12),  # Every 12 hours
        'options': {'queue': 'ml'}
    },
    
    # Analytics
    'calculate-daily-metrics': {
        'task': 'core.tasks.analytics_tasks.calculate_daily_metrics',
        'schedule': crontab(minute=30, hour=0),  # Daily at 12:30 AM
        'options': {'queue': 'analytics'}
    },
    'update-cache-analytics': {
        'task': 'core.tasks.analytics_tasks.update_cache_analytics',
        'schedule': timedelta(minutes=5),  # Every 5 minutes
        'options': {'queue': 'analytics'}
    },
    
    # Health checks
    'check-sync-health': {
        'task': 'core.tasks.cleanup_tasks.check_sync_health',
        'schedule': timedelta(minutes=10),  # Every 10 minutes
        'options': {'queue': 'cleanup'}
    }
}

# Custom task base class with Dead Letter Queue support
from celery import Task
from core.tasks.dead_letter import TaskWithDLQ, DeadLetterReason, dead_letter_queue


class CallbackTaskWithDLQ(TaskWithDLQ):
    """Task that runs callbacks and supports dead letter queue"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Success callback"""
        from core.tasks.callbacks import on_task_success
        on_task_success(self.name, task_id, retval)
        super().on_success(retval, task_id, args, kwargs)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure callback with DLQ support"""
        from core.tasks.callbacks import on_task_failure
        on_task_failure(self.name, task_id, exc, einfo)
        
        # Let parent class handle DLQ logic
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Retry callback"""
        from core.tasks.callbacks import on_task_retry
        on_task_retry(self.name, task_id, exc, einfo)
        super().on_retry(exc, task_id, args, kwargs, einfo)


# Set default task base with DLQ support
celery_app.Task = CallbackTaskWithDLQ

# Configure dead letter queue settings
celery_app.conf.update(
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_send_sent_event=True,
    
    # Dead letter queue configuration
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Task failure handling
    task_annotations={
        '*': {
            'on_failure': lambda *args, **kwargs: None,  # Handled by TaskWithDLQ
            'autoretry_for': (Exception,),
            'retry_kwargs': {'max_retries': 3},
            'retry_backoff': True,
            'retry_backoff_max': 600,  # 10 minutes max
            'retry_jitter': True
        }
    }
)


if __name__ == '__main__':
    celery_app.start()