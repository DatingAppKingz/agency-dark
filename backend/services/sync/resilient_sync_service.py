"""Resilient sync service with integrated error recovery."""

from typing import Any, Dict, List, Optional, Tuple, TypeVar, Generic
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from services.sync.base_sync_service import BaseSyncService, SyncConfig, SyncState, SyncResult, SyncStatus
from services.sync.error_recovery import (
    SyncErrorRecoveryService,
    ErrorContext,
    ErrorType,
    RecoveryStrategy,
    RecoveryAction,
    RetryHandler,
    CircuitBreaker
)
from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class ResilientSyncConfig(SyncConfig):
    """Extended configuration for resilient sync."""
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
    enable_adaptive_batch_size: bool = True
    min_batch_size: int = 10
    max_batch_size: int = 1000
    batch_size_reduction_factor: float = 0.5
    batch_size_increase_factor: float = 1.2
    error_threshold_for_pause: int = 10
    pause_duration_seconds: int = 600


class ResilientSyncService(BaseSyncService[T], Generic[T]):
    """Sync service with built-in error recovery and resilience."""
    
    def __init__(
        self,
        db: AsyncSession,
        service_id: str,
        config: Optional[ResilientSyncConfig] = None
    ):
        super().__init__(db, config or ResilientSyncConfig())
        self.service_id = service_id
        self.config: ResilientSyncConfig = config or ResilientSyncConfig()
        
        # Initialize error recovery
        self.error_recovery = SyncErrorRecoveryService(db)
        self._setup_recovery_callbacks()
        
        # Dynamic batch size management
        self.current_batch_size = self.config.batch_size
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        
        # Pause management
        self.is_paused = False
        self.pause_until: Optional[datetime] = None
    
    def _setup_recovery_callbacks(self):
        """Setup recovery callbacks for different strategies."""
        self.error_recovery.register_recovery_callback(
            RecoveryStrategy.REFRESH_AUTH,
            self._handle_auth_refresh
        )
        self.error_recovery.register_recovery_callback(
            RecoveryStrategy.REDUCE_BATCH_SIZE,
            self._handle_batch_size_reduction
        )
        self.error_recovery.register_recovery_callback(
            RecoveryStrategy.PAUSE_SYNC,
            self._handle_pause_sync
        )
    
    async def sync(self, state: SyncState) -> SyncResult:
        """Enhanced sync with error recovery."""
        # Check if sync is paused
        if self.is_paused and self.pause_until:
            if datetime.utcnow() < self.pause_until:
                remaining = (self.pause_until - datetime.utcnow()).total_seconds()
                logger.warning(
                    f"Sync paused for {self.service_id}, {remaining}s remaining"
                )
                return SyncResult(
                    status=SyncStatus.FAILED,
                    errors=[{"error": "Sync paused", "remaining_seconds": remaining}]
                )
            else:
                self.is_paused = False
                self.pause_until = None
                logger.info(f"Resuming sync for {self.service_id}")
        
        # Check circuit breaker
        circuit_breaker = self.error_recovery.get_circuit_breaker(self.service_id)
        if not circuit_breaker.can_execute():
            wait_time = circuit_breaker.get_wait_time()
            return SyncResult(
                status=SyncStatus.FAILED,
                errors=[{"error": "Circuit breaker open", "wait_time": wait_time}]
            )
        
        # Perform sync with error handling
        result = SyncResult(status=SyncStatus.IN_PROGRESS)
        
        try:
            result = await self._sync_with_recovery(state, result)
            
            # Record success
            circuit_breaker.record_success()
            self._handle_successful_sync()
            
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            self._handle_failed_sync()
            
            # Handle error
            recovery_action = await self.error_recovery.handle_sync_error(
                exception=e,
                service_id=self.service_id,
                context={
                    "state": state.__dict__,
                    "batch_size": self.current_batch_size,
                    "result": result.__dict__
                }
            )
            
            # Apply recovery action
            if recovery_action.strategy == RecoveryStrategy.ABORT_SYNC:
                result.status = SyncStatus.FAILED
                result.errors.append({"error": str(e), "action": "aborted"})
            else:
                result.status = SyncStatus.PARTIAL
                result.errors.append({
                    "error": str(e),
                    "recovery_action": recovery_action.strategy.value
                })
        
        finally:
            result.complete()
        
        return result
    
    async def _sync_with_recovery(self, state: SyncState, result: SyncResult) -> SyncResult:
        """Perform sync with item-level error recovery."""
        last_sync = state.last_successful_sync_at if not state.is_initial_sync else None
        cursor = state.last_cursor
        page = state.last_page
        has_more = True
        
        while has_more:
            # Rate limiting
            if self._rate_limiter:
                await self._rate_limiter.acquire()
            
            # Fetch batch with retry
            try:
                fetch_result = await self._fetch_with_retry(
                    last_sync, cursor, page, result
                )
                if not fetch_result:
                    break
                
                raw_data, next_cursor, has_more = fetch_result
                result.items_fetched += len(raw_data)
                
            except Exception as e:
                logger.error(f"Failed to fetch batch after retries: {e}")
                break
            
            # Process batch with item-level error handling
            if raw_data:
                await self._process_batch_resilient(raw_data, result)
            
            # Update pagination
            cursor = next_cursor
            if page is not None:
                page += 1
            
            # Update state for resume capability
            state.last_cursor = cursor
            state.last_page = page
            
            # Check if we should continue based on errors
            if len(result.errors) >= self.config.error_threshold_for_pause:
                logger.warning(
                    f"Too many errors ({len(result.errors)}), pausing sync"
                )
                await self._handle_pause_sync(None, RecoveryAction(
                    RecoveryStrategy.PAUSE_SYNC,
                    delay_seconds=self.config.pause_duration_seconds
                ))
                break
            
            # Respect adaptive batch size
            if result.items_fetched >= self.current_batch_size:
                break
        
        # Update sync state
        state.last_sync_at = datetime.utcnow()
        if len(result.errors) == 0:
            state.last_successful_sync_at = state.last_sync_at
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1
        
        state.total_synced += result.items_created + result.items_updated
        
        # Set final status
        if len(result.errors) == 0:
            result.status = SyncStatus.COMPLETED
        elif result.items_created + result.items_updated > 0:
            result.status = SyncStatus.PARTIAL
        else:
            result.status = SyncStatus.FAILED
        
        return result
    
    async def _fetch_with_retry(
        self,
        last_sync: Optional[datetime],
        cursor: Optional[str],
        page: Optional[int],
        result: SyncResult
    ) -> Optional[Tuple[List[Dict[str, Any]], Optional[str], bool]]:
        """Fetch data with retry logic."""
        retry_handler = RetryHandler(
            lambda: self.fetch_data(last_sync, cursor, page)
        )
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(
                    self.fetch_data(last_sync, cursor, page),
                    timeout=self.config.timeout_seconds
                )
            except asyncio.TimeoutError:
                error_context = ErrorContext(
                    error_type=ErrorType.TIMEOUT_ERROR,
                    error_message="Fetch timeout",
                    retry_count=attempt
                )
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    result.errors.append({
                        "error": "Fetch timeout after retries",
                        "cursor": cursor,
                        "page": page
                    })
                    return None
            
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
        
        return None
    
    async def _process_batch_resilient(
        self,
        raw_data: List[Dict[str, Any]],
        result: SyncResult
    ) -> None:
        """Process batch with item-level error handling."""
        try:
            # Transform data with error handling
            items = []
            transform_errors = []
            
            for idx, raw_item in enumerate(raw_data):
                try:
                    transformed = await self.transform_data([raw_item])
                    if transformed:
                        items.extend(transformed)
                except Exception as e:
                    transform_errors.append({
                        "index": idx,
                        "error": str(e),
                        "raw_data": raw_item
                    })
                    result.errors.append({
                        "error": f"Transform failed: {e}",
                        "item_index": idx
                    })
            
            if not items:
                return
            
            # Get external IDs
            external_ids = [self._get_external_id(item) for item in items]
            
            # Get existing items
            existing_items = await self.get_existing_items(external_ids)
            
            # Process each item with error recovery
            for item in items:
                await self._process_item_resilient(
                    item, existing_items, result
                )
            
            # Commit batch
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch processing failed: {e}")
            result.errors.append({
                "error": f"Batch processing failed: {e}",
                "batch_size": len(raw_data)
            })
    
    async def _process_item_resilient(
        self,
        item: T,
        existing_items: Dict[str, T],
        result: SyncResult
    ) -> None:
        """Process single item with error recovery."""
        external_id = self._get_external_id(item)
        
        try:
            existing = existing_items.get(external_id)
            
            if existing:
                # Check for conflicts
                needs_update, conflict = await self._check_conflict(existing, item)
                
                if conflict:
                    result.conflicts.append(conflict)
                    # Use conflict resolver if available
                    resolved, should_update = await self.resolve_conflict(
                        existing, item, self.config.conflict_resolution
                    )
                    if should_update:
                        await self.update_item(existing, resolved)
                        result.items_updated += 1
                    else:
                        result.items_skipped += 1
                elif needs_update:
                    await self.update_item(existing, item)
                    result.items_updated += 1
                else:
                    result.items_skipped += 1
            else:
                # Create new item
                await self.create_item(item)
                result.items_created += 1
                
        except Exception as e:
            # Log item-level error
            error_context = {
                "error": str(e),
                "item_id": external_id,
                "operation": "create" if external_id not in existing_items else "update"
            }
            result.errors.append(error_context)
            
            # Determine if we should skip or retry
            recovery_action = await self.error_recovery.handle_sync_error(
                exception=e,
                service_id=self.service_id,
                context=error_context
            )
            
            if recovery_action.strategy != RecoveryStrategy.SKIP_ITEM:
                # Re-raise to trigger batch-level handling
                raise
    
    def _handle_successful_sync(self):
        """Handle successful sync for adaptive behavior."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Increase batch size if enabled
        if (self.config.enable_adaptive_batch_size and
            self.consecutive_successes >= 3 and
            self.current_batch_size < self.config.max_batch_size):
            
            new_size = int(
                min(
                    self.current_batch_size * self.config.batch_size_increase_factor,
                    self.config.max_batch_size
                )
            )
            
            if new_size != self.current_batch_size:
                logger.info(
                    f"Increasing batch size from {self.current_batch_size} to {new_size}"
                )
                self.current_batch_size = new_size
    
    def _handle_failed_sync(self):
        """Handle failed sync for adaptive behavior."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
    
    async def _handle_auth_refresh(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Handle authentication refresh."""
        # This should be implemented by the specific sync service
        logger.info("Authentication refresh requested")
        return False
    
    async def _handle_batch_size_reduction(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Handle batch size reduction."""
        if self.config.enable_adaptive_batch_size:
            new_size = recovery_action.new_batch_size or int(
                max(
                    self.current_batch_size * self.config.batch_size_reduction_factor,
                    self.config.min_batch_size
                )
            )
            
            if new_size != self.current_batch_size:
                logger.info(
                    f"Reducing batch size from {self.current_batch_size} to {new_size}"
                )
                self.current_batch_size = new_size
                return True
        
        return False
    
    async def _handle_pause_sync(
        self,
        error_context: Optional[ErrorContext],
        recovery_action: RecoveryAction
    ) -> bool:
        """Handle sync pause."""
        pause_duration = recovery_action.delay_seconds or self.config.pause_duration_seconds
        self.is_paused = True
        self.pause_until = datetime.utcnow() + timedelta(seconds=pause_duration)
        
        logger.warning(
            f"Pausing sync for {self.service_id} until {self.pause_until}"
        )
        
        return True