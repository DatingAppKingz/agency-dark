"""
Analytics data aggregation service.

Handles real-time and batch aggregation of analytics data,
replacing mock data with actual calculations from the database.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, extract
from sqlalchemy.sql import text

from core.domain.models import User, Agency, ModelProfile
from models.subscriber import Subscriber as Fan
from models.chat import Message
from models.media import Media
from models.financial import Transaction as FinancialTransaction, TransactionType
from models.analytics import MetricSnapshot
from modules.analytics.domain.models import AggregationPeriod, Analytics
from modules.analytics.domain.schemas import (
    TimeSeriesDataPoint as TimeSeriesData,
    MetricType
)
from core.simple_cache import cache_manager
from pydantic import BaseModel
from typing import List


# Define missing metric classes
class RevenueMetrics(BaseModel):
    """Revenue metrics aggregation result."""
    total_revenue: float
    transaction_count: int
    average_transaction: float
    growth_rate: float
    revenue_by_type: Dict[str, float]
    time_series: List[Dict[str, Any]]


class EngagementMetrics(BaseModel):
    """Engagement metrics aggregation result."""
    total_messages: int
    active_conversations: int
    average_response_time: float
    message_read_rate: float
    content_views: int
    engagement_rate: float
    time_series: List[Dict[str, Any]]


class AnalyticsMetric(BaseModel):
    """Analytics metric record."""
    agency_id: str
    model_id: Optional[str]
    metric_type: MetricType
    metric_name: str
    metric_value: float
    period: AggregationPeriod
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """Aggregates analytics data from various sources."""
    
    # Cache TTLs in seconds
    CACHE_TTL = {
        'realtime': 60,        # 1 minute
        'hourly': 3600,        # 1 hour
        'daily': 86400,        # 24 hours
        'weekly': 604800,      # 7 days
        'monthly': 2592000     # 30 days
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def aggregate_metrics(
        self,
        agency_id: str,
        model_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period: AggregationPeriod = AggregationPeriod.DAILY
    ) -> Dict[str, Any]:
        """
        Aggregate all metrics for the specified period.
        
        Args:
            agency_id: Agency ID to aggregate for
            model_id: Optional model ID for model-specific metrics
            start_date: Start of aggregation period
            end_date: End of aggregation period
            period: Aggregation granularity
            
        Returns:
            Dictionary of aggregated metrics
        """
        # Default to last 30 days if no dates specified
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Check cache first
        cache_key = self._generate_cache_key(
            'aggregate',
            agency_id,
            model_id,
            start_date,
            end_date,
            period
        )
        
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached
            
        # Aggregate different metric types in parallel
        results = await asyncio.gather(
            self._aggregate_revenue_metrics(agency_id, model_id, start_date, end_date, period),
            self._aggregate_engagement_metrics(agency_id, model_id, start_date, end_date, period),
            self._aggregate_fan_metrics(agency_id, model_id, start_date, end_date, period),
            self._aggregate_content_metrics(agency_id, model_id, start_date, end_date, period),
            return_exceptions=True
        )
        
        # Handle any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error aggregating metrics {i}: {result}")
                results[i] = {}
        
        # Combine results
        aggregated = {
            'revenue': results[0],
            'engagement': results[1],
            'fans': results[2],
            'content': results[3],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'aggregation': period.value
            }
        }
        
        # Cache results
        ttl = self.CACHE_TTL.get(period.value, self.CACHE_TTL['daily'])
        await cache_manager.set(cache_key, aggregated, ttl)
        
        return aggregated
        
    async def _aggregate_revenue_metrics(
        self,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> RevenueMetrics:
        """Aggregate revenue-related metrics."""
        # Build base query
        query = select(
            func.sum(FinancialTransaction.amount).label('total_revenue'),
            func.count(FinancialTransaction.id).label('transaction_count'),
            func.avg(FinancialTransaction.amount).label('avg_transaction'),
            self._get_period_expression(FinancialTransaction.transaction_date, period).label('period')
        ).where(
            and_(
                FinancialTransaction.agency_id == agency_id,
                FinancialTransaction.type == TransactionType.REVENUE,
                FinancialTransaction.transaction_date >= start_date,
                FinancialTransaction.transaction_date <= end_date
            )
        )
        
        if model_id:
            query = query.where(FinancialTransaction.model_id == model_id)
            
        # Group by period
        query = query.group_by('period').order_by('period')
        
        result = await self.db.execute(query)
        revenue_data = result.all()
        
        # Calculate additional metrics
        total_revenue = sum(row.total_revenue or 0 for row in revenue_data)
        
        # Get previous period for comparison
        prev_start = start_date - (end_date - start_date)
        prev_end = start_date
        
        prev_query = select(
            func.sum(FinancialTransaction.amount)
        ).where(
            and_(
                FinancialTransaction.agency_id == agency_id,
                FinancialTransaction.type == TransactionType.REVENUE,
                FinancialTransaction.transaction_date >= prev_start,
                FinancialTransaction.transaction_date < prev_end
            )
        )
        
        if model_id:
            prev_query = prev_query.where(FinancialTransaction.model_id == model_id)
            
        prev_result = await self.db.execute(prev_query)
        prev_revenue = prev_result.scalar() or 0
        
        # Calculate growth
        growth_rate = 0
        if prev_revenue > 0:
            growth_rate = ((total_revenue - prev_revenue) / prev_revenue) * 100
            
        # Get revenue by type
        type_query = select(
            FinancialTransaction.metadata['payment_type'].astext.label('type'),
            func.sum(FinancialTransaction.amount).label('amount')
        ).where(
            and_(
                FinancialTransaction.agency_id == agency_id,
                FinancialTransaction.type == TransactionType.REVENUE,
                FinancialTransaction.transaction_date >= start_date,
                FinancialTransaction.transaction_date <= end_date
            )
        ).group_by('type')
        
        if model_id:
            type_query = type_query.where(FinancialTransaction.model_id == model_id)
            
        type_result = await self.db.execute(type_query)
        revenue_by_type = {row.type: float(row.amount) for row in type_result}
        
        return RevenueMetrics(
            total_revenue=float(total_revenue),
            transaction_count=sum(row.transaction_count for row in revenue_data),
            average_transaction=float(sum(row.avg_transaction or 0 for row in revenue_data) / len(revenue_data)) if revenue_data else 0,
            growth_rate=float(growth_rate),
            revenue_by_type=revenue_by_type,
            time_series=[{
                'period': row.period,
                'revenue': float(row.total_revenue or 0),
                'transactions': row.transaction_count
            } for row in revenue_data]
        )
        
    async def _aggregate_engagement_metrics(
        self,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> EngagementMetrics:
        """Aggregate engagement-related metrics."""
        # Message metrics
        message_query = select(
            func.count(Message.id).label('message_count'),
            func.count(func.distinct(Message.fan_id)).label('active_fans'),
            func.avg(
                case(
                    (Message.is_read == True, 1),
                    else_=0
                )
            ).label('read_rate'),
            self._get_period_expression(Message.created_at, period).label('period')
        ).join(
            ModelProfile,
            Message.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Message.created_at >= start_date,
                Message.created_at <= end_date
            )
        )
        
        if model_id:
            message_query = message_query.where(Message.model_id == model_id)
            
        message_query = message_query.group_by('period').order_by('period')
        
        message_result = await self.db.execute(message_query)
        message_data = message_result.all()
        
        # Media views
        media_query = select(
            func.sum(Media.view_count).label('total_views'),
            func.count(Media.id).label('media_count'),
            self._get_period_expression(Media.created_at, period).label('period')
        ).join(
            ModelProfile,
            Media.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Media.created_at >= start_date,
                Media.created_at <= end_date
            )
        )
        
        if model_id:
            media_query = media_query.where(Media.model_id == model_id)
            
        media_query = media_query.group_by('period').order_by('period')
        
        media_result = await self.db.execute(media_query)
        media_data = media_result.all()
        
        # Calculate response times
        response_query = select(
            func.avg(
                extract('epoch', Message.created_at - Message.metadata['replied_to_at'].astext.cast(type_=text))
            ).label('avg_response_time')
        ).join(
            ModelProfile,
            Message.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Message.sender_type == 'model',
                Message.metadata['replied_to_at'].isnot(None),
                Message.created_at >= start_date,
                Message.created_at <= end_date
            )
        )
        
        if model_id:
            response_query = response_query.where(Message.model_id == model_id)
            
        response_result = await self.db.execute(response_query)
        avg_response_time = response_result.scalar() or 0
        
        return EngagementMetrics(
            total_messages=sum(row.message_count for row in message_data),
            active_conversations=sum(row.active_fans for row in message_data),
            average_response_time=float(avg_response_time) / 3600,  # Convert to hours
            message_read_rate=float(sum(row.read_rate or 0 for row in message_data) / len(message_data)) if message_data else 0,
            content_views=sum(row.total_views or 0 for row in media_data),
            engagement_rate=self._calculate_engagement_rate(message_data, media_data),
            time_series=[{
                'period': row.period,
                'messages': row.message_count,
                'active_fans': row.active_fans,
                'read_rate': float(row.read_rate or 0)
            } for row in message_data]
        )
        
    async def _aggregate_fan_metrics(
        self,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> Dict[str, Any]:
        """Aggregate fan-related metrics."""
        # Base fan query
        fan_query = select(
            func.count(Fan.id).label('total_fans'),
            func.count(case((Fan.is_active == True, 1))).label('active_fans'),
            func.count(case((Fan.subscription_status == 'active', 1))).label('subscribers'),
            self._get_period_expression(Fan.created_at, period).label('period')
        ).join(
            ModelProfile,
            Fan.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Fan.created_at <= end_date
            )
        )
        
        if model_id:
            fan_query = fan_query.where(Fan.model_id == model_id)
            
        fan_query = fan_query.group_by('period').order_by('period')
        
        fan_result = await self.db.execute(fan_query)
        fan_data = fan_result.all()
        
        # Fan lifetime value
        ltv_query = select(
            func.avg(FinancialTransaction.amount).label('avg_ltv'),
            func.percentile_cont(0.5).within_group(FinancialTransaction.amount).label('median_ltv')
        ).where(
            and_(
                FinancialTransaction.agency_id == agency_id,
                FinancialTransaction.type == TransactionType.REVENUE,
                FinancialTransaction.fan_id.isnot(None)
            )
        )
        
        if model_id:
            ltv_query = ltv_query.where(FinancialTransaction.model_id == model_id)
            
        ltv_result = await self.db.execute(ltv_query)
        ltv_data = ltv_result.first()
        
        # Churn calculation
        churn_rate = await self._calculate_churn_rate(agency_id, model_id, start_date, end_date)
        
        return {
            'total_fans': sum(row.total_fans for row in fan_data),
            'active_fans': sum(row.active_fans for row in fan_data),
            'subscribers': sum(row.subscribers for row in fan_data),
            'average_fan_ltv': float(ltv_data.avg_ltv or 0),
            'median_fan_ltv': float(ltv_data.median_ltv or 0),
            'churn_rate': churn_rate,
            'time_series': [{
                'period': row.period,
                'total': row.total_fans,
                'active': row.active_fans,
                'subscribers': row.subscribers
            } for row in fan_data]
        }
        
    async def _aggregate_content_metrics(
        self,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> Dict[str, Any]:
        """Aggregate content-related metrics."""
        # Content creation metrics
        content_query = select(
            func.count(Media.id).label('content_count'),
            func.sum(Media.view_count).label('total_views'),
            func.avg(Media.view_count).label('avg_views'),
            Media.media_type,
            self._get_period_expression(Media.created_at, period).label('period')
        ).join(
            ModelProfile,
            Media.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Media.created_at >= start_date,
                Media.created_at <= end_date
            )
        )
        
        if model_id:
            content_query = content_query.where(Media.model_id == model_id)
            
        content_query = content_query.group_by('period', Media.media_type).order_by('period')
        
        content_result = await self.db.execute(content_query)
        content_data = content_result.all()
        
        # Aggregate by type
        content_by_type = defaultdict(lambda: {'count': 0, 'views': 0})
        time_series = defaultdict(lambda: {'photos': 0, 'videos': 0, 'views': 0})
        
        for row in content_data:
            content_by_type[row.media_type]['count'] += row.content_count
            content_by_type[row.media_type]['views'] += row.total_views or 0
            time_series[row.period][row.media_type] = row.content_count
            time_series[row.period]['views'] += row.total_views or 0
            
        return {
            'total_content': sum(row.content_count for row in content_data),
            'total_views': sum(row.total_views or 0 for row in content_data),
            'average_views_per_content': float(
                sum(row.total_views or 0 for row in content_data) / 
                sum(row.content_count for row in content_data)
            ) if content_data else 0,
            'content_by_type': dict(content_by_type),
            'time_series': [
                {
                    'period': period,
                    **data
                }
                for period, data in sorted(time_series.items())
            ]
        }
        
    def _get_period_expression(self, column, period: AggregationPeriod):
        """Get SQL expression for period grouping."""
        if period == AggregationPeriod.HOURLY:
            return func.date_trunc('hour', column)
        elif period == AggregationPeriod.DAILY:
            return func.date_trunc('day', column)
        elif period == AggregationPeriod.WEEKLY:
            return func.date_trunc('week', column)
        elif period == AggregationPeriod.MONTHLY:
            return func.date_trunc('month', column)
        else:
            return func.date_trunc('day', column)
            
    def _calculate_engagement_rate(
        self,
        message_data: List[Any],
        media_data: List[Any]
    ) -> float:
        """Calculate overall engagement rate."""
        total_interactions = sum(row.message_count for row in message_data)
        total_views = sum(row.total_views or 0 for row in media_data)
        total_fans = sum(row.active_fans for row in message_data)
        
        if total_fans == 0:
            return 0.0
            
        return float((total_interactions + total_views) / total_fans)
        
    async def _calculate_churn_rate(
        self,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate fan churn rate for the period."""
        # Get fans at start of period
        start_query = select(
            func.count(Fan.id)
        ).join(
            ModelProfile,
            Fan.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Fan.created_at < start_date,
                or_(
                    Fan.unfollowed_at.is_(None),
                    Fan.unfollowed_at >= start_date
                )
            )
        )
        
        if model_id:
            start_query = start_query.where(Fan.model_id == model_id)
            
        start_result = await self.db.execute(start_query)
        fans_at_start = start_result.scalar() or 0
        
        # Get churned fans during period
        churn_query = select(
            func.count(Fan.id)
        ).join(
            ModelProfile,
            Fan.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Fan.unfollowed_at >= start_date,
                Fan.unfollowed_at <= end_date
            )
        )
        
        if model_id:
            churn_query = churn_query.where(Fan.model_id == model_id)
            
        churn_result = await self.db.execute(churn_query)
        churned_fans = churn_result.scalar() or 0
        
        if fans_at_start == 0:
            return 0.0
            
        return float(churned_fans / fans_at_start * 100)
        
    def _generate_cache_key(
        self,
        prefix: str,
        agency_id: str,
        model_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> str:
        """Generate cache key for metrics."""
        parts = [
            prefix,
            agency_id,
            model_id or 'all',
            start_date.strftime('%Y%m%d'),
            end_date.strftime('%Y%m%d'),
            period.value
        ]
        return ':'.join(parts)
        
    async def save_aggregated_metrics(
        self,
        metrics: Dict[str, Any],
        agency_id: str,
        model_id: Optional[str] = None,
        period: AggregationPeriod = AggregationPeriod.DAILY
    ) -> None:
        """
        Save aggregated metrics to database for faster retrieval.
        
        Args:
            metrics: Aggregated metrics dictionary
            agency_id: Agency ID
            model_id: Optional model ID
            period: Aggregation period
        """
        timestamp = datetime.utcnow()
        
        # Save each metric type
        metric_records = []
        
        # Revenue metrics
        if 'revenue' in metrics:
            revenue = metrics['revenue']
            metric_records.append(
                AnalyticsMetric(
                    agency_id=agency_id,
                    model_id=model_id,
                    metric_type=MetricType.REVENUE,
                    metric_name='total_revenue',
                    metric_value=revenue.get('total_revenue', 0),
                    period=period,
                    timestamp=timestamp,
                    metadata={'currency': 'USD'}
                )
            )
            
        # Engagement metrics
        if 'engagement' in metrics:
            engagement = metrics['engagement']
            metric_records.append(
                AnalyticsMetric(
                    agency_id=agency_id,
                    model_id=model_id,
                    metric_type=MetricType.ENGAGEMENT,
                    metric_name='total_messages',
                    metric_value=engagement.get('total_messages', 0),
                    period=period,
                    timestamp=timestamp
                )
            )
            
        # Fan metrics
        if 'fans' in metrics:
            fans = metrics['fans']
            metric_records.append(
                AnalyticsMetric(
                    agency_id=agency_id,
                    model_id=model_id,
                    metric_type=MetricType.FANS,
                    metric_name='active_fans',
                    metric_value=fans.get('active_fans', 0),
                    period=period,
                    timestamp=timestamp
                )
            )
            
        # Save all metrics
        for metric in metric_records:
            self.db.add(metric)
            
        await self.db.commit()
        logger.info(f"Saved {len(metric_records)} aggregated metrics")