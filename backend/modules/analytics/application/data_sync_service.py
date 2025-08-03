"""
Analytics data synchronization service.
Syncs real financial data to analytics tables for reporting.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.dialects.postgresql import insert

from models.analytics import MetricSnapshot
from modules.analytics.domain.models import RevenueTransaction, ContentPerformance, FanSpendingHistory, CategoryPerformance
from models.financial import TransactionType
from modules.financial.domain.models import FinancialTransaction, BillingCycle
from core.domain.models import (
    ModelProfile,
    Fan,
    Subscription,
    Content,
    ContentCategory
)
from modules.financial.application.commission_service import CommissionService


logger = logging.getLogger(__name__)


class AnalyticsDataSyncService:
    """Synchronizes real data to analytics tables."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.commission_service = CommissionService(db)
    
    async def sync_all_model_data(self, model_id: str, force: bool = False):
        """
        Sync all analytics data for a model.
        
        Args:
            model_id: Model profile ID
            force: Force resync even if data exists
        """
        logger.info(f"Starting analytics sync for model {model_id}")
        
        # Get model profile
        model = await self.db.get(ModelProfile, model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Sync revenue transactions
        await self.sync_revenue_transactions(model_id, force)
        
        # Update metric snapshots
        await self.update_metric_snapshots(model_id)
        
        # Sync content performance
        await self.sync_content_performance(model_id, force)
        
        # Update fan spending history
        await self.update_fan_spending_history(model_id)
        
        # Update category performance
        await self.update_category_performance(model_id)
        
        logger.info(f"Completed analytics sync for model {model_id}")
    
    async def sync_revenue_transactions(
        self,
        model_id: str,
        force: bool = False,
        start_date: Optional[datetime] = None
    ):
        """
        Sync financial transactions to revenue transactions table.
        
        Args:
            model_id: Model profile ID
            force: Force resync
            start_date: Only sync transactions after this date
        """
        # Get last sync date
        if not force and not start_date:
            result = await self.db.execute(
                select(func.max(RevenueTransaction.transaction_date))
                .where(RevenueTransaction.model_id == model_id)
            )
            last_sync = result.scalar()
            if last_sync:
                start_date = last_sync
        
        # Build query for financial transactions
        query = select(FinancialTransaction).where(
            and_(
                FinancialTransaction.model_id == model_id,
                FinancialTransaction.type == TransactionType.REVENUE
            )
        )
        
        if start_date:
            query = query.where(FinancialTransaction.transaction_date > start_date)
        
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        # Convert to revenue transactions
        for tx in transactions:
            # Determine transaction type
            if tx.metadata and tx.metadata.get('type'):
                tx_type = tx.metadata['type']
            elif 'subscription' in (tx.description or '').lower():
                tx_type = 'subscription'
            elif 'tip' in (tx.description or '').lower():
                tx_type = 'tip'
            elif 'ppv' in (tx.description or '').lower() or 'pay-per-view' in (tx.description or '').lower():
                tx_type = 'ppv_message'
            else:
                tx_type = 'other'
            
            # Get fan info if available
            fan_id = tx.metadata.get('fan_id') if tx.metadata else None
            if not fan_id and tx.user_id:
                # Try to find fan by user_id
                fan_result = await self.db.execute(
                    select(Fan).where(Fan.user_id == tx.user_id)
                )
                fan = fan_result.scalar_one_or_none()
                if fan:
                    fan_id = str(fan.id)
            
            # Create or update revenue transaction
            revenue_tx = RevenueTransaction(
                model_id=str(tx.model_id),
                fan_id=fan_id,
                transaction_id=tx.external_reference or str(tx.id),
                transaction_type=tx_type,
                amount=tx.amount,
                currency=tx.currency,
                transaction_date=tx.transaction_date,
                platform='onlyfans',  # Default, could be from metadata
                metadata={
                    'original_tx_id': str(tx.id),
                    'billing_cycle_id': str(tx.billing_cycle_id) if tx.billing_cycle_id else None,
                    'commission_rate': float(tx.commission_rate) if tx.commission_rate else None,
                    'commission_amount': float(tx.commission_amount) if tx.commission_amount else None
                }
            )
            
            # Upsert revenue transaction
            stmt = insert(RevenueTransaction).values(
                model_id=revenue_tx.model_id,
                fan_id=revenue_tx.fan_id,
                transaction_id=revenue_tx.transaction_id,
                transaction_type=revenue_tx.transaction_type,
                amount=revenue_tx.amount,
                currency=revenue_tx.currency,
                transaction_date=revenue_tx.transaction_date,
                platform=revenue_tx.platform,
                metadata=revenue_tx.metadata
            ).on_conflict_do_update(
                index_elements=['transaction_id'],
                set_={
                    'amount': revenue_tx.amount,
                    'metadata': revenue_tx.metadata,
                    'updated_at': datetime.utcnow()
                }
            )
            
            await self.db.execute(stmt)
        
        await self.db.commit()
        logger.info(f"Synced {len(transactions)} revenue transactions for model {model_id}")
    
    async def update_metric_snapshots(
        self,
        model_id: str,
        lookback_days: int = 90
    ):
        """
        Update metric snapshots from real data.
        
        Args:
            model_id: Model profile ID
            lookback_days: How many days to update
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Generate daily snapshots
        current_date = start_date
        while current_date <= end_date:
            await self._create_daily_snapshot(model_id, current_date)
            current_date += timedelta(days=1)
        
        await self.db.commit()
        logger.info(f"Updated metric snapshots for model {model_id}")
    
    async def _create_daily_snapshot(
        self,
        model_id: str,
        snapshot_date: datetime
    ):
        """Create or update a daily metric snapshot."""
        # Get subscriber counts
        subscriber_result = await self.db.execute(
            select(
                func.count(Subscription.id).label('total'),
                func.count(Subscription.id).filter(
                    Subscription.is_active == True
                ).label('active'),
                func.count(Subscription.id).filter(
                    and_(
                        Subscription.is_active == True,
                        Subscription.price > 0
                    )
                ).label('paying')
            ).where(
                and_(
                    Subscription.model_id == model_id,
                    Subscription.created_at <= snapshot_date
                )
            )
        )
        
        subscriber_data = subscriber_result.one()
        total_subscribers = subscriber_data.total or 0
        active_subscribers = subscriber_data.active or 0
        paying_subscribers = subscriber_data.paying or 0
        non_paying_fans = active_subscribers - paying_subscribers
        
        # Get revenue data for the day
        revenue_result = await self.db.execute(
            select(
                func.sum(RevenueTransaction.amount).label('total_revenue'),
                func.avg(RevenueTransaction.amount).label('avg_transaction')
            ).where(
                and_(
                    RevenueTransaction.model_id == model_id,
                    func.date(RevenueTransaction.transaction_date) == snapshot_date.date()
                )
            )
        )
        
        revenue_data = revenue_result.one()
        daily_revenue = revenue_data.total_revenue or Decimal('0')
        avg_transaction = revenue_data.avg_transaction or Decimal('0')
        
        # Get unique paying fans for the period
        paying_fans_result = await self.db.execute(
            select(func.count(func.distinct(RevenueTransaction.fan_id)))
            .where(
                and_(
                    RevenueTransaction.model_id == model_id,
                    RevenueTransaction.fan_id.isnot(None),
                    func.date(RevenueTransaction.transaction_date) <= snapshot_date.date()
                )
            )
        )
        
        unique_paying_fans = paying_fans_result.scalar() or 0
        
        # Calculate metrics
        conversion_rate = (
            (paying_subscribers / total_subscribers * 100)
            if total_subscribers > 0 else 0
        )
        
        avg_fan_spend = (
            daily_revenue / unique_paying_fans
            if unique_paying_fans > 0 else Decimal('0')
        )
        
        # Create or update snapshot
        snapshot = MetricSnapshot(
            model_id=model_id,
            timestamp=snapshot_date,
            total_revenue=daily_revenue,
            total_subscribers=total_subscribers,
            paying_subscribers=paying_subscribers,
            non_paying_fans=non_paying_fans,
            conversion_rate=float(conversion_rate),
            avg_fan_spend=avg_fan_spend,
            metadata={
                'active_subscribers': active_subscribers,
                'unique_paying_fans': unique_paying_fans,
                'avg_transaction_value': float(avg_transaction)
            }
        )
        
        # Upsert snapshot
        stmt = insert(MetricSnapshot).values(
            model_id=snapshot.model_id,
            timestamp=snapshot.timestamp,
            total_revenue=snapshot.total_revenue,
            total_subscribers=snapshot.total_subscribers,
            paying_subscribers=snapshot.paying_subscribers,
            non_paying_fans=snapshot.non_paying_fans,
            conversion_rate=snapshot.conversion_rate,
            avg_fan_spend=snapshot.avg_fan_spend,
            metadata=snapshot.metadata
        ).on_conflict_do_update(
            index_elements=['model_id', 'timestamp'],
            set_={
                'total_revenue': snapshot.total_revenue,
                'total_subscribers': snapshot.total_subscribers,
                'paying_subscribers': snapshot.paying_subscribers,
                'non_paying_fans': snapshot.non_paying_fans,
                'conversion_rate': snapshot.conversion_rate,
                'avg_fan_spend': snapshot.avg_fan_spend,
                'metadata': snapshot.metadata,
                'updated_at': datetime.utcnow()
            }
        )
        
        await self.db.execute(stmt)
    
    async def sync_content_performance(
        self,
        model_id: str,
        force: bool = False
    ):
        """
        Sync content performance data.
        
        Note: This requires content tracking data which may come from
        platform APIs (OnlyFans, etc.)
        """
        # Get content for model
        result = await self.db.execute(
            select(Content).where(Content.model_id == model_id)
        )
        content_items = result.scalars().all()
        
        for content in content_items:
            # Calculate performance metrics
            # In a real implementation, this would pull from platform APIs
            performance = ContentPerformance(
                model_id=model_id,
                content_id=str(content.id),
                content_type=content.content_type,
                title=content.title or f"{content.content_type} {content.id}",
                published_at=content.created_at,
                categories=content.categories or [],
                views=content.metadata.get('views', 0) if content.metadata else 0,
                likes=content.metadata.get('likes', 0) if content.metadata else 0,
                comments=content.metadata.get('comments', 0) if content.metadata else 0,
                total_revenue=Decimal('0'),  # Would calculate from transactions
                metadata=content.metadata
            )
            
            # Calculate revenue for this content
            if content.metadata and content.metadata.get('price'):
                # Estimate revenue based on views and price
                performance.total_revenue = Decimal(str(
                    content.metadata['price'] * performance.views * 0.1  # 10% conversion estimate
                ))
            
            # Upsert performance
            stmt = insert(ContentPerformance).values(
                model_id=performance.model_id,
                content_id=performance.content_id,
                content_type=performance.content_type,
                title=performance.title,
                published_at=performance.published_at,
                categories=performance.categories,
                views=performance.views,
                likes=performance.likes,
                comments=performance.comments,
                total_revenue=performance.total_revenue,
                metadata=performance.metadata
            ).on_conflict_do_update(
                index_elements=['content_id'],
                set_={
                    'views': performance.views,
                    'likes': performance.likes,
                    'comments': performance.comments,
                    'total_revenue': performance.total_revenue,
                    'metadata': performance.metadata,
                    'updated_at': datetime.utcnow()
                }
            )
            
            await self.db.execute(stmt)
        
        await self.db.commit()
        logger.info(f"Synced performance for {len(content_items)} content items")
    
    async def update_fan_spending_history(
        self,
        model_id: str,
        lookback_days: int = 30
    ):
        """Update fan spending history."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get fan spending data
        result = await self.db.execute(
            select(
                RevenueTransaction.fan_id,
                func.sum(RevenueTransaction.amount).label('total_spent'),
                func.count(RevenueTransaction.id).label('transaction_count'),
                func.max(RevenueTransaction.transaction_date).label('last_transaction')
            ).where(
                and_(
                    RevenueTransaction.model_id == model_id,
                    RevenueTransaction.fan_id.isnot(None),
                    RevenueTransaction.transaction_date >= cutoff_date
                )
            ).group_by(RevenueTransaction.fan_id)
        )
        
        fan_spending = result.all()
        
        for fan_data in fan_spending:
            # Get subscription info
            subscription_result = await self.db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.model_id == model_id,
                        Subscription.fan_id == fan_data.fan_id
                    )
                )
            )
            subscription = subscription_result.scalar_one_or_none()
            
            # Create spending history
            history = FanSpendingHistory(
                model_id=model_id,
                fan_id=fan_data.fan_id,
                period_start=cutoff_date,
                period_end=datetime.utcnow(),
                total_spent=fan_data.total_spent,
                transaction_count=fan_data.transaction_count,
                avg_transaction_value=fan_data.total_spent / fan_data.transaction_count,
                subscription_status='active' if subscription and subscription.is_active else 'inactive',
                last_transaction_date=fan_data.last_transaction
            )
            
            # Upsert history
            stmt = insert(FanSpendingHistory).values(
                model_id=history.model_id,
                fan_id=history.fan_id,
                period_start=history.period_start,
                period_end=history.period_end,
                total_spent=history.total_spent,
                transaction_count=history.transaction_count,
                avg_transaction_value=history.avg_transaction_value,
                subscription_status=history.subscription_status,
                last_transaction_date=history.last_transaction_date
            ).on_conflict_do_update(
                index_elements=['model_id', 'fan_id', 'period_start'],
                set_={
                    'period_end': history.period_end,
                    'total_spent': history.total_spent,
                    'transaction_count': history.transaction_count,
                    'avg_transaction_value': history.avg_transaction_value,
                    'subscription_status': history.subscription_status,
                    'last_transaction_date': history.last_transaction_date,
                    'updated_at': datetime.utcnow()
                }
            )
            
            await self.db.execute(stmt)
        
        await self.db.commit()
        logger.info(f"Updated spending history for {len(fan_spending)} fans")
    
    async def update_category_performance(
        self,
        model_id: str,
        lookback_days: int = 30
    ):
        """Update category performance metrics."""
        period_start = datetime.utcnow() - timedelta(days=lookback_days)
        period_end = datetime.utcnow()
        
        # Get content by category
        result = await self.db.execute(
            select(
                ContentCategory.name,
                func.count(Content.id).label('content_count'),
                func.sum(ContentPerformance.views).label('total_views'),
                func.sum(ContentPerformance.likes).label('total_likes'),
                func.sum(ContentPerformance.comments).label('total_comments'),
                func.sum(ContentPerformance.total_revenue).label('total_revenue')
            ).select_from(Content)
            .join(ContentCategory, Content.category_id == ContentCategory.id)
            .join(ContentPerformance, Content.id == ContentPerformance.content_id)
            .where(
                and_(
                    Content.model_id == model_id,
                    Content.created_at >= period_start
                )
            ).group_by(ContentCategory.name)
        )
        
        category_data = result.all()
        
        for cat_data in category_data:
            performance = CategoryPerformance(
                model_id=model_id,
                category_name=cat_data.name,
                period_start=period_start,
                period_end=period_end,
                content_count=cat_data.content_count,
                total_views=cat_data.total_views or 0,
                total_likes=cat_data.total_likes or 0,
                total_comments=cat_data.total_comments or 0,
                total_revenue=cat_data.total_revenue or Decimal('0')
            )
            
            # Upsert category performance
            stmt = insert(CategoryPerformance).values(
                model_id=performance.model_id,
                category_name=performance.category_name,
                period_start=performance.period_start,
                period_end=performance.period_end,
                content_count=performance.content_count,
                total_views=performance.total_views,
                total_likes=performance.total_likes,
                total_comments=performance.total_comments,
                total_revenue=performance.total_revenue
            ).on_conflict_do_update(
                index_elements=['model_id', 'category_name', 'period_start'],
                set_={
                    'period_end': performance.period_end,
                    'content_count': performance.content_count,
                    'total_views': performance.total_views,
                    'total_likes': performance.total_likes,
                    'total_comments': performance.total_comments,
                    'total_revenue': performance.total_revenue,
                    'updated_at': datetime.utcnow()
                }
            )
            
            await self.db.execute(stmt)
        
        await self.db.commit()
        logger.info(f"Updated performance for {len(category_data)} categories")