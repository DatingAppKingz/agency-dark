"""
Enhanced OnlyFans sync service with delta updates and pagination.

Provides efficient incremental syncing for OnlyFans data.
"""
import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func
from sqlalchemy.dialects.postgresql import insert

from core.database import get_db
from core.redis import redis_manager
from core.domain.models import ModelProfile, Fan, Subscription, Content, Message
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionType,
    TransactionStatus,
    BillingCycle
)
from modules.financial.application.transaction_service import TransactionService
from modules.analytics.application.data_sync_service import AnalyticsDataSyncService
from ..domain.schemas import (
    OnlyFansUser,
    OnlyFansSubscription,
    OnlyFansTransaction,
    OnlyFansContent,
    OnlyFansMessage,
    OnlyFansStats
)
from ..infrastructure.client_v2 import OnlyFansClient


logger = logging.getLogger(__name__)


class OnlyFansSyncState:
    """Tracks sync state for OnlyFans delta updates."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "onlyfans_sync:"
        self.ttl = 86400 * 7  # 7 days
    
    async def get_last_sync(self, model_id: str, data_type: str) -> Optional[datetime]:
        """Get last successful sync timestamp."""
        key = f"{self.prefix}{model_id}:{data_type}:last_sync"
        timestamp = await self.redis.get(key)
        if timestamp:
            return datetime.fromisoformat(timestamp)
        return None
    
    async def set_last_sync(self, model_id: str, data_type: str, timestamp: datetime):
        """Set last successful sync timestamp."""
        key = f"{self.prefix}{model_id}:{data_type}:last_sync"
        await self.redis.setex(key, self.ttl, timestamp.isoformat())
    
    async def get_sync_offset(self, model_id: str, data_type: str) -> int:
        """Get pagination offset for incremental sync."""
        key = f"{self.prefix}{model_id}:{data_type}:offset"
        offset = await self.redis.get(key)
        return int(offset) if offset else 0
    
    async def set_sync_offset(self, model_id: str, data_type: str, offset: int):
        """Set pagination offset."""
        key = f"{self.prefix}{model_id}:{data_type}:offset"
        await self.redis.setex(key, self.ttl, str(offset))
    
    async def get_message_hash(self, model_id: str, message_id: str) -> Optional[str]:
        """Get stored hash of message for duplicate detection."""
        key = f"{self.prefix}{model_id}:message:{message_id}:hash"
        return await self.redis.get(key)
    
    async def set_message_hash(self, model_id: str, message_id: str, msg_hash: str):
        """Store message hash."""
        key = f"{self.prefix}{model_id}:message:{message_id}:hash"
        await self.redis.setex(key, self.ttl, msg_hash)
    
    async def clear_sync_state(self, model_id: str):
        """Clear all sync state for a model."""
        pattern = f"{self.prefix}{model_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)


class EnhancedOnlyFansSyncService:
    """Enhanced sync service for OnlyFans with incremental updates."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.transaction_service = TransactionService(db)
        self.analytics_sync = AnalyticsDataSyncService(db)
        self.sync_state = None  # Will be initialized with Redis
        self.batch_size = 50  # OnlyFans has stricter rate limits
        self.rate_limit_delay = 0.5  # Delay between API calls
    
    async def initialize(self):
        """Initialize sync service with Redis connection."""
        redis = await get_redis()
        self.sync_state = OnlyFansSyncState(redis)
    
    async def get_client(self, model_profile: ModelProfile) -> OnlyFansClient:
        """Get authenticated OnlyFans client."""
        if not model_profile.onlyfans_api_key:
            raise ValueError(f"Model {model_profile.id} has no OnlyFans API key")
        
        return OnlyFansClient(
            auth_token=model_profile.onlyfans_api_key,
            user_id=model_profile.onlyfans_user_id
        )
    
    async def sync_all_data_incremental(
        self,
        model_profile: ModelProfile,
        force_full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Perform incremental sync with delta updates for OnlyFans.
        
        Args:
            model_profile: Model profile to sync
            force_full_sync: Force full sync instead of incremental
            
        Returns:
            Dict with sync results and statistics
        """
        if not self.sync_state:
            await self.initialize()
        
        logger.info(f"Starting OnlyFans incremental sync for model {model_profile.id}")
        
        # Clear state if forcing full sync
        if force_full_sync:
            await self.sync_state.clear_sync_state(str(model_profile.id))
        
        sync_results = {
            'fans': {'added': 0, 'updated': 0},
            'subscriptions': {'active': 0, 'expired': 0},
            'content': {'posts': 0, 'media': 0},
            'messages': {'processed': 0, 'ppv': 0},
            'transactions': {'added': 0, 'total_amount': 0},
            'duration_seconds': 0,
            'errors': []
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Get client
            client = await self.get_client(model_profile)
            
            # 1. Sync fans and subscriptions
            fan_results = await self.sync_fans_incremental(model_profile, client)
            sync_results['fans'] = fan_results
            
            # 2. Sync subscriptions
            sub_results = await self.sync_subscriptions_incremental(model_profile, client)
            sync_results['subscriptions'] = sub_results
            
            # 3. Sync content (posts and media)
            content_results = await self.sync_content_incremental(model_profile, client)
            sync_results['content'] = content_results
            
            # 4. Sync messages and PPV
            msg_results = await self.sync_messages_incremental(model_profile, client)
            sync_results['messages'] = msg_results
            
            # 5. Sync transactions
            tx_results = await self.sync_transactions_incremental(model_profile, client)
            sync_results['transactions'] = tx_results
            
            # 6. Update statistics
            await self.update_statistics(model_profile, client)
            
            # Update sync timestamp
            model_profile.last_sync_at = datetime.utcnow()
            await self.db.commit()
            
            sync_results['duration_seconds'] = (
                datetime.utcnow() - start_time
            ).total_seconds()
            
            logger.info(f"Completed OnlyFans sync for model {model_profile.id}: {sync_results}")
            return sync_results
            
        except Exception as e:
            logger.error(f"Failed OnlyFans sync for model {model_profile.id}: {e}")
            sync_results['errors'].append(str(e))
            await self.db.rollback()
            raise
    
    async def sync_fans_incremental(
        self,
        model_profile: ModelProfile,
        client: OnlyFansClient
    ) -> Dict[str, int]:
        """Sync fans with incremental updates."""
        logger.info(f"Syncing OnlyFans fans for model {model_profile.id}")
        
        results = {'added': 0, 'updated': 0}
        
        # Get last sync offset
        offset = await self.sync_state.get_sync_offset(
            str(model_profile.id),
            'fans'
        )
        
        # Get fans in batches
        while True:
            try:
                fans_data = await client.get_fans(
                    offset=offset,
                    limit=self.batch_size
                )
                
                if not fans_data or not fans_data.get('list'):
                    break
                
                for fan_data in fans_data['list']:
                    # Check if fan exists
                    result = await self.db.execute(
                        select(Fan).where(
                            and_(
                                Fan.model_id == model_profile.id,
                                Fan.onlyfans_user_id == str(fan_data['id'])
                            )
                        )
                    )
                    existing_fan = result.scalar_one_or_none()
                    
                    if not existing_fan:
                        # Create new fan
                        fan = Fan(
                            id=uuid4(),
                            model_id=model_profile.id,
                            onlyfans_user_id=str(fan_data['id']),
                            username=fan_data.get('username', ''),
                            display_name=fan_data.get('name', ''),
                            avatar_url=fan_data.get('avatar'),
                            created_at=datetime.utcnow()
                        )
                        self.db.add(fan)
                        results['added'] += 1
                    else:
                        # Update existing fan
                        existing_fan.username = fan_data.get('username', existing_fan.username)
                        existing_fan.display_name = fan_data.get('name', existing_fan.display_name)
                        existing_fan.avatar_url = fan_data.get('avatar')
                        existing_fan.updated_at = datetime.utcnow()
                        results['updated'] += 1
                
                # Update offset
                offset += len(fans_data['list'])
                await self.sync_state.set_sync_offset(
                    str(model_profile.id),
                    'fans',
                    offset
                )
                
                # Check if more data available
                if not fans_data.get('hasMore', False):
                    # Reset offset for next sync
                    await self.sync_state.set_sync_offset(
                        str(model_profile.id),
                        'fans',
                        0
                    )
                    break
                
                # Rate limit delay
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error syncing fans at offset {offset}: {e}")
                raise
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'fans',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def sync_subscriptions_incremental(
        self,
        model_profile: ModelProfile,
        client: OnlyFansClient
    ) -> Dict[str, int]:
        """Sync active subscriptions."""
        logger.info(f"Syncing OnlyFans subscriptions for model {model_profile.id}")
        
        results = {'active': 0, 'expired': 0}
        
        offset = await self.sync_state.get_sync_offset(
            str(model_profile.id),
            'subscriptions'
        )
        
        while True:
            try:
                subs_data = await client.get_subscriptions(
                    offset=offset,
                    limit=self.batch_size,
                    type='active'
                )
                
                if not subs_data or not subs_data.get('list'):
                    break
                
                for sub_data in subs_data['list']:
                    # Get or create fan
                    result = await self.db.execute(
                        select(Fan).where(
                            and_(
                                Fan.model_id == model_profile.id,
                                Fan.onlyfans_user_id == str(sub_data['id'])
                            )
                        )
                    )
                    fan = result.scalar_one_or_none()
                    
                    if not fan:
                        # Create fan from subscription data
                        fan = Fan(
                            id=uuid4(),
                            model_id=model_profile.id,
                            onlyfans_user_id=str(sub_data['id']),
                            username=sub_data.get('username', ''),
                            display_name=sub_data.get('name', '')
                        )
                        self.db.add(fan)
                        await self.db.flush()
                    
                    # Create or update subscription
                    sub_info = sub_data.get('subscribedByData', {})
                    if sub_info:
                        stmt = insert(Subscription).values(
                            id=uuid4(),
                            model_id=model_profile.id,
                            fan_id=fan.id,
                            platform_subscription_id=str(sub_data['id']),
                            price=Decimal(str(sub_info.get('price', 0))),
                            is_active=True,
                            started_at=datetime.fromisoformat(
                                sub_info.get('subscribedAt', datetime.utcnow().isoformat())
                            ),
                            expires_at=datetime.fromisoformat(
                                sub_info.get('expiredAt', datetime.utcnow().isoformat())
                            ) if sub_info.get('expiredAt') else None,
                            auto_renew=sub_info.get('autoRenew', True),
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        ).on_conflict_do_update(
                            index_elements=['model_id', 'fan_id'],
                            set_={
                                'is_active': True,
                                'expires_at': datetime.fromisoformat(
                                    sub_info.get('expiredAt', datetime.utcnow().isoformat())
                                ) if sub_info.get('expiredAt') else None,
                                'auto_renew': sub_info.get('autoRenew', True),
                                'updated_at': datetime.utcnow()
                            }
                        )
                        await self.db.execute(stmt)
                        results['active'] += 1
                
                # Update offset
                offset += len(subs_data['list'])
                await self.sync_state.set_sync_offset(
                    str(model_profile.id),
                    'subscriptions',
                    offset
                )
                
                if not subs_data.get('hasMore', False):
                    await self.sync_state.set_sync_offset(
                        str(model_profile.id),
                        'subscriptions',
                        0
                    )
                    break
                
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error syncing subscriptions at offset {offset}: {e}")
                raise
        
        # Mark expired subscriptions
        await self.db.execute(
            update(Subscription).where(
                and_(
                    Subscription.model_id == model_profile.id,
                    Subscription.expires_at < datetime.utcnow(),
                    Subscription.is_active == True
                )
            ).values(
                is_active=False,
                updated_at=datetime.utcnow()
            )
        )
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'subscriptions',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def sync_content_incremental(
        self,
        model_profile: ModelProfile,
        client: OnlyFansClient
    ) -> Dict[str, int]:
        """Sync content posts and media."""
        logger.info(f"Syncing OnlyFans content for model {model_profile.id}")
        
        results = {'posts': 0, 'media': 0}
        
        # Get last sync timestamp for content
        last_sync = await self.sync_state.get_last_sync(
            str(model_profile.id),
            'content'
        )
        
        if not last_sync:
            last_sync = datetime.utcnow() - timedelta(days=30)
        
        offset = await self.sync_state.get_sync_offset(
            str(model_profile.id),
            'content'
        )
        
        while True:
            try:
                posts_data = await client.get_posts(
                    offset=offset,
                    limit=self.batch_size
                )
                
                if not posts_data or not posts_data.get('list'):
                    break
                
                for post in posts_data['list']:
                    # Only process posts created after last sync
                    post_date = datetime.fromisoformat(post.get('createdAt', datetime.utcnow().isoformat()))
                    if post_date <= last_sync:
                        continue
                    
                    # Create or update content
                    content_id = str(post['id'])
                    
                    result = await self.db.execute(
                        select(Content).where(
                            and_(
                                Content.model_id == model_profile.id,
                                Content.platform_content_id == content_id
                            )
                        )
                    )
                    existing_content = result.scalar_one_or_none()
                    
                    if not existing_content:
                        content = Content(
                            id=uuid4(),
                            model_id=model_profile.id,
                            platform_content_id=content_id,
                            content_type='post',
                            title=post.get('text', '')[:100],  # First 100 chars as title
                            description=post.get('text', ''),
                            url=f"https://onlyfans.com/{post['id']}",
                            price=Decimal(str(post.get('price', 0))) if post.get('price') else None,
                            is_ppv=bool(post.get('price', 0) > 0),
                            is_locked=post.get('isLocked', False),
                            created_at=post_date,
                            metadata={
                                'likes': post.get('favoritesCount', 0),
                                'comments': post.get('commentsCount', 0),
                                'media_count': len(post.get('media', []))
                            }
                        )
                        self.db.add(content)
                        results['posts'] += 1
                    else:
                        # Update metrics
                        existing_content.metadata = {
                            'likes': post.get('favoritesCount', 0),
                            'comments': post.get('commentsCount', 0),
                            'media_count': len(post.get('media', []))
                        }
                        existing_content.updated_at = datetime.utcnow()
                    
                    # Process media
                    for media in post.get('media', []):
                        results['media'] += 1
                
                # Update offset
                offset += len(posts_data['list'])
                await self.sync_state.set_sync_offset(
                    str(model_profile.id),
                    'content',
                    offset
                )
                
                if not posts_data.get('hasMore', False):
                    await self.sync_state.set_sync_offset(
                        str(model_profile.id),
                        'content',
                        0
                    )
                    break
                
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error syncing content at offset {offset}: {e}")
                raise
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'content',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def sync_messages_incremental(
        self,
        model_profile: ModelProfile,
        client: OnlyFansClient
    ) -> Dict[str, int]:
        """Sync messages and track PPV."""
        logger.info(f"Syncing OnlyFans messages for model {model_profile.id}")
        
        results = {'processed': 0, 'ppv': 0}
        
        # Get recent chats
        offset = 0
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        while True:
            try:
                chats_data = await client.get_chats(
                    offset=offset,
                    limit=self.batch_size
                )
                
                if not chats_data or not chats_data.get('list'):
                    break
                
                # Process each chat
                for chat in chats_data['list']:
                    user_id = str(chat['withUser']['id'])
                    
                    # Get messages in chat
                    messages = await client.get_messages(
                        user_id=user_id,
                        limit=20  # Recent messages only
                    )
                    
                    if messages and messages.get('list'):
                        for msg in messages['list']:
                            # Check if already processed
                            msg_id = str(msg['id'])
                            msg_hash = self._calculate_message_hash(msg)
                            
                            stored_hash = await self.sync_state.get_message_hash(
                                str(model_profile.id),
                                msg_id
                            )
                            
                            if stored_hash == msg_hash:
                                continue  # Already processed
                            
                            results['processed'] += 1
                            
                            # Check for PPV
                            if msg.get('price', 0) > 0 and msg.get('isPaid'):
                                # Create PPV transaction
                                await self._create_ppv_transaction(
                                    model_profile,
                                    msg,
                                    user_id,
                                    current_cycle
                                )
                                results['ppv'] += 1
                            
                            # Store hash
                            await self.sync_state.set_message_hash(
                                str(model_profile.id),
                                msg_id,
                                msg_hash
                            )
                
                offset += len(chats_data['list'])
                
                if not chats_data.get('hasMore', False):
                    break
                
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error syncing messages: {e}")
                raise
        
        await self.db.commit()
        return results
    
    async def sync_transactions_incremental(
        self,
        model_profile: ModelProfile,
        client: OnlyFansClient
    ) -> Dict[str, Any]:
        """Sync financial transactions."""
        logger.info(f"Syncing OnlyFans transactions for model {model_profile.id}")
        
        results = {'added': 0, 'total_amount': Decimal('0')}
        
        # Get transactions (tips, subscriptions, PPV)
        offset = await self.sync_state.get_sync_offset(
            str(model_profile.id),
            'transactions'
        )
        
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        while True:
            try:
                tx_data = await client.get_transactions(
                    offset=offset,
                    limit=self.batch_size
                )
                
                if not tx_data or not tx_data.get('list'):
                    break
                
                for tx in tx_data['list']:
                    # Check if already exists
                    ext_ref = f"of_{tx['id']}"
                    result = await self.db.execute(
                        select(func.count(FinancialTransaction.id)).where(
                            FinancialTransaction.external_reference == ext_ref
                        )
                    )
                    if result.scalar() > 0:
                        continue
                    
                    # Create transaction
                    amount = Decimal(str(tx.get('amount', 0)))
                    tx_type = self._map_transaction_type(tx.get('type', ''))
                    
                    # Find fan
                    fan = None
                    if tx.get('fromUser'):
                        result = await self.db.execute(
                            select(Fan).where(
                                and_(
                                    Fan.model_id == model_profile.id,
                                    Fan.onlyfans_user_id == str(tx['fromUser']['id'])
                                )
                            )
                        )
                        fan = result.scalar_one_or_none()
                    
                    transaction = await self.transaction_service.create_transaction(
                        model_id=model_profile.id,
                        amount=amount,
                        currency='USD',
                        type=tx_type,
                        description=f"OnlyFans {tx.get('type', 'transaction')}",
                        billing_cycle_id=current_cycle.id,
                        user_id=fan.user_id if fan and fan.user_id else None,
                        external_reference=ext_ref,
                        transaction_date=datetime.fromisoformat(
                            tx.get('createdAt', datetime.utcnow().isoformat())
                        ),
                        metadata={
                            'source': 'onlyfans',
                            'type': tx.get('type'),
                            'fan_id': str(fan.id) if fan else None
                        }
                    )
                    
                    results['added'] += 1
                    results['total_amount'] += amount
                
                offset += len(tx_data['list'])
                await self.sync_state.set_sync_offset(
                    str(model_profile.id),
                    'transactions',
                    offset
                )
                
                if not tx_data.get('hasMore', False):
                    await self.sync_state.set_sync_offset(
                        str(model_profile.id),
                        'transactions',
                        0
                    )
                    break
                
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error syncing transactions: {e}")
                raise
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'transactions',
            datetime.utcnow()
        )
        
        await self.db.commit()
        
        # Sync to analytics
        if results['added'] > 0:
            await self.analytics_sync.sync_revenue_transactions(
                str(model_profile.id),
                start_date=datetime.utcnow() - timedelta(days=1)
            )
        
        return results
    
    async def update_statistics(self, model_profile: ModelProfile, client: OnlyFansClient):
        """Update model statistics from OnlyFans."""
        try:
            stats = await client.get_account_stats()
            
            if stats:
                model_profile.subscriber_count = stats.get('subscribersCount', 0)
                
                # Cache detailed stats
                await self._cache_statistics(model_profile.id, stats)
        except Exception as e:
            logger.error(f"Failed to update statistics: {e}")
    
    # Helper methods
    
    def _calculate_message_hash(self, message: Dict[str, Any]) -> str:
        """Calculate hash of message for duplicate detection."""
        msg_data = {
            'id': message.get('id'),
            'text': message.get('text', ''),
            'price': message.get('price', 0),
            'isPaid': message.get('isPaid', False),
            'createdAt': message.get('createdAt')
        }
        msg_str = json.dumps(msg_data, sort_keys=True)
        return hashlib.sha256(msg_str.encode()).hexdigest()
    
    def _map_transaction_type(self, of_type: str) -> TransactionType:
        """Map OnlyFans transaction type to our type."""
        type_map = {
            'subscribe': TransactionType.REVENUE,
            'tip': TransactionType.REVENUE,
            'post': TransactionType.REVENUE,
            'message': TransactionType.REVENUE,
            'stream': TransactionType.REVENUE,
            'refund': TransactionType.REFUND,
            'chargeback': TransactionType.REFUND
        }
        return type_map.get(of_type.lower(), TransactionType.REVENUE)
    
    async def _create_ppv_transaction(
        self,
        model_profile: ModelProfile,
        message: Dict[str, Any],
        user_id: str,
        billing_cycle: BillingCycle
    ):
        """Create transaction for PPV message."""
        # Find fan
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.model_id == model_profile.id,
                    Fan.onlyfans_user_id == user_id
                )
            )
        )
        fan = result.scalar_one_or_none()
        
        ext_ref = f"of_ppv_{message['id']}"
        
        # Check if already exists
        result = await self.db.execute(
            select(func.count(FinancialTransaction.id)).where(
                FinancialTransaction.external_reference == ext_ref
            )
        )
        if result.scalar() > 0:
            return
        
        await self.transaction_service.create_transaction(
            model_id=model_profile.id,
            amount=Decimal(str(message['price'])),
            currency='USD',
            type=TransactionType.REVENUE,
            description=f"PPV Message",
            billing_cycle_id=billing_cycle.id,
            user_id=fan.user_id if fan and fan.user_id else None,
            external_reference=ext_ref,
            transaction_date=datetime.fromisoformat(
                message.get('createdAt', datetime.utcnow().isoformat())
            ),
            metadata={
                'source': 'onlyfans',
                'type': 'ppv_message',
                'message_id': message['id'],
                'fan_id': str(fan.id) if fan else None
            }
        )
    
    async def _get_or_create_billing_cycle(
        self,
        model_id: uuid4,
        date: datetime
    ) -> BillingCycle:
        """Get or create billing cycle for a given date."""
        # Find billing cycle that contains this date
        result = await self.db.execute(
            select(BillingCycle).where(
                and_(
                    BillingCycle.model_id == model_id,
                    BillingCycle.start_date <= date,
                    BillingCycle.end_date >= date
                )
            )
        )
        cycle = result.scalar_one_or_none()
        
        if not cycle:
            # Create new monthly cycle
            start_date = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if date.month == 12:
                end_date = date.replace(year=date.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_date = date.replace(month=date.month + 1, day=1) - timedelta(seconds=1)
            
            cycle = BillingCycle(
                id=uuid4(),
                model_id=model_id,
                start_date=start_date,
                end_date=end_date,
                cycle_number=f"{date.year}-{date.month:02d}"
            )
            self.db.add(cycle)
            await self.db.flush()
        
        return cycle
    
    async def _cache_statistics(self, model_id: uuid4, stats: Dict[str, Any]):
        """Cache OnlyFans statistics."""
        if self.sync_state and self.sync_state.redis:
            key = f"of_stats:{model_id}:latest"
            data = {
                'subscribers_count': stats.get('subscribersCount', 0),
                'photos_count': stats.get('photosCount', 0),
                'videos_count': stats.get('videosCount', 0),
                'posts_count': stats.get('postsCount', 0),
                'updated_at': datetime.utcnow().isoformat()
            }
            await self.sync_state.redis.setex(
                key,
                3600,  # 1 hour cache
                json.dumps(data)
            )