"""
Sync Orchestrator for managing external API synchronization.

Coordinates sync operations across multiple platforms (Inflow, OnlyFans)
with proper scheduling, error handling, and monitoring.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from celery import Task

from core.database import get_db
from core.redis import redis_manager
from core.domain.models import ModelProfile
from modules.inflow_wrapper.application.enhanced_sync_service import EnhancedInflowSyncService
from modules.onlyfans_wrapper.application.enhanced_sync_service import EnhancedOnlyFansSyncService


logger = logging.getLogger(__name__)


class SyncStatus(str, Enum):
    """Sync job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncPlatform(str, Enum):
    """Supported sync platforms."""
    INFLOW = "inflow"
    ONLYFANS = "onlyfans"
    ALL = "all"


class SyncOrchestrator:
    """Orchestrates sync operations across platforms."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inflow_sync = EnhancedInflowSyncService(db)
        self.onlyfans_sync = EnhancedOnlyFansSyncService(db)
        self.redis = None
        self.sync_interval = timedelta(minutes=15)  # Default sync interval
        self.max_concurrent_syncs = 5
        self.sync_timeout = timedelta(minutes=30)
    
    async def initialize(self):
        """Initialize orchestrator with Redis."""
        self.redis = await redis_manager.connect()
        await self.inflow_sync.initialize()
        await self.onlyfans_sync.initialize()
    
    async def sync_model(
        self,
        model_profile: ModelProfile,
        platform: SyncPlatform = SyncPlatform.ALL,
        force_full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Sync data for a specific model.
        
        Args:
            model_profile: Model to sync
            platform: Which platform(s) to sync
            force_full_sync: Force full sync instead of incremental
            
        Returns:
            Dict with sync results for each platform
        """
        sync_id = f"sync_{model_profile.id}_{datetime.utcnow().timestamp()}"
        
        # Set sync status
        await self._set_sync_status(model_profile.id, sync_id, SyncStatus.RUNNING)
        
        results = {
            'sync_id': sync_id,
            'model_id': str(model_profile.id),
            'started_at': datetime.utcnow().isoformat(),
            'platforms': {},
            'errors': []
        }
        
        try:
            # Sync Inflow
            if platform in [SyncPlatform.INFLOW, SyncPlatform.ALL] and model_profile.inflow_api_key:
                try:
                    logger.info(f"Starting Inflow sync for model {model_profile.id}")
                    inflow_results = await self.inflow_sync.sync_all_data_incremental(
                        model_profile,
                        force_full_sync=force_full_sync
                    )
                    results['platforms']['inflow'] = inflow_results
                except Exception as e:
                    logger.error(f"Inflow sync failed for model {model_profile.id}: {e}")
                    results['errors'].append({
                        'platform': 'inflow',
                        'error': str(e)
                    })
            
            # Sync OnlyFans
            if platform in [SyncPlatform.ONLYFANS, SyncPlatform.ALL] and model_profile.onlyfans_api_key:
                try:
                    logger.info(f"Starting OnlyFans sync for model {model_profile.id}")
                    onlyfans_results = await self.onlyfans_sync.sync_all_data_incremental(
                        model_profile,
                        force_full_sync=force_full_sync
                    )
                    results['platforms']['onlyfans'] = onlyfans_results
                except Exception as e:
                    logger.error(f"OnlyFans sync failed for model {model_profile.id}: {e}")
                    results['errors'].append({
                        'platform': 'onlyfans',
                        'error': str(e)
                    })
            
            results['completed_at'] = datetime.utcnow().isoformat()
            results['status'] = SyncStatus.COMPLETED if not results['errors'] else SyncStatus.FAILED
            
            # Update sync status
            await self._set_sync_status(
                model_profile.id,
                sync_id,
                SyncStatus.COMPLETED if not results['errors'] else SyncStatus.FAILED,
                results
            )
            
            # Store sync results
            await self._store_sync_results(model_profile.id, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Sync orchestration failed for model {model_profile.id}: {e}")
            results['errors'].append({
                'platform': 'orchestrator',
                'error': str(e)
            })
            results['status'] = SyncStatus.FAILED
            
            await self._set_sync_status(model_profile.id, sync_id, SyncStatus.FAILED, results)
            raise
    
    async def sync_all_models(
        self,
        agency_id: Optional[str] = None,
        platform: SyncPlatform = SyncPlatform.ALL,
        force_full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Sync all models or models for a specific agency.
        
        Args:
            agency_id: Optional agency ID to filter models
            platform: Which platform(s) to sync
            force_full_sync: Force full sync
            
        Returns:
            Dict with sync results summary
        """
        # Get models to sync
        query = select(ModelProfile).where(
            or_(
                ModelProfile.inflow_api_key.isnot(None),
                ModelProfile.onlyfans_api_key.isnot(None)
            )
        )
        
        if agency_id:
            query = query.where(ModelProfile.agency_id == agency_id)
        
        result = await self.db.execute(query)
        models = result.scalars().all()
        
        logger.info(f"Starting sync for {len(models)} models")
        
        # Process models in batches
        results = {
            'total_models': len(models),
            'successful': 0,
            'failed': 0,
            'model_results': []
        }
        
        # Use semaphore to limit concurrent syncs
        semaphore = asyncio.Semaphore(self.max_concurrent_syncs)
        
        async def sync_with_limit(model: ModelProfile):
            async with semaphore:
                try:
                    # Check if model should be synced
                    if await self._should_sync_model(model):
                        model_result = await self.sync_model(
                            model,
                            platform=platform,
                            force_full_sync=force_full_sync
                        )
                        
                        if model_result.get('status') == SyncStatus.COMPLETED:
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                        
                        results['model_results'].append(model_result)
                except Exception as e:
                    logger.error(f"Failed to sync model {model.id}: {e}")
                    results['failed'] += 1
                    results['model_results'].append({
                        'model_id': str(model.id),
                        'status': SyncStatus.FAILED,
                        'error': str(e)
                    })
        
        # Run syncs concurrently
        await asyncio.gather(*[sync_with_limit(model) for model in models])
        
        return results
    
    async def get_sync_status(self, model_id: str) -> Dict[str, Any]:
        """Get current sync status for a model."""
        if not self.redis:
            await self.initialize()
        
        key = f"sync_status:{model_id}"
        status_data = await self.redis.get(key)
        
        if status_data:
            return json.loads(status_data)
        
        return {
            'status': SyncStatus.PENDING,
            'last_sync': None,
            'next_sync': None
        }
    
    async def get_sync_history(
        self,
        model_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get sync history for a model."""
        if not self.redis:
            await self.initialize()
        
        key = f"sync_history:{model_id}"
        history = await self.redis.lrange(key, 0, limit - 1)
        
        return [json.loads(item) for item in history]
    
    async def schedule_sync(
        self,
        model_id: str,
        platform: SyncPlatform = SyncPlatform.ALL,
        delay_minutes: int = 0
    ) -> str:
        """Schedule a sync job for a model."""
        if not self.redis:
            await self.initialize()
        
        job_id = f"sync_job_{model_id}_{datetime.utcnow().timestamp()}"
        
        job_data = {
            'job_id': job_id,
            'model_id': model_id,
            'platform': platform,
            'scheduled_at': datetime.utcnow().isoformat(),
            'execute_at': (datetime.utcnow() + timedelta(minutes=delay_minutes)).isoformat(),
            'status': SyncStatus.PENDING
        }
        
        # Add to job queue
        await self.redis.zadd(
            'sync_job_queue',
            {json.dumps(job_data): (datetime.utcnow() + timedelta(minutes=delay_minutes)).timestamp()}
        )
        
        return job_id
    
    async def cancel_sync(self, job_id: str) -> bool:
        """Cancel a scheduled sync job."""
        if not self.redis:
            await self.initialize()
        
        # Find and remove job from queue
        jobs = await self.redis.zrange('sync_job_queue', 0, -1)
        
        for job_data in jobs:
            job = json.loads(job_data)
            if job['job_id'] == job_id:
                await self.redis.zrem('sync_job_queue', job_data)
                return True
        
        return False
    
    # Private helper methods
    
    async def _should_sync_model(self, model: ModelProfile) -> bool:
        """Check if model should be synced based on last sync time."""
        if not model.last_sync_at:
            return True
        
        time_since_sync = datetime.utcnow() - model.last_sync_at
        return time_since_sync >= self.sync_interval
    
    async def _set_sync_status(
        self,
        model_id: str,
        sync_id: str,
        status: SyncStatus,
        details: Optional[Dict[str, Any]] = None
    ):
        """Set sync status in Redis."""
        if not self.redis:
            await self.initialize()
        
        key = f"sync_status:{model_id}"
        
        status_data = {
            'sync_id': sync_id,
            'status': status,
            'updated_at': datetime.utcnow().isoformat(),
            'details': details
        }
        
        await self.redis.setex(
            key,
            86400,  # 24 hours
            json.dumps(status_data)
        )
    
    async def _store_sync_results(self, model_id: str, results: Dict[str, Any]):
        """Store sync results in history."""
        if not self.redis:
            await self.initialize()
        
        key = f"sync_history:{model_id}"
        
        # Add to history list
        await self.redis.lpush(key, json.dumps(results))
        
        # Keep only last 100 entries
        await self.redis.ltrim(key, 0, 99)
        
        # Set expiry
        await self.redis.expire(key, 86400 * 30)  # 30 days


# Celery task wrapper
class SyncModelTask(Task):
    """Celery task for model sync."""
    
    async def run(self, model_id: str, platform: str = "all", force_full_sync: bool = False):
        """Run sync for a model."""
        async with get_db() as db:
            orchestrator = SyncOrchestrator(db)
            await orchestrator.initialize()
            
            # Get model
            result = await db.execute(
                select(ModelProfile).where(ModelProfile.id == model_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            # Run sync
            return await orchestrator.sync_model(
                model,
                platform=SyncPlatform(platform),
                force_full_sync=force_full_sync
            )