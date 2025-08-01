"""Example implementation of resilient sync for Inflow platform."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import aiohttp

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.sync.resilient_sync_service import ResilientSyncService, ResilientSyncConfig
from services.sync.base_sync_service import ConflictResolution
from models.model import Model
from models.transaction import Transaction
from core.logger import get_logger

logger = get_logger(__name__)


class InflowResilientSyncService(ResilientSyncService[Model]):
    """Resilient sync service for Inflow platform."""
    
    def __init__(self, db: AsyncSession, api_key: str, agency_id: str):
        config = ResilientSyncConfig(
            batch_size=50,
            max_retries=5,
            retry_delay_seconds=30,
            timeout_seconds=120,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            enable_soft_delete=True,
            sync_interval_minutes=30,
            rate_limit_calls=10,  # 10 calls per minute
            enable_circuit_breaker=True,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=300,
            enable_adaptive_batch_size=True,
            min_batch_size=10,
            max_batch_size=200,
            batch_size_reduction_factor=0.5,
            batch_size_increase_factor=1.5,
            error_threshold_for_pause=20,
            pause_duration_seconds=900  # 15 minutes
        )
        
        super().__init__(
            db=db,
            service_id=f"inflow_sync_{agency_id}",
            config=config
        )
        
        self.api_key = api_key
        self.agency_id = agency_id
        self.base_url = "https://api.inflow.com/v1"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
    
    async def fetch_data(
        self,
        last_sync: Optional[datetime] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Fetch models data from Inflow API."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        params = {
            "limit": self.current_batch_size,
            "page": page or 1
        }
        
        if last_sync:
            params["updated_since"] = last_sync.isoformat()
        
        if cursor:
            params["cursor"] = cursor
        
        try:
            async with self.session.get(
                f"{self.base_url}/models",
                params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                models = data.get("models", [])
                next_cursor = data.get("next_cursor")
                has_more = data.get("has_more", False)
                
                return models, next_cursor, has_more
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:  # Rate limit
                retry_after = int(e.headers.get("Retry-After", "60"))
                logger.warning(f"Rate limited, retry after {retry_after}s")
                raise Exception(f"Rate limit exceeded. Retry after {retry_after}s")
            elif e.status == 401:
                raise Exception("Authentication failed. Check API key.")
            else:
                raise
    
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Model]:
        """Transform Inflow API data to Model entities."""
        models = []
        
        for item in raw_data:
            try:
                model = Model(
                    username=item["username"],
                    display_name=item.get("display_name", item["username"]),
                    email=item.get("email"),
                    bio=item.get("bio", ""),
                    profile_pic=item.get("profile_picture_url"),
                    is_active=item.get("is_active", True),
                    is_verified=item.get("is_verified", False),
                    agency_id=self.agency_id,
                    inflow_id=item["id"],
                    stage_name=item.get("stage_name"),
                    subscriber_count=item.get("subscriber_count", 0),
                    total_earnings=item.get("total_earnings", 0.0),
                    commission_rate=item.get("commission_rate", 20.0),
                    tags=item.get("tags", []),
                    metadata={
                        "inflow_data": {
                            "joined_date": item.get("joined_date"),
                            "last_active": item.get("last_active"),
                            "content_count": item.get("content_count", 0)
                        }
                    }
                )
                models.append(model)
            except Exception as e:
                logger.error(f"Failed to transform model {item.get('id')}: {e}")
                # Continue with other items
        
        return models
    
    async def get_existing_items(self, external_ids: List[str]) -> Dict[str, Model]:
        """Get existing models by Inflow IDs."""
        result = await self.db.execute(
            select(Model).where(
                Model.inflow_id.in_(external_ids),
                Model.agency_id == self.agency_id
            )
        )
        models = result.scalars().all()
        return {m.inflow_id: m for m in models}
    
    async def create_item(self, data: Model) -> Model:
        """Create new model."""
        self.db.add(data)
        await self.db.flush()
        return data
    
    async def update_item(self, existing: Model, new_data: Model) -> Model:
        """Update existing model."""
        # Update fields
        existing.display_name = new_data.display_name
        existing.bio = new_data.bio
        existing.profile_pic = new_data.profile_pic
        existing.is_active = new_data.is_active
        existing.is_verified = new_data.is_verified
        existing.subscriber_count = new_data.subscriber_count
        existing.total_earnings = new_data.total_earnings
        existing.commission_rate = new_data.commission_rate
        existing.tags = new_data.tags
        existing.metadata.update(new_data.metadata)
        existing.updated_at = datetime.utcnow()
        
        await self.db.flush()
        return existing
    
    async def delete_item(self, item: Model) -> None:
        """Soft delete model."""
        item.is_active = False
        item.deleted_at = datetime.utcnow()
        await self.db.flush()
    
    async def resolve_conflict(
        self,
        local_item: Model,
        remote_item: Model,
        strategy: ConflictResolution
    ) -> Tuple[Model, bool]:
        """Resolve conflicts between local and remote model data."""
        if strategy == ConflictResolution.NEWEST_WINS:
            # Compare update timestamps if available
            if hasattr(remote_item, 'updated_at') and local_item.updated_at:
                if remote_item.updated_at > local_item.updated_at:
                    return remote_item, True
                else:
                    return local_item, False
            # Default to remote
            return remote_item, True
        
        elif strategy == ConflictResolution.MANUAL:
            # Log for manual review
            logger.warning(
                f"Manual conflict resolution required for model {local_item.username}"
            )
            return local_item, False
        
        # Default to remote
        return remote_item, True
    
    def _get_external_id(self, item: Model) -> str:
        """Get Inflow ID from model."""
        return item.inflow_id
    
    async def _check_conflict(
        self,
        local: Model,
        remote: Model
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if there's a conflict between local and remote data."""
        # Simple check - if key fields differ
        if (local.subscriber_count != remote.subscriber_count or
            local.total_earnings != remote.total_earnings or
            local.commission_rate != remote.commission_rate):
            
            conflict = {
                "type": "data_mismatch",
                "fields": []
            }
            
            if local.subscriber_count != remote.subscriber_count:
                conflict["fields"].append({
                    "field": "subscriber_count",
                    "local": local.subscriber_count,
                    "remote": remote.subscriber_count
                })
            
            if local.total_earnings != remote.total_earnings:
                conflict["fields"].append({
                    "field": "total_earnings",
                    "local": local.total_earnings,
                    "remote": remote.total_earnings
                })
            
            if local.commission_rate != remote.commission_rate:
                conflict["fields"].append({
                    "field": "commission_rate",
                    "local": local.commission_rate,
                    "remote": remote.commission_rate
                })
            
            return True, conflict
        
        # Check if update is needed
        needs_update = (
            local.display_name != remote.display_name or
            local.bio != remote.bio or
            local.profile_pic != remote.profile_pic or
            local.is_active != remote.is_active or
            local.is_verified != remote.is_verified
        )
        
        return needs_update, None
    
    async def _handle_auth_refresh(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Handle authentication refresh for Inflow."""
        # In a real implementation, this would refresh the OAuth token
        logger.info("Attempting to refresh Inflow authentication")
        
        # For now, just return False to indicate manual intervention needed
        return False


# Example usage
async def sync_inflow_models(db: AsyncSession, api_key: str, agency_id: str):
    """Example function to sync Inflow models."""
    from services.sync.delta_sync import DeltaSyncStateManager
    
    # Load sync state
    state_manager = DeltaSyncStateManager(db, f"inflow_models_{agency_id}")
    sync_state = await state_manager.load_state()
    
    # Perform sync
    async with InflowResilientSyncService(db, api_key, agency_id) as sync_service:
        result = await sync_service.sync(sync_state)
        
        # Save state
        await state_manager.save_state(sync_state)
        
        # Log results
        logger.info(
            f"Inflow sync completed: {result.items_created} created, "
            f"{result.items_updated} updated, {len(result.errors)} errors"
        )
        
        return result