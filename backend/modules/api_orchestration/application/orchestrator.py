"""
API Orchestration service.

This service coordinates between Inflow and OnlyFans APIs to provide
unified functionality with conflict resolution and intelligent routing.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.core.database import get_db
from backend.core.redis import redis_client
from backend.core.domain.models import ModelProfile, Fan, FanClaim, User
from backend.modules.inflow_wrapper.application.service import InflowService
from backend.modules.onlyfans_wrapper.application.service import OnlyFansService
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


class APIOrchestrator:
    """Orchestrates API calls between multiple sources."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inflow_service = InflowService(db)
        self.onlyfans_service = OnlyFansService(db)
    
    async def get_unified_fans(
        self,
        model_profile: ModelProfile,
        limit: int = 100,
        offset: int = 0,
        include_unclaimed: bool = True
    ) -> List[UnifiedFan]:
        """Get unified list of fans from all sources."""
        # Get fans from database (already synced)
        query = select(Fan).where(Fan.model_id == model_profile.id)
        
        if not include_unclaimed:
            # Only get fans with active claims
            query = query.join(
                FanClaim,
                and_(
                    FanClaim.fan_id == Fan.id,
                    FanClaim.is_active == True
                )
            )
        
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        fans = result.scalars().all()
        
        unified_fans = []
        for fan in fans:
            # Check if fan is claimed
            claim_result = await self.db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.fan_id == fan.id,
                        FanClaim.is_active == True
                    )
                )
            )
            claim = claim_result.scalar_one_or_none()
            
            # Determine data sources
            data_sources = []
            if fan.onlyfans_user_id:
                data_sources.append(DataSource.ONLYFANS)
            # TODO: Add Inflow ID tracking
            
            unified_fan = UnifiedFan(
                id=str(fan.id),
                username=fan.username,
                display_name=fan.display_name,
                avatar_url=fan.avatar_url,
                is_subscriber=fan.is_subscriber,
                is_paying=fan.is_paying,
                subscription_price=fan.subscription_price,
                subscribed_at=fan.subscribed_at,
                expires_at=fan.expires_at,
                total_spent=fan.total_spent,
                tip_count=fan.tip_count,
                message_count=fan.message_count,
                ppv_purchased_count=fan.ppv_purchased_count,
                last_active_at=fan.last_active_at,
                is_claimed=claim is not None,
                claimed_by=str(claim.chatter_id) if claim else None,
                claimed_at=claim.claimed_at if claim else None,
                claim_expires_at=claim.expires_at if claim else None,
                data_sources=data_sources,
                onlyfans_id=fan.onlyfans_user_id,
                last_synced_at=fan.updated_at
            )
            unified_fans.append(unified_fan)
        
        return unified_fans
    
    async def sync_all_data(
        self,
        model_profile: ModelProfile,
        sync_inflow: bool = True,
        sync_onlyfans: bool = True
    ) -> SyncStatus:
        """Sync data from all configured sources."""
        sync_status = SyncStatus(model_id=str(model_profile.id))
        sync_status.is_syncing = True
        
        # Store sync status in Redis
        await self._update_sync_status(model_profile.id, sync_status)
        
        tasks = []
        
        # Sync from Inflow if configured
        if sync_inflow and model_profile.inflow_api_key:
            sync_status.inflow_enabled = True
            tasks.append(self._sync_inflow_data(model_profile, sync_status))
        
        # Sync from OnlyFans if configured
        if sync_onlyfans and model_profile.onlyfans_api_key:
            sync_status.onlyfans_enabled = True
            tasks.append(self._sync_onlyfans_data(model_profile, sync_status))
        
        # Run syncs in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update final status
        sync_status.is_syncing = False
        sync_status.last_full_sync = datetime.utcnow()
        sync_status.next_sync_scheduled = datetime.utcnow() + timedelta(hours=1)
        
        await self._update_sync_status(model_profile.id, sync_status)
        
        return sync_status
    
    async def send_message(
        self,
        model_profile: ModelProfile,
        request: MessageRequest,
        user: User
    ) -> Dict[str, Any]:
        """Send message through the best available channel."""
        # Get fan information
        fan = await self.db.get(Fan, request.fan_id)
        if not fan:
            raise ValueError(f"Fan {request.fan_id} not found")
        
        # Check fan claim status
        claim_result = await self.db.execute(
            select(FanClaim).where(
                and_(
                    FanClaim.fan_id == request.fan_id,
                    FanClaim.is_active == True
                )
            )
        )
        claim = claim_result.scalar_one_or_none()
        
        # Verify user has permission to message this fan
        if claim:
            if claim.claimed_by_model:
                # Model has exclusive claim
                if user.role != "model" or model_profile.user_id != user.id:
                    raise ValueError("This fan is exclusively claimed by the model")
            elif claim.chatter_id != user.id:
                # Another chatter has the claim
                raise ValueError("This fan is claimed by another chatter")
        
        # Determine which API to use
        source = request.preferred_source
        if not source:
            # Auto-select based on availability
            if fan.onlyfans_user_id and model_profile.onlyfans_api_key:
                source = DataSource.ONLYFANS
            elif model_profile.inflow_api_key:
                source = DataSource.INFLOW
            else:
                raise ValueError("No messaging API configured")
        
        # Send message through selected source
        try:
            if source == DataSource.ONLYFANS:
                message = await self.onlyfans_service.send_message(
                    model_profile=model_profile,
                    fan_id=request.fan_id,
                    text=request.text,
                    media_ids=request.media_ids,
                    price=request.price
                )
                return {
                    "success": True,
                    "source": DataSource.ONLYFANS,
                    "message_id": message.id,
                    "created_at": message.created_at
                }
            elif source == DataSource.INFLOW:
                message = await self.inflow_service.send_message(
                    model_profile=model_profile,
                    fan_id=request.fan_id,
                    content=request.text or "",
                    price=float(request.price) if request.price else None
                )
                return {
                    "success": True,
                    "source": DataSource.INFLOW,
                    "message_id": message.id,
                    "created_at": message.created_at
                }
        except Exception as e:
            logger.error(f"Failed to send message through {source}: {e}")
            
            # Try fallback if enabled
            if request.fallback_enabled:
                alt_source = DataSource.INFLOW if source == DataSource.ONLYFANS else DataSource.ONLYFANS
                try:
                    # Recursively try with alternative source
                    request.preferred_source = alt_source
                    request.fallback_enabled = False
                    return await self.send_message(model_profile, request, user)
                except Exception as fallback_error:
                    logger.error(f"Fallback to {alt_source} also failed: {fallback_error}")
            
            raise
    
    async def get_unified_analytics(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ) -> UnifiedAnalytics:
        """Get combined analytics from all sources."""
        tasks = []
        
        # Get analytics from each source
        if model_profile.inflow_api_key:
            tasks.append(self.inflow_service.get_analytics(
                model_profile, start_date, end_date
            ))
        
        if model_profile.onlyfans_api_key:
            tasks.append(self.onlyfans_service.get_statistics(
                model_profile, start_date, end_date
            ))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Initialize unified analytics
        unified = UnifiedAnalytics(
            period_start=start_date,
            period_end=end_date,
            total_revenue=Decimal("0.00"),
            subscription_revenue=Decimal("0.00"),
            tip_revenue=Decimal("0.00"),
            ppv_revenue=Decimal("0.00"),
            total_subscribers=0,
            new_subscribers=0,
            lost_subscribers=0,
            paying_subscribers=0,
            messages_sent=0,
            messages_received=0,
            data_sources=[]
        )
        
        # Process Inflow analytics if available
        if tasks and not isinstance(results[0], Exception):
            inflow_data = results[0]
            unified.data_sources.append(DataSource.INFLOW)
            unified.inflow_revenue = inflow_data.total_revenue
            unified.total_revenue += inflow_data.total_revenue
            unified.subscription_revenue += inflow_data.subscription_revenue
            unified.tip_revenue += inflow_data.tip_revenue
            unified.ppv_revenue += inflow_data.ppv_revenue
            unified.new_subscribers += inflow_data.new_subscribers
            unified.lost_subscribers += inflow_data.lost_subscribers
            unified.messages_sent += inflow_data.message_count
        
        # Process OnlyFans analytics if available
        if len(tasks) > 1 and not isinstance(results[1], Exception):
            of_data = results[1]
            unified.data_sources.append(DataSource.ONLYFANS)
            unified.onlyfans_revenue = of_data.total_earnings
            unified.total_revenue += of_data.total_earnings
            unified.subscription_revenue += of_data.subscription_earnings
            unified.tip_revenue += of_data.tip_earnings
            unified.ppv_revenue += of_data.message_earnings + of_data.post_earnings
            unified.new_subscribers += of_data.new_subscribers
            unified.lost_subscribers += of_data.lost_subscribers
            unified.paying_subscribers = of_data.total_subscribers
            unified.messages_sent += of_data.messages_sent
            unified.messages_received += of_data.messages_received
            unified.posts_created = of_data.posts_count
        
        # Get total subscriber count from database
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.model_id == model_profile.id,
                    Fan.is_subscriber == True
                )
            )
        )
        unified.total_subscribers = len(result.scalars().all())
        
        return unified
    
    async def _sync_inflow_data(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus
    ):
        """Sync data from Inflow API."""
        try:
            # Sync subscribers
            synced_count = await self.inflow_service.sync_subscribers(model_profile)
            sync_status.inflow_subscribers_synced = synced_count
            
            # Sync messages
            message_count = await self.inflow_service.sync_messages(model_profile)
            sync_status.inflow_messages_synced = message_count
            
            sync_status.inflow_last_sync = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Inflow sync failed for model {model_profile.id}: {e}")
            sync_status.inflow_sync_errors.append(str(e))
    
    async def _sync_onlyfans_data(
        self,
        model_profile: ModelProfile,
        sync_status: SyncStatus
    ):
        """Sync data from OnlyFans API."""
        try:
            # Sync profile
            await self.onlyfans_service.sync_profile(model_profile)
            
            # Sync fans
            synced_count = await self.onlyfans_service.sync_fans(model_profile)
            sync_status.onlyfans_fans_synced = synced_count
            
            # Get recent messages
            messages = await self.onlyfans_service.get_messages(model_profile, limit=100)
            sync_status.onlyfans_messages_synced = len(messages)
            
            sync_status.onlyfans_last_sync = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"OnlyFans sync failed for model {model_profile.id}: {e}")
            sync_status.onlyfans_sync_errors.append(str(e))
    
    async def _update_sync_status(
        self,
        model_id: str,
        sync_status: SyncStatus
    ):
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