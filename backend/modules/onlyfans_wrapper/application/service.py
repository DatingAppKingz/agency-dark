"""
OnlyFans API application service.

This service provides high-level operations for integrating with OnlyFans API.
"""
import logging
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.database import get_db
from core.redis import redis_client
from core.domain.models import ModelProfile, Fan, User, FanClaim
from ..domain.interfaces import IOnlyFansClient
from ..domain.schemas import (
    OnlyFansConfig,
    OnlyFansProfile,
    OnlyFansFan,
    OnlyFansPost,
    OnlyFansMessage,
    OnlyFansTransaction,
    OnlyFansStatistics,
    OnlyFansMedia
)
from ..infrastructure.client import OnlyFansClient


logger = logging.getLogger(__name__)


class OnlyFansService:
    """Application service for OnlyFans API integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._clients: Dict[str, OnlyFansClient] = {}
    
    async def get_client(self, model_profile: ModelProfile) -> IOnlyFansClient:
        """Get or create OnlyFans client for a model."""
        if not model_profile.onlyfans_api_key:
            raise ValueError(f"Model {model_profile.id} has no OnlyFans API key configured")
        
        # Check if client already exists
        client_key = f"onlyfans_client_{model_profile.id}"
        if client_key not in self._clients:
            config = OnlyFansConfig(
                api_key=model_profile.onlyfans_api_key,
                # TODO: Make these configurable per model/agency
                base_url="https://onlyfansapi.com/api/v1",
                timeout=30,
                max_retries=3
            )
            client = OnlyFansClient(config)
            
            # Authenticate the client
            if not await client.authenticate():
                raise ValueError(f"Failed to authenticate with OnlyFans for model {model_profile.id}")
            
            self._clients[client_key] = client
        
        return self._clients[client_key]
    
    async def sync_profile(self, model_profile: ModelProfile) -> OnlyFansProfile:
        """Sync profile information from OnlyFans."""
        client = await self.get_client(model_profile)
        
        # Get profile from OnlyFans
        profile = await client.get_profile()
        
        # Update model profile
        model_profile.onlyfans_username = profile.username
        model_profile.display_name = profile.name
        model_profile.bio = profile.about
        if profile.avatar:
            model_profile.profile_photo_url = str(profile.avatar)
        if profile.header:
            model_profile.cover_photo_url = str(profile.header)
        
        # Update statistics
        model_profile.subscriber_count = profile.subscribers_count
        
        await self.db.commit()
        
        logger.info(f"Synced OnlyFans profile for model {model_profile.id}")
        return profile
    
    async def sync_fans(self, model_profile: ModelProfile) -> int:
        """Sync fans/subscribers from OnlyFans to local database."""
        client = await self.get_client(model_profile)
        
        # Get all fans (active and expired)
        all_fans = []
        for filter_type in ["active", "expired"]:
            fans = await client.get_fans(filter_type=filter_type, limit=1000)
            all_fans.extend(fans)
        
        synced_count = 0
        paying_count = 0
        
        for of_fan in all_fans:
            # Get or create fan record
            result = await self.db.execute(
                select(Fan).where(
                    and_(
                        Fan.model_id == model_profile.id,
                        Fan.onlyfans_user_id == of_fan.id
                    )
                )
            )
            fan = result.scalar_one_or_none()
            
            if not fan:
                fan = Fan(
                    model_id=model_profile.id,
                    onlyfans_user_id=of_fan.id,
                    username=of_fan.username,
                    display_name=of_fan.name
                )
                self.db.add(fan)
            
            # Update fan info
            fan.username = of_fan.username
            fan.display_name = of_fan.name
            if of_fan.avatar:
                fan.avatar_url = str(of_fan.avatar)
            
            # Update subscription info
            fan.is_subscriber = of_fan.is_subscriber
            fan.is_paying = of_fan.subscription_price and of_fan.subscription_price > 0
            fan.subscription_price = of_fan.subscription_price
            fan.subscribed_at = of_fan.subscribed_at
            fan.expires_at = of_fan.renew_at or of_fan.expired_at
            
            # Update spending stats
            fan.total_spent = of_fan.total_spent
            fan.tip_count = of_fan.tips_count
            fan.message_count = of_fan.messages_count
            fan.ppv_purchased_count = of_fan.ppv_purchased
            fan.last_active_at = of_fan.last_seen
            
            if fan.is_paying:
                paying_count += 1
            
            synced_count += 1
        
        # Update model statistics
        model_profile.subscriber_count = len([f for f in all_fans if f.is_subscriber])
        model_profile.paying_subscriber_count = paying_count
        model_profile.last_sync_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Synced {synced_count} fans for model {model_profile.id}")
        return synced_count
    
    async def get_messages(
        self,
        model_profile: ModelProfile,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[OnlyFansMessage]:
        """Get messages from OnlyFans."""
        client = await self.get_client(model_profile)
        
        # Get messages
        messages = await client.get_messages(user_id=user_id, limit=limit)
        
        # Cache messages in Redis for real-time access
        if messages:
            cache_key = f"of_messages:{model_profile.id}"
            if user_id:
                cache_key += f":{user_id}"
            
            message_data = [msg.model_dump_json() for msg in messages]
            
            await redis_client.delete(cache_key)
            await redis_client.lpush(cache_key, *message_data)
            await redis_client.expire(cache_key, 3600)  # 1 hour cache
        
        return messages
    
    async def send_message(
        self,
        model_profile: ModelProfile,
        fan_id: str,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> OnlyFansMessage:
        """Send a message through OnlyFans."""
        client = await self.get_client(model_profile)
        
        # Get fan's OnlyFans user ID
        fan = await self.db.get(Fan, fan_id)
        if not fan:
            raise ValueError(f"Fan {fan_id} not found")
        
        # Check if fan is claimed by another chatter
        result = await self.db.execute(
            select(FanClaim).where(
                and_(
                    FanClaim.fan_id == fan_id,
                    FanClaim.is_active == True
                )
            )
        )
        claim = result.scalar_one_or_none()
        
        # TODO: Check if current user has permission to message this fan
        
        # Send message
        message = await client.send_message(
            user_id=fan.onlyfans_user_id,
            text=text,
            media_ids=media_ids,
            price=price
        )
        
        # Update fan stats
        fan.message_count += 1
        if price:
            fan.ppv_purchased_count += 1
            fan.total_spent += price
        
        await self.db.commit()
        
        return message
    
    async def send_mass_message(
        self,
        model_profile: ModelProfile,
        fan_ids: List[str],
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Send mass message to multiple fans."""
        client = await self.get_client(model_profile)
        
        # Get OnlyFans user IDs for the fans
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.id.in_(fan_ids),
                    Fan.model_id == model_profile.id
                )
            )
        )
        fans = result.scalars().all()
        
        if not fans:
            raise ValueError("No valid fans found")
        
        of_user_ids = [fan.onlyfans_user_id for fan in fans]
        
        # Send mass message
        result = await client.send_mass_message(
            user_ids=of_user_ids,
            text=text,
            media_ids=media_ids,
            price=price
        )
        
        # Update fan stats
        for fan in fans:
            fan.message_count += 1
            if price:
                fan.ppv_purchased_count += 1
        
        await self.db.commit()
        
        return result
    
    async def get_statistics(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ) -> OnlyFansStatistics:
        """Get statistics from OnlyFans."""
        # Check cache first
        cache_key = f"of_stats:{model_profile.id}:{start_date.date()}:{end_date.date()}"
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            return OnlyFansStatistics.model_validate_json(cached_data)
        
        # Fetch from API
        client = await self.get_client(model_profile)
        statistics = await client.get_statistics(start_date, end_date)
        
        # Update model earnings if this is current data
        if end_date.date() >= datetime.utcnow().date():
            model_profile.total_earnings = statistics.total_earnings
        
        await self.db.commit()
        
        # Cache for 1 hour
        await redis_client.setex(
            cache_key,
            3600,
            statistics.model_dump_json()
        )
        
        return statistics
    
    async def get_fan_details(
        self,
        model_profile: ModelProfile,
        fan_id: str
    ) -> Optional[OnlyFansFan]:
        """Get detailed information about a specific fan."""
        client = await self.get_client(model_profile)
        
        # Get fan from local database first
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.id == fan_id,
                    Fan.model_id == model_profile.id
                )
            )
        )
        fan = result.scalar_one_or_none()
        
        if not fan or not fan.onlyfans_user_id:
            return None
        
        # Get fresh data from OnlyFans
        return await client.get_fan(fan.onlyfans_user_id)
    
    async def get_posts(
        self,
        model_profile: ModelProfile,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansPost]:
        """Get posts from OnlyFans."""
        client = await self.get_client(model_profile)
        
        return await client.get_posts(
            limit=limit,
            offset=offset,
            include_archived=False
        )
    
    async def get_transactions(
        self,
        model_profile: ModelProfile,
        type_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[OnlyFansTransaction]:
        """Get transactions from OnlyFans."""
        client = await self.get_client(model_profile)
        
        return await client.get_transactions(
            type_filter=type_filter,
            start_date=start_date,
            end_date=end_date,
            limit=1000  # TODO: Implement pagination
        )
    
    async def create_post(
        self,
        model_profile: ModelProfile,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> OnlyFansPost:
        """Create a post on OnlyFans."""
        client = await self.get_client(model_profile)
        
        return await client.create_post(
            text=text,
            media_ids=media_ids,
            price=price,
            is_paid=price is not None
        )
    
    async def upload_media(
        self,
        model_profile: ModelProfile,
        file: BinaryIO,
        media_type: str,
        filename: Optional[str] = None
    ) -> OnlyFansMedia:
        """Upload media to OnlyFans."""
        client = await self.get_client(model_profile)
        
        return await client.upload_media(
            file=file,
            media_type=media_type,
            filename=filename
        )