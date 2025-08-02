"""Delta sync implementation for efficient data synchronization."""

from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib
import json
from sqlalchemy import Column, Integer, String, DateTime, JSON, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.sync.base_sync_service import BaseSyncService, SyncState, SyncResult, SyncConfig
from core.logger import get_logger
from models.base import Base

logger = get_logger(__name__)


@dataclass
class DeltaSyncState(SyncState):
    """Extended sync state for delta sync operations."""
    deleted_ids: Set[str] = field(default_factory=set)
    checksum_cache: Dict[str, str] = field(default_factory=dict)
    last_full_sync_at: Optional[datetime] = None
    full_sync_interval_days: int = 7


class DeltaSyncMixin:
    """Mixin for delta sync capabilities."""
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for data to detect changes."""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(sorted_data.encode()).hexdigest()
    
    async def get_deleted_items(
        self,
        last_sync: datetime,
        current_ids: Set[str],
        stored_ids: Set[str]
    ) -> Set[str]:
        """
        Identify deleted items by comparing current and stored IDs.
        
        Args:
            last_sync: Last sync timestamp
            current_ids: IDs from current API fetch
            stored_ids: IDs from local database
            
        Returns:
            Set of deleted item IDs
        """
        # Items that exist locally but not in remote
        return stored_ids - current_ids
    
    async def get_modified_items(
        self,
        items: List[Dict[str, Any]],
        checksum_cache: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Filter items that have been modified based on checksums.
        
        Args:
            items: All items from API
            checksum_cache: Previous checksums
            
        Returns:
            List of modified items
        """
        modified = []
        new_checksums = {}
        
        for item in items:
            item_id = self._extract_id(item)
            current_checksum = self.calculate_checksum(item)
            new_checksums[item_id] = current_checksum
            
            # Check if item is new or modified
            if item_id not in checksum_cache or checksum_cache[item_id] != current_checksum:
                modified.append(item)
        
        return modified, new_checksums
    
    def _extract_id(self, item: Dict[str, Any]) -> str:
        """Extract ID from item data."""
        # Try common ID field names
        for field in ['id', 'external_id', 'uuid', '_id']:
            if field in item:
                return str(item[field])
        
        # Fallback to first unique field
        raise ValueError(f"Could not extract ID from item: {item}")
    
    def should_perform_full_sync(self, state: DeltaSyncState) -> bool:
        """Determine if a full sync should be performed."""
        if state.is_initial_sync:
            return True
        
        if not state.last_full_sync_at:
            return True
        
        # Perform full sync periodically
        days_since_full = (datetime.utcnow() - state.last_full_sync_at).days
        return days_since_full >= state.full_sync_interval_days


class DeltaSyncService(BaseSyncService, DeltaSyncMixin):
    """Base service with delta sync capabilities."""
    
    async def sync_delta(self, state: DeltaSyncState) -> SyncResult:
        """
        Perform delta sync operation.
        
        Args:
            state: Delta sync state
            
        Returns:
            Sync result
        """
        result = SyncResult(status="in_progress")
        
        try:
            # Determine if full sync is needed
            if self.should_perform_full_sync(state):
                logger.info("Performing full sync")
                result = await self.sync(state)
                state.last_full_sync_at = datetime.utcnow()
                state.is_initial_sync = False
                return result
            
            # Delta sync logic
            logger.info(f"Performing delta sync since {state.last_successful_sync_at}")
            
            # Fetch changed data since last sync
            has_more = True
            cursor = state.last_cursor
            all_current_ids = set()
            all_items = []
            
            while has_more:
                # Rate limiting
                if self._rate_limiter:
                    await self._rate_limiter.acquire()
                
                # Fetch data with last sync timestamp
                raw_data, next_cursor, has_more = await self.fetch_data(
                    last_sync=state.last_successful_sync_at,
                    cursor=cursor
                )
                
                result.items_fetched += len(raw_data)
                all_items.extend(raw_data)
                
                # Collect current IDs
                for item in raw_data:
                    all_current_ids.add(self._extract_id(item))
                
                cursor = next_cursor
                
                # Respect batch limits
                if len(all_items) >= self.config.batch_size:
                    break
            
            # Get stored IDs for deletion detection
            stored_ids = await self._get_stored_ids()
            
            # Identify deletions (only if we fetched all data)
            if not has_more:
                deleted_ids = await self.get_deleted_items(
                    state.last_successful_sync_at,
                    all_current_ids,
                    stored_ids
                )
                
                # Process deletions
                for deleted_id in deleted_ids:
                    try:
                        await self._process_deletion(deleted_id)
                        result.items_deleted += 1
                        state.deleted_ids.add(deleted_id)
                    except Exception as e:
                        logger.error(f"Failed to delete item {deleted_id}: {e}")
                        result.errors.append({
                            "error": str(e),
                            "item_id": deleted_id,
                            "type": "deletion_error"
                        })
            
            # Filter to only modified items using checksums
            modified_items, new_checksums = await self.get_modified_items(
                all_items,
                state.checksum_cache
            )
            
            logger.info(f"Found {len(modified_items)} modified items out of {len(all_items)}")
            
            # Process modified items
            if modified_items:
                await self._process_batch(modified_items, result)
            
            # Update checksum cache
            state.checksum_cache.update(new_checksums)
            
            # Update sync state
            state.last_sync_at = datetime.utcnow()
            if not result.errors:
                state.last_successful_sync_at = state.last_sync_at
                state.consecutive_failures = 0
            else:
                state.consecutive_failures += 1
            
            state.last_cursor = cursor
            state.total_synced += result.items_created + result.items_updated
            
        except Exception as e:
            logger.error(f"Delta sync failed: {e}", exc_info=True)
            result.errors.append({"error": str(e), "type": "delta_sync_error"})
            state.consecutive_failures += 1
        
        finally:
            result.complete()
        
        return result
    
    async def _get_stored_ids(self) -> Set[str]:
        """Get all stored external IDs from database."""
        # This method should be implemented by subclasses
        # Example implementation:
        raise NotImplementedError("Subclasses must implement _get_stored_ids")
    
    async def _process_deletion(self, external_id: str) -> None:
        """Process deletion of an item."""
        # This method should be implemented by subclasses
        # Example implementation:
        raise NotImplementedError("Subclasses must implement _process_deletion")


class DeltaSyncTracker(Base):
    """Database model for tracking delta sync state."""
    __tablename__ = "delta_sync_trackers"
    
    id = Column(Integer, primary_key=True)
    service_name = Column(String(100), unique=True, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    last_full_sync_at = Column(DateTime, nullable=True)
    last_cursor = Column(String(500), nullable=True)
    checksum_cache = Column(JSON, default=dict, nullable=False)
    deleted_ids = Column(JSON, default=list, nullable=False)
    extra_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DeltaSyncStateManager:
    """Manager for persisting delta sync state."""
    
    def __init__(self, db: AsyncSession, service_name: str):
        self.db = db
        self.service_name = service_name
    
    async def load_state(self) -> DeltaSyncState:
        """Load sync state from database."""
        result = await self.db.execute(
            select(DeltaSyncTracker).where(
                DeltaSyncTracker.service_name == self.service_name
            )
        )
        tracker = result.scalar_one_or_none()
        
        if tracker:
            return DeltaSyncState(
                last_sync_at=tracker.last_sync_at,
                last_successful_sync_at=tracker.last_successful_sync_at,
                last_full_sync_at=tracker.last_full_sync_at,
                last_cursor=tracker.last_cursor,
                checksum_cache=tracker.checksum_cache or {},
                deleted_ids=set(tracker.deleted_ids or []),
                metadata=tracker.metadata or {},
                is_initial_sync=False
            )
        
        return DeltaSyncState()
    
    async def save_state(self, state: DeltaSyncState) -> None:
        """Save sync state to database."""
        result = await self.db.execute(
            select(DeltaSyncTracker).where(
                DeltaSyncTracker.service_name == self.service_name
            )
        )
        tracker = result.scalar_one_or_none()
        
        if tracker:
            # Update existing
            await self.db.execute(
                update(DeltaSyncTracker).where(
                    DeltaSyncTracker.service_name == self.service_name
                ).values(
                    last_sync_at=state.last_sync_at,
                    last_successful_sync_at=state.last_successful_sync_at,
                    last_full_sync_at=state.last_full_sync_at,
                    last_cursor=state.last_cursor,
                    checksum_cache=state.checksum_cache,
                    deleted_ids=list(state.deleted_ids),
                    metadata=state.metadata,
                    updated_at=datetime.utcnow()
                )
            )
        else:
            # Create new
            tracker = DeltaSyncTracker(
                service_name=self.service_name,
                last_sync_at=state.last_sync_at,
                last_successful_sync_at=state.last_successful_sync_at,
                last_full_sync_at=state.last_full_sync_at,
                last_cursor=state.last_cursor,
                checksum_cache=state.checksum_cache,
                deleted_ids=list(state.deleted_ids),
                metadata=state.metadata
            )
            self.db.add(tracker)
        
        await self.db.commit()
    
    async def reset_state(self) -> None:
        """Reset sync state (triggers full sync)."""
        await self.db.execute(
            delete(DeltaSyncTracker).where(
                DeltaSyncTracker.service_name == self.service_name
            )
        )
        await self.db.commit()


# Example implementation for a specific service
class ExampleDeltaSyncService(DeltaSyncService):
    """Example implementation of delta sync service."""
    
    async def fetch_data(
        self,
        last_sync: Optional[datetime] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Fetch data from external API with delta support."""
        # Implementation would call external API with last_sync parameter
        # to get only changed records
        pass
    
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Any]:
        """Transform API data to internal format."""
        # Transform raw API data to internal models
        pass
    
    async def get_existing_items(self, external_ids: List[str]) -> Dict[str, Any]:
        """Get existing items from database."""
        # Query database for existing items by external IDs
        pass
    
    async def create_item(self, data: Any) -> Any:
        """Create new item in database."""
        # Create new database record
        pass
    
    async def update_item(self, existing: Any, new_data: Any) -> Any:
        """Update existing item."""
        # Update existing database record
        pass
    
    async def delete_item(self, item: Any) -> None:
        """Delete item from database."""
        # Delete or soft-delete database record
        pass
    
    async def resolve_conflict(
        self,
        local_item: Any,
        remote_item: Any,
        strategy: str
    ) -> Tuple[Any, bool]:
        """Resolve data conflicts."""
        # Implement conflict resolution logic
        pass
    
    def _get_external_id(self, item: Any) -> str:
        """Get external ID from item."""
        # Extract external ID from item
        pass
    
    async def _check_conflict(self, local: Any, remote: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check for conflicts between local and remote data."""
        # Compare local and remote data for conflicts
        pass
    
    async def _get_stored_ids(self) -> Set[str]:
        """Get all stored external IDs."""
        # Query database for all external IDs
        pass
    
    async def _process_deletion(self, external_id: str) -> None:
        """Process deletion of an item."""
        # Delete or mark as deleted in database
        pass