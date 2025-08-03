"""
Enhanced OnlyFans API sync service for financial data integration.

This service syncs financial data from OnlyFans to our local database,
creating proper financial transactions, updating analytics, and maintaining
data consistency.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from core.domain.models import ModelProfile, Fan, Subscription, Content
from models.financial import TransactionType, TransactionStatus
from modules.financial.domain.models import FinancialTransaction, BillingCycle
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


class OnlyFansSyncService:
    """Enhanced sync service for OnlyFans API integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.of_service = OnlyFansService(db)
        self.transaction_service = TransactionService(db)
        self.analytics_sync = AnalyticsDataSyncService(db)
    
    async def sync_all_data(
        self,
        model_profile: ModelProfile,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sync_messages: bool = True
    ) -> Dict[str, int]:
        """
        Sync all data from OnlyFans for a model.
        
        Args:
            model_profile: Model profile to sync
            start_date: Start date for transaction sync (default: last 30 days)
            end_date: End date for transaction sync (default: now)
            sync_messages: Whether to sync messages (can be slow)
            
        Returns:
            Dict with sync counts for each data type
        """
        if not model_profile.onlyfans_api_key:
            raise ValueError(f"Model {model_profile.id} has no OnlyFans API key")
        
        # Default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        logger.info(f"Starting OnlyFans sync for model {model_profile.id} from {start_date} to {end_date}")
        
        sync_results = {}
        
        try:
            # 1. Sync profile
            await self.sync_profile(model_profile)
            sync_results['profile'] = 1
            
            # 2. Sync fans/subscribers
            sync_results['fans'] = await self.sync_fans(model_profile)
            
            # 3. Sync transactions
            sync_results['transactions'] = await self.sync_transactions(
                model_profile,
                start_date,
                end_date
            )
            
            # 4. Sync posts (for content tracking)
            sync_results['posts'] = await self.sync_posts(model_profile)
            
            # 5. Sync messages (optional - can be slow)
            if sync_messages:
                sync_results['messages'] = await self.sync_recent_messages(
                    model_profile,
                    since=start_date
                )
            
            # 6. Update statistics
            await self.update_statistics(model_profile, start_date, end_date)
            
            # Update last sync timestamp
            model_profile.last_sync_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(f"Completed OnlyFans sync for model {model_profile.id}: {sync_results}")
            return sync_results
            
        except Exception as e:
            logger.error(f"Failed to sync OnlyFans data for model {model_profile.id}: {e}")
            await self.db.rollback()
            raise
    
    async def sync_profile(self, model_profile: ModelProfile) -> OnlyFansProfile:
        """Sync and update model profile from OnlyFans."""
        logger.info(f"Syncing OnlyFans profile for model {model_profile.id}")
        
        # Use existing service method
        profile = await self.of_service.sync_profile(model_profile)
        
        # Update OnlyFans-specific fields
        model_profile.onlyfans_user_id = profile.id
        
        return profile
    
    async def sync_fans(self, model_profile: ModelProfile) -> int:
        """Sync fans/subscribers from OnlyFans."""
        logger.info(f"Syncing OnlyFans fans for model {model_profile.id}")
        
        # Use existing service method which already handles fan creation
        fan_count = await self.of_service.sync_fans(model_profile)
        
        # Additionally sync subscription records
        client = await self.of_service.get_client(model_profile)
        
        # Get active subscribers
        active_fans = await client.get_fans(filter_type="active", limit=1000)
        
        for of_fan in active_fans:
            if of_fan.is_subscriber and of_fan.subscription_price:
                await self._create_or_update_subscription(model_profile, of_fan)
        
        return fan_count
    
    async def sync_transactions(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Sync financial transactions from OnlyFans."""
        logger.info(f"Syncing OnlyFans transactions for model {model_profile.id}")
        
        # Get transactions from OnlyFans
        transactions = await self.of_service.get_transactions(
            model_profile,
            start_date=start_date,
            end_date=end_date
        )
        
        synced_count = 0
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            end_date
        )
        
        for of_tx in transactions:
            try:
                await self._create_financial_transaction(
                    model_profile,
                    of_tx,
                    current_cycle
                )
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync transaction {of_tx.id}: {e}")
                continue
        
        await self.db.commit()
        
        # Sync to analytics
        await self.analytics_sync.sync_revenue_transactions(
            str(model_profile.id),
            start_date=start_date
        )
        
        return synced_count
    
    async def sync_posts(self, model_profile: ModelProfile) -> int:
        """Sync posts from OnlyFans for content tracking."""
        logger.info(f"Syncing OnlyFans posts for model {model_profile.id}")
        
        client = await self.of_service.get_client(model_profile)
        posts = await client.get_posts(limit=100)
        
        synced_count = 0
        for post in posts:
            try:
                await self._create_or_update_content(model_profile, post)
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync post {post.id}: {e}")
                continue
        
        await self.db.commit()
        return synced_count
    
    async def sync_recent_messages(
        self,
        model_profile: ModelProfile,
        since: datetime,
        limit: int = 1000
    ) -> int:
        """Sync recent messages to track PPV sales."""
        logger.info(f"Syncing OnlyFans messages for model {model_profile.id}")
        
        # Get messages
        messages = await self.of_service.get_messages(model_profile, limit=limit)
        
        ppv_count = 0
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        for msg in messages:
            # Only process PPV messages sent after 'since' date
            if msg.is_paid and msg.price and msg.created_at >= since:
                # Create transaction for PPV message
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
        
        if ppv_count > 0:
            await self.db.commit()
            logger.info(f"Created {ppv_count} PPV transactions from messages")
        
        return len(messages)
    
    async def update_statistics(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ):
        """Update statistics from OnlyFans."""
        logger.info(f"Updating OnlyFans statistics for model {model_profile.id}")
        
        # Get statistics
        stats = await self.of_service.get_statistics(
            model_profile,
            start_date,
            end_date
        )
        
        # Log statistics for monitoring
        logger.info(
            f"OnlyFans stats for model {model_profile.id}: "
            f"Revenue: ${stats.total_earnings}, "
            f"Subscribers: {stats.subscribers_count} "
            f"(+{stats.new_subscribers}/-{stats.expired_subscribers})"
        )
        
        # Update model earnings if this includes current data
        if end_date >= datetime.utcnow() - timedelta(days=1):
            model_profile.total_earnings = stats.total_earnings
    
    async def _create_or_update_subscription(
        self,
        model_profile: ModelProfile,
        of_fan: OnlyFansFan
    ):
        """Create or update subscription record."""
        # Find fan by OnlyFans user ID
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
            logger.warning(f"Fan {of_fan.id} not found for subscription sync")
            return
        
        # Create subscription ID from fan and model IDs
        subscription_id = str(uuid4())
        
        # Upsert subscription
        stmt = insert(Subscription).values(
            id=subscription_id,
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
    
    async def _create_or_update_content(
        self,
        model_profile: ModelProfile,
        of_post: OnlyFansPost
    ):
        """Create or update content record from OnlyFans post."""
        # Determine content type
        content_type = "text"
        if of_post.media and len(of_post.media) > 0:
            # Use first media type
            media_type = of_post.media[0].type
            if media_type in ["photo", "image"]:
                content_type = "photo"
            elif media_type == "video":
                content_type = "video"
            elif media_type == "audio":
                content_type = "audio"
        
        # Check if content exists
        result = await self.db.execute(
            select(Content).where(
                and_(
                    Content.model_id == model_profile.id,
                    Content.platform_content_id == of_post.id
                )
            )
        )
        content = result.scalar_one_or_none()
        
        if not content:
            content = Content(
                id=uuid4(),
                model_id=model_profile.id,
                platform_content_id=of_post.id,
                content_type=content_type,
                title=f"Post from {of_post.posted_at.strftime('%Y-%m-%d')}" if of_post.posted_at else "OnlyFans Post",
                description=of_post.text[:500] if of_post.text else None,
                url=of_post.link if of_post.link else f"https://onlyfans.com/post/{of_post.id}",
                thumbnail_url=str(of_post.media[0].preview) if of_post.media and of_post.media[0].preview else None,
                price=Decimal(str(of_post.price)) if of_post.price else None,
                is_ppv=of_post.is_paid,
                is_locked=of_post.is_paid,
                created_at=of_post.posted_at or datetime.utcnow(),
                metadata={
                    'likes_count': of_post.likes_count,
                    'comments_count': of_post.comments_count,
                    'media_count': len(of_post.media) if of_post.media else 0
                }
            )
            self.db.add(content)
        else:
            # Update existing content
            content.description = of_post.text[:500] if of_post.text else content.description
            content.price = Decimal(str(of_post.price)) if of_post.price else content.price
            content.is_ppv = of_post.is_paid
            content.is_locked = of_post.is_paid
            content.metadata = {
                'likes_count': of_post.likes_count,
                'comments_count': of_post.comments_count,
                'media_count': len(of_post.media) if of_post.media else 0
            }
            content.updated_at = datetime.utcnow()
    
    async def _create_financial_transaction(
        self,
        model_profile: ModelProfile,
        of_tx: OnlyFansTransaction,
        billing_cycle: BillingCycle
    ):
        """Create financial transaction from OnlyFans transaction."""
        # Check if transaction already exists
        result = await self.db.execute(
            select(FinancialTransaction).where(
                FinancialTransaction.external_reference == of_tx.id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.debug(f"Transaction {of_tx.id} already exists, skipping")
            return
        
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