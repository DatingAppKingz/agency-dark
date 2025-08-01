"""Background tasks for data export."""

from typing import Dict, Any
from datetime import datetime, timedelta
import io

from core.celery_app import celery_app
from core.database_sync import get_db_sync
from core.redis import redis_client_sync
from core.logger import get_logger
from services.export_service import ExportService
from schemas.export import ExportConfig, ExportProgress, ExportResponse
from models.user import User
from tasks.email_tasks import send_export_email

logger = get_logger(__name__)


@celery_app.task(bind=True, name="process_export")
def process_export_task(
    self,
    export_id: str,
    config: Dict[str, Any],
    user_id: str,
    email_delivery: bool = False
):
    """Process data export in background."""
    try:
        # Update status
        _update_export_progress(
            export_id,
            ExportProgress(
                export_id=export_id,
                status="processing",
                current=0,
                total=0,
                percentage=0,
                message="Starting export..."
            )
        )
        
        # Get database session
        with get_db_sync() as db:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Create export config
            export_config = ExportConfig(**config)
            
            # Create export service
            service = ExportService(db)
            
            # Perform export
            result = service.export_data(export_config, user)
            
            # Store export file in cache
            redis_client_sync.set(
                f"export:file:{export_id}",
                result.content,
                ex=3600 * 24  # 24 hours
            )
            
            # Store metadata
            metadata = ExportResponse(
                export_id=export_id,
                status="completed",
                filename=result.filename,
                download_url=f"/api/v1/exports/{export_id}/download",
                expires_at=datetime.now() + timedelta(days=1),
                record_count=result.record_count,
                created_at=datetime.now()
            )
            
            redis_client_sync.set(
                f"export:metadata:{export_id}",
                metadata.json(),
                ex=3600 * 24  # 24 hours
            )
            
            # Update final status
            _update_export_progress(
                export_id,
                ExportProgress(
                    export_id=export_id,
                    status="completed",
                    current=result.record_count,
                    total=result.record_count,
                    percentage=100,
                    message=f"Export completed: {result.record_count} records"
                )
            )
            
            # Send email if requested
            if email_delivery:
                send_export_email.delay(
                    user_id=user_id,
                    export_id=export_id,
                    filename=result.filename,
                    record_count=result.record_count
                )
            
            logger.info(f"Export {export_id} completed successfully")
            
    except Exception as e:
        logger.error(f"Export {export_id} failed: {e}")
        
        # Update error status
        _update_export_progress(
            export_id,
            ExportProgress(
                export_id=export_id,
                status="failed",
                current=0,
                total=0,
                percentage=0,
                message=f"Export failed: {str(e)}"
            )
        )
        
        raise


@celery_app.task(name="cleanup_old_exports")
def cleanup_old_exports():
    """Clean up old export files."""
    try:
        # Get all export keys
        export_keys = redis_client_sync.keys("export:file:*")
        metadata_keys = redis_client_sync.keys("export:metadata:*")
        
        cleaned = 0
        for key in export_keys + metadata_keys:
            # Check TTL
            ttl = redis_client_sync.ttl(key)
            if ttl < 0:  # Key doesn't exist or has no TTL
                redis_client_sync.delete(key)
                cleaned += 1
        
        logger.info(f"Cleaned up {cleaned} old export files")
        
    except Exception as e:
        logger.error(f"Export cleanup failed: {e}")
        raise


@celery_app.task(name="generate_scheduled_export")
def generate_scheduled_export(
    schedule_id: str,
    config: Dict[str, Any],
    user_id: str,
    recipients: list
):
    """Generate scheduled export."""
    try:
        # Create export ID
        export_id = f"scheduled_{schedule_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Process export
        process_export_task.delay(
            export_id=export_id,
            config=config,
            user_id=user_id,
            email_delivery=bool(recipients)
        )
        
        logger.info(f"Scheduled export {export_id} queued")
        
    except Exception as e:
        logger.error(f"Scheduled export generation failed: {e}")
        raise


def _update_export_progress(export_id: str, progress: ExportProgress):
    """Update export progress in cache."""
    redis_client_sync.set(
        f"export:{export_id}",
        progress.json(),
        ex=3600  # 1 hour
    )