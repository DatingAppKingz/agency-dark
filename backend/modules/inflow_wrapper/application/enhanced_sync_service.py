"""
Enhanced Inflow sync service with delta updates and pagination.

This service provides incremental syncing capabilities to efficiently
keep data up-to-date without re-syncing everything.
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
from core.redis import get_redis
from core.domain.models import ModelProfile, Fan, Subscription, Content
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionType,
    TransactionStatus,
    BillingCycle
)
from ..domain.schemas import (
    InflowUser,
    InflowSubscription,
    InflowTransaction,
    InflowContent,
    InflowMessage,
    InflowAnalytics
)
from .sync_service import InflowSyncService


logger = logging.getLogger(__name__)


class SyncState:
    """Tracks sync state for delta updates."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "inflow_sync:"
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
    
    async def get_sync_cursor(self, model_id: str, data_type: str) -> Optional[str]:
        """Get pagination cursor for incremental sync."""
        key = f"{self.prefix}{model_id}:{data_type}:cursor"
        return await self.redis.get(key)
    
    async def set_sync_cursor(self, model_id: str, data_type: str, cursor: str):
        """Set pagination cursor."""
        key = f"{self.prefix}{model_id}:{data_type}:cursor"
        await self.redis.setex(key, self.ttl, cursor)
    
    async def get_content_hash(self, model_id: str, content_id: str) -> Optional[str]:
        """Get stored hash of content for change detection."""
        key = f"{self.prefix}{model_id}:content:{content_id}:hash"
        return await self.redis.get(key)
    
    async def set_content_hash(self, model_id: str, content_id: str, content_hash: str):
        """Store content hash."""
        key = f"{self.prefix}{model_id}:content:{content_id}:hash"
        await self.redis.setex(key, self.ttl, content_hash)
    
    async def clear_sync_state(self, model_id: str):
        """Clear all sync state for a model."""
        pattern = f"{self.prefix}{model_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)


class EnhancedInflowSyncService(InflowSyncService):
    """Enhanced sync service with delta updates and pagination."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.sync_state = None  # Will be initialized with Redis
        self.batch_size = 100
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def initialize(self):
        """Initialize sync service with Redis connection."""
        redis = await get_redis()
        self.sync_state = SyncState(redis)
    
    async def sync_all_data_incremental(
        self,
        model_profile: ModelProfile,
        force_full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Perform incremental sync with delta updates.
        
        Args:
            model_profile: Model profile to sync
            force_full_sync: Force full sync instead of incremental
            
        Returns:
            Dict with sync results and statistics
        """
        if not self.sync_state:
            await self.initialize()
        
        logger.info(f"Starting incremental sync for model {model_profile.id}")
        
        # Clear state if forcing full sync
        if force_full_sync:
            await self.sync_state.clear_sync_state(str(model_profile.id))
        
        sync_results = {
            'subscribers': {'added': 0, 'updated': 0, 'removed': 0},
            'content': {'added': 0, 'updated': 0, 'removed': 0},
            'transactions': {'added': 0, 'errors': 0},
            'messages': {'processed': 0, 'ppv_transactions': 0},
            'duration_seconds': 0,
            'errors': []
        }
        
        start_time = datetime.utcnow()
        
        try:
            # 1. Sync subscribers with delta
            sub_results = await self.sync_subscribers_incremental(model_profile)
            sync_results['subscribers'] = sub_results
            
            # 2. Sync content with change detection
            content_results = await self.sync_content_incremental(model_profile)
            sync_results['content'] = content_results
            
            # 3. Sync transactions since last sync
            tx_results = await self.sync_transactions_incremental(model_profile)
            sync_results['transactions'] = tx_results
            
            # 4. Sync messages for PPV tracking
            msg_results = await self.sync_messages_incremental(model_profile)
            sync_results['messages'] = msg_results
            
            # 5. Update analytics
            await self.update_analytics_incremental(model_profile)
            
            # Update sync timestamp
            model_profile.last_sync_at = datetime.utcnow()
            await self.db.commit()
            
            sync_results['duration_seconds'] = (
                datetime.utcnow() - start_time
            ).total_seconds()
            
            logger.info(f"Completed incremental sync for model {model_profile.id}: {sync_results}")
            return sync_results
            
        except Exception as e:
            logger.error(f"Failed incremental sync for model {model_profile.id}: {e}")
            sync_results['errors'].append(str(e))
            await self.db.rollback()
            raise
    
    async def sync_subscribers_incremental(self, model_profile: ModelProfile) -> Dict[str, int]:
        """Sync subscribers with delta updates."""
        logger.info(f"Syncing subscribers incrementally for model {model_profile.id}")
        
        results = {'added': 0, 'updated': 0, 'removed': 0}
        client = await self.inflow_service.get_client(model_profile)
        
        # Get last sync timestamp
        last_sync = await self.sync_state.get_last_sync(
            str(model_profile.id),
            'subscribers'
        )
        
        # Fetch all current subscriber IDs for comparison
        current_sub_ids = set()
        cursor = await self.sync_state.get_sync_cursor(
            str(model_profile.id),
            'subscribers'
        )
        
        async for batch in self._paginate_subscribers(client, model_profile, cursor):
            for sub in batch['items']:
                current_sub_ids.add(sub.subscriber_id)
                
                # Check if subscriber is new or updated
                is_new = await self._process_subscriber_delta(
                    model_profile,
                    sub,
                    last_sync
                )
                
                if is_new:
                    results['added'] += 1
                else:
                    results['updated'] += 1
            
            # Save cursor for resume capability
            if batch.get('next_cursor'):
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'subscribers',
                    batch['next_cursor']
                )
            else:
                # Clear cursor when done
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'subscribers',
                    ''
                )
        
        # Find removed subscribers
        if not cursor:  # Only check removals on complete sync
            existing_subs = await self.db.execute(
                select(Fan.onlyfans_user_id).where(
                    Fan.model_id == model_profile.id
                )
            )
            existing_ids = {row[0] for row in existing_subs}
            
            removed_ids = existing_ids - current_sub_ids
            if removed_ids:
                # Mark removed subscribers as inactive
                await self.db.execute(
                    update(Subscription).where(
                        and_(
                            Subscription.model_id == model_profile.id,
                            Fan.id == Subscription.fan_id,
                            Fan.onlyfans_user_id.in_(removed_ids)
                        )
                    ).values(
                        is_active=False,
                        updated_at=datetime.utcnow()
                    )
                )
                results['removed'] = len(removed_ids)
        
        # Update last sync timestamp
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'subscribers',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def sync_content_incremental(self, model_profile: ModelProfile) -> Dict[str, int]:
        """Sync content with change detection."""
        logger.info(f"Syncing content incrementally for model {model_profile.id}")
        
        results = {'added': 0, 'updated': 0, 'removed': 0}
        client = await self.inflow_service.get_client(model_profile)
        
        cursor = await self.sync_state.get_sync_cursor(
            str(model_profile.id),
            'content'
        )
        
        current_content_ids = set()
        
        async for batch in self._paginate_content(client, cursor):
            for item in batch['items']:
                current_content_ids.add(item.id)
                
                # Calculate content hash for change detection
                content_hash = self._calculate_content_hash(item)
                stored_hash = await self.sync_state.get_content_hash(
                    str(model_profile.id),
                    item.id
                )
                
                if stored_hash != content_hash:
                    # Content changed or is new
                    is_new = stored_hash is None
                    await self._create_or_update_content(model_profile, item)
                    await self.sync_state.set_content_hash(
                        str(model_profile.id),
                        item.id,
                        content_hash
                    )
                    
                    if is_new:
                        results['added'] += 1
                    else:
                        results['updated'] += 1
            
            # Save cursor
            if batch.get('next_cursor'):
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'content',
                    batch['next_cursor']
                )
            else:
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'content',
                    ''
                )
        
        # Check for removed content
        if not cursor:
            existing_content = await self.db.execute(
                select(Content.platform_content_id).where(
                    Content.model_id == model_profile.id
                )
            )
            existing_ids = {row[0] for row in existing_content}
            
            removed_ids = existing_ids - current_content_ids
            if removed_ids:
                # Mark as deleted (soft delete)
                await self.db.execute(
                    update(Content).where(
                        and_(
                            Content.model_id == model_profile.id,
                            Content.platform_content_id.in_(removed_ids)
                        )
                    ).values(
                        is_deleted=True,
                        updated_at=datetime.utcnow()
                    )
                )
                results['removed'] = len(removed_ids)
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'content',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def sync_transactions_incremental(self, model_profile: ModelProfile) -> Dict[str, int]:
        """Sync only new transactions since last sync."""
        logger.info(f"Syncing transactions incrementally for model {model_profile.id}")
        
        results = {'added': 0, 'errors': 0}
        client = await self.inflow_service.get_client(model_profile)
        
        # Get last sync timestamp
        last_sync = await self.sync_state.get_last_sync(
            str(model_profile.id),
            'transactions'
        )
        
        if not last_sync:
            # First sync - get last 30 days
            last_sync = datetime.utcnow() - timedelta(days=30)
        
        # Add small overlap to catch any edge cases
        sync_from = last_sync - timedelta(minutes=5)
        
        cursor = await self.sync_state.get_sync_cursor(
            str(model_profile.id),
            'transactions'
        )
        
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        async for batch in self._paginate_transactions(
            client,
            start_date=sync_from,
            cursor=cursor
        ):
            for tx in batch['items']:
                # Only process if model is recipient
                if tx.to_user_id == model_profile.onlyfans_user_id:
                    try:
                        created = await self._create_financial_transaction(
                            model_profile,
                            tx,
                            current_cycle
                        )
                        if created:
                            results['added'] += 1
                    except Exception as e:
                        logger.error(f"Failed to sync transaction {tx.id}: {e}")
                        results['errors'] += 1
            
            # Save cursor
            if batch.get('next_cursor'):
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'transactions',
                    batch['next_cursor']
                )
            else:
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'transactions',
                    ''
                )
        
        # Update last sync
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'transactions',
            datetime.utcnow()
        )
        
        await self.db.commit()
        
        # Sync to analytics if new transactions
        if results['added'] > 0:
            await self.analytics_sync.sync_revenue_transactions(
                str(model_profile.id),
                start_date=sync_from
            )
        
        return results
    
    async def sync_messages_incremental(self, model_profile: ModelProfile) -> Dict[str, int]:
        """Sync messages incrementally for PPV tracking."""
        logger.info(f"Syncing messages incrementally for model {model_profile.id}")
        
        results = {'processed': 0, 'ppv_transactions': 0}
        client = await self.inflow_service.get_client(model_profile)
        
        last_sync = await self.sync_state.get_last_sync(
            str(model_profile.id),
            'messages'
        )
        
        if not last_sync:
            last_sync = datetime.utcnow() - timedelta(days=7)
        
        cursor = await self.sync_state.get_sync_cursor(
            str(model_profile.id),
            'messages'
        )
        
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        async for batch in self._paginate_messages(client, since=last_sync, cursor=cursor):
            for msg in batch['items']:
                results['processed'] += 1
                
                # Process PPV messages
                if msg.is_ppv and msg.price and msg.price > 0:
                    tx = InflowTransaction(
                        id=f"ppv_{msg.id}",
                        type="ppv_message",
                        amount=msg.price,
                        currency="USD",
                        from_user_id=msg.sender_id,
                        to_user_id=msg.recipient_id,
                        status="completed",
                        created_at=msg.created_at,
                        metadata={"message_id": msg.id, "content": msg.content[:100]}
                    )
                    
                    created = await self._create_financial_transaction(
                        model_profile,
                        tx,
                        current_cycle
                    )
                    if created:
                        results['ppv_transactions'] += 1
            
            # Save cursor
            if batch.get('next_cursor'):
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'messages',
                    batch['next_cursor']
                )
            else:
                await self.sync_state.set_sync_cursor(
                    str(model_profile.id),
                    'messages',
                    ''
                )
        
        await self.sync_state.set_last_sync(
            str(model_profile.id),
            'messages',
            datetime.utcnow()
        )
        
        await self.db.commit()
        return results
    
    async def update_analytics_incremental(self, model_profile: ModelProfile):
        """Update analytics with latest data."""
        # Get analytics for last 24 hours
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        
        analytics = await self.inflow_service.get_analytics(
            model_profile,
            start_date,
            end_date
        )
        
        # Update model statistics
        model_profile.subscriber_count = analytics.total_subscribers
        
        # Store detailed analytics in cache for dashboard
        await self._cache_analytics(model_profile.id, analytics)
    
    # Pagination helpers
    
    async def _paginate_subscribers(
        self,
        client,
        model_profile: ModelProfile,
        cursor: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through subscribers."""
        while True:
            try:
                response = await client.list_subscribers(
                    creator_id=model_profile.onlyfans_user_id or str(model_profile.id),
                    cursor=cursor,
                    limit=self.batch_size
                )
                
                yield {
                    'items': response.get('data', []),
                    'next_cursor': response.get('next_cursor')
                }
                
                cursor = response.get('next_cursor')
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Error paginating subscribers: {e}")
                raise
    
    async def _paginate_content(
        self,
        client,
        cursor: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through content."""
        while True:
            try:
                response = await client.list_content(
                    cursor=cursor,
                    limit=self.batch_size
                )
                
                yield {
                    'items': response.get('data', []),
                    'next_cursor': response.get('next_cursor')
                }
                
                cursor = response.get('next_cursor')
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Error paginating content: {e}")
                raise
    
    async def _paginate_transactions(
        self,
        client,
        start_date: datetime,
        cursor: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through transactions."""
        while True:
            try:
                response = await client.list_transactions(
                    start_date=start_date,
                    end_date=datetime.utcnow(),
                    cursor=cursor,
                    limit=self.batch_size
                )
                
                yield {
                    'items': response.get('data', []),
                    'next_cursor': response.get('next_cursor')
                }
                
                cursor = response.get('next_cursor')
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Error paginating transactions: {e}")
                raise
    
    async def _paginate_messages(
        self,
        client,
        since: datetime,
        cursor: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through messages."""
        while True:
            try:
                response = await client.list_messages(
                    since=since,
                    cursor=cursor,
                    limit=self.batch_size
                )
                
                yield {
                    'items': response.get('data', []),
                    'next_cursor': response.get('next_cursor')
                }
                
                cursor = response.get('next_cursor')
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Error paginating messages: {e}")
                raise
    
    # Helper methods
    
    async def _process_subscriber_delta(
        self,
        model_profile: ModelProfile,
        sub: InflowSubscription,
        last_sync: Optional[datetime]
    ) -> bool:
        """Process subscriber delta update. Returns True if new."""
        # Check if subscriber exists
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.model_id == model_profile.id,
                    Fan.onlyfans_user_id == sub.subscriber_id
                )
            )
        )
        existing_fan = result.scalar_one_or_none()
        
        is_new = existing_fan is None
        
        # Create or update subscription
        await self._create_or_update_subscription(model_profile, sub)
        
        return is_new
    
    def _calculate_content_hash(self, content: InflowContent) -> str:
        """Calculate hash of content for change detection."""
        # Create a stable hash of content properties
        content_data = {
            'title': content.title,
            'description': content.description,
            'price': str(content.price) if content.price else None,
            'is_ppv': content.is_ppv,
            'is_locked': content.is_locked,
            'content_type': content.content_type
        }
        
        content_str = json.dumps(content_data, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    async def _cache_analytics(self, model_id: uuid4, analytics: InflowAnalytics):
        """Cache analytics data for quick access."""
        if self.sync_state and self.sync_state.redis:
            key = f"analytics:{model_id}:latest"
            data = {
                'total_revenue': float(analytics.total_revenue),
                'total_subscribers': analytics.total_subscribers,
                'new_subscribers': analytics.new_subscribers,
                'lost_subscribers': analytics.lost_subscribers,
                'updated_at': datetime.utcnow().isoformat()
            }
            await self.sync_state.redis.setex(
                key,
                3600,  # 1 hour cache
                json.dumps(data)
            )
    
    async def _create_financial_transaction(
        self,
        model_profile: ModelProfile,
        inflow_tx: InflowTransaction,
        billing_cycle: BillingCycle
    ) -> bool:
        """Create financial transaction. Returns True if created."""
        # Check if already exists
        result = await self.db.execute(
            select(func.count(FinancialTransaction.id)).where(
                FinancialTransaction.external_reference == inflow_tx.id
            )
        )
        if result.scalar() > 0:
            return False
        
        # Call parent implementation
        await super()._create_financial_transaction(
            model_profile,
            inflow_tx,
            billing_cycle
        )
        return True