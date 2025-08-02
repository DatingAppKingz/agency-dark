"""OnlyFans sync service implementation."""

from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from services.sync.delta_sync import DeltaSyncService, DeltaSyncState, DeltaSyncStateManager
from services.sync.base_sync_service import SyncResult, SyncConfig, ConflictResolution
from core.domain.models import ModelProfile, Fan as FanProfile
from models.financial import Transaction, TransactionType, TransactionStatus
from models.chat import Message
from core.logger import get_logger
from core.errors import ExternalServiceError

logger = get_logger(__name__)


class OnlyFansSyncService(DeltaSyncService):
    """Sync service for OnlyFans data."""
    
    def __init__(
        self,
        db: AsyncSession,
        api_key: str,
        api_secret: str,
        config: Optional[SyncConfig] = None
    ):
        # Default config for OnlyFans
        if not config:
            config = SyncConfig(
                batch_size=100,
                max_retries=3,
                retry_delay_seconds=60,
                timeout_seconds=300,
                conflict_resolution=ConflictResolution.NEWEST_WINS,
                sync_interval_minutes=15,
                rate_limit_calls=60  # OnlyFans rate limit
            )
        
        super().__init__(db, config)
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://onlyfans.com/api2/v2"
        self.state_manager = DeltaSyncStateManager(db, "onlyfans_sync")
    
    async def sync_all(self) -> Dict[str, SyncResult]:
        """Sync all OnlyFans data types."""
        results = {}
        
        # Load state
        state = await self.state_manager.load_state()
        
        # Sync different data types
        for data_type in ["subscribers", "transactions", "messages"]:
            logger.info(f"Syncing OnlyFans {data_type}")
            
            # Set sync type in metadata
            state.metadata["sync_type"] = data_type
            
            # Perform sync
            result = await self.sync_delta(state)
            results[data_type] = result
            
            # Save state after each sync
            await self.state_manager.save_state(state)
        
        return results
    
    async def fetch_data(
        self,
        last_sync: Optional[datetime] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Fetch data from OnlyFans API."""
        sync_type = self.state_metadata.get("sync_type", "subscribers")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json"
        }
        
        # Build request based on sync type
        if sync_type == "subscribers":
            endpoint = "/subscriptions/subscribers"
            params = {
                "limit": self.config.batch_size,
                "offset": cursor or "0"
            }
            if last_sync:
                params["updated_after"] = last_sync.isoformat()
        
        elif sync_type == "transactions":
            endpoint = "/earnings/transactions"
            params = {
                "limit": self.config.batch_size,
                "offset": cursor or "0"
            }
            if last_sync:
                params["after"] = last_sync.isoformat()
        
        elif sync_type == "messages":
            endpoint = "/chats/messages"
            params = {
                "limit": self.config.batch_size,
                "offset": cursor or "0"
            }
            if last_sync:
                params["updated_after"] = last_sync.isoformat()
        
        else:
            raise ValueError(f"Unknown sync type: {sync_type}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status != 200:
                        raise ExternalServiceError(
                            f"OnlyFans API error: {response.status}",
                            code="OF_API_ERROR"
                        )
                    
                    data = await response.json()
                    
                    # Extract items and pagination
                    items = data.get("list", [])
                    has_more = data.get("hasMore", False)
                    next_offset = str(int(cursor or "0") + len(items))
                    
                    return items, next_offset if has_more else None, has_more
        
        except aiohttp.ClientError as e:
            raise ExternalServiceError(f"OnlyFans connection error: {e}", code="OF_CONNECTION_ERROR")
    
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Any]:
        """Transform OnlyFans data to internal models."""
        sync_type = self.state_metadata.get("sync_type", "subscribers")
        transformed = []
        
        for item in raw_data:
            try:
                if sync_type == "subscribers":
                    transformed.append(self._transform_subscriber(item))
                elif sync_type == "transactions":
                    transformed.append(await self._transform_transaction(item))
                elif sync_type == "messages":
                    transformed.append(await self._transform_message(item))
            except Exception as e:
                logger.error(f"Failed to transform {sync_type} item: {e}", extra={"item": item})
        
        return transformed
    
    def _transform_subscriber(self, data: Dict[str, Any]) -> FanProfile:
        """Transform subscriber data to FanProfile."""
        return FanProfile(
            external_id=str(data["id"]),
            platform="onlyfans",
            username=data.get("username", ""),
            display_name=data.get("name", ""),
            email=data.get("email"),
            avatar_url=data.get("avatar"),
            is_subscriber=True,
            subscription_price=Decimal(str(data.get("subscribePrice", "0"))),
            subscription_date=datetime.fromisoformat(data["subscribedOn"]) if data.get("subscribedOn") else None,
            total_spent=Decimal(str(data.get("totalSpent", "0"))),
            metadata={
                "location": data.get("location"),
                "bio": data.get("bio"),
                "verified": data.get("isVerified", False)
            }
        )
    
    async def _transform_transaction(self, data: Dict[str, Any]) -> Transaction:
        """Transform transaction data."""
        # Map OnlyFans transaction types
        type_mapping = {
            "subscription": TransactionType.SUBSCRIPTION,
            "tip": TransactionType.TIP,
            "post": TransactionType.PPV_UNLOCK,
            "message": TransactionType.MESSAGE_TIP,
            "stream": TransactionType.TIP
        }
        
        transaction_type = type_mapping.get(
            data.get("type", "").lower(),
            TransactionType.OTHER
        )
        
        # Get fan profile
        fan_external_id = str(data.get("fromUser", {}).get("id", ""))
        fan_profile = await self._get_or_create_fan_profile(fan_external_id, data.get("fromUser", {}))
        
        return Transaction(
            external_id=str(data["id"]),
            platform="onlyfans",
            type=transaction_type,
            amount=Decimal(str(data.get("amount", "0"))),
            currency=data.get("currency", "USD"),
            status=TransactionStatus.COMPLETED if data.get("status") == "completed" else TransactionStatus.PENDING,
            fan_id=fan_profile.id if fan_profile else None,
            model_id=self.model_id,  # Set by sync context
            description=data.get("description", ""),
            metadata={
                "original_type": data.get("type"),
                "message": data.get("message"),
                "post_id": data.get("postId")
            },
            created_at=datetime.fromisoformat(data["createdAt"]) if data.get("createdAt") else datetime.utcnow()
        )
    
    async def _transform_message(self, data: Dict[str, Any]) -> Message:
        """Transform message data."""
        # Get fan profile
        is_from_fan = not data.get("fromMe", False)
        fan_external_id = str(data.get("fromUser", {}).get("id", "") if is_from_fan else data.get("toUser", {}).get("id", ""))
        fan_profile = await self._get_or_create_fan_profile(fan_external_id, data.get("fromUser" if is_from_fan else "toUser", {}))
        
        return Message(
            external_id=str(data["id"]),
            platform="onlyfans",
            conversation_id=str(data.get("chatId", "")),
            fan_id=fan_profile.id if fan_profile else None,
            model_id=self.model_id,
            content=data.get("text", ""),
            is_from_fan=is_from_fan,
            has_media=bool(data.get("media")),
            media_urls=data.get("media", []),
            is_paid=bool(data.get("price")),
            price=Decimal(str(data.get("price", "0"))) if data.get("price") else None,
            metadata={
                "tip_amount": data.get("tipAmount"),
                "is_opened": data.get("isOpened", False),
                "opened_at": data.get("openedAt")
            },
            created_at=datetime.fromisoformat(data["createdAt"]) if data.get("createdAt") else datetime.utcnow()
        )
    
    async def _get_or_create_fan_profile(self, external_id: str, data: Dict[str, Any]) -> Optional[FanProfile]:
        """Get or create fan profile."""
        if not external_id:
            return None
        
        # Check if profile exists
        result = await self.db.execute(
            select(FanProfile).where(
                and_(
                    FanProfile.external_id == external_id,
                    FanProfile.platform == "onlyfans"
                )
            )
        )
        profile = result.scalar_one_or_none()
        
        if not profile and data:
            # Create new profile
            profile = FanProfile(
                external_id=external_id,
                platform="onlyfans",
                username=data.get("username", f"user_{external_id}"),
                display_name=data.get("name", ""),
                avatar_url=data.get("avatar"),
                metadata={"source": "sync"}
            )
            self.db.add(profile)
            await self.db.flush()
        
        return profile
    
    async def get_existing_items(self, external_ids: List[str]) -> Dict[str, Any]:
        """Get existing items from database."""
        sync_type = self.state_metadata.get("sync_type", "subscribers")
        existing = {}
        
        if sync_type == "subscribers":
            result = await self.db.execute(
                select(FanProfile).where(
                    and_(
                        FanProfile.external_id.in_(external_ids),
                        FanProfile.platform == "onlyfans"
                    )
                )
            )
            for profile in result.scalars():
                existing[profile.external_id] = profile
        
        elif sync_type == "transactions":
            result = await self.db.execute(
                select(Transaction).where(
                    and_(
                        Transaction.external_id.in_(external_ids),
                        Transaction.platform == "onlyfans"
                    )
                )
            )
            for transaction in result.scalars():
                existing[transaction.external_id] = transaction
        
        elif sync_type == "messages":
            result = await self.db.execute(
                select(Message).where(
                    and_(
                        Message.external_id.in_(external_ids),
                        Message.platform == "onlyfans"
                    )
                )
            )
            for message in result.scalars():
                existing[message.external_id] = message
        
        return existing
    
    async def create_item(self, data: Any) -> Any:
        """Create new item in database."""
        self.db.add(data)
        await self.db.flush()
        return data
    
    async def update_item(self, existing: Any, new_data: Any) -> Any:
        """Update existing item with new data."""
        # Update fields based on type
        if isinstance(existing, FanProfile):
            existing.username = new_data.username
            existing.display_name = new_data.display_name
            existing.email = new_data.email
            existing.avatar_url = new_data.avatar_url
            existing.is_subscriber = new_data.is_subscriber
            existing.subscription_price = new_data.subscription_price
            existing.total_spent = new_data.total_spent
            existing.metadata.update(new_data.metadata)
        
        elif isinstance(existing, Transaction):
            existing.status = new_data.status
            existing.metadata.update(new_data.metadata)
        
        elif isinstance(existing, Message):
            existing.is_opened = new_data.metadata.get("is_opened", existing.is_opened)
            existing.metadata.update(new_data.metadata)
        
        existing.updated_at = datetime.utcnow()
        await self.db.flush()
        return existing
    
    async def delete_item(self, item: Any) -> None:
        """Soft delete item."""
        if hasattr(item, "is_deleted"):
            item.is_deleted = True
            item.deleted_at = datetime.utcnow()
            await self.db.flush()
        else:
            await self.db.delete(item)
            await self.db.flush()
    
    async def resolve_conflict(
        self,
        local_item: Any,
        remote_item: Any,
        strategy: ConflictResolution
    ) -> Tuple[Any, bool]:
        """Resolve conflicts between local and remote data."""
        if strategy == ConflictResolution.REMOTE_WINS:
            return remote_item, True
        
        elif strategy == ConflictResolution.LOCAL_WINS:
            return local_item, False
        
        elif strategy == ConflictResolution.NEWEST_WINS:
            # Compare update timestamps
            local_updated = getattr(local_item, "updated_at", datetime.min)
            remote_updated = getattr(remote_item, "updated_at", datetime.utcnow())
            
            if remote_updated > local_updated:
                return remote_item, True
            else:
                return local_item, False
        
        elif strategy == ConflictResolution.MERGE:
            # Merge logic - combine non-conflicting fields
            if isinstance(local_item, FanProfile):
                # Keep local computed fields, update profile fields
                local_item.username = remote_item.username
                local_item.display_name = remote_item.display_name
                local_item.avatar_url = remote_item.avatar_url
                # Merge metadata
                local_item.metadata.update(remote_item.metadata)
                return local_item, True
            
            # Default to remote wins for other types
            return remote_item, True
        
        else:
            # Manual resolution - log and skip
            logger.warning(
                f"Manual conflict resolution required for {type(local_item).__name__}",
                extra={
                    "local_id": getattr(local_item, "id", None),
                    "external_id": getattr(local_item, "external_id", None)
                }
            )
            return local_item, False
    
    def _get_external_id(self, item: Any) -> str:
        """Get external ID from item."""
        if hasattr(item, "external_id"):
            return item.external_id
        elif isinstance(item, dict):
            return str(item.get("id", ""))
        raise ValueError(f"Cannot extract external ID from {type(item)}")
    
    async def _check_conflict(self, local: Any, remote: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check for conflicts between local and remote data."""
        conflict_info = None
        needs_update = False
        
        # Check for field differences
        if isinstance(local, FanProfile) and isinstance(remote, FanProfile):
            if local.username != remote.username or local.total_spent != remote.total_spent:
                needs_update = True
                if local.updated_at and remote.updated_at:
                    # Both have been modified - conflict
                    conflict_info = {
                        "type": "fan_profile",
                        "external_id": local.external_id,
                        "local_updated": local.updated_at.isoformat(),
                        "fields": {
                            "username": {"local": local.username, "remote": remote.username},
                            "total_spent": {"local": str(local.total_spent), "remote": str(remote.total_spent)}
                        }
                    }
        
        elif isinstance(local, Transaction):
            # Transactions are mostly immutable, only status changes
            if local.status != remote.status:
                needs_update = True
        
        elif isinstance(local, Message):
            # Messages can have read status updates
            local_opened = local.metadata.get("is_opened", False)
            remote_opened = remote.metadata.get("is_opened", False)
            if local_opened != remote_opened:
                needs_update = True
        
        return needs_update, conflict_info
    
    async def _get_stored_ids(self) -> Set[str]:
        """Get all stored external IDs for current sync type."""
        sync_type = self.state_metadata.get("sync_type", "subscribers")
        ids = set()
        
        if sync_type == "subscribers":
            result = await self.db.execute(
                select(FanProfile.external_id).where(
                    FanProfile.platform == "onlyfans"
                )
            )
            ids = {row[0] for row in result}
        
        elif sync_type == "transactions":
            result = await self.db.execute(
                select(Transaction.external_id).where(
                    Transaction.platform == "onlyfans"
                )
            )
            ids = {row[0] for row in result}
        
        elif sync_type == "messages":
            result = await self.db.execute(
                select(Message.external_id).where(
                    Message.platform == "onlyfans"
                )
            )
            ids = {row[0] for row in result}
        
        return ids
    
    async def _process_deletion(self, external_id: str) -> None:
        """Process deletion of an item."""
        sync_type = self.state_metadata.get("sync_type", "subscribers")
        
        if sync_type == "subscribers":
            # Soft delete - mark as unsubscribed
            result = await self.db.execute(
                select(FanProfile).where(
                    and_(
                        FanProfile.external_id == external_id,
                        FanProfile.platform == "onlyfans"
                    )
                )
            )
            profile = result.scalar_one_or_none()
            if profile:
                profile.is_subscriber = False
                profile.unsubscribed_at = datetime.utcnow()
                await self.db.flush()
        
        elif sync_type == "transactions":
            # Transactions should not be deleted, log warning
            logger.warning(f"Attempted to delete transaction {external_id}")
        
        elif sync_type == "messages":
            # Soft delete messages
            result = await self.db.execute(
                select(Message).where(
                    and_(
                        Message.external_id == external_id,
                        Message.platform == "onlyfans"
                    )
                )
            )
            message = result.scalar_one_or_none()
            if message and hasattr(message, "is_deleted"):
                message.is_deleted = True
                message.deleted_at = datetime.utcnow()
                await self.db.flush()
    
    @property
    def state_metadata(self) -> Dict[str, Any]:
        """Get state metadata."""
        # This would be set from the state passed to sync_delta
        return getattr(self, "_state_metadata", {})
    
    @property
    def model_id(self) -> Optional[int]:
        """Get current model ID from context."""
        # This would be set based on API key owner
        return getattr(self, "_model_id", None)