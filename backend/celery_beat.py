#!/usr/bin/env python
"""Celery beat scheduler entry point."""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.celery_app import celery_app
from core.logger import get_logger
from celery.bin import beat

logger = get_logger(__name__)

# Configure Celery to use the same settings as the main app
os.environ.setdefault('ENV', 'development')

if __name__ == '__main__':
    logger.info("Starting Celery beat scheduler...")
    
    # Start the beat scheduler
    beat = beat.beat(app=celery_app)
    beat.run()