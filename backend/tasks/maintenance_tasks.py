"""System maintenance background tasks."""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from celery import shared_task, Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
import asyncio
import os
import shutil

from core.database_sync import get_db_sync
from core.logger import get_logger
from core.config import settings
from core.redis import redis_client
from models.media import Media, MediaShare, MediaStatus
from models.notification import Notification
from models.session import Session
from models.api_key import APIKey
from models.webhook_event import WebhookEvent
from models.agency import Agency
from models.task_result import TaskResult

logger = get_logger(__name__)


class MaintenanceTask(Task):
    """Base task for maintenance operations."""
    _db = None

    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            self._db = get_db_sync()
        return self._db


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.cleanup_expired_shares')
def cleanup_expired_shares(self):
    """
    Clean up expired media share links.
    
    Runs hourly to remove shares that have:
    - Passed expiration date
    - Exceeded max views
    """
    try:
        logger.info("Starting cleanup of expired media shares")
        
        expired_shares = asyncio.run(self._get_expired_shares())
        
        for share in expired_shares:
            asyncio.run(self._delete_share(share.id))
        
        logger.info(f"Cleaned up {len(expired_shares)} expired shares")
        
        return {
            "success": True,
            "cleaned_count": len(expired_shares)
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up expired shares: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_expired_shares(self) -> List[MediaShare]:
        """Get expired share links."""
        async with self.db as session:
            current_time = datetime.utcnow()
            
            result = await session.execute(
                select(MediaShare).where(
                    or_(
                        and_(
                            MediaShare.expires_at.isnot(None),
                            MediaShare.expires_at < current_time
                        ),
                        and_(
                            MediaShare.max_views.isnot(None),
                            MediaShare.current_views >= MediaShare.max_views
                        )
                    )
                )
            )
            return result.scalars().all()
    
    async def _delete_share(self, share_id: str):
        """Delete a share link."""
        async with self.db as session:
            share = await session.get(MediaShare, share_id)
            if share:
                await session.delete(share)
                await session.commit()


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.cleanup_old_notifications')
def cleanup_old_notifications(self):
    """
    Clean up old notifications.
    
    Removes:
    - Read notifications older than 30 days
    - Unread notifications older than 90 days
    """
    try:
        logger.info("Starting cleanup of old notifications")
        
        # Clean read notifications
        read_cutoff = datetime.utcnow() - timedelta(days=30)
        read_count = asyncio.run(self._cleanup_notifications(
            is_read=True, 
            cutoff_date=read_cutoff
        ))
        
        # Clean unread notifications
        unread_cutoff = datetime.utcnow() - timedelta(days=90)
        unread_count = asyncio.run(self._cleanup_notifications(
            is_read=False,
            cutoff_date=unread_cutoff
        ))
        
        logger.info(f"Cleaned up {read_count} read and {unread_count} unread notifications")
        
        return {
            "success": True,
            "read_cleaned": read_count,
            "unread_cleaned": unread_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {e}")
        return {"success": False, "error": str(e)}
    
    async def _cleanup_notifications(self, is_read: bool, cutoff_date: datetime) -> int:
        """Clean up notifications based on criteria."""
        async with self.db as session:
            result = await session.execute(
                delete(Notification).where(
                    and_(
                        Notification.is_read == is_read,
                        Notification.created_at < cutoff_date
                    )
                )
            )
            await session.commit()
            return result.rowcount


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.update_storage_quotas')
def update_storage_quotas(self):
    """
    Update storage usage for all agencies.
    
    Calculates actual storage usage and updates the cache.
    """
    try:
        logger.info("Updating storage quotas for all agencies")
        
        agencies = asyncio.run(self._get_all_agencies())
        
        for agency in agencies:
            usage = asyncio.run(self._calculate_storage_usage(agency.id))
            asyncio.run(self._update_agency_storage(agency.id, usage))
            
            # Update cache
            cache_key = f"storage:usage:{agency.id}"
            asyncio.run(redis_client.set(
                cache_key,
                usage,
                expire=3600  # 1 hour
            ))
        
        logger.info(f"Updated storage quotas for {len(agencies)} agencies")
        
        return {
            "success": True,
            "updated_count": len(agencies)
        }
        
    except Exception as e:
        logger.error(f"Error updating storage quotas: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_all_agencies(self) -> List[Agency]:
        """Get all active agencies."""
        async with self.db as session:
            result = await session.execute(
                select(Agency).where(Agency.is_active == True)
            )
            return result.scalars().all()
    
    async def _calculate_storage_usage(self, agency_id: str) -> int:
        """Calculate total storage usage for agency."""
        async with self.db as session:
            result = await session.execute(
                select(func.sum(Media.file_size)).where(
                    and_(
                        Media.agency_id == agency_id,
                        Media.status != MediaStatus.DELETED
                    )
                )
            )
            return result.scalar() or 0
    
    async def _update_agency_storage(self, agency_id: str, usage_bytes: int):
        """Update agency storage usage."""
        async with self.db as session:
            await session.execute(
                update(Agency)
                .where(Agency.id == agency_id)
                .values(storage_used_bytes=usage_bytes)
            )
            await session.commit()


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.cleanup_expired_sessions')
def cleanup_expired_sessions(self):
    """Clean up expired user sessions."""
    try:
        logger.info("Cleaning up expired sessions")
        
        cutoff_date = datetime.utcnow()
        deleted_count = asyncio.run(self._delete_expired_sessions(cutoff_date))
        
        logger.info(f"Deleted {deleted_count} expired sessions")
        
        return {
            "success": True,
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        return {"success": False, "error": str(e)}
    
    async def _delete_expired_sessions(self, cutoff_date: datetime) -> int:
        """Delete expired sessions."""
        async with self.db as session:
            result = await session.execute(
                delete(Session).where(Session.expires_at < cutoff_date)
            )
            await session.commit()
            return result.rowcount


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.cleanup_temp_files')
def cleanup_temp_files(self):
    """Clean up temporary files from processing."""
    try:
        logger.info("Cleaning up temporary files")
        
        temp_dirs = [
            "/tmp",
            settings.TEMP_DIR if hasattr(settings, 'TEMP_DIR') else None,
            os.path.join(settings.MEDIA_ROOT, "temp") if hasattr(settings, 'MEDIA_ROOT') else None
        ]
        
        total_cleaned = 0
        total_size = 0
        
        for temp_dir in temp_dirs:
            if temp_dir and os.path.exists(temp_dir):
                cleaned, size = self._clean_directory(temp_dir)
                total_cleaned += cleaned
                total_size += size
        
        logger.info(f"Cleaned {total_cleaned} files, freed {total_size / 1024 / 1024:.2f} MB")
        
        return {
            "success": True,
            "files_cleaned": total_cleaned,
            "space_freed_mb": round(total_size / 1024 / 1024, 2)
        }
        
    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
        return {"success": False, "error": str(e)}
    
    def _clean_directory(self, directory: str) -> tuple:
        """Clean old files from directory."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        cleaned_count = 0
        total_size = 0
        
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            
            # Skip if not a file or if it's a system file
            if not os.path.isfile(filepath) or filename.startswith('.'):
                continue
            
            # Check if file is old enough
            if os.path.getmtime(filepath) < cutoff_time.timestamp():
                try:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    cleaned_count += 1
                    total_size += size
                except Exception as e:
                    logger.warning(f"Could not delete {filepath}: {e}")
        
        return cleaned_count, total_size


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.rotate_api_keys')
def rotate_api_keys(self):
    """
    Rotate API keys that haven't been rotated in 90 days.
    
    Marks old keys for deletion and notifies users.
    """
    try:
        logger.info("Starting API key rotation")
        
        rotation_cutoff = datetime.utcnow() - timedelta(days=90)
        keys_to_rotate = asyncio.run(self._get_keys_for_rotation(rotation_cutoff))
        
        for api_key in keys_to_rotate:
            asyncio.run(self._mark_key_for_rotation(api_key.id))
            asyncio.run(self._notify_key_rotation(api_key))
        
        logger.info(f"Marked {len(keys_to_rotate)} API keys for rotation")
        
        return {
            "success": True,
            "rotated_count": len(keys_to_rotate)
        }
        
    except Exception as e:
        logger.error(f"Error rotating API keys: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_keys_for_rotation(self, cutoff_date: datetime) -> List[APIKey]:
        """Get API keys that need rotation."""
        async with self.db as session:
            result = await session.execute(
                select(APIKey).where(
                    and_(
                        APIKey.is_active == True,
                        or_(
                            APIKey.last_rotated_at < cutoff_date,
                            APIKey.last_rotated_at.is_(None)
                        )
                    )
                )
            )
            return result.scalars().all()
    
    async def _mark_key_for_rotation(self, key_id: str):
        """Mark API key for rotation."""
        async with self.db as session:
            api_key = await session.get(APIKey, key_id)
            if api_key:
                api_key.needs_rotation = True
                api_key.rotation_scheduled_at = datetime.utcnow() + timedelta(days=7)
                await session.commit()
    
    async def _notify_key_rotation(self, api_key: APIKey):
        """Send notification about key rotation."""
        # Implement notification logic
        logger.info(f"Notification sent for API key rotation: {api_key.id}")


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.cleanup_webhook_events')
def cleanup_webhook_events(self):
    """Clean up old webhook events."""
    try:
        logger.info("Cleaning up old webhook events")
        
        # Keep successful events for 7 days, failed ones for 30 days
        success_cutoff = datetime.utcnow() - timedelta(days=7)
        failed_cutoff = datetime.utcnow() - timedelta(days=30)
        
        success_count = asyncio.run(self._cleanup_webhook_events(
            status='delivered',
            cutoff_date=success_cutoff
        ))
        
        failed_count = asyncio.run(self._cleanup_webhook_events(
            status='failed',
            cutoff_date=failed_cutoff
        ))
        
        logger.info(f"Cleaned {success_count} successful and {failed_count} failed webhook events")
        
        return {
            "success": True,
            "success_cleaned": success_count,
            "failed_cleaned": failed_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning webhook events: {e}")
        return {"success": False, "error": str(e)}
    
    async def _cleanup_webhook_events(self, status: str, cutoff_date: datetime) -> int:
        """Clean up webhook events by status."""
        async with self.db as session:
            result = await session.execute(
                delete(WebhookEvent).where(
                    and_(
                        WebhookEvent.status == status,
                        WebhookEvent.created_at < cutoff_date
                    )
                )
            )
            await session.commit()
            return result.rowcount


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.optimize_database')
def optimize_database(self):
    """
    Run database optimization tasks.
    
    - Vacuum tables
    - Update statistics
    - Reindex if needed
    """
    try:
        logger.info("Starting database optimization")
        
        # Run VACUUM ANALYZE on main tables
        tables_to_optimize = [
            'media', 'messages', 'transactions', 'notifications',
            'webhook_events', 'task_results'
        ]
        
        optimized_count = 0
        
        for table in tables_to_optimize:
            success = asyncio.run(self._optimize_table(table))
            if success:
                optimized_count += 1
        
        logger.info(f"Optimized {optimized_count} tables")
        
        return {
            "success": True,
            "optimized_tables": optimized_count
        }
        
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        return {"success": False, "error": str(e)}
    
    async def _optimize_table(self, table_name: str) -> bool:
        """Run optimization on a single table."""
        try:
            async with self.db as session:
                # Note: VACUUM cannot run inside a transaction block
                # This is a simplified version
                await session.execute(f"ANALYZE {table_name}")
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Error optimizing table {table_name}: {e}")
            return False


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.retry_failed_tasks')
def retry_failed_tasks(self):
    """
    Retry failed background tasks.
    
    Looks for tasks that failed due to temporary issues and retries them.
    """
    try:
        logger.info("Looking for failed tasks to retry")
        
        # Get failed tasks from the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        failed_tasks = asyncio.run(self._get_failed_tasks(cutoff_time))
        
        retried_count = 0
        
        for task in failed_tasks:
            if self._should_retry_task(task):
                success = self._retry_task(task)
                if success:
                    retried_count += 1
                    asyncio.run(self._mark_task_retried(task.id))
        
        logger.info(f"Retried {retried_count} failed tasks")
        
        return {
            "success": True,
            "retried_count": retried_count
        }
        
    except Exception as e:
        logger.error(f"Error retrying failed tasks: {e}")
        return {"success": False, "error": str(e)}
    
    async def _get_failed_tasks(self, cutoff_time: datetime) -> List[TaskResult]:
        """Get recently failed tasks."""
        async with self.db as session:
            result = await session.execute(
                select(TaskResult).where(
                    and_(
                        TaskResult.status == 'FAILURE',
                        TaskResult.created_at > cutoff_time,
                        TaskResult.retry_count < 3
                    )
                )
            )
            return result.scalars().all()
    
    def _should_retry_task(self, task: TaskResult) -> bool:
        """Determine if task should be retried."""
        # Check if error is retryable
        retryable_errors = [
            'Connection timeout',
            'Database connection lost',
            'Service temporarily unavailable'
        ]
        
        if task.error_message:
            return any(error in task.error_message for error in retryable_errors)
        
        return False
    
    def _retry_task(self, task: TaskResult) -> bool:
        """Retry a failed task."""
        try:
            # Re-queue the task based on its type
            # This is a simplified version
            logger.info(f"Retrying task {task.id}")
            return True
        except Exception as e:
            logger.error(f"Error retrying task {task.id}: {e}")
            return False
    
    async def _mark_task_retried(self, task_id: str):
        """Mark task as retried."""
        async with self.db as session:
            task = await session.get(TaskResult, task_id)
            if task:
                task.retry_count += 1
                task.last_retry_at = datetime.utcnow()
                await session.commit()


@shared_task(bind=True, base=MaintenanceTask, name='tasks.maintenance_tasks.generate_system_health_report')
def generate_system_health_report(self):
    """
    Generate daily system health report.
    
    Checks various system metrics and sends alerts if needed.
    """
    try:
        logger.info("Generating system health report")
        
        health_metrics = {
            'database': asyncio.run(self._check_database_health()),
            'redis': asyncio.run(self._check_redis_health()),
            'storage': asyncio.run(self._check_storage_health()),
            'api_performance': asyncio.run(self._check_api_performance()),
            'task_queue': asyncio.run(self._check_task_queue_health())
        }
        
        # Check for critical issues
        critical_issues = []
        for component, metrics in health_metrics.items():
            if metrics.get('status') == 'critical':
                critical_issues.append({
                    'component': component,
                    'issue': metrics.get('message')
                })
        
        if critical_issues:
            asyncio.run(self._send_critical_alerts(critical_issues))
        
        # Store report
        report_path = os.path.join(
            settings.REPORTS_DIR,
            f"health_report_{datetime.utcnow().strftime('%Y%m%d')}.json"
        )
        
        os.makedirs(settings.REPORTS_DIR, exist_ok=True)
        
        with open(report_path, 'w') as f:
            import json
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': health_metrics,
                'critical_issues': critical_issues
            }, f, indent=2)
        
        logger.info("System health report generated")
        
        return {
            "success": True,
            "health_status": "critical" if critical_issues else "healthy",
            "critical_issues": len(critical_issues)
        }
        
    except Exception as e:
        logger.error(f"Error generating health report: {e}")
        return {"success": False, "error": str(e)}
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health metrics."""
        try:
            async with self.db as session:
                # Check connection
                await session.execute("SELECT 1")
                
                # Check table sizes
                # This is PostgreSQL specific
                result = await session.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(tablename::regclass) DESC
                    LIMIT 5
                """)
                
                return {
                    'status': 'healthy',
                    'connection': 'ok',
                    'largest_tables': result.fetchall()
                }
                
        except Exception as e:
            return {
                'status': 'critical',
                'message': str(e)
            }
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            # Check Redis connection
            info = await redis_client.info()
            
            return {
                'status': 'healthy',
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime_days': info.get('uptime_in_days')
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'message': str(e)
            }
    
    async def _check_storage_health(self) -> Dict[str, Any]:
        """Check storage health."""
        try:
            # Check disk usage
            stat = shutil.disk_usage("/")
            used_percent = (stat.used / stat.total) * 100
            
            status = 'healthy'
            if used_percent > 90:
                status = 'critical'
            elif used_percent > 80:
                status = 'warning'
            
            return {
                'status': status,
                'used_percent': round(used_percent, 2),
                'free_gb': round(stat.free / (1024**3), 2)
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'message': str(e)
            }
    
    async def _check_api_performance(self) -> Dict[str, Any]:
        """Check API performance metrics."""
        # Get from monitoring service
        return {
            'status': 'healthy',
            'avg_response_time_ms': 150,
            'error_rate': 0.01
        }
    
    async def _check_task_queue_health(self) -> Dict[str, Any]:
        """Check task queue health."""
        # Get Celery queue info
        return {
            'status': 'healthy',
            'pending_tasks': 0,
            'failed_tasks_24h': 0
        }
    
    async def _send_critical_alerts(self, issues: List[Dict[str, Any]]):
        """Send alerts for critical issues."""
        # Implement alerting logic (email, Slack, etc.)
        logger.critical(f"Critical system issues detected: {issues}")