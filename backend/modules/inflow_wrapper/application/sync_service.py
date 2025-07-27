"""
Enhanced Inflow API sync service for financial data integration.

This service syncs financial data from Inflow to our local database,
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
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionType,
    TransactionStatus,
    BillingCycle
)
from modules.financial.application.transaction_service import TransactionService
from modules.analytics.application.data_sync_service import AnalyticsDataSyncService
from ..domain.schemas import (
    InflowUser,
    InflowSubscription,
    InflowTransaction,
    InflowContent,
    InflowMessage,
    InflowAnalytics
)
from .service import InflowService


logger = logging.getLogger(__name__)


class InflowSyncService:
    """Enhanced sync service for Inflow API integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inflow_service = InflowService(db)
        self.transaction_service = TransactionService(db)
        self.analytics_sync = AnalyticsDataSyncService(db)
    
    async def sync_all_data(
        self,
        model_profile: ModelProfile,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Sync all data from Inflow for a model.
        
        Args:
            model_profile: Model profile to sync
            start_date: Start date for transaction sync (default: last 30 days)
            end_date: End date for transaction sync (default: now)
            
        Returns:
            Dict with sync counts for each data type
        """
        if not model_profile.inflow_api_key:
            raise ValueError(f"Model {model_profile.id} has no Inflow API key")
        
        # Default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        logger.info(f"Starting Inflow sync for model {model_profile.id} from {start_date} to {end_date}")
        
        sync_results = {}
        
        try:
            # 1. Sync subscribers/fans
            sync_results['subscribers'] = await self.sync_subscribers(model_profile)
            
            # 2. Sync content
            sync_results['content'] = await self.sync_content(model_profile)
            
            # 3. Sync transactions
            sync_results['transactions'] = await self.sync_transactions(
                model_profile,
                start_date,
                end_date
            )
            
            # 4. Sync messages (for PPV tracking)
            sync_results['messages'] = await self.sync_messages(
                model_profile,
                start_date
            )
            
            # 5. Update analytics
            await self.update_analytics(model_profile, start_date, end_date)
            
            # Update last sync timestamp
            model_profile.last_sync_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(f"Completed Inflow sync for model {model_profile.id}: {sync_results}")
            return sync_results
            
        except Exception as e:
            logger.error(f"Failed to sync Inflow data for model {model_profile.id}: {e}")
            await self.db.rollback()
            raise
    
    async def sync_subscribers(self, model_profile: ModelProfile) -> int:
        """Sync subscribers from Inflow and create/update fan records."""
        logger.info(f"Syncing subscribers for model {model_profile.id}")
        
        subscribers = await self.inflow_service.sync_subscribers(model_profile)
        
        # Additionally sync subscription details
        client = await self.inflow_service.get_client(model_profile)
        active_subs = await client.list_subscribers(
            creator_id=model_profile.onlyfans_user_id or str(model_profile.id),
            active_only=True,
            limit=1000
        )
        
        # Update subscription records
        for sub in active_subs:
            await self._create_or_update_subscription(model_profile, sub)
        
        return subscribers
    
    async def sync_content(self, model_profile: ModelProfile) -> int:
        """Sync content from Inflow."""
        logger.info(f"Syncing content for model {model_profile.id}")
        
        content_items = await self.inflow_service.list_content(model_profile)
        synced_count = 0
        
        for item in content_items:
            try:
                await self._create_or_update_content(model_profile, item)
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync content {item.id}: {e}")
                continue
        
        await self.db.commit()
        return synced_count
    
    async def sync_transactions(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Sync financial transactions from Inflow."""
        logger.info(f"Syncing transactions for model {model_profile.id}")
        
        client = await self.inflow_service.get_client(model_profile)
        
        # Get all transactions in date range
        transactions = await client.list_transactions(
            start_date=start_date,
            end_date=end_date,
            limit=1000  # TODO: Implement pagination
        )
        
        synced_count = 0
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            end_date
        )
        
        for tx in transactions:
            try:
                # Only process transactions where model is the recipient
                if tx.to_user_id == model_profile.onlyfans_user_id:
                    await self._create_financial_transaction(
                        model_profile,
                        tx,
                        current_cycle
                    )
                    synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync transaction {tx.id}: {e}")
                continue
        
        await self.db.commit()
        
        # Sync to analytics
        await self.analytics_sync.sync_revenue_transactions(
            str(model_profile.id),
            start_date=start_date
        )
        
        return synced_count
    
    async def sync_messages(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> int:
        """Sync messages to track PPV sales."""
        logger.info(f"Syncing messages for model {model_profile.id}")
        
        # Use existing service method
        message_count = await self.inflow_service.sync_messages(
            model_profile,
            since
        )
        
        # Additionally, get PPV messages and create transactions
        client = await self.inflow_service.get_client(model_profile)
        messages = await client.list_messages(limit=1000)
        
        ppv_count = 0
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        for msg in messages:
            if msg.is_ppv and msg.price and msg.created_at >= since:
                # Create transaction for PPV message
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
                
                await self._create_financial_transaction(
                    model_profile,
                    tx,
                    current_cycle
                )
                ppv_count += 1
        
        if ppv_count > 0:
            await self.db.commit()
            logger.info(f"Created {ppv_count} PPV transactions from messages")
        
        return message_count
    
    async def update_analytics(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ):
        """Update analytics from Inflow data."""
        logger.info(f"Updating analytics for model {model_profile.id}")
        
        # Get analytics from Inflow
        analytics = await self.inflow_service.get_analytics(
            model_profile,
            start_date,
            end_date
        )
        
        # Store analytics data in a separate analytics record or cache
        # For now, we'll just log it
        logger.info(f"Inflow analytics for model {model_profile.id}: "
                   f"Revenue: ${analytics.total_revenue}, "
                   f"Subscribers: {analytics.total_subscribers} "
                   f"(+{analytics.new_subscribers}/-{analytics.lost_subscribers})")
        
        # Update model statistics
        model_profile.subscriber_count = analytics.total_subscribers
        
        await self.db.flush()
    
    async def _create_or_update_subscription(
        self,
        model_profile: ModelProfile,
        inflow_sub: InflowSubscription
    ):
        """Create or update subscription record."""
        # Find fan by Inflow user ID
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.model_id == model_profile.id,
                    Fan.onlyfans_user_id == inflow_sub.subscriber_id
                )
            )
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            # Create fan if doesn't exist
            client = await self.inflow_service.get_client(model_profile)
            user_info = await client.get_user(inflow_sub.subscriber_id)
            
            fan = Fan(
                id=uuid4(),
                model_id=model_profile.id,
                onlyfans_user_id=inflow_sub.subscriber_id,
                username=user_info.username,
                display_name=user_info.display_name
            )
            self.db.add(fan)
            await self.db.flush()
        
        # Update or create subscription
        stmt = insert(Subscription).values(
            id=uuid4(),
            model_id=model_profile.id,
            fan_id=fan.id,
            platform_subscription_id=inflow_sub.id,
            price=Decimal(str(inflow_sub.price)),
            is_active=inflow_sub.is_active,
            started_at=inflow_sub.started_at,
            expires_at=inflow_sub.expires_at,
            auto_renew=inflow_sub.auto_renew,
            created_at=inflow_sub.started_at,
            updated_at=datetime.utcnow()
        ).on_conflict_do_update(
            index_elements=['model_id', 'fan_id'],
            set_={
                'platform_subscription_id': inflow_sub.id,
                'price': Decimal(str(inflow_sub.price)),
                'is_active': inflow_sub.is_active,
                'expires_at': inflow_sub.expires_at,
                'auto_renew': inflow_sub.auto_renew,
                'updated_at': datetime.utcnow()
            }
        )
        
        await self.db.execute(stmt)
    
    async def _create_or_update_content(
        self,
        model_profile: ModelProfile,
        inflow_content: InflowContent
    ):
        """Create or update content record."""
        # Check if content exists
        result = await self.db.execute(
            select(Content).where(
                and_(
                    Content.model_id == model_profile.id,
                    Content.platform_content_id == inflow_content.id
                )
            )
        )
        content = result.scalar_one_or_none()
        
        if not content:
            content = Content(
                id=uuid4(),
                model_id=model_profile.id,
                platform_content_id=inflow_content.id,
                content_type=inflow_content.content_type,
                title=inflow_content.title,
                description=inflow_content.description,
                url=str(inflow_content.url),
                thumbnail_url=str(inflow_content.thumbnail_url) if inflow_content.thumbnail_url else None,
                price=Decimal(str(inflow_content.price)) if inflow_content.price else None,
                is_ppv=inflow_content.is_ppv,
                is_locked=inflow_content.is_locked,
                created_at=inflow_content.created_at,
                metadata=inflow_content.metadata
            )
            self.db.add(content)
        else:
            # Update existing content
            content.title = inflow_content.title
            content.description = inflow_content.description
            content.url = str(inflow_content.url)
            content.thumbnail_url = str(inflow_content.thumbnail_url) if inflow_content.thumbnail_url else None
            content.price = Decimal(str(inflow_content.price)) if inflow_content.price else None
            content.is_ppv = inflow_content.is_ppv
            content.is_locked = inflow_content.is_locked
            content.metadata = inflow_content.metadata
            content.updated_at = datetime.utcnow()
    
    async def _create_financial_transaction(
        self,
        model_profile: ModelProfile,
        inflow_tx: InflowTransaction,
        billing_cycle: BillingCycle
    ):
        """Create financial transaction from Inflow transaction."""
        # Check if transaction already exists
        result = await self.db.execute(
            select(FinancialTransaction).where(
                FinancialTransaction.external_reference == inflow_tx.id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.debug(f"Transaction {inflow_tx.id} already exists, skipping")
            return
        
        # Map Inflow transaction type to our type
        tx_type_map = {
            'subscription': TransactionType.REVENUE,
            'tip': TransactionType.REVENUE,
            'ppv': TransactionType.REVENUE,
            'ppv_message': TransactionType.REVENUE,
            'ppv_post': TransactionType.REVENUE,
            'refund': TransactionType.REFUND,
            'chargeback': TransactionType.REFUND
        }
        
        tx_type = tx_type_map.get(inflow_tx.type, TransactionType.REVENUE)
        
        # Find fan
        fan = None
        if inflow_tx.from_user_id:
            result = await self.db.execute(
                select(Fan).where(
                    and_(
                        Fan.model_id == model_profile.id,
                        Fan.onlyfans_user_id == inflow_tx.from_user_id
                    )
                )
            )
            fan = result.scalar_one_or_none()
        
        # Create transaction
        description = f"Inflow {inflow_tx.type}"
        if fan:
            description += f" from {fan.username}"
        
        metadata = inflow_tx.metadata.copy()
        metadata.update({
            'source': 'inflow',
            'type': inflow_tx.type,
            'fan_id': str(fan.id) if fan else None,
            'inflow_user_id': inflow_tx.from_user_id
        })
        
        # Create through transaction service for proper commission calculation
        transaction = await self.transaction_service.create_transaction(
            model_id=model_profile.id,
            amount=Decimal(str(inflow_tx.amount)),
            currency=inflow_tx.currency,
            type=tx_type,
            description=description,
            billing_cycle_id=billing_cycle.id,
            user_id=fan.user_id if fan and fan.user_id else None,
            external_reference=inflow_tx.id,
            transaction_date=inflow_tx.created_at,
            metadata=metadata
        )
        
        # Mark as completed if Inflow says so
        if inflow_tx.status == 'completed':
            transaction.status = TransactionStatus.COMPLETED
            transaction.processed_at = inflow_tx.created_at
    
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