"""
Database context wrapper for Celery tasks.

This provides a sync-compatible database context for Celery tasks.
"""
from contextlib import contextmanager
from core.database import get_db_sync

@contextmanager
def get_db_context():
    """
    Get database context for Celery tasks.
    
    This is a compatibility wrapper that provides a context manager
    for sync database access in Celery tasks.
    """
    db = next(get_db_sync())
    try:
        yield db
    finally:
        db.close()