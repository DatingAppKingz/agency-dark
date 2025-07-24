"""
Inflow API application service.

This service provides high-level operations for integrating with Inflow API.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.redis import redis_client
from core.domain.models import ModelProfile, Fan, User
from ..domain.interfaces import IInflowClient
from ..domain.schemas import (
    InflowConfig,
    InflowUser,
    InflowSubscription,
    InflowContent,
    InflowMessage,
    InflowTransaction,
    InflowAnalytics
)
from ..infrastructure.client import InflowClient


logger = logging.getLogger(__name__)


class InflowService:
    """Application service for Inflow API integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._clients: Dict[str, InflowClient] = {}
    
    async def get_client(self, model_profile: ModelProfile) -> IInflowClient:
        """Get or create Inflow client for a model."""
        if not model_profile.inflow_api_key:
            raise ValueError(f"Model {model_profile.id} has no Inflow API key configured")
        
        # Check if client already exists
        client_key = f"inflow_client_{model_profile.id}"
        if client_key not in self._clients:
            config = InflowConfig(
                api_key=model_profile.inflow_api_key,
                # TODO: Make these configurable per agency
                base_url="https://api.inflow.com",
                timeout=30,
                max_retries=3
            )
            client = InflowClient(config)
            
            # Authenticate the client
            if not await client.authenticate():
                raise ValueError(f"Failed to authenticate with Inflow for model {model_profile.id}")
            
            self._clients[client_key] = client
        
        return self._clients[client_key]
    
    async def sync_subscribers(self, model_profile: ModelProfile) -> int:
        """Sync subscribers from Inflow to local database."""
        client = await self.get_client(model_profile)
        
        # Get all active subscribers
        subscribers = await client.list_subscribers(
            creator_id=model_profile.onlyfans_user_id,
            active_only=True,
            limit=1000  # TODO: Implement pagination
        )
        
        synced_count = 0
        for sub in subscribers:
            # Get or create fan record
            fan = await self._upsert_fan(model_profile.id, sub)
            if fan:
                synced_count += 1
        
        # Update model statistics
        model_profile.subscriber_count = len(subscribers)
        model_profile.paying_subscriber_count = len([s for s in subscribers if s.price > 0])
        model_profile.last_sync_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Synced {synced_count} subscribers for model {model_profile.id}")
        return synced_count
    
    async def sync_messages(
        self,
        model_profile: ModelProfile,
        since: Optional[datetime] = None
    ) -> int:
        """Sync messages from Inflow."""
        client = await self.get_client(model_profile)
        
        # Default to last 24 hours if no since date
        if not since:
            since = datetime.utcnow() - timedelta(days=1)
        
        # Get messages
        messages = await client.list_messages(limit=1000)  # TODO: Implement pagination
        
        # Cache messages in Redis for real-time access
        cache_key = f"messages:{model_profile.id}"
        message_data = [msg.model_dump_json() for msg in messages]
        
        await redis_client.delete(cache_key)
        if message_data:
            await redis_client.lpush(cache_key, *message_data)
            await redis_client.expire(cache_key, 3600)  # 1 hour cache
        
        logger.info(f"Synced {len(messages)} messages for model {model_profile.id}")
        return len(messages)
    
    async def send_message(
        self,
        model_profile: ModelProfile,
        fan_id: str,
        content: str,
        price: Optional[float] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> InflowMessage:
        """Send a message through Inflow."""
        client = await self.get_client(model_profile)
        
        # Get fan's Inflow user ID
        fan = await self.db.get(Fan, fan_id)
        if not fan:
            raise ValueError(f"Fan {fan_id} not found")
        
        # Send message
        message = await client.send_message(
            recipient_id=fan.onlyfans_user_id,
            content=content,
            price=price,
            attachments=attachments
        )
        
        # Log transaction if it's a PPV message
        if price:
            # TODO: Create transaction record
            pass
        
        return message
    
    async def get_analytics(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ) -> InflowAnalytics:
        """Get analytics from Inflow."""
        # Check cache first
        cache_key = f"analytics:{model_profile.id}:{start_date.date()}:{end_date.date()}"
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            return InflowAnalytics.model_validate_json(cached_data)
        
        # Fetch from API
        client = await self.get_client(model_profile)
        analytics = await client.get_analytics(
            creator_id=model_profile.onlyfans_user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Cache for 1 hour
        await redis_client.setex(
            cache_key,
            3600,
            analytics.model_dump_json()
        )
        
        return analytics
    
    async def list_content(
        self,
        model_profile: ModelProfile,
        content_type: Optional[str] = None
    ) -> List[InflowContent]:
        """List content from Inflow."""
        client = await self.get_client(model_profile)
        
        return await client.list_content(
            creator_id=model_profile.onlyfans_user_id,
            content_type=content_type,
            limit=1000  # TODO: Implement pagination
        )
    
    async def _upsert_fan(
        self,
        model_id: str,
        subscription: InflowSubscription
    ) -> Optional[Fan]:
        """Create or update fan record from subscription."""
        try:
            # Get subscriber details
            client = await self.get_client(model_profile)
            user_info = await client.get_user(subscription.subscriber_id)
            
            # Check if fan exists
            fan = await self.db.query(Fan).filter(
                Fan.model_id == model_id,
                Fan.onlyfans_user_id == subscription.subscriber_id
            ).first()
            
            if not fan:
                fan = Fan(
                    model_id=model_id,
                    onlyfans_user_id=subscription.subscriber_id,
                    username=user_info.username,
                    display_name=user_info.display_name
                )
                self.db.add(fan)
            
            # Update subscription info
            fan.is_subscriber = subscription.is_active
            fan.is_paying = subscription.price > 0
            fan.subscription_price = subscription.price
            fan.subscribed_at = subscription.started_at
            fan.expires_at = subscription.expires_at
            
            await self.db.flush()
            return fan
            
        except Exception as e:
            logger.error(f"Failed to upsert fan {subscription.subscriber_id}: {e}")
            return None