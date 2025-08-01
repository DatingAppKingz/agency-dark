"""Sync scheduler for automated synchronization."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from core.database import get_db
from services.sync.delta_sync import DeltaSyncStateManager
from services.sync.onlyfans_sync import OnlyFansSyncService
from models.api_key import APIKey
from services.api_key_service import APIKeyService

logger = get_logger(__name__)


class SyncStatus(str, Enum):
    """Sync job status."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SyncJob:
    """Represents a scheduled sync job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    provider: str = ""
    api_key_id: str = ""
    agency_id: str = ""
    status: SyncStatus = SyncStatus.SCHEDULED
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3


class SyncScheduler:
    """Manages automated sync scheduling."""
    
    def __init__(self, max_concurrent_syncs: int = 5):
        self.max_concurrent_syncs = max_concurrent_syncs
        self._running = False
        self._jobs: Dict[str, SyncJob] = {}
        self._active_syncs: Dict[str, asyncio.Task] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._job_queue: asyncio.Queue[SyncJob] = asyncio.Queue()
    
    async def start(self) -> None:
        """Start the sync scheduler."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_concurrent_syncs):
            asyncio.create_task(self._sync_worker(i))
        
        # Start scheduler task
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info(f"Sync scheduler started with {self.max_concurrent_syncs} workers")
    
    async def stop(self) -> None:
        """Stop the sync scheduler."""
        self._running = False
        
        # Cancel scheduler task
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active syncs
        for task in self._active_syncs.values():
            task.cancel()
        
        # Wait for active syncs to complete
        if self._active_syncs:
            await asyncio.gather(*self._active_syncs.values(), return_exceptions=True)
        
        logger.info("Sync scheduler stopped")
    
    async def schedule_sync(
        self,
        provider: str,
        api_key_id: str,
        agency_id: str,
        delay_seconds: int = 0
    ) -> str:
        """Schedule a sync job."""
        job = SyncJob(
            provider=provider,
            api_key_id=api_key_id,
            agency_id=agency_id,
            scheduled_at=datetime.utcnow() + timedelta(seconds=delay_seconds)
        )
        
        self._jobs[job.id] = job
        
        # Add to queue if should run now
        if delay_seconds == 0:
            await self._job_queue.put(job)
        
        logger.info(
            f"Scheduled sync job {job.id}",
            extra={
                "provider": provider,
                "api_key_id": api_key_id,
                "delay_seconds": delay_seconds
            }
        )
        
        return job.id
    
    async def cancel_sync(self, job_id: str) -> bool:
        """Cancel a scheduled sync job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        # If running, cancel the task
        if job_id in self._active_syncs:
            self._active_syncs[job_id].cancel()
        
        job.status = SyncStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        
        logger.info(f"Cancelled sync job {job_id}")
        return True
    
    async def get_job_status(self, job_id: str) -> Optional[SyncJob]:
        """Get status of a sync job."""
        return self._jobs.get(job_id)
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks for jobs to run."""
        while self._running:
            try:
                # Check for scheduled jobs every minute
                await asyncio.sleep(60)
                
                # Get all active API keys
                async for db in get_db():
                    try:
                        # Find API keys that need syncing
                        api_key_service = APIKeyService(db)
                        
                        # Get all active API keys
                        result = await db.execute(
                            select(APIKey).where(
                                and_(
                                    APIKey.is_active == True,
                                    APIKey.sync_enabled == True
                                )
                            )
                        )
                        api_keys = result.scalars().all()
                        
                        # Schedule syncs for each API key based on interval
                        for api_key in api_keys:
                            await self._check_and_schedule_sync(api_key, db)
                        
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Scheduler loop error: {e}", exc_info=True)
                        await db.rollback()
                    finally:
                        await db.close()
                        break
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
    
    async def _check_and_schedule_sync(self, api_key: APIKey, db: AsyncSession) -> None:
        """Check if an API key needs syncing and schedule if needed."""
        # Get sync state
        state_manager = DeltaSyncStateManager(db, f"{api_key.provider}_sync_{api_key.id}")
        state = await state_manager.load_state()
        
        # Check if sync is needed
        if state.last_successful_sync_at:
            time_since_sync = datetime.utcnow() - state.last_successful_sync_at
            sync_interval = timedelta(minutes=api_key.sync_interval_minutes or 30)
            
            if time_since_sync < sync_interval:
                return  # Not time yet
        
        # Check if already scheduled or running
        for job in self._jobs.values():
            if (job.api_key_id == str(api_key.id) and 
                job.status in [SyncStatus.SCHEDULED, SyncStatus.RUNNING]):
                return  # Already scheduled/running
        
        # Schedule sync
        await self.schedule_sync(
            provider=api_key.provider,
            api_key_id=str(api_key.id),
            agency_id=str(api_key.agency_id)
        )
    
    async def _sync_worker(self, worker_id: int) -> None:
        """Worker that processes sync jobs."""
        logger.info(f"Sync worker {worker_id} started")
        
        while self._running:
            try:
                # Get next job from queue
                job = await asyncio.wait_for(
                    self._job_queue.get(),
                    timeout=5.0
                )
                
                # Process job
                task = asyncio.create_task(self._execute_sync(job))
                self._active_syncs[job.id] = task
                
                try:
                    await task
                finally:
                    self._active_syncs.pop(job.id, None)
            
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync worker {worker_id} error: {e}", exc_info=True)
        
        logger.info(f"Sync worker {worker_id} stopped")
    
    async def _execute_sync(self, job: SyncJob) -> None:
        """Execute a sync job."""
        job.status = SyncStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        try:
            # Get database session
            async for db in get_db():
                try:
                    # Get API key
                    api_key_service = APIKeyService(db)
                    api_key = await api_key_service.get_by_id(job.api_key_id)
                    
                    if not api_key or not api_key.is_active:
                        raise ValueError(f"API key {job.api_key_id} not found or inactive")
                    
                    # Decrypt API credentials
                    decrypted_key = await api_key_service.decrypt_key(api_key)
                    
                    # Create sync service based on provider
                    if job.provider == "onlyfans":
                        sync_service = OnlyFansSyncService(
                            db=db,
                            api_key=decrypted_key,
                            api_secret=api_key.key_metadata.get("api_secret", "")
                        )
                        
                        # Run sync
                        results = await sync_service.sync_all()
                        job.result = {
                            "success": True,
                            "results": {k: v.to_dict() for k, v in results.items()}
                        }
                    else:
                        raise ValueError(f"Unsupported provider: {job.provider}")
                    
                    # Update last sync time
                    api_key.last_sync_at = datetime.utcnow()
                    await db.commit()
                    
                    job.status = SyncStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    
                    logger.info(
                        f"Sync job {job.id} completed successfully",
                        extra={"provider": job.provider, "api_key_id": job.api_key_id}
                    )
                    
                except Exception as e:
                    await db.rollback()
                    raise
                finally:
                    await db.close()
                    break
        
        except Exception as e:
            job.status = SyncStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            job.retry_count += 1
            
            logger.error(
                f"Sync job {job.id} failed",
                extra={
                    "provider": job.provider,
                    "api_key_id": job.api_key_id,
                    "error": str(e),
                    "retry_count": job.retry_count
                },
                exc_info=True
            )
            
            # Schedule retry if not exceeded
            if job.retry_count < job.max_retries:
                retry_delay = min(300 * job.retry_count, 3600)  # 5min, 10min, 15min...
                await self.schedule_sync(
                    provider=job.provider,
                    api_key_id=job.api_key_id,
                    agency_id=job.agency_id,
                    delay_seconds=retry_delay
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        job_stats = {
            "scheduled": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self._jobs.values():
            job_stats[job.status.value] += 1
        
        return {
            "running": self._running,
            "active_syncs": len(self._active_syncs),
            "max_concurrent": self.max_concurrent_syncs,
            "total_jobs": len(self._jobs),
            "job_stats": job_stats,
            "queue_size": self._job_queue.qsize()
        }


# Global scheduler instance
_scheduler: Optional[SyncScheduler] = None


async def get_sync_scheduler() -> SyncScheduler:
    """Get or create sync scheduler instance."""
    global _scheduler
    
    if not _scheduler:
        _scheduler = SyncScheduler()
        await _scheduler.start()
    
    return _scheduler


async def shutdown_scheduler() -> None:
    """Shutdown sync scheduler."""
    global _scheduler
    
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None