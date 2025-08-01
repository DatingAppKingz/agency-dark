"""Application lifecycle events."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import engine, get_db
from core.logger import get_logger
from services.webhook_queue import get_webhook_processor, shutdown_processor

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    
    try:
        # Initialize webhook processor
        processor = await get_webhook_processor()
        logger.info("Webhook processor initialized")
        
        # Add processor to app state
        app.state.webhook_processor = processor
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        
        # Stop webhook processor
        await shutdown_processor()
        logger.info("Webhook processor stopped")
        
        # Close database connections
        await engine.dispose()
        logger.info("Database connections closed")


async def create_startup_handler(app: FastAPI):
    """
    Create startup event handler.
    
    For backwards compatibility with older FastAPI versions.
    """
    async def startup_handler():
        logger.info("Starting application (legacy handler)...")
        
        # Initialize webhook processor
        processor = await get_webhook_processor()
        app.state.webhook_processor = processor
        logger.info("Webhook processor initialized")
    
    return startup_handler


async def create_shutdown_handler(app: FastAPI):
    """
    Create shutdown event handler.
    
    For backwards compatibility with older FastAPI versions.
    """
    async def shutdown_handler():
        logger.info("Shutting down application (legacy handler)...")
        
        # Stop webhook processor
        await shutdown_processor()
        logger.info("Webhook processor stopped")
        
        # Close database connections
        await engine.dispose()
        logger.info("Database connections closed")
    
    return shutdown_handler