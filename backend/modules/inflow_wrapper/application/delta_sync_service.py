"""
Delta sync service for efficient incremental data synchronization with Inflow API.

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
from models.financial import TransactionType, TransactionStatus
from modules.financial.domain.models import FinancialTransaction, BillingCycle
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


class InflowDeltaSyncService:
    """Delta sync service for efficient incremental data synchronization."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inflow_service = InflowService(db)
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
                - subscribers: bool (default: True)
                - transactions: bool (default: True)
                - content: bool (default: True)
                - messages: bool (default: False)
                
        Returns:
            Dict with sync results and statistics
        """
        if not model_profile.inflow_api_key:
            raise ValueError(f"Model {model_profile.id} has no Inflow API key")
        
        # Default sync options
        if sync_options is None:
            sync_options = {
                'subscribers': True,
                'transactions': True,
                'content': True,
                'messages': False  # Messages can be slow, disabled by default
            }
        
        # Get last sync timestamp
        last_sync = model_profile.last_sync_at or datetime.utcnow() - timedelta(days=30)
        current_sync_time = datetime.utcnow()
        
        logger.info(
            f"Starting delta sync for model {model_profile.id} "
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
            # Run sync tasks concurrently where possible
            tasks = []
            
            if sync_options.get('subscribers', True):
                tasks.append(self._sync_subscribers_delta(model_profile, last_sync))
            
            if sync_options.get('transactions', True):
                tasks.append(self._sync_transactions_delta(model_profile, last_sync))
            
            if sync_options.get('content', True):
                tasks.append(self._sync_content_delta(model_profile, last_sync))
            
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
            
            # Update analytics
            await self._update_analytics_delta(model_profile, last_sync, current_sync_time)
            
            # Update last sync timestamp
            model_profile.last_sync_at = current_sync_time
            await self.db.commit()
            
            # Calculate duration
            sync_results['duration'] = (datetime.utcnow() - current_sync_time).total_seconds()
            
            logger.info(
                f"Completed delta sync for model {model_profile.id}: "
                f"{sync_results['synced']} in {sync_results['duration']:.2f}s"
            )
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Delta sync failed for model {model_profile.id}: {e}")
            await self.db.rollback()
            sync_results['errors'].append(f"Fatal error: {str(e)}")
            raise
    
    async def _sync_subscribers_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new or updated subscribers since last sync."""
        logger.info(f"Delta syncing subscribers for model {model_profile.id}")
        
        client = await self.inflow_service.get_client(model_profile)
        
        new_count = 0
        updated_count = 0
        page = 1
        has_more = True
        
        while has_more:
            # Get subscribers modified since last sync
            subscribers = await client.list_subscribers(
                creator_id=model_profile.onlyfans_user_id or str(model_profile.id),
                modified_since=since,
                page=page,
                limit=self.page_size
            )
            
            if not subscribers:
                has_more = False
                continue
            
            for sub in subscribers:
                # Check if fan exists
                result = await self.db.execute(
                    select(Fan).where(
                        and_(
                            Fan.model_id == model_profile.id,
                            Fan.onlyfans_user_id == sub.id
                        )
                    )
                )
                existing_fan = result.scalar_one_or_none()
                
                if existing_fan:
                    # Update existing fan
                    existing_fan.username = sub.username
                    existing_fan.display_name = sub.display_name
                    existing_fan.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    # Create new fan
                    fan = Fan(
                        id=uuid4(),
                        model_id=model_profile.id,
                        onlyfans_user_id=sub.id,
                        username=sub.username,
                        display_name=sub.display_name,
                        created_at=sub.created_at or datetime.utcnow()
                    )
                    self.db.add(fan)
                    new_count += 1
                
                # Update subscription if this is a subscriber
                if hasattr(sub, 'subscription') and sub.subscription:
                    await self._update_subscription_delta(model_profile, sub)
            
            # Check if there are more pages
            if len(subscribers) < self.page_size:
                has_more = False
            else:
                page += 1
            
            # Commit periodically to avoid large transactions
            if page % 5 == 0:
                await self.db.commit()
        
        await self.db.commit()
        
        return {
            'subscribers_new': new_count,
            'subscribers_updated': updated_count
        }
    
    async def _sync_transactions_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new transactions since last sync."""
        logger.info(f"Delta syncing transactions for model {model_profile.id}")
        
        client = await self.inflow_service.get_client(model_profile)
        
        synced_count = 0
        skipped_count = 0
        page = 1
        has_more = True
        
        # Get current billing cycle
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        while has_more:
            # Get transactions since last sync
            transactions = await client.list_transactions(
                start_date=since,
                end_date=datetime.utcnow(),
                page=page,
                limit=self.page_size
            )
            
            if not transactions:
                has_more = False
                continue
            
            for tx in transactions:
                # Check if transaction already exists
                result = await self.db.execute(
                    select(FinancialTransaction.id).where(
                        FinancialTransaction.external_reference == tx.id
                    )
                )
                if result.scalar_one_or_none():
                    skipped_count += 1
                    continue
                
                # Only process transactions where model is the recipient
                if tx.to_user_id == model_profile.onlyfans_user_id:
                    try:
                        await self._create_financial_transaction(
                            model_profile,
                            tx,
                            current_cycle
                        )
                        synced_count += 1
                    except Exception as e:
                        logger.error(f"Failed to sync transaction {tx.id}: {e}")
            
            # Check if there are more pages
            if len(transactions) < self.page_size:
                has_more = False
            else:
                page += 1
            
            # Commit periodically
            if page % 5 == 0:
                await self.db.commit()
        
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
    
    async def _sync_content_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync only new or updated content since last sync."""
        logger.info(f"Delta syncing content for model {model_profile.id}")
        
        client = await self.inflow_service.get_client(model_profile)
        
        new_count = 0
        updated_count = 0
        page = 1
        has_more = True
        
        while has_more:
            # Get content modified since last sync
            content_items = await client.list_content(
                modified_since=since,
                page=page,
                limit=self.page_size
            )
            
            if not content_items:
                has_more = False
                continue
            
            for item in content_items:
                # Check if content exists
                result = await self.db.execute(
                    select(Content).where(
                        and_(
                            Content.model_id == model_profile.id,
                            Content.platform_content_id == item.id
                        )
                    )
                )
                existing_content = result.scalar_one_or_none()
                
                if existing_content:
                    # Update existing content
                    await self._update_content(existing_content, item)
                    updated_count += 1
                else:
                    # Create new content
                    await self._create_content(model_profile, item)
                    new_count += 1
            
            # Check if there are more pages
            if len(content_items) < self.page_size:
                has_more = False
            else:
                page += 1
            
            # Commit periodically
            if page % 5 == 0:
                await self.db.commit()
        
        await self.db.commit()
        
        return {
            'content_new': new_count,
            'content_updated': updated_count
        }
    
    async def _sync_messages_delta(
        self,
        model_profile: ModelProfile,
        since: datetime
    ) -> Dict[str, int]:
        """Sync messages with pagination for PPV tracking."""
        logger.info(f"Delta syncing messages for model {model_profile.id}")
        
        client = await self.inflow_service.get_client(model_profile)
        
        message_count = 0
        ppv_count = 0
        page = 1
        has_more = True
        
        # Get current billing cycle
        current_cycle = await self._get_or_create_billing_cycle(
            model_profile.id,
            datetime.utcnow()
        )
        
        while has_more:
            # Get messages since last sync
            messages = await client.list_messages(
                since=since,
                page=page,
                limit=self.page_size
            )
            
            if not messages:
                has_more = False
                continue
            
            for msg in messages:
                message_count += 1
                
                # Process PPV messages
                if msg.is_ppv and msg.price:
                    # Check if PPV transaction already exists
                    result = await self.db.execute(
                        select(FinancialTransaction.id).where(
                            FinancialTransaction.external_reference == f"ppv_{msg.id}"
                        )
                    )
                    if not result.scalar_one_or_none():
                        # Create PPV transaction
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
                        
                        try:
                            await self._create_financial_transaction(
                                model_profile,
                                tx,
                                current_cycle
                            )
                            ppv_count += 1
                        except Exception as e:
                            logger.error(f"Failed to create PPV transaction for message {msg.id}: {e}")
            
            # Check if there are more pages
            if len(messages) < self.page_size:
                has_more = False
            else:
                page += 1
            
            # Commit periodically
            if page % 5 == 0:
                await self.db.commit()
        
        if ppv_count > 0:
            await self.db.commit()
            logger.info(f"Created {ppv_count} PPV transactions from messages")
        
        return {
            'messages_processed': message_count,
            'ppv_transactions': ppv_count
        }
    
    async def _update_analytics_delta(
        self,
        model_profile: ModelProfile,
        start_date: datetime,
        end_date: datetime
    ):
        """Update analytics for the delta sync period."""
        logger.info(f"Updating analytics for model {model_profile.id}")
        
        # Get analytics from Inflow
        analytics = await self.inflow_service.get_analytics(
            model_profile,
            start_date,
            end_date
        )
        
        # Update model statistics
        model_profile.subscriber_count = analytics.total_subscribers
        
        # Log analytics for monitoring
        logger.info(
            f"Analytics update for model {model_profile.id}: "
            f"Revenue: ${analytics.total_revenue}, "
            f"Subscribers: {analytics.total_subscribers} "
            f"(+{analytics.new_subscribers}/-{analytics.lost_subscribers})"
        )
    
    async def _update_subscription_delta(
        self,
        model_profile: ModelProfile,
        subscriber: InflowUser
    ):
        """Update subscription record for delta sync."""
        if not hasattr(subscriber, 'subscription') or not subscriber.subscription:
            return
        
        sub = subscriber.subscription
        
        # Find fan
        result = await self.db.execute(
            select(Fan).where(
                and_(
                    Fan.model_id == model_profile.id,
                    Fan.onlyfans_user_id == subscriber.id
                )
            )
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            logger.warning(f"Fan {subscriber.id} not found for subscription update")
            return
        
        # Upsert subscription
        stmt = insert(Subscription).values(
            id=uuid4(),
            model_id=model_profile.id,
            fan_id=fan.id,
            platform_subscription_id=sub.id,
            price=Decimal(str(sub.price)),
            is_active=sub.is_active,
            started_at=sub.started_at,
            expires_at=sub.expires_at,
            auto_renew=sub.auto_renew,
            created_at=sub.started_at,
            updated_at=datetime.utcnow()
        ).on_conflict_do_update(
            index_elements=['model_id', 'fan_id'],
            set_={
                'platform_subscription_id': sub.id,
                'price': Decimal(str(sub.price)),
                'is_active': sub.is_active,
                'expires_at': sub.expires_at,
                'auto_renew': sub.auto_renew,
                'updated_at': datetime.utcnow()
            }
        )
        
        await self.db.execute(stmt)
    
    async def _create_content(self, model_profile: ModelProfile, item: InflowContent):
        """Create new content record."""
        content = Content(
            id=uuid4(),
            model_id=model_profile.id,
            platform_content_id=item.id,
            content_type=item.content_type,
            title=item.title,
            description=item.description,
            url=str(item.url),
            thumbnail_url=str(item.thumbnail_url) if item.thumbnail_url else None,
            price=Decimal(str(item.price)) if item.price else None,
            is_ppv=item.is_ppv,
            is_locked=item.is_locked,
            created_at=item.created_at,
            metadata=item.metadata
        )
        self.db.add(content)
    
    async def _update_content(self, content: Content, item: InflowContent):
        """Update existing content record."""
        content.title = item.title
        content.description = item.description
        content.url = str(item.url)
        content.thumbnail_url = str(item.thumbnail_url) if item.thumbnail_url else None
        content.price = Decimal(str(item.price)) if item.price else None
        content.is_ppv = item.is_ppv
        content.is_locked = item.is_locked
        content.metadata = item.metadata
        content.updated_at = datetime.utcnow()
    
    async def _create_financial_transaction(
        self,
        model_profile: ModelProfile,
        inflow_tx: InflowTransaction,
        billing_cycle: BillingCycle
    ):
        """Create financial transaction from Inflow transaction."""
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
        
        metadata = inflow_tx.metadata.copy() if hasattr(inflow_tx, 'metadata') and inflow_tx.metadata else {}
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