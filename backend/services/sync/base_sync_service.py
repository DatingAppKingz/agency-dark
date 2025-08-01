"""Base sync service for external API synchronization."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from core.errors import ValidationError as AppValidationError

logger = get_logger(__name__)

T = TypeVar('T')  # Generic type for synced entities


class SyncStatus(str, Enum):
    """Sync operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    REMOTE_WINS = "remote_wins"  # Always use remote data
    LOCAL_WINS = "local_wins"    # Always use local data
    NEWEST_WINS = "newest_wins"  # Use most recently updated
    MANUAL = "manual"            # Require manual resolution
    MERGE = "merge"             # Attempt to merge changes


@dataclass
class SyncResult:
    """Result of a sync operation."""
    status: SyncStatus
    items_fetched: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    items_skipped: int = 0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def complete(self):
        """Mark sync as completed."""
        self.completed_at = datetime.utcnow()
        if self.errors:
            self.status = SyncStatus.PARTIAL if self.items_created or self.items_updated else SyncStatus.FAILED
        else:
            self.status = SyncStatus.COMPLETED
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get sync duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "items_fetched": self.items_fetched,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "items_deleted": self.items_deleted,
            "items_skipped": self.items_skipped,
            "conflicts_count": len(self.conflicts),
            "errors_count": len(self.errors),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class SyncConfig:
    """Configuration for sync operations."""
    batch_size: int = 100
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 300
    conflict_resolution: ConflictResolution = ConflictResolution.NEWEST_WINS
    enable_soft_delete: bool = True
    sync_interval_minutes: int = 30
    rate_limit_calls: Optional[int] = None  # Calls per minute
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyncState:
    """State tracking for sync operations."""
    last_sync_at: Optional[datetime] = None
    last_successful_sync_at: Optional[datetime] = None
    last_cursor: Optional[str] = None
    last_page: Optional[int] = None
    total_synced: int = 0
    consecutive_failures: int = 0
    is_initial_sync: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseSyncService(ABC, Generic[T]):
    """Base class for external API sync services."""
    
    def __init__(self, db: AsyncSession, config: Optional[SyncConfig] = None):
        self.db = db
        self.config = config or SyncConfig()
        self._rate_limiter = None
        if self.config.rate_limit_calls:
            from core.rate_limiting import RateLimiter
            self._rate_limiter = RateLimiter(
                max_calls=self.config.rate_limit_calls,
                time_window=60  # Per minute
            )
    
    @abstractmethod
    async def fetch_data(
        self,
        last_sync: Optional[datetime] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """
        Fetch data from external API.
        
        Args:
            last_sync: Last successful sync timestamp for delta sync
            cursor: Pagination cursor
            page: Page number for pagination
            
        Returns:
            Tuple of (data, next_cursor, has_more)
        """
        pass
    
    @abstractmethod
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[T]:
        """
        Transform raw API data to internal format.
        
        Args:
            raw_data: Raw data from API
            
        Returns:
            List of transformed entities
        """
        pass
    
    @abstractmethod
    async def get_existing_items(self, external_ids: List[str]) -> Dict[str, T]:
        """
        Get existing items by external IDs.
        
        Args:
            external_ids: List of external IDs
            
        Returns:
            Dict mapping external_id to existing item
        """
        pass
    
    @abstractmethod
    async def create_item(self, data: T) -> T:
        """Create a new item in the database."""
        pass
    
    @abstractmethod
    async def update_item(self, existing: T, new_data: T) -> T:
        """Update an existing item with new data."""
        pass
    
    @abstractmethod
    async def delete_item(self, item: T) -> None:
        """Delete or soft-delete an item."""
        pass
    
    @abstractmethod
    async def resolve_conflict(
        self,
        local_item: T,
        remote_item: T,
        strategy: ConflictResolution
    ) -> Tuple[T, bool]:
        """
        Resolve conflict between local and remote data.
        
        Args:
            local_item: Local database item
            remote_item: Remote API item
            strategy: Conflict resolution strategy
            
        Returns:
            Tuple of (resolved_item, should_update)
        """
        pass
    
    async def sync(self, state: SyncState) -> SyncResult:
        """
        Perform sync operation.
        
        Args:
            state: Current sync state
            
        Returns:
            Sync result
        """
        result = SyncResult(status=SyncStatus.IN_PROGRESS)
        
        try:
            # Determine sync parameters
            last_sync = state.last_successful_sync_at if not state.is_initial_sync else None
            cursor = state.last_cursor
            page = state.last_page
            
            has_more = True
            
            while has_more:
                # Rate limiting
                if self._rate_limiter:
                    await self._rate_limiter.acquire()
                
                # Fetch batch of data
                try:
                    raw_data, next_cursor, has_more = await asyncio.wait_for(
                        self.fetch_data(last_sync, cursor, page),
                        timeout=self.config.timeout_seconds
                    )
                    result.items_fetched += len(raw_data)
                except asyncio.TimeoutError:
                    error = {"error": "Fetch timeout", "cursor": cursor, "page": page}
                    result.errors.append(error)
                    logger.error("Sync fetch timeout", extra=error)
                    break
                except Exception as e:
                    error = {"error": str(e), "cursor": cursor, "page": page}
                    result.errors.append(error)
                    logger.error("Sync fetch error", extra=error, exc_info=True)
                    break
                
                # Process batch
                if raw_data:
                    await self._process_batch(raw_data, result)
                
                # Update pagination
                cursor = next_cursor
                if page is not None:
                    page += 1
                
                # Update state for resume capability
                state.last_cursor = cursor
                state.last_page = page
                
                # Respect batch size limit
                if result.items_fetched >= self.config.batch_size:
                    break
            
            # Update sync state
            state.last_sync_at = datetime.utcnow()
            if not result.errors:
                state.last_successful_sync_at = state.last_sync_at
                state.consecutive_failures = 0
                state.is_initial_sync = False
            else:
                state.consecutive_failures += 1
            
            state.total_synced += result.items_created + result.items_updated
            
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            result.errors.append({"error": str(e), "type": "sync_error"})
            state.consecutive_failures += 1
        
        finally:
            result.complete()
            
        return result
    
    async def _process_batch(self, raw_data: List[Dict[str, Any]], result: SyncResult) -> None:
        """Process a batch of fetched data."""
        try:
            # Transform data
            items = await self.transform_data(raw_data)
            
            # Get external IDs
            external_ids = [self._get_external_id(item) for item in items]
            
            # Get existing items
            existing_items = await self.get_existing_items(external_ids)
            
            # Process each item
            for item in items:
                try:
                    external_id = self._get_external_id(item)
                    existing = existing_items.get(external_id)
                    
                    if existing:
                        # Check for conflicts
                        needs_update, conflict = await self._check_conflict(existing, item)
                        
                        if conflict:
                            result.conflicts.append(conflict)
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
                    error = {
                        "error": str(e),
                        "item": self._get_external_id(item),
                        "type": "item_error"
                    }
                    result.errors.append(error)
                    logger.error("Item processing error", extra=error, exc_info=True)
            
            # Commit batch
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            raise
    
    @abstractmethod
    def _get_external_id(self, item: T) -> str:
        """Extract external ID from item."""
        pass
    
    @abstractmethod
    async def _check_conflict(self, local: T, remote: T) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if there's a conflict between local and remote data.
        
        Returns:
            Tuple of (needs_update, conflict_info)
        """
        pass
    
    async def sync_with_retry(self, state: SyncState) -> SyncResult:
        """Sync with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = await self.sync(state)
                
                # If successful or partial success, return
                if result.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]:
                    return result
                
                # If failed, retry
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay_seconds * (attempt + 1)
                    logger.warning(
                        f"Sync failed, retrying in {delay}s",
                        extra={"attempt": attempt + 1, "errors": len(result.errors)}
                    )
                    await asyncio.sleep(delay)
                
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay_seconds * (attempt + 1)
                    logger.warning(f"Sync error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
        
        # All retries failed
        result = SyncResult(status=SyncStatus.FAILED)
        result.errors.append({
            "error": str(last_error) if last_error else "Max retries exceeded",
            "type": "retry_exhausted"
        })
        result.complete()
        return result