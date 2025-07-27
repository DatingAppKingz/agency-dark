"""
Background tasks for analytics data synchronization.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from core.config import settings
from core.domain.models import ModelProfile
from modules.analytics.application.data_sync_service import AnalyticsDataSyncService
from modules.financial.domain.models import BillingCycle, BillingCycleStatus

logger = logging.getLogger(__name__)


class AnalyticsBackgroundTasks:
    """Manages background tasks for analytics data sync."""
    
    def __init__(self):
        # Create async engine for background tasks
        self.engine = create_async_engine(
            settings.ASYNC_DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=5
        )
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def sync_all_models_daily(self):
        """
        Daily task to sync analytics data for all active models.
        
        This task:
        1. Finds all active model profiles
        2. Syncs their analytics data for the past day
        3. Updates metric snapshots
        """
        logger.info("Starting daily analytics sync for all models")
        
        async with self.async_session() as db:
            try:
                # Get all active model profiles
                result = await db.execute(
                    select(ModelProfile).where(ModelProfile.is_active == True)
                )
                models = result.scalars().all()
                
                logger.info(f"Found {len(models)} active models to sync")
                
                # Sync each model
                for model in models:
                    try:
                        await self._sync_model_data(db, str(model.id))
                    except Exception as e:
                        logger.error(f"Failed to sync model {model.id}: {e}")
                        continue
                
                logger.info("Completed daily analytics sync")
                
            except Exception as e:
                logger.error(f"Failed to run daily sync: {e}")
    
    async def sync_on_billing_cycle_close(self, billing_cycle_id: str):
        """
        Sync analytics when a billing cycle closes.
        
        Args:
            billing_cycle_id: The billing cycle that just closed
        """
        logger.info(f"Syncing analytics for closed billing cycle {billing_cycle_id}")
        
        async with self.async_session() as db:
            try:
                # Get the billing cycle
                result = await db.execute(
                    select(BillingCycle).where(BillingCycle.id == billing_cycle_id)
                )
                billing_cycle = result.scalar_one_or_none()
                
                if not billing_cycle:
                    logger.error(f"Billing cycle {billing_cycle_id} not found")
                    return
                
                if billing_cycle.status != BillingCycleStatus.CLOSED:
                    logger.warning(f"Billing cycle {billing_cycle_id} is not closed")
                    return
                
                # Sync analytics for the model
                await self._sync_model_data(
                    db,
                    str(billing_cycle.model_id),
                    start_date=billing_cycle.start_date,
                    end_date=billing_cycle.end_date
                )
                
                logger.info(f"Completed analytics sync for billing cycle {billing_cycle_id}")
                
            except Exception as e:
                logger.error(f"Failed to sync for billing cycle: {e}")
    
    async def sync_recent_transactions(self, model_id: str, hours: int = 1):
        """
        Sync recent transactions for real-time analytics.
        
        Args:
            model_id: Model to sync
            hours: How many hours back to sync (default: 1)
        """
        logger.info(f"Syncing recent transactions for model {model_id}")
        
        async with self.async_session() as db:
            try:
                sync_service = AnalyticsDataSyncService(db)
                
                # Sync transactions from the past N hours
                start_date = datetime.utcnow() - timedelta(hours=hours)
                await sync_service.sync_revenue_transactions(
                    model_id,
                    start_date=start_date
                )
                
                # Update today's metric snapshot
                await sync_service._create_daily_snapshot(
                    model_id,
                    datetime.utcnow()
                )
                
                await db.commit()
                logger.info(f"Completed recent transaction sync for model {model_id}")
                
            except Exception as e:
                logger.error(f"Failed to sync recent transactions: {e}")
    
    async def _sync_model_data(
        self,
        db: AsyncSession,
        model_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """
        Internal method to sync model data.
        
        Args:
            db: Database session
            model_id: Model to sync
            start_date: Optional start date
            end_date: Optional end date
        """
        sync_service = AnalyticsDataSyncService(db)
        
        # If no date range specified, sync yesterday's data
        if not start_date:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0) - timedelta(days=1)
        
        # Sync revenue transactions
        await sync_service.sync_revenue_transactions(
            model_id,
            start_date=start_date
        )
        
        # Update metrics for the period
        if start_date and end_date:
            days = (end_date - start_date).days
        else:
            days = 1
        
        await sync_service.update_metric_snapshots(
            model_id,
            lookback_days=days
        )
        
        # Update fan spending and category performance
        await sync_service.update_fan_spending_history(model_id, lookback_days=30)
        await sync_service.update_category_performance(model_id, lookback_days=30)
        
        await db.commit()


# Singleton instance
analytics_tasks = AnalyticsBackgroundTasks()


async def schedule_daily_sync():
    """
    Schedule daily analytics sync.
    
    This should be called when the application starts.
    """
    while True:
        try:
            # Run at 2 AM UTC every day
            now = datetime.utcnow()
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            
            # If it's already past 2 AM today, schedule for tomorrow
            if now >= next_run:
                next_run += timedelta(days=1)
            
            # Calculate seconds until next run
            seconds_until_run = (next_run - now).total_seconds()
            
            logger.info(f"Next analytics sync scheduled in {seconds_until_run} seconds")
            
            # Wait until scheduled time
            await asyncio.sleep(seconds_until_run)
            
            # Run the sync
            await analytics_tasks.sync_all_models_daily()
            
            # Wait a bit before scheduling next run to avoid duplicate runs
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in scheduled sync: {e}")
            # Wait 5 minutes before retrying
            await asyncio.sleep(300)


async def schedule_hourly_sync():
    """
    Schedule hourly sync for recent transactions.
    
    This provides more real-time analytics updates.
    """
    while True:
        try:
            # Wait for an hour
            await asyncio.sleep(3600)
            
            logger.info("Running hourly analytics sync")
            
            # Get all active models
            async with analytics_tasks.async_session() as db:
                result = await db.execute(
                    select(ModelProfile).where(ModelProfile.is_active == True)
                )
                models = result.scalars().all()
                
                # Sync recent transactions for each model
                for model in models:
                    try:
                        await analytics_tasks.sync_recent_transactions(
                            str(model.id),
                            hours=2  # Sync last 2 hours for overlap
                        )
                    except Exception as e:
                        logger.error(f"Failed hourly sync for model {model.id}: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"Error in hourly sync: {e}")
            # Wait 5 minutes before retrying
            await asyncio.sleep(300)