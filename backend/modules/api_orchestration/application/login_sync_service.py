"""
Login synchronization service.

Automatically syncs data from external APIs when users log in.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.redis import redis_client
from core.domain.models import User, ModelProfile
from modules.analytics.domain.models import AnalyticsEvent

from .orchestrator_v2 import EnhancedAPIOrchestrator
from ..domain.schemas import SyncStatus


logger = logging.getLogger(__name__)


class LoginSyncService:
    """Handles data synchronization on user login."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = EnhancedAPIOrchestrator(db)
        
    async def sync_on_login(self, user: User) -> List[SyncStatus]:
        """Trigger synchronization for user's models on login."""
        # Check if sync is needed
        if not await self._should_sync_on_login(user):
            logger.info(f"Skipping login sync for user {user.id} - recently synced")
            return []
            
        # Record login event
        login_event = AnalyticsEvent(
            event_type="user_login",
            user_id=str(user.id),
            metadata={
                "role": user.role,
                "email": user.email,
                "timestamp": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow()
        )
        self.db.add(login_event)
        
        sync_statuses = []
        
        if user.role == "model":
            # Sync model's own data
            model_profile = await self._get_model_profile(user)
            if model_profile:
                status = await self._sync_model_data(model_profile, background=True)
                sync_statuses.append(status)
                
        elif user.role in ["agency_owner", "agency_admin"]:
            # Sync all agency models
            model_profiles = await self._get_agency_models(user)
            
            # Limit concurrent syncs to avoid overwhelming APIs
            semaphore = asyncio.Semaphore(3)
            
            async def sync_with_limit(model_profile):
                async with semaphore:
                    return await self._sync_model_data(model_profile, background=True)
                    
            # Sync models concurrently
            tasks = [sync_with_limit(mp) for mp in model_profiles]
            statuses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for status in statuses:
                if isinstance(status, SyncStatus):
                    sync_statuses.append(status)
                elif isinstance(status, Exception):
                    logger.error(f"Sync failed: {status}")
                    
        elif user.role == "chatter":
            # Sync only models the chatter has access to
            model_profiles = await self._get_chatter_models(user)
            
            for model_profile in model_profiles[:5]:  # Limit to 5 models
                status = await self._sync_model_data(model_profile, background=True)
                sync_statuses.append(status)
                
        # Record sync initiation
        if sync_statuses:
            sync_event = AnalyticsEvent(
                event_type="login_sync_initiated",
                user_id=str(user.id),
                metadata={
                    "models_synced": len(sync_statuses),
                    "sync_ids": [s.model_id for s in sync_statuses]
                },
                timestamp=datetime.utcnow()
            )
            self.db.add(sync_event)
            
        await self.db.commit()
        
        return sync_statuses
        
    async def _should_sync_on_login(self, user: User) -> bool:
        """Check if sync should be triggered on login."""
        # Check last sync time
        last_sync_key = f"last_login_sync:{user.id}"
        last_sync = await redis_client.get(last_sync_key)
        
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync)
            time_since_sync = datetime.utcnow() - last_sync_time
            
            # Skip if synced within last hour
            if time_since_sync < timedelta(hours=1):
                return False
                
        # Check user preferences
        if user.metadata and not user.metadata.get("auto_sync_on_login", True):
            return False
            
        # Record this sync attempt
        await redis_client.setex(
            last_sync_key,
            3600,  # 1 hour TTL
            datetime.utcnow().isoformat()
        )
        
        return True
        
    async def _get_model_profile(self, user: User) -> Optional[ModelProfile]:
        """Get model profile for a model user."""
        result = await self.db.execute(
            select(ModelProfile).where(ModelProfile.user_id == user.id)
        )
        return result.scalar_one_or_none()
        
    async def _get_agency_models(self, user: User) -> List[ModelProfile]:
        """Get all models for an agency owner/admin."""
        if not user.agency_id:
            return []
            
        result = await self.db.execute(
            select(ModelProfile).where(
                and_(
                    ModelProfile.agency_id == user.agency_id,
                    ModelProfile.is_active == True
                )
            ).limit(20)  # Limit to prevent overwhelming
        )
        return list(result.scalars().all())
        
    async def _get_chatter_models(self, user: User) -> List[ModelProfile]:
        """Get models a chatter has access to."""
        # Get models where chatter has active fan claims
        from core.domain.models import FanClaim, Fan
        
        result = await self.db.execute(
            select(ModelProfile).distinct().join(
                Fan, Fan.model_id == ModelProfile.id
            ).join(
                FanClaim, FanClaim.fan_id == Fan.id
            ).where(
                and_(
                    FanClaim.chatter_id == user.id,
                    FanClaim.is_active == True,
                    ModelProfile.is_active == True
                )
            ).limit(10)
        )
        return list(result.scalars().all())
        
    async def _sync_model_data(
        self,
        model_profile: ModelProfile,
        background: bool = True
    ) -> SyncStatus:
        """Sync data for a specific model."""
        # Check if model has any API keys configured
        if not model_profile.inflow_api_key and not model_profile.onlyfans_api_key:
            logger.info(f"Model {model_profile.id} has no API keys configured")
            return SyncStatus(
                model_id=str(model_profile.id),
                is_syncing=False,
                inflow_enabled=False,
                onlyfans_enabled=False
            )
            
        if background:
            # Start sync in background
            asyncio.create_task(self._background_sync(model_profile))
            
            # Return pending status
            return SyncStatus(
                model_id=str(model_profile.id),
                is_syncing=True,
                inflow_enabled=bool(model_profile.inflow_api_key),
                onlyfans_enabled=bool(model_profile.onlyfans_api_key)
            )
        else:
            # Sync synchronously
            return await self.orchestrator.sync_all_data(
                model_profile,
                sync_inflow=True,
                sync_onlyfans=True,
                force=False
            )
            
    async def _background_sync(self, model_profile: ModelProfile):
        """Run sync in background."""
        try:
            logger.info(f"Starting background sync for model {model_profile.id}")
            
            # Create new session for background task
            from core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                orchestrator = EnhancedAPIOrchestrator(db)
                
                await orchestrator.sync_all_data(
                    model_profile,
                    sync_inflow=True,
                    sync_onlyfans=True,
                    force=False
                )
                
            logger.info(f"Background sync completed for model {model_profile.id}")
            
        except Exception as e:
            logger.error(f"Background sync failed for model {model_profile.id}: {e}")
            
    async def configure_auto_sync(
        self,
        user: User,
        enabled: bool,
        sync_interval_hours: Optional[int] = None,
        sync_on_login: bool = True
    ):
        """Configure auto-sync settings for a user."""
        if not user.metadata:
            user.metadata = {}
            
        user.metadata.update({
            "auto_sync_enabled": enabled,
            "auto_sync_on_login": sync_on_login,
            "sync_interval_hours": sync_interval_hours or 24
        })
        
        await self.db.commit()
        
        logger.info(
            f"Updated auto-sync settings for user {user.id}: "
            f"enabled={enabled}, on_login={sync_on_login}, interval={sync_interval_hours}h"
        )
        
    async def get_sync_history(
        self,
        user: User,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent sync history for a user."""
        # Query sync events
        result = await self.db.execute(
            select(AnalyticsEvent).where(
                and_(
                    AnalyticsEvent.user_id == str(user.id),
                    AnalyticsEvent.event_type.in_([
                        "api_sync_completed",
                        "login_sync_initiated"
                    ])
                )
            ).order_by(AnalyticsEvent.timestamp.desc()).limit(limit)
        )
        
        events = result.scalars().all()
        
        history = []
        for event in events:
            history.append({
                "timestamp": event.timestamp,
                "type": event.event_type,
                "details": event.metadata,
                "id": str(event.id)
            })
            
        return history