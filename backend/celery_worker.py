#!/usr/bin/env python
"""Celery worker entry point."""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.celery_app import celery_app
from core.logger import get_logger

logger = get_logger(__name__)

# Configure Celery to use the same settings as the main app
os.environ.setdefault('ENV', 'development')

# Import all task modules to register them
from tasks import (
    analytics,
    notifications,
    sync,
    financial,
    media_tasks,
    export_tasks,
    maintenance_tasks,
    notification_tasks
)

if __name__ == '__main__':
    logger.info("Starting Celery worker...")
    
    # Start the worker
    celery_app.start()