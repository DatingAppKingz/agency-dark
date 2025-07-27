"""
Enhanced API Orchestration service using External API Framework.

This service coordinates between Inflow and OnlyFans APIs with advanced
features like intelligent routing, conflict resolution, and failover.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from core.database import get_db
from core.redis import redis_client
from core.domain.models import ModelProfile, Fan, FanClaim, User, Transaction
from core.external_api import APIError, APIRateLimitError

from modules.inflow_wrapper.infrastructure.factory import create_inflow_client
from modules.onlyfans_wrapper.infrastructure.factory import create_onlyfans_client
from modules.analytics.domain.models import AnalyticsEvent

from ..domain.schemas import (
    DataSource,
    ConflictResolution,
    UnifiedFan,
    UnifiedMessage,
    UnifiedAnalytics,
    SyncStatus,
    MessageRequest,
    MassMessageRequest,
    ContentPost
)


logger = logging.getLogger(__name__)


class EnhancedAPIOrchestrator:
    """Enhanced orchestrator with advanced routing and conflict resolution."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._inflow_clients: Dict[str, Any] = {}
        self._onlyfans_clients: Dict[str, Any] = {}
        self._sync_locks: Dict[str, asyncio.Lock] = {}
        
    async def get_inflow_client(self, model_profile: ModelProfile):
        """Get or create Inflow client for model."""
        client_key = f"inflow_{model_profile.id}"
        if client_key not in self._inflow_clients:
            from modules.inflow_wrapper.domain.schemas import InflowConfig
            config = InflowConfig(
                base_url="https://api.inflow.com",
                api_key=model_profile.inflow_api_key,
                timeout=30,
                max_retries=3,
                auth_method="api_key"
            )
            self._inflow_clients[client_key] = await create_inflow_client(config=config)
        return self._inflow_clients[client_key]
        
    async def get_onlyfans_client(self, model_profile: ModelProfile):
        """Get or create OnlyFans client for model."""
        client_key = f"onlyfans_{model_profile.id}"
        if client_key not in self._onlyfans_clients:
            from modules.onlyfans_wrapper.domain.schemas import OnlyFansConfig
            config = OnlyFansConfig(
                base_url="https://onlyfansapi.com/api/v1",
                api_key=model_profile.onlyfans_api_key,
                timeout=30,
                max_retries=3
            )
            self._onlyfans_clients[client_key] = await create_onlyfans_client(config=config)
        return self._onlyfans_clients[client_key]
        
    def _get_sync_lock(self, model_id: str) -> asyncio.Lock:
        """Get or create sync lock for model."""
        if model_id not in self._sync_locks:
            self._sync_locks[model_id] = asyncio.Lock()
        return self._sync_locks[model_id]
        
    async def sync_all_data(
        self,
        model_profile: ModelProfile,
        sync_inflow: bool = True,
        sync_onlyfans: bool = True,
        force: bool = False
    ) -> SyncStatus:
        """Enhanced sync with locking and deduplication."""
        sync_lock = self._get_sync_lock(str(model_profile.id))
        
        # Check if already syncing
        if sync_lock.locked() and not force:
            # Return current sync status
            existing_status = await self.get_sync_status(str(model_profile.id))
            if existing_status and existing_status.is_syncing:
                return existing_status
                
        async with sync_lock:
            sync_status = SyncStatus(model_id=str(model_profile.id))
            sync_status.is_syncing = True
            
            # Store initial sync status
            await self._update_sync_status(str(model_profile.id), sync_status)
            
            # Track all synced fan IDs to detect duplicates
            inflow_fan_ids: Set[str] = set()
            onlyfans_fan_ids: Set[str] = set()
            
            tasks = []
            
            # Sync from Inflow
            if sync_inflow and model_profile.inflow_api_key:
                sync_status.inflow_enabled = True
                tasks.append(self._enhanced_sync_inflow(
                    model_profile, sync_status, inflow_fan_ids
                ))
                
            # Sync from OnlyFans
            if sync_onlyfans and model_profile.onlyfans_api_key:
                sync_status.onlyfans_enabled = True
                tasks.append(self._enhanced_sync_onlyfans(
                    model_profile, sync_status, onlyfans_fan_ids
                ))
                
            # Run syncs in parallel
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle errors
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        error_msg = f"Sync task {i} failed: {str(result)}"
                        logger.error(error_msg)
                        if i == 0:  # Inflow
                            sync_status.inflow_sync_errors.append(error_msg)
                        else:  # OnlyFans
                            sync_status.onlyfans_sync_errors.append(error_msg)
                            
            # Detect and merge duplicates
            duplicate_count = await self._merge_duplicate_fans(
                model_profile, inflow_fan_ids, onlyfans_fan_ids
            )
            
            # Update final status
            sync_status.is_syncing = False
            sync_status.last_full_sync = datetime.utcnow()
            sync_status.next_sync_scheduled = datetime.utcnow() + timedelta(hours=1)
            
            # Create analytics event
            analytics_event = AnalyticsEvent(
                event_type="api_sync_completed",
                user_id=str(model_profile.user_id),
                metadata={
                    "model_id": str(model_profile.id),
                    "inflow_synced": sync_status.inflow_subscribers_synced,
                    "onlyfans_synced": sync_status.onlyfans_fans_synced,
                    "duplicates_merged": duplicate_count,
                    "errors": len(sync_status.inflow_sync_errors) + len(sync_status.onlyfans_sync_errors)
                },
                timestamp=datetime.utcnow()
            )
            self.db.add(analytics_event)
            await self.db.commit()
            
            await self._update_sync_status(str(model_profile.id), sync_status)
            
            return sync_status
            
    async def _enhanced_sync_inflow(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus,
        synced_ids: Set[str]
    ):
        """Enhanced Inflow sync with deduplication."""
        try:
            client = await self.get_inflow_client(model_profile)
            
            # Sync subscribers with pagination
            offset = 0
            limit = 100
            total_synced = 0
            
            while True:
                subscribers = await client.list_subscribers(
                    creator_id=model_profile.onlyfans_user_id or str(model_profile.id),
                    limit=limit,
                    offset=offset,
                    active_only=False  # Get all, we'll filter later
                )
                
                if not subscribers:
                    break
                    
                for sub in subscribers:
                    # Create unique ID for deduplication
                    unique_id = self._generate_fan_unique_id(
                        username=sub.subscriber.username if hasattr(sub, 'subscriber') else None,
                        email=sub.subscriber.email if hasattr(sub, 'subscriber') else None,
                        platform_id=sub.id
                    )
                    synced_ids.add(unique_id)
                    
                    # Upsert fan record
                    await self._upsert_fan_from_inflow(model_profile, sub)
                    total_synced += 1
                    
                offset += limit
                
                # Respect rate limits
                await asyncio.sleep(0.1)
                
            sync_status.inflow_subscribers_synced = total_synced
            sync_status.inflow_last_sync = datetime.utcnow()
            
            # Sync recent transactions
            await self._sync_inflow_transactions(model_profile, sync_status)
            
        except APIRateLimitError as e:
            logger.warning(f"Inflow rate limit hit: {e}")
            sync_status.inflow_sync_errors.append(f"Rate limit: {str(e)}")
        except Exception as e:
            logger.error(f"Inflow sync failed: {e}")
            sync_status.inflow_sync_errors.append(str(e))
            raise
            
    async def _enhanced_sync_onlyfans(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus,
        synced_ids: Set[str]
    ):
        """Enhanced OnlyFans sync with deduplication."""
        try:
            client = await self.get_onlyfans_client(model_profile)
            
            # Sync fans with pagination
            offset = 0
            limit = 100
            total_synced = 0
            
            while True:
                fans = await client.get_fans(limit=limit, offset=offset)
                
                if not fans:
                    break
                    
                for fan in fans:
                    # Create unique ID for deduplication
                    unique_id = self._generate_fan_unique_id(
                        username=fan.username,
                        email=getattr(fan, 'email', None),
                        platform_id=fan.id
                    )
                    synced_ids.add(unique_id)
                    
                    # Upsert fan record
                    await self._upsert_fan_from_onlyfans(model_profile, fan)
                    total_synced += 1
                    
                offset += limit
                
                # Respect rate limits
                await asyncio.sleep(0.1)
                
            sync_status.onlyfans_fans_synced = total_synced
            sync_status.onlyfans_last_sync = datetime.utcnow()
            
            # Sync recent transactions
            await self._sync_onlyfans_transactions(model_profile, sync_status)
            
        except APIRateLimitError as e:
            logger.warning(f"OnlyFans rate limit hit: {e}")
            sync_status.onlyfans_sync_errors.append(f"Rate limit: {str(e)}")
        except Exception as e:
            logger.error(f"OnlyFans sync failed: {e}")
            sync_status.onlyfans_sync_errors.append(str(e))
            raise
            
    def _generate_fan_unique_id(
        self,
        username: Optional[str],
        email: Optional[str],
        platform_id: str
    ) -> str:
        """Generate unique ID for fan deduplication."""
        # Use email as primary identifier if available
        if email:
            return hashlib.sha256(email.lower().encode()).hexdigest()
        # Fall back to username
        elif username:
            return hashlib.sha256(username.lower().encode()).hexdigest()
        # Last resort: platform ID
        else:
            return hashlib.sha256(platform_id.encode()).hexdigest()
            
    async def _merge_duplicate_fans(
        self,
        model_profile: ModelProfile,
        inflow_ids: Set[str],
        onlyfans_ids: Set[str]
    ) -> int:
        """Merge duplicate fan records from different sources."""
        duplicates = inflow_ids.intersection(onlyfans_ids)
        merged_count = 0
        
        for unique_id in duplicates:
            # Find all fan records with this unique ID
            result = await self.db.execute(
                select(Fan).where(
                    and_(
                        Fan.model_id == model_profile.id,
                        # Custom field for unique ID tracking
                        Fan.metadata.contains({"unique_id": unique_id})
                    )
                )
            )
            fans = result.scalars().all()
            
            if len(fans) > 1:
                # Merge into the most complete record
                primary_fan = max(fans, key=lambda f: (
                    f.total_spent,
                    f.message_count,
                    f.last_active_at or datetime.min
                ))
                
                # Merge data from other records
                for fan in fans:
                    if fan.id != primary_fan.id:
                        # Aggregate financial data
                        primary_fan.total_spent += fan.total_spent
                        primary_fan.tip_count += fan.tip_count
                        primary_fan.message_count += fan.message_count
                        primary_fan.ppv_purchased_count += fan.ppv_purchased_count
                        
                        # Keep latest activity
                        if fan.last_active_at and (
                            not primary_fan.last_active_at or 
                            fan.last_active_at > primary_fan.last_active_at
                        ):
                            primary_fan.last_active_at = fan.last_active_at
                            
                        # Transfer claims
                        await self.db.execute(
                            FanClaim.__table__.update().where(
                                FanClaim.fan_id == fan.id
                            ).values(fan_id=primary_fan.id)
                        )
                        
                        # Delete duplicate
                        await self.db.delete(fan)
                        merged_count += 1
                        
        if merged_count > 0:
            await self.db.commit()
            logger.info(f"Merged {merged_count} duplicate fan records for model {model_profile.id}")
            
        return merged_count
        
    async def send_message_with_failover(
        self,
        model_profile: ModelProfile,
        request: MessageRequest,
        user: User
    ) -> Dict[str, Any]:
        """Send message with automatic failover between APIs."""
        # Validate fan access
        fan = await self._validate_fan_access(request.fan_id, user, model_profile)
        
        # Determine primary and fallback sources
        sources = self._determine_message_sources(model_profile, fan, request)
        
        errors = []
        for source in sources:
            try:
                result = await self._send_message_via_source(
                    model_profile, fan, request, source
                )
                
                # Log successful delivery
                analytics_event = AnalyticsEvent(
                    event_type="message_sent",
                    user_id=str(user.id),
                    metadata={
                        "fan_id": str(fan.id),
                        "source": source.value,
                        "is_ppv": bool(request.price),
                        "price": float(request.price) if request.price else None,
                        "has_media": bool(request.media_ids),
                        "campaign_id": request.campaign_id
                    },
                    timestamp=datetime.utcnow()
                )
                self.db.add(analytics_event)
                await self.db.commit()
                
                return result
                
            except APIRateLimitError as e:
                errors.append(f"{source}: Rate limit - {str(e)}")
                # Wait before trying next source
                await asyncio.sleep(1)
            except Exception as e:
                errors.append(f"{source}: {str(e)}")
                logger.error(f"Failed to send via {source}: {e}")
                
        # All sources failed
        raise APIError(
            message="Failed to send message through any available source",
            details={"errors": errors}
        )
        
    def _determine_message_sources(
        self,
        model_profile: ModelProfile,
        fan: Fan,
        request: MessageRequest
    ) -> List[DataSource]:
        """Determine ordered list of sources to try."""
        sources = []
        
        # Check preferred source first
        if request.preferred_source:
            if request.preferred_source == DataSource.ONLYFANS and model_profile.onlyfans_api_key and fan.onlyfans_user_id:
                sources.append(DataSource.ONLYFANS)
            elif request.preferred_source == DataSource.INFLOW and model_profile.inflow_api_key:
                sources.append(DataSource.INFLOW)
                
        # Add other available sources if fallback enabled
        if request.fallback_enabled:
            if DataSource.ONLYFANS not in sources and model_profile.onlyfans_api_key and fan.onlyfans_user_id:
                sources.append(DataSource.ONLYFANS)
            if DataSource.INFLOW not in sources and model_profile.inflow_api_key:
                sources.append(DataSource.INFLOW)
                
        return sources
        
    async def _send_message_via_source(
        self,
        model_profile: ModelProfile,
        fan: Fan,
        request: MessageRequest,
        source: DataSource
    ) -> Dict[str, Any]:
        """Send message through specific source."""
        if source == DataSource.ONLYFANS:
            client = await self.get_onlyfans_client(model_profile)
            message = await client.send_message(
                user_id=fan.onlyfans_user_id,
                text=request.text,
                media_ids=request.media_ids,
                price=request.price
            )
            return {
                "success": True,
                "source": DataSource.ONLYFANS,
                "message_id": message.id,
                "created_at": message.created_at,
                "external_id": message.id
            }
            
        elif source == DataSource.INFLOW:
            client = await self.get_inflow_client(model_profile)
            # Inflow might use different ID
            recipient_id = fan.metadata.get("inflow_id") if fan.metadata else fan.onlyfans_user_id
            message = await client.send_message(
                recipient_id=recipient_id or fan.onlyfans_user_id,
                content=request.text,
                price=float(request.price) if request.price else None
            )
            return {
                "success": True,
                "source": DataSource.INFLOW,
                "message_id": message.id,
                "created_at": message.created_at,
                "external_id": message.id
            }
            
        else:
            raise ValueError(f"Unsupported source: {source}")
            
    async def _validate_fan_access(
        self,
        fan_id: str,
        user: User,
        model_profile: ModelProfile
    ) -> Fan:
        """Validate user has access to message this fan."""
        fan = await self.db.get(Fan, fan_id)
        if not fan:
            raise ValueError(f"Fan {fan_id} not found")
            
        if fan.model_id != model_profile.id:
            raise ValueError("Fan belongs to different model")
            
        # Check claim status
        result = await self.db.execute(
            select(FanClaim).where(
                and_(
                    FanClaim.fan_id == fan_id,
                    FanClaim.is_active == True
                )
            )
        )
        claim = result.scalar_one_or_none()
        
        if claim:
            if claim.claimed_by_model and user.role != "model":
                raise ValueError("Fan is exclusively claimed by model")
            elif claim.chatter_id != user.id and user.role not in ["model", "super_admin", "agency_owner"]:
                raise ValueError("Fan is claimed by another chatter")
                
        return fan
        
    async def _sync_inflow_transactions(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus
    ):
        """Sync recent transactions from Inflow."""
        try:
            client = await self.get_inflow_client(model_profile)
            
            # Get transactions from last 7 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            transactions = await client.list_transactions(
                start_date=start_date,
                end_date=end_date,
                limit=500
            )
            
            for trans in transactions:
                # Check if transaction already exists
                result = await self.db.execute(
                    select(Transaction).where(
                        Transaction.external_id == f"inflow_{trans.id}"
                    )
                )
                if not result.scalar_one_or_none():
                    # Create new transaction
                    transaction = Transaction(
                        user_id=str(model_profile.user_id),
                        amount=float(trans.amount),
                        currency=trans.currency,
                        type=trans.type,
                        status="completed",
                        external_id=f"inflow_{trans.id}",
                        metadata={
                            "platform": "inflow",
                            "fan_id": trans.user_id,
                            "description": trans.description
                        }
                    )
                    self.db.add(transaction)
                    
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to sync Inflow transactions: {e}")
            
    async def _sync_onlyfans_transactions(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus
    ):
        """Sync recent transactions from OnlyFans."""
        try:
            client = await self.get_onlyfans_client(model_profile)
            
            # Get transactions from last 7 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            transactions = await client.get_transactions(
                start_date=start_date,
                end_date=end_date,
                limit=500
            )
            
            for trans in transactions:
                # Check if transaction already exists
                result = await self.db.execute(
                    select(Transaction).where(
                        Transaction.external_id == f"onlyfans_{trans.id}"
                    )
                )
                if not result.scalar_one_or_none():
                    # Create new transaction
                    transaction = Transaction(
                        user_id=str(model_profile.user_id),
                        amount=float(trans.amount),
                        currency=trans.currency or "USD",
                        type=trans.type,
                        status="completed",
                        external_id=f"onlyfans_{trans.id}",
                        metadata={
                            "platform": "onlyfans",
                            "fan_id": trans.user_id,
                            "description": trans.description
                        }
                    )
                    self.db.add(transaction)
                    
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to sync OnlyFans transactions: {e}")
            
    async def _upsert_fan_from_inflow(self, model_profile: ModelProfile, subscriber):
        """Upsert fan record from Inflow data."""
        # Implementation details...
        pass
        
    async def _upsert_fan_from_onlyfans(self, model_profile: ModelProfile, fan_data):
        """Upsert fan record from OnlyFans data."""
        # Implementation details...
        pass
        
    async def _update_sync_status(self, model_id: str, sync_status: SyncStatus):
        """Update sync status in Redis."""
        cache_key = f"sync_status:{model_id}"
        await redis_client.setex(
            cache_key,
            3600,  # 1 hour TTL
            sync_status.model_dump_json()
        )
        
    async def get_sync_status(self, model_id: str) -> Optional[SyncStatus]:
        """Get current sync status from Redis."""
        cache_key = f"sync_status:{model_id}"
        data = await redis_client.get(cache_key)
        if data:
            return SyncStatus.model_validate_json(data)
        return None