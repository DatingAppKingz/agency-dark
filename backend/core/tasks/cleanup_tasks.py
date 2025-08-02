"""
Data cleanup and maintenance tasks
"""
from typing import Dict, Any
from datetime import datetime, timedelta
import os
import shutil

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, delete, and_, or_

from .db_context import get_db_context
from models.user import Session
from models.audit import AuditLog
# from models.notification import EmailLog
from models.sync_log import SyncLog
from models.temp_file import TempFile
# from models.user import PasswordHistory
from models.task import Task
from core.config import settings

logger = get_task_logger(__name__)


@shared_task
def cleanup_expired_sessions() -> Dict[str, Any]:
    """
    Clean up expired user sessions
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                # Delete expired active sessions
                result = await db.execute(
                    delete(Session).where(
                        or_(
                            and_(
                                Session.is_active == True,
                                Session.refresh_expires_at < datetime.utcnow()
                            ),
                            and_(
                                Session.is_active == False,
                                Session.revoked_at < datetime.utcnow() - timedelta(days=30)
                            )
                        )
                    )
                )
                
                await db.commit()
                
                count = result.rowcount
                logger.info(f"Cleaned up {count} expired sessions")
                
                return {
                    'sessions_deleted': count,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Session cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def cleanup_old_audit_logs(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old audit logs
    
    Args:
        days_to_keep: Number of days to keep audit logs
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Keep important events longer
                important_events = [
                    'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT',
                    'PASSWORD_CHANGED', 'PERMISSION_GRANTED', 'PERMISSION_REVOKED',
                    'DATA_EXPORTED', 'DATA_DELETED', 'SECURITY_ALERT'
                ]
                
                # Delete old non-important logs
                result = await db.execute(
                    delete(AuditLog).where(
                        and_(
                            AuditLog.created_at < cutoff_date,
                            ~AuditLog.event_type.in_(important_events)
                        )
                    )
                )
                
                normal_deleted = result.rowcount
                
                # Delete important logs older than 1 year
                year_cutoff = datetime.utcnow() - timedelta(days=365)
                result = await db.execute(
                    delete(AuditLog).where(
                        and_(
                            AuditLog.created_at < year_cutoff,
                            AuditLog.event_type.in_(important_events)
                        )
                    )
                )
                
                important_deleted = result.rowcount
                
                await db.commit()
                
                total_deleted = normal_deleted + important_deleted
                logger.info(f"Cleaned up {total_deleted} audit logs")
                
                return {
                    'normal_logs_deleted': normal_deleted,
                    'important_logs_deleted': important_deleted,
                    'total_deleted': total_deleted,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Audit log cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def cleanup_temp_files() -> Dict[str, Any]:
    """
    Clean up temporary files
    """
    try:
        async def _cleanup():
            files_deleted = 0
            space_freed = 0
            
            async with get_db_context() as db:
                # Get old temp file records
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                result = await db.execute(
                    select(TempFile).where(
                        TempFile.created_at < cutoff_time
                    )
                )
                temp_files = result.scalars().all()
                
                for temp_file in temp_files:
                    try:
                        # Delete physical file
                        if os.path.exists(temp_file.file_path):
                            file_size = os.path.getsize(temp_file.file_path)
                            os.remove(temp_file.file_path)
                            files_deleted += 1
                            space_freed += file_size
                        
                        # Delete database record
                        await db.delete(temp_file)
                        
                    except Exception as exc:
                        logger.warning(f"Failed to delete temp file {temp_file.file_path}: {exc}")
                
                await db.commit()
            
            # Clean up temp directory
            temp_dir = getattr(settings, 'TEMP_DIR', '/tmp/agency')
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    try:
                        # Check file age
                        file_age = datetime.utcnow() - datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_age > timedelta(hours=24):
                            if os.path.isfile(file_path):
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                files_deleted += 1
                                space_freed += file_size
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                                files_deleted += 1
                    except Exception as exc:
                        logger.warning(f"Failed to delete {file_path}: {exc}")
            
            logger.info(f"Cleaned up {files_deleted} temp files, freed {space_freed / 1024 / 1024:.2f} MB")
            
            return {
                'files_deleted': files_deleted,
                'space_freed_mb': round(space_freed / 1024 / 1024, 2),
                'status': 'success'
            }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Temp file cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def cleanup_old_tasks(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old completed/failed tasks


@shared_task
def cleanup_old_email_logs(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old email logs
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                result = await db.execute(
                    delete(EmailLog).where(
                        EmailLog.created_at < cutoff_date
                    )
                )
                
                await db.commit()
                
                count = result.rowcount
                logger.info(f"Cleaned up {count} old email logs")
                
                return {
                    'email_logs_deleted': count,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Email log cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def cleanup_old_sync_logs(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old sync logs
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Keep failed sync logs longer for debugging
                result = await db.execute(
                    delete(SyncLog).where(
                        and_(
                            SyncLog.created_at < cutoff_date,
                            SyncLog.status == 'success'
                        )
                    )
                )
                
                success_deleted = result.rowcount
                
                # Delete failed logs older than 90 days
                failed_cutoff = datetime.utcnow() - timedelta(days=90)
                result = await db.execute(
                    delete(SyncLog).where(
                        and_(
                            SyncLog.created_at < failed_cutoff,
                            SyncLog.status == 'failed'
                        )
                    )
                )
                
                failed_deleted = result.rowcount
                
                await db.commit()
                
                total_deleted = success_deleted + failed_deleted
                logger.info(f"Cleaned up {total_deleted} sync logs")
                
                return {
                    'success_logs_deleted': success_deleted,
                    'failed_logs_deleted': failed_deleted,
                    'total_deleted': total_deleted,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Sync log cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def cleanup_old_password_history(user_id: str = None) -> Dict[str, Any]:
    """
    Clean up old password history entries
    """
    try:
        async def _cleanup():
            async with get_db_context() as db:
                # Keep only last N passwords per user
                passwords_to_keep = 5
                
                if user_id:
                    # Clean up for specific user
                    result = await db.execute(
                        select(PasswordHistory).where(
                            PasswordHistory.user_id == user_id
                        ).order_by(
                            PasswordHistory.created_at.desc()
                        )
                    )
                    passwords = result.scalars().all()
                    
                    # Delete old entries
                    if len(passwords) > passwords_to_keep:
                        for pwd in passwords[passwords_to_keep:]:
                            await db.delete(pwd)
                    
                    deleted_count = max(0, len(passwords) - passwords_to_keep)
                else:
                    # Clean up for all users
                    # This is more complex and would need a different approach
                    # For now, just clean up entries older than 2 years
                    cutoff_date = datetime.utcnow() - timedelta(days=730)
                    
                    result = await db.execute(
                        delete(PasswordHistory).where(
                            PasswordHistory.created_at < cutoff_date
                        )
                    )
                    
                    deleted_count = result.rowcount
                
                await db.commit()
                
                logger.info(f"Cleaned up {deleted_count} password history entries")
                
                return {
                    'entries_deleted': deleted_count,
                    'status': 'success'
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_cleanup())
        
    except Exception as exc:
        logger.error(f"Password history cleanup failed: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }


@shared_task
def check_sync_health() -> Dict[str, Any]:
    """
    Check health of sync operations
    """
    # Imported from sync_tasks to avoid circular import
    from .celery_sync_tasks import check_sync_health as _check_sync_health
    return _check_sync_health()