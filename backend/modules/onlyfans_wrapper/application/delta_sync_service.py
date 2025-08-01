"""
Delta sync service for efficient incremental data synchronization with OnlyFans API.

This service implements delta synchronization to sync only changed data since the last sync,
improving performance and reducing API calls.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func
from sqlalchemy.dialects.postgresql import insert

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
    OnlyFansFan,
    OnlyFansTransaction,
    OnlyFansPost,
    OnlyFansMessage,
    OnlyFansStatistics,
    OnlyFansProfile
)
from .service import OnlyFansService


logger = logging.getLogger(__name__)


class OnlyFansDeltaSyncService:
    """Delta sync service for efficient incremental data synchronization with OnlyFans."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.of_service = OnlyFansService(db)
        self.transaction_service = TransactionService(db)
        self.analytics_sync = AnalyticsDataSyncService(db)
        self.page_size = 100  # Default page size for pagination
    
    async def delta_sync(
        self,
        model_profile: ModelProfile,
        sync_options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Perform delta sync for a model, syncing only changed data since last sync.
        
        Args:
            model_profile: Model profile to sync
            sync_options: Optional dict specifying what to sync
                - fans: bool (default: True)
                - transactions: bool (default: True)
                - posts: bool (default: True)
                - messages: bool (default: False)
                - stories: bool (default: False)
                
        Returns:
            Dict with sync results and statistics
        """
        if not model_profile.onlyfans_api_key:
            raise ValueError(f"Model {model_profile.id} has no OnlyFans API key")
        
        # Default sync options
        if sync_options is None:
            sync_options = {
                'fans': True,
                'transactions': True,
                'posts': True,
                'messages': False,  # Messages can be slow
                'stories': False    # Stories are ephemeral
            }
        
        # Get last sync timestamp
        last_sync = model_profile.last_sync_at or datetime.utcnow() - timedelta(days=30)
        current_sync_time = datetime.utcnow()
        
        logger.info(
            f"Starting OnlyFans delta sync for model {model_profile.id} "
            f"from {last_sync} to {current_sync_time}"
        )
        
        sync_results = {
            'start_time': current_sync_time,
            'last_sync': last_sync,
            'synced': {},
            'errors': [],
            'duration': 0
        }
        
        try:
            # Sync profile first (always needed)
            await self.of_service.sync_profile(model_profile)
            
            # Run sync tasks concurrently where possible
            tasks = []
            
            if sync_options.get('fans', True):
                tasks.append(self._sync_fans_delta(model_profile, last_sync))
            
            if sync_options.get('transactions', True):
                tasks.append(self._sync_transactions_delta(model_profile, last_sync))
            
            if sync_options.get('posts', True):
                tasks.append(self._sync_posts_delta(model_profile, last_sync))
            
            # Execute concurrent tasks
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        sync_results['errors'].append(str(result))
                        logger.error(f"Sync task {i} failed: {result}")
                    else:
                        sync_results['synced'].update(result)
            
            # Sync messages separately (usually slower)
            if sync_options.get('messages', False):
                try:
                    msg_result = await self._sync_messages_delta(model_profile, last_sync)
                    sync_results['synced'].update(msg_result)
                except Exception as e:
                    sync_results['errors'].append(f"Message sync failed: {str(e)}")
                    logger.error(f"Failed to sync messages: {e}")
            
            # Sync stories if requested
            if sync_options.get('stories', False):
                try:
                    story_result = await self._sync_stories_delta(model_profile)
                    sync_results['synced'].update(story_result)
                except Exception as e:
                    sync_results['errors'].append(f"Story sync failed: {str(e)}")
                    logger.error(f"Failed to sync stories: {e}")
            
            # Update statistics
            await self._update_statistics_delta(model_profile, last_sync, current_sync_time)
            
            # Update last sync timestamp
            model_profile.last_sync_at = current_sync_time
            await self.db.commit()
            
            # Calculate duration
            sync_results['duration'] = (datetime.utcnow() - current_sync_time).total_seconds()
            
            logger.info(
                f"Completed OnlyFans delta sync for model {model_profile.id}: "
                f"{sync_results['synced']} in {sync_results['duration']:.2f}s"
            )
            
            return sync_results
            
        except Exception as e:
            logger.error(f"OnlyFans delta sync failed for model {model_profile.id}: {e}")
            await self.db.rollback()
            sync_results['errors'].append(f"Fatal error: {str(e)}")
            raise
    
    async def _sync_fans_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new or updated fans since last sync."""
        logger.info(f"Delta syncing OnlyFans fans for model {model_profile.id}")
        
        client = await self.of_service.get_client(model_profile)
        
        new_count = 0
        updated_count = 0
        offset = 0
        has_more = True
        
        while has_more:
            # Get fans with pagination
            fans = await client.get_fans(
                filter_type="all",
                offset=offset,
                limit=self.page_size
            )
            
            if not fans:
                has_more = False
                continue
            
            for of_fan in fans:
                # Check if fan was updated since last sync
                fan_updated = False
                if hasattr(of_fan, 'last_seen_at') and of_fan.last_seen_at:
                    fan_updated = of_fan.last_seen_at >= since
                elif hasattr(of_fan, 'subscribed_at') and of_fan.subscribed_at:
                    fan_updated = of_fan.subscribed_at >= since
                
                if not fan_updated:
                    continue
                
                # Check if fan exists
                result = await self.db.execute(
                    select(Fan).where(
                        and_(
                            Fan.model_id == model_profile.id,
                            Fan.onlyfans_user_id == of_fan.id
                        )
                    )
                )
                existing_fan = result.scalar_one_or_none()
                
                if existing_fan:
                    # Update existing fan
                    existing_fan.username = of_fan.username
                    existing_fan.display_name = of_fan.name or of_fan.username
                    existing_fan.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    # Create new fan
                    fan = Fan(
                        id=uuid4(),
                        model_id=model_profile.id,
                        onlyfans_user_id=of_fan.id,
                        username=of_fan.username,
                        display_name=of_fan.name or of_fan.username,
                        created_at=of_fan.subscribed_at or datetime.utcnow()
                    )
                    self.db.add(fan)
                    new_count += 1
                
                # Update subscription if active
                if of_fan.is_subscriber and of_fan.subscription_price:
                    await self._update_subscription_delta(model_profile, of_fan)
            
            # Check if there are more pages
            if len(fans) < self.page_size:
                has_more = False
            else:
                offset += self.page_size
            
            # Commit periodically to avoid large transactions
            if offset % (self.page_size * 5) == 0:
                await self.db.commit()
        
        await self.db.commit()
        
        return {
            'fans_new': new_count,
            'fans_updated': updated_count
        }
    
    async def _sync_transactions_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new transactions since last sync."""
        logger.info(f"Delta syncing OnlyFans transactions for model {model_profile.id}")
        
        # Get transactions from OnlyFans
        transactions = await self.of_service.get_transactions(
            model_profile,
            start_date=since,
            end_date=datetime.utcnow()
        )
        
        synced_count = 0
        skipped_count = 0
        
        # Get current billing cycle
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        for of_tx in transactions:
            # Check if transaction already exists
            result = await self.db.execute(
                select(FinancialTransaction.id).where(
                    FinancialTransaction.external_reference == of_tx.id
                )
            )
            if result.scalar_one_or_none():
                skipped_count += 1
                continue
            
            try:
                await self._create_financial_transaction(
                    model_profile,
                    of_tx,
                    current_cycle
                )
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync transaction {of_tx.id}: {e}")
        
        await self.db.commit()
        
        # Sync to analytics
        await self.analytics_sync.sync_revenue_transactions(
            str(model_profile.id),
            start_date=since
        )
        
        return {
            'transactions_new': synced_count,
            'transactions_skipped': skipped_count
        }
    
    async def _sync_posts_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new or updated posts since last sync."""
        logger.info(f"Delta syncing OnlyFans posts for model {model_profile.id}")
        
        client = await self.of_service.get_client(model_profile)
        
        new_count = 0
        updated_count = 0
        offset = 0
        has_more = True
        
        while has_more:
            # Get posts with pagination
            posts = await client.get_posts(
                offset=offset,
                limit=self.page_size
            )
            
            if not posts:
                has_more = False
                continue
            
            for post in posts:
                # Check if post is newer than last sync
                if post.posted_at and post.posted_at < since:
                    continue  # Skip old posts
                
                # Check if content exists
                result = await self.db.execute(
                    select(Content).where(
                        and_(
                            Content.model_id == model_profile.id,
                            Content.platform_content_id == post.id
                        )
                    )
                )
                existing_content = result.scalar_one_or_none()
                
                if existing_content:
                    # Update existing content
                    await self._update_content(existing_content, post)
                    updated_count += 1
                else:
                    # Create new content
                    await self._create_content(model_profile, post)
                    new_count += 1
            
            # Check if there are more pages
            if len(posts) < self.page_size:
                has_more = False
            else:
                offset += self.page_size
            
            # Commit periodically
            if offset % (self.page_size * 5) == 0:
                await self.db.commit()
        
        await self.db.commit()
        
        return {
            'posts_new': new_count,
            'posts_updated': updated_count
        }
    
    async def _sync_messages_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync messages with pagination for PPV tracking."""
        logger.info(f"Delta syncing OnlyFans messages for model {model_profile.id}")
        
        message_count = 0
        ppv_count = 0
        offset = 0
        has_more = True
        
        # Get current billing cycle
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        while has_more and offset < 1000:  # Limit to 1000 messages to avoid timeout
            # Get messages with pagination
            messages = await self.of_service.get_messages(
                model_profile,
                offset=offset,
                limit=self.page_size
            )
            
            if not messages:
                has_more = False
                continue
            
            for msg in messages:
                # Check if message is newer than last sync
                if msg.created_at < since:
                    continue
                
                message_count += 1
                
                # Process PPV messages
                if msg.is_paid and msg.price:
                    # Check if PPV transaction already exists
                    result = await self.db.execute(
                        select(FinancialTransaction.id).where(
                            FinancialTransaction.external_reference == f"ppv_msg_{msg.id}"
                        )
                    )
                    if not result.scalar_one_or_none():
                        # Create PPV transaction
                        of_tx = OnlyFansTransaction(
                            id=f"ppv_msg_{msg.id}",
                            type="ppv_message",
                            amount=msg.price,
                            currency="USD",
                            from_user=OnlyFansFan(
                                id=msg.from_user.id,
                                username=msg.from_user.username
                            ) if msg.from_user else None,
                            description=f"PPV Message: {msg.text[:50] if msg.text else 'Media'}",
                            created_at=msg.created_at
                        )
                        
                        try:
                            await self._create_financial_transaction(
                                model_profile,
                                of_tx,
                                current_cycle
                            )
                            ppv_count += 1
                        except Exception as e:
                            logger.error(f"Failed to create PPV transaction for message {msg.id}: {e}")
            
            # Check if there are more pages
            if len(messages) < self.page_size:
                has_more = False
            else:
                offset += self.page_size
            
            # Commit periodically
            if offset % (self.page_size * 5) == 0:
                await self.db.commit()
        
        if ppv_count > 0:
            await self.db.commit()
            logger.info(f"Created {ppv_count} PPV transactions from messages")
        
        return {
            'messages_processed': message_count,
            'ppv_transactions': ppv_count
        }
    
    async def _sync_stories_delta(
        self,
        model_profile: ModelProfile
    ) -> Dict[str, int]:
        """Sync current stories (ephemeral content)."""
        logger.info(f"Delta syncing OnlyFans stories for model {model_profile.id}")
        
        client = await self.of_service.get_client(model_profile)
        
        # Get current stories
        stories = await client.get_stories()
        
        story_count = len(stories) if stories else 0
        
        # Stories are ephemeral, so we just log them for now
        # Could be extended to save story metrics or archive them
        logger.info(f"Found {story_count} active stories for model {model_profile.id}")
        
        return {
            'stories_active': story_count
        }
    
    async def _update_statistics_delta(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ):
        """Update statistics for the delta sync period."""
        logger.info(f"Updating OnlyFans statistics for model {model_profile.id}")
        
        # Get statistics
        stats = await self.of_service.get_statistics(
            model_profile,
            start_date,
            end_date
        )
        
        # Update model earnings if this includes current data
        if end_date >= datetime.utcnow() - timedelta(days=1):
            model_profile.total_earnings = stats.total_earnings
            model_profile.subscriber_count = stats.subscribers_count
        
        # Log statistics for monitoring
        logger.info(
            f"OnlyFans stats update for model {model_profile.id}: "
            f"Revenue: ${stats.total_earnings}, "
            f"Subscribers: {stats.subscribers_count} "
            f"(+{stats.new_subscribers}/-{stats.expired_subscribers})"
        )
    
    async def _update_subscription_delta(
        self,
        model_profile: ModelProfile,
        of_fan: OnlyFansFan
    ):
        """Update subscription record for delta sync."""
        # Find fan
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
            logger.warning(f"Fan {of_fan.id} not found for subscription update")
            return
        
        # Upsert subscription
        stmt = insert(Subscription).values(
            id=uuid4(),
            model_id=model_profile.id,
            fan_id=fan.id,
            platform_subscription_id=f"of_{of_fan.id}_{model_profile.id}",
            price=Decimal(str(of_fan.subscription_price or 0)),
            is_active=of_fan.is_subscriber,
            started_at=of_fan.subscribed_at,
            expires_at=of_fan.renew_at or of_fan.expired_at,
            auto_renew=bool(of_fan.renew_at),
            created_at=of_fan.subscribed_at or datetime.utcnow(),
            updated_at=datetime.utcnow()
        ).on_conflict_do_update(
            index_elements=['model_id', 'fan_id'],
            set_={
                'price': Decimal(str(of_fan.subscription_price or 0)),
                'is_active': of_fan.is_subscriber,
                'expires_at': of_fan.renew_at or of_fan.expired_at,
                'auto_renew': bool(of_fan.renew_at),
                'updated_at': datetime.utcnow()
            }
        )
        
        await self.db.execute(stmt)
    
    async def _create_content(self, model_profile: ModelProfile, post: OnlyFansPost):
        """Create new content record from OnlyFans post."""
        # Determine content type
        content_type = "text"
        if post.media and len(post.media) > 0:
            media_type = post.media[0].type
            if media_type in ["photo", "image"]:
                content_type = "photo"
            elif media_type == "video":
                content_type = "video"
            elif media_type == "audio":
                content_type = "audio"
        
        content = Content(
            id=uuid4(),
            model_id=model_profile.id,
            platform_content_id=post.id,
            content_type=content_type,
            title=f"Post from {post.posted_at.strftime('%Y-%m-%d')}" if post.posted_at else "OnlyFans Post",
            description=post.text[:500] if post.text else None,
            url=post.link if post.link else f"https://onlyfans.com/post/{post.id}",
            thumbnail_url=str(post.media[0].preview) if post.media and post.media[0].preview else None,
            price=Decimal(str(post.price)) if post.price else None,
            is_ppv=post.is_paid,
            is_locked=post.is_paid,
            created_at=post.posted_at or datetime.utcnow(),
            metadata={
                'likes_count': post.likes_count,
                'comments_count': post.comments_count,
                'media_count': len(post.media) if post.media else 0
            }
        )
        self.db.add(content)
    
    async def _update_content(self, content: Content, post: OnlyFansPost):
        """Update existing content record."""
        content.description = post.text[:500] if post.text else content.description
        content.price = Decimal(str(post.price)) if post.price else content.price
        content.is_ppv = post.is_paid
        content.is_locked = post.is_paid
        content.metadata = {
            'likes_count': post.likes_count,
            'comments_count': post.comments_count,
            'media_count': len(post.media) if post.media else 0
        }
        content.updated_at = datetime.utcnow()
    
    async def _create_financial_transaction(
        self,
        model_profile: ModelProfile,
        of_tx: OnlyFansTransaction,
        billing_cycle: BillingCycle
    ):
        """Create financial transaction from OnlyFans transaction."""
        # Map OnlyFans transaction type to our type
        tx_type_map = {
            'subscription': TransactionType.REVENUE,
            'tip': TransactionType.REVENUE,
            'ppv_message': TransactionType.REVENUE,
            'ppv_post': TransactionType.REVENUE,
            'ppv_stream': TransactionType.REVENUE,
            'stream': TransactionType.REVENUE,
            'referral': TransactionType.REVENUE,
            'refund': TransactionType.REFUND,
            'chargeback': TransactionType.REFUND
        }
        
        tx_type = tx_type_map.get(of_tx.type, TransactionType.REVENUE)
        
        # Find fan if available
        fan = None
        if of_tx.from_user:
            result = await self.db.execute(
                select(Fan).where(
                    and_(
                        Fan.model_id == model_profile.id,
                        Fan.onlyfans_user_id == of_tx.from_user.id
                    )
                )
            )
            fan = result.scalar_one_or_none()
        
        # Create transaction description
        description = f"OnlyFans {of_tx.type}"
        if of_tx.description:
            description = of_tx.description
        elif fan:
            description += f" from {fan.username}"
        
        metadata = {
            'source': 'onlyfans',
            'type': of_tx.type,
            'fan_id': str(fan.id) if fan else None,
            'onlyfans_user_id': of_tx.from_user.id if of_tx.from_user else None
        }
        
        # Add any additional metadata from OnlyFans
        if hasattr(of_tx, 'metadata') and of_tx.metadata:
            metadata.update(of_tx.metadata)
        
        # Create through transaction service for proper commission calculation
        transaction = await self.transaction_service.create_transaction(
            model_id=model_profile.id,
            amount=Decimal(str(of_tx.amount)),
            currency=of_tx.currency,
            type=tx_type,
            description=description,
            billing_cycle_id=billing_cycle.id,
            user_id=fan.user_id if fan and fan.user_id else None,
            external_reference=of_tx.id,
            transaction_date=of_tx.created_at,
            metadata=metadata
        )
        
        # Mark as completed
        transaction.status = TransactionStatus.COMPLETED
        transaction.processed_at = of_tx.created_at
    
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