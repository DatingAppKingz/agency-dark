"""
Metrics collection service for background jobs.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from core.database import get_db
from modules.analytics.domain.models import (
    MetricSnapshot,
    RevenueTransaction,
    ContentPerformance,
    FanSpendingHistory,
    CategoryPerformance
)
from core.domain.models import (
    ModelProfile,
    Fan,
    Message,
    User
)
from modules.api_orchestration.application.orchestrator import APIOrchestrator


logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and stores analytics metrics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = APIOrchestrator(db)
    
    async def collect_model_metrics(self, model: ModelProfile) -> MetricSnapshot:
        """
        Collect current metrics for a model and store snapshot.
        
        Args:
            model: Model profile to collect metrics for
            
        Returns:
            Created metric snapshot
        """
        logger.info(f"Collecting metrics for model {model.id} ({model.username})")
        
        # Get current subscriber counts
        total_subs = await self._count_subscribers(model.id, is_paying=None)
        paying_subs = await self._count_subscribers(model.id, is_paying=True)
        non_paying = await self._count_subscribers(model.id, is_paying=False)
        
        # Get revenue data from orchestrator
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        analytics = await self.orchestrator.get_unified_analytics(
            model_profile=model,
            start_date=today,
            end_date=datetime.utcnow()
        )
        
        # Get previous snapshot for delta calculations
        prev_snapshot = await self._get_previous_snapshot(model.id)
        
        # Calculate deltas
        new_subs = 0
        lost_subs = 0
        if prev_snapshot:
            new_subs = max(0, total_subs - prev_snapshot.total_subscribers)
            lost_subs = max(0, prev_snapshot.total_subscribers - total_subs)
        
        # Create new snapshot
        snapshot = MetricSnapshot(
            model_id=model.id,
            timestamp=datetime.utcnow(),
            total_subscribers=total_subs,
            paying_subscribers=paying_subs,
            non_paying_fans=non_paying,
            new_subscribers=new_subs,
            lost_subscribers=lost_subs,
            total_revenue=analytics.total_revenue,
            subscription_revenue=analytics.subscription_revenue,
            tip_revenue=analytics.tip_revenue,
            ppv_revenue=analytics.ppv_revenue,
            total_messages_sent=analytics.messages_sent,
            total_messages_received=analytics.messages_received,
            avg_fan_spend=analytics.total_revenue / max(1, paying_subs),
            conversion_rate=(paying_subs / max(1, total_subs)) * 100
        )
        
        self.db.add(snapshot)
        await self.db.commit()
        
        logger.info(f"Stored metrics snapshot for model {model.id}")
        return snapshot
    
    async def collect_revenue_transactions(
        self,
        model: ModelProfile,
        since: Optional[datetime] = None
    ) -> List[RevenueTransaction]:
        """
        Collect and store revenue transactions.
        
        Args:
            model: Model profile
            since: Collect transactions since this date
            
        Returns:
            List of created revenue transactions
        """
        if not since:
            # Default to last 24 hours
            since = datetime.utcnow() - timedelta(days=1)
        
        transactions = []
        
        # Get transactions from OnlyFans if configured
        if model.onlyfans_api_key:
            # TODO: Implement OnlyFans transaction collection
            pass
        
        # Get transactions from Inflow if configured
        if model.inflow_api_key:
            # TODO: Implement Inflow transaction collection
            pass
        
        # Store transactions
        for tx_data in transactions:
            tx = RevenueTransaction(
                model_id=model.id,
                fan_id=tx_data['fan_id'],
                transaction_type=tx_data['type'],
                amount=Decimal(str(tx_data['amount'])),
                currency=tx_data.get('currency', 'USD'),
                source=tx_data['source'],
                external_transaction_id=tx_data.get('external_id'),
                transaction_date=tx_data['date']
            )
            self.db.add(tx)
        
        await self.db.commit()
        return transactions
    
    async def collect_content_performance(
        self,
        model: ModelProfile
    ) -> List[ContentPerformance]:
        """
        Collect content performance metrics.
        
        Args:
            model: Model profile
            
        Returns:
            List of content performance records
        """
        performances = []
        
        # Get content data from APIs
        # TODO: Implement content data collection from OF/Inflow
        
        # For now, return empty list
        return performances
    
    async def update_fan_spending_history(
        self,
        model_id: str,
        period_start: datetime,
        period_end: datetime
    ):
        """
        Update fan spending history for a period.
        
        Args:
            model_id: Model ID
            period_start: Start of period
            period_end: End of period
        """
        # Get all fans for this model
        result = await self.db.execute(
            select(Fan).where(Fan.model_id == model_id)
        )
        fans = result.scalars().all()
        
        for fan in fans:
            # Calculate spending for this period
            spending_data = await self._calculate_fan_spending(
                fan.id,
                period_start,
                period_end
            )
            
            # Create or update spending history record
            history = FanSpendingHistory(
                fan_id=fan.id,
                model_id=model_id,
                period_start=period_start,
                period_end=period_end,
                subscription_amount=spending_data['subscription'],
                tip_amount=spending_data['tips'],
                ppv_amount=spending_data['ppv'],
                total_amount=spending_data['total'],
                tip_count=spending_data['tip_count'],
                ppv_purchase_count=spending_data['ppv_count']
            )
            
            self.db.add(history)
        
        await self.db.commit()
    
    async def update_category_performance(
        self,
        model_id: str,
        period_start: datetime,
        period_end: datetime
    ):
        """
        Update category performance metrics.
        
        Args:
            model_id: Model ID
            period_start: Start of period
            period_end: End of period
        """
        # Get unique categories for this model's content
        result = await self.db.execute(
            select(ContentPerformance.categories).where(
                ContentPerformance.model_id == model_id
            ).distinct()
        )
        
        all_categories = set()
        for row in result:
            if row.categories:
                all_categories.update(row.categories)
        
        # Calculate performance for each category
        for category in all_categories:
            perf_data = await self._calculate_category_performance(
                model_id,
                category,
                period_start,
                period_end
            )
            
            cat_perf = CategoryPerformance(
                model_id=model_id,
                category_name=category,
                period_start=period_start,
                period_end=period_end,
                content_count=perf_data['content_count'],
                total_views=perf_data['total_views'],
                total_likes=perf_data['total_likes'],
                total_comments=perf_data['total_comments'],
                total_revenue=perf_data['total_revenue'],
                avg_revenue_per_content=perf_data['avg_revenue'],
                avg_engagement_rate=perf_data['engagement_rate']
            )
            
            self.db.add(cat_perf)
        
        await self.db.commit()
    
    async def _count_subscribers(
        self,
        model_id: str,
        is_paying: Optional[bool] = None
    ) -> int:
        """Count subscribers for a model."""
        query = select(func.count(Fan.id)).where(
            and_(
                Fan.model_id == model_id,
                Fan.is_subscriber == True
            )
        )
        
        if is_paying is not None:
            query = query.where(Fan.is_paying == is_paying)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _get_previous_snapshot(
        self,
        model_id: str
    ) -> Optional[MetricSnapshot]:
        """Get the most recent snapshot for a model."""
        result = await self.db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.model_id == model_id)
            .order_by(MetricSnapshot.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _calculate_fan_spending(
        self,
        fan_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Calculate fan spending for a period."""
        # Query revenue transactions
        result = await self.db.execute(
            select(
                RevenueTransaction.transaction_type,
                func.sum(RevenueTransaction.amount).label('total'),
                func.count(RevenueTransaction.id).label('count')
            )
            .where(
                and_(
                    RevenueTransaction.fan_id == fan_id,
                    RevenueTransaction.transaction_date >= period_start,
                    RevenueTransaction.transaction_date <= period_end
                )
            )
            .group_by(RevenueTransaction.transaction_type)
        )
        
        spending = {
            'subscription': Decimal('0'),
            'tips': Decimal('0'),
            'ppv': Decimal('0'),
            'total': Decimal('0'),
            'tip_count': 0,
            'ppv_count': 0
        }
        
        for row in result:
            if row.transaction_type == 'subscription':
                spending['subscription'] = row.total or Decimal('0')
            elif row.transaction_type == 'tip':
                spending['tips'] = row.total or Decimal('0')
                spending['tip_count'] = row.count or 0
            elif row.transaction_type in ['ppv_message', 'ppv_post']:
                spending['ppv'] += row.total or Decimal('0')
                spending['ppv_count'] += row.count or 0
        
        spending['total'] = (
            spending['subscription'] +
            spending['tips'] +
            spending['ppv']
        )
        
        return spending
    
    async def _calculate_category_performance(
        self,
        model_id: str,
        category: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Calculate performance metrics for a category."""
        # Query content in this category
        result = await self.db.execute(
            select(
                func.count(ContentPerformance.id).label('content_count'),
                func.sum(ContentPerformance.views).label('total_views'),
                func.sum(ContentPerformance.likes).label('total_likes'),
                func.sum(ContentPerformance.comments).label('total_comments'),
                func.sum(ContentPerformance.total_revenue).label('total_revenue')
            )
            .where(
                and_(
                    ContentPerformance.model_id == model_id,
                    ContentPerformance.published_at >= period_start,
                    ContentPerformance.published_at <= period_end,
                    ContentPerformance.categories.contains([category])
                )
            )
        )
        
        row = result.one()
        
        content_count = row.content_count or 0
        total_views = row.total_views or 0
        total_likes = row.total_likes or 0
        total_comments = row.total_comments or 0
        total_revenue = row.total_revenue or Decimal('0')
        
        # Calculate derived metrics
        avg_revenue = total_revenue / content_count if content_count > 0 else Decimal('0')
        engagement_rate = (
            ((total_likes + total_comments) / total_views * 100)
            if total_views > 0 else 0
        )
        
        return {
            'content_count': content_count,
            'total_views': total_views,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_revenue': total_revenue,
            'avg_revenue': avg_revenue,
            'engagement_rate': engagement_rate
        }