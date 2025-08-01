"""Background tasks for data import."""

from typing import Dict, Any
from datetime import datetime
import json

from core.celery_app import celery_app
from core.database_sync import get_db_sync
from core.redis import redis_client_sync
from core.logger import get_logger
from services.import_service import ImportService
from schemas.import_schema import ImportConfig, ImportProgress, ImportResult
from models.user import User
from tasks.email_tasks import send_import_notification

logger = get_logger(__name__)


@celery_app.task(bind=True, name="process_import")
def process_import_task(
    self,
    import_id: str,
    file_content: str,  # Hex encoded
    config: Dict[str, Any],
    user_id: str,
    filename: str,
    send_notifications: bool = True
):
    """Process data import in background."""
    try:
        # Update status
        _update_import_progress(
            import_id,
            ImportProgress(
                current=0,
                total=0,
                percentage=0,
                status="processing",
                message="Starting import..."
            )
        )
        
        # Convert hex back to bytes
        file_bytes = bytes.fromhex(file_content)
        
        # Get database session
        with get_db_sync() as db:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Create import config
            import_config = ImportConfig(**config)
            
            # Create import service
            service = ImportService(db)
            
            # Perform import
            result = service.import_data(file_bytes, import_config, user)
            
            # Store errors if any
            if result.errors:
                redis_client_sync.set(
                    f"import:errors:{import_id}",
                    json.dumps([e.dict() for e in result.errors]),
                    ex=3600 * 24  # 24 hours
                )
            
            # Update final status
            _update_import_progress(
                import_id,
                ImportProgress(
                    current=result.total_records,
                    total=result.total_records,
                    percentage=100,
                    status="completed",
                    message=f"Import completed: {result.successful_records} successful, {result.failed_records} failed"
                )
            )
            
            # Send notification if requested
            if send_notifications:
                send_import_notification.delay(
                    user_id=user_id,
                    import_id=import_id,
                    filename=filename,
                    total_records=result.total_records,
                    successful_records=result.successful_records,
                    failed_records=result.failed_records
                )
            
            logger.info(f"Import {import_id} completed successfully")
            
            return {
                "import_id": import_id,
                "total_records": result.total_records,
                "successful_records": result.successful_records,
                "failed_records": result.failed_records
            }
            
    except Exception as e:
        logger.error(f"Import {import_id} failed: {e}")
        
        # Update error status
        _update_import_progress(
            import_id,
            ImportProgress(
                current=0,
                total=0,
                percentage=0,
                status="failed",
                message=f"Import failed: {str(e)}"
            )
        )
        
        raise


@celery_app.task(name="validate_import_file")
def validate_import_file(
    file_content: str,  # Hex encoded
    config: Dict[str, Any],
    user_id: str
):
    """Validate import file without importing."""
    try:
        # Convert hex back to bytes
        file_bytes = bytes.fromhex(file_content)
        
        # Get database session
        with get_db_sync() as db:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Create import config with validate_only
            import_config = ImportConfig(**config)
            import_config.validate_only = True
            
            # Create import service
            service = ImportService(db)
            
            # Perform validation
            result = service.import_data(file_bytes, import_config, user)
            
            return {
                "total_records": result.total_records,
                "valid_records": result.successful_records,
                "invalid_records": result.failed_records,
                "errors": [e.dict() for e in result.errors[:100]],  # Limit errors
                "preview": result.preview_data
            }
            
    except Exception as e:
        logger.error(f"Import validation failed: {e}")
        raise


@celery_app.task(name="cleanup_old_imports")
def cleanup_old_imports():
    """Clean up old import data."""
    try:
        # Get all import keys
        import_keys = redis_client_sync.keys("import:*")
        error_keys = redis_client_sync.keys("import:errors:*")
        
        cleaned = 0
        for key in import_keys + error_keys:
            # Check TTL
            ttl = redis_client_sync.ttl(key)
            if ttl < 0:  # Key doesn't exist or has no TTL
                redis_client_sync.delete(key)
                cleaned += 1
        
        logger.info(f"Cleaned up {cleaned} old import files")
        
    except Exception as e:
        logger.error(f"Import cleanup failed: {e}")
        raise


def _update_import_progress(import_id: str, progress: ImportProgress):
    """Update import progress in cache."""
    redis_client_sync.set(
        f"import:{import_id}",
        progress.json(),
        ex=3600  # 1 hour
    )