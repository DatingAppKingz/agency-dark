"""
Data synchronization background tasks.

Handles periodic synchronization of data from external APIs.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.config import settings
from backend.core.domain.models import ModelProfile, Agency
from backend.modules.api_orchestration.application.orchestrator import APIOrchestrator


logger = logging.getLogger(__name__)


class SyncScheduler:
    """Manages periodic data synchronization tasks."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
    
    async def start(self):
        """Start the scheduler."""
        # Schedule periodic sync for all models
        self.scheduler.add_job(
            self.sync_all_models,
            IntervalTrigger(hours=1),  # Run every hour
            id="sync_all_models",
            name="Sync all model data",
            replace_existing=True
        )
        
        # Schedule analytics refresh
        self.scheduler.add_job(
            self.refresh_analytics,
            IntervalTrigger(hours=6),  # Run every 6 hours
            id="refresh_analytics",
            name="Refresh analytics data",
            replace_existing=True
        )
        
        # Schedule claim cleanup
        self.scheduler.add_job(
            self.cleanup_expired_claims,
            IntervalTrigger(minutes=5),  # Run every 5 minutes
            id="cleanup_expired_claims",
            name="Cleanup expired fan claims",
            replace_existing=True
        )
        
        # Schedule metrics collection
        self.scheduler.add_job(
            self.collect_metrics,
            IntervalTrigger(hours=1),  # Run every hour
            id="collect_metrics",
            name="Collect analytics metrics",
            replace_existing=True
        )
        
        # Start the scheduler
        self.scheduler.start()
        logger.info("Sync scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        await self.engine.dispose()
        logger.info("Sync scheduler stopped")
    
    async def sync_all_models(self):
        """Sync data for all models with API keys configured."""
        logger.info("Starting scheduled sync for all models")
        
        async with self.async_session() as db:
            try:
                # Get all models with API keys
                result = await db.execute(
                    select(ModelProfile).where(
                        (ModelProfile.inflow_api_key.isnot(None)) |
                        (ModelProfile.onlyfans_api_key.isnot(None))
                    )
                )
                models = result.scalars().all()
                
                logger.info(f"Found {len(models)} models to sync")
                
                # Sync each model
                for model in models:
                    try:
                        await self.sync_model(db, model)
                    except Exception as e:
                        logger.error(f"Failed to sync model {model.id}: {e}")
                        continue
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Failed to sync all models: {e}")
                await db.rollback()
    
    async def sync_model(self, db: AsyncSession, model: ModelProfile):
        """Sync data for a single model."""
        logger.info(f"Syncing data for model {model.id} ({model.username})")
        
        orchestrator = APIOrchestrator(db)
        
        # Check last sync time
        sync_status = await orchestrator.get_sync_status(str(model.id))
        
        # Skip if recently synced (within last 30 minutes)
        if sync_status and sync_status.last_full_sync:
            time_since_sync = datetime.utcnow() - sync_status.last_full_sync
            if time_since_sync < timedelta(minutes=30):
                logger.info(f"Model {model.id} was recently synced, skipping")
                return
        
        # Skip if currently syncing
        if sync_status and sync_status.is_syncing:
            logger.info(f"Model {model.id} is already syncing, skipping")
            return
        
        # Perform sync
        try:
            await orchestrator.sync_all_data(
                model_profile=model,
                sync_inflow=bool(model.inflow_api_key),
                sync_onlyfans=bool(model.onlyfans_api_key)
            )
            logger.info(f"Successfully synced model {model.id}")
        except Exception as e:
            logger.error(f"Sync failed for model {model.id}: {e}")
            raise
    
    async def refresh_analytics(self):
        """Refresh analytics data for all agencies."""
        logger.info("Starting scheduled analytics refresh")
        
        async with self.async_session() as db:
            try:
                # Get all agencies
                result = await db.execute(select(Agency))
                agencies = result.scalars().all()
                
                logger.info(f"Found {len(agencies)} agencies to refresh analytics")
                
                # TODO: Implement analytics refresh logic
                # This would calculate and cache analytics data
                
            except Exception as e:
                logger.error(f"Failed to refresh analytics: {e}")
    
    async def cleanup_expired_claims(self):
        """Clean up expired fan claims."""
        logger.info("Starting expired claims cleanup")
        
        try:
            from backend.modules.chat.application.claim_manager import ClaimManager
            claim_manager = ClaimManager()
            await claim_manager.release_expired_claims()
        except Exception as e:
            logger.error(f"Failed to cleanup expired claims: {e}")
    
    async def collect_metrics(self):
        """Collect analytics metrics for all models."""
        logger.info("Starting metrics collection")
        
        async with self.async_session() as db:
            try:
                from backend.modules.analytics.application.collector import MetricsCollector
                collector = MetricsCollector(db)
                
                # Get all models
                result = await db.execute(select(ModelProfile))
                models = result.scalars().all()
                
                # Collect metrics for each model
                for model in models:
                    try:
                        await collector.collect_model_metrics(model)
                        logger.info(f"Collected metrics for model {model.id}")
                    except Exception as e:
                        logger.error(f"Failed to collect metrics for model {model.id}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Failed to collect metrics: {e}")
    
    async def sync_model_now(self, model_id: str):
        """Manually trigger sync for a specific model."""
        async with self.async_session() as db:
            result = await db.execute(
                select(ModelProfile).where(ModelProfile.id == model_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            await self.sync_model(db, model)
            await db.commit()


# Global scheduler instance
sync_scheduler = SyncScheduler()


async def start_sync_scheduler():
    """Start the sync scheduler (called on app startup)."""
    await sync_scheduler.start()


async def stop_sync_scheduler():
    """Stop the sync scheduler (called on app shutdown)."""
    await sync_scheduler.stop()