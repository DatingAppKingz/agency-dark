"""
Analytics service for generating charts and reports.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text

from backend.core.redis import redis_client
from backend.modules.analytics.domain.models import (
    MetricSnapshot,
    RevenueTransaction,
    ContentPerformance,
    FanSpendingHistory,
    CategoryPerformance,
    AnalyticsCache
)
from backend.modules.analytics.domain.schemas import (
    TimeGranularity,
    ChartType,
    TimeSeriesDataPoint,
    ChartSeries,
    ChartData,
    SubscriberGrowthData,
    RevenueBreakdown,
    RevenueTimeSeriesData,
    FanRevenueData,
    TopFansAnalytics,
    ContentCategoryPerformance,
    CategoryPopularityData,
    ContentPerformanceData,
    DashboardSummary,
    ChartRequest,
    ChartResponse
)
from backend.core.domain.models import ModelProfile, Fan


logger = logging.getLogger(__name__)


class AnalyticsService:
    """Provides analytics data and chart generation."""
    
    CACHE_TTL = 3600  # 1 hour cache for analytics
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_subscriber_growth_chart(
        self,
        model_id: str,
        period_start: date,
        period_end: date,
        granularity: TimeGranularity = TimeGranularity.DAY
    ) -> ChartResponse:
        """
        Get subscriber growth chart data.
        
        Returns data for:
        - Total subscribers
        - Paying subscribers
        - Non-paying fans
        """
        # Check cache
        cache_key = f"chart:subscriber_growth:{model_id}:{period_start}:{period_end}:{granularity}"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return ChartResponse(**cached)
        
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Get time series data
        snapshots = await self._get_metric_snapshots(
            model_id,
            start_dt,
            end_dt,
            granularity
        )
        
        # Build chart series
        total_series = ChartSeries(
            name="Total Subscribers",
            data=[
                TimeSeriesDataPoint(
                    timestamp=s.timestamp,
                    value=s.total_subscribers
                ) for s in snapshots
            ],
            color="#8884d8"
        )
        
        paying_series = ChartSeries(
            name="Paying Subscribers",
            data=[
                TimeSeriesDataPoint(
                    timestamp=s.timestamp,
                    value=s.paying_subscribers
                ) for s in snapshots
            ],
            color="#82ca9d"
        )
        
        non_paying_series = ChartSeries(
            name="Non-Paying Fans",
            data=[
                TimeSeriesDataPoint(
                    timestamp=s.timestamp,
                    value=s.non_paying_fans
                ) for s in snapshots
            ],
            color="#ffc658"
        )
        
        # Create chart data
        chart_data = ChartData(
            title="Subscriber Growth",
            type=ChartType.LINE,
            series=[total_series, paying_series, non_paying_series],
            xAxis={
                "dataKey": "timestamp",
                "type": "time",
                "label": "Date"
            },
            yAxis={
                "label": "Subscribers",
                "type": "number"
            }
        )
        
        response = ChartResponse(
            chart_data=chart_data,
            period_start=start_dt,
            period_end=end_dt,
            generated_at=datetime.utcnow(),
            cache_expires_at=datetime.utcnow() + timedelta(seconds=self.CACHE_TTL)
        )
        
        # Cache the response
        await self._save_to_cache(cache_key, response.model_dump(), self.CACHE_TTL)
        
        return response
    
    async def get_revenue_timeline_chart(
        self,
        model_id: str,
        period_start: date,
        period_end: date,
        granularity: TimeGranularity = TimeGranularity.DAY
    ) -> ChartResponse:
        """
        Get revenue timeline chart data.
        
        Returns data for:
        - Total revenue
        - Subscription revenue
        - Tip revenue
        - PPV revenue
        """
        # Check cache
        cache_key = f"chart:revenue_timeline:{model_id}:{period_start}:{period_end}:{granularity}"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return ChartResponse(**cached)
        
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Get revenue data
        revenue_data = await self._get_revenue_time_series(
            model_id,
            start_dt,
            end_dt,
            granularity
        )
        
        # Build chart series
        series = []
        
        # Total revenue
        series.append(ChartSeries(
            name="Total Revenue",
            data=revenue_data['total'],
            color="#8884d8",
            type=ChartType.AREA
        ))
        
        # Subscription revenue
        series.append(ChartSeries(
            name="Subscriptions",
            data=revenue_data['subscription'],
            color="#82ca9d"
        ))
        
        # Tip revenue
        series.append(ChartSeries(
            name="Tips",
            data=revenue_data['tip'],
            color="#ffc658"
        ))
        
        # PPV revenue
        series.append(ChartSeries(
            name="PPV",
            data=revenue_data['ppv'],
            color="#ff7c7c"
        ))
        
        # Create chart data
        chart_data = ChartData(
            title="Revenue Timeline",
            type=ChartType.LINE,
            series=series,
            xAxis={
                "dataKey": "timestamp",
                "type": "time",
                "label": "Date"
            },
            yAxis={
                "label": "Revenue ($)",
                "type": "number",
                "tickFormatter": "currency"
            }
        )
        
        response = ChartResponse(
            chart_data=chart_data,
            period_start=start_dt,
            period_end=end_dt,
            generated_at=datetime.utcnow(),
            cache_expires_at=datetime.utcnow() + timedelta(seconds=self.CACHE_TTL)
        )
        
        # Cache the response
        await self._save_to_cache(cache_key, response.model_dump(), self.CACHE_TTL)
        
        return response
    
    async def get_per_fan_revenue_chart(
        self,
        model_id: str,
        fan_ids: List[str],
        period_start: date,
        period_end: date,
        granularity: TimeGranularity = TimeGranularity.DAY
    ) -> ChartResponse:
        """
        Get revenue chart for specific fans (up to 10).
        
        Args:
            model_id: Model ID
            fan_ids: List of fan IDs (max 10)
            period_start: Start date
            period_end: End date
            granularity: Time granularity
            
        Returns:
            Chart with one line per fan
        """
        # Limit to 10 fans
        fan_ids = fan_ids[:10]
        
        # Check cache
        cache_key = f"chart:fan_revenue:{model_id}:{'-'.join(fan_ids)}:{period_start}:{period_end}"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return ChartResponse(**cached)
        
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Get fan details
        fans = await self._get_fans_by_ids(fan_ids)
        
        # Build series for each fan
        series = []
        colors = [
            "#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1",
            "#d084d0", "#ffb347", "#79d2a6", "#ff91a4", "#a4a4ff"
        ]
        
        for i, fan in enumerate(fans):
            # Get revenue data for this fan
            revenue_data = await self._get_fan_revenue_time_series(
                fan.id,
                start_dt,
                end_dt,
                granularity
            )
            
            series.append(ChartSeries(
                name=fan.username,
                data=revenue_data,
                color=colors[i % len(colors)]
            ))
        
        # Create chart data
        chart_data = ChartData(
            title="Per-Fan Revenue",
            type=ChartType.LINE,
            series=series,
            xAxis={
                "dataKey": "timestamp",
                "type": "time",
                "label": "Date"
            },
            yAxis={
                "label": "Revenue ($)",
                "type": "number",
                "tickFormatter": "currency"
            }
        )
        
        response = ChartResponse(
            chart_data=chart_data,
            period_start=start_dt,
            period_end=end_dt,
            generated_at=datetime.utcnow(),
            cache_expires_at=datetime.utcnow() + timedelta(seconds=self.CACHE_TTL)
        )
        
        # Cache the response
        await self._save_to_cache(cache_key, response.model_dump(), self.CACHE_TTL)
        
        return response
    
    async def get_category_popularity_data(
        self,
        model_id: str,
        period_start: date,
        period_end: date
    ) -> CategoryPopularityData:
        """
        Get content category popularity metrics.
        
        Returns:
        - Category performance metrics
        - Most profitable/viewed/engaging categories
        """
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Get category performance data
        result = await self.db.execute(
            select(CategoryPerformance)
            .where(
                and_(
                    CategoryPerformance.model_id == model_id,
                    CategoryPerformance.period_start >= start_dt,
                    CategoryPerformance.period_end <= end_dt
                )
            )
            .order_by(CategoryPerformance.total_revenue.desc())
        )
        
        performances = result.scalars().all()
        
        # Aggregate by category
        category_data = {}
        for perf in performances:
            if perf.category_name not in category_data:
                category_data[perf.category_name] = {
                    'content_count': 0,
                    'total_revenue': Decimal('0'),
                    'total_views': 0,
                    'total_likes': 0,
                    'total_comments': 0
                }
            
            data = category_data[perf.category_name]
            data['content_count'] += perf.content_count
            data['total_revenue'] += perf.total_revenue
            data['total_views'] += perf.total_views
            data['total_likes'] += perf.total_likes
            data['total_comments'] += perf.total_comments
        
        # Build category performance list
        categories = []
        for name, data in category_data.items():
            engagement_rate = (
                (data['total_likes'] + data['total_comments']) / 
                max(1, data['total_views']) * 100
            )
            
            categories.append(ContentCategoryPerformance(
                category_name=name,
                content_count=data['content_count'],
                total_revenue=data['total_revenue'],
                avg_revenue_per_content=(
                    data['total_revenue'] / max(1, data['content_count'])
                ),
                total_views=data['total_views'],
                total_likes=data['total_likes'],
                engagement_rate=engagement_rate,
                top_performing_content=[]  # TODO: Add top content
            ))
        
        # Sort to find top categories
        by_revenue = sorted(categories, key=lambda x: x.total_revenue, reverse=True)
        by_views = sorted(categories, key=lambda x: x.total_views, reverse=True)
        by_engagement = sorted(categories, key=lambda x: x.engagement_rate, reverse=True)
        
        return CategoryPopularityData(
            period_start=start_dt,
            period_end=end_dt,
            categories=categories,
            most_profitable_category=by_revenue[0].category_name if by_revenue else "",
            most_viewed_category=by_views[0].category_name if by_views else "",
            highest_engagement_category=by_engagement[0].category_name if by_engagement else ""
        )
    
    async def get_content_performance_data(
        self,
        model_id: str,
        content_ids: List[str]
    ) -> List[ContentPerformanceData]:
        """Get performance data for specific content pieces."""
        result = await self.db.execute(
            select(ContentPerformance)
            .where(
                and_(
                    ContentPerformance.model_id == model_id,
                    ContentPerformance.content_id.in_(content_ids)
                )
            )
        )
        
        performances = result.scalars().all()
        
        return [
            ContentPerformanceData(
                content_id=perf.content_id,
                content_type=perf.content_type,
                title=perf.title,
                published_at=perf.published_at,
                categories=perf.categories or [],
                views=perf.views,
                likes=perf.likes,
                comments=perf.comments,
                engagement_rate=(
                    (perf.likes + perf.comments) / max(1, perf.views) * 100
                ),
                total_revenue=perf.total_revenue,
                revenue_per_view=perf.total_revenue / max(1, perf.views)
            )
            for perf in performances
        ]
    
    async def get_dashboard_summary(
        self,
        model_id: str,
        period: str = "today"
    ) -> DashboardSummary:
        """
        Get high-level dashboard metrics.
        
        Args:
            model_id: Model ID
            period: Period to show (today, week, month)
            
        Returns:
            Dashboard summary data
        """
        # Calculate date ranges
        now = datetime.utcnow()
        if period == "today":
            current_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = current_start - timedelta(days=1)
            prev_end = current_start
        elif period == "week":
            current_start = now - timedelta(days=now.weekday())
            current_start = current_start.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = current_start - timedelta(days=7)
            prev_end = current_start
        else:  # month
            current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_start = (current_start - timedelta(days=1)).replace(day=1)
            prev_end = current_start
        
        # Get current period snapshot
        current_snapshot = await self._get_latest_snapshot_in_range(
            model_id,
            current_start,
            now
        )
        
        # Get previous period snapshot
        prev_snapshot = await self._get_latest_snapshot_in_range(
            model_id,
            prev_start,
            prev_end
        )
        
        # Calculate changes
        revenue_change = 0.0
        subscriber_change = 0.0
        paying_subscriber_change = 0.0
        
        if current_snapshot and prev_snapshot:
            if prev_snapshot.total_revenue > 0:
                revenue_change = (
                    (current_snapshot.total_revenue - prev_snapshot.total_revenue) /
                    prev_snapshot.total_revenue * 100
                )
            
            if prev_snapshot.total_subscribers > 0:
                subscriber_change = (
                    (current_snapshot.total_subscribers - prev_snapshot.total_subscribers) /
                    prev_snapshot.total_subscribers * 100
                )
            
            if prev_snapshot.paying_subscribers > 0:
                paying_subscriber_change = (
                    (current_snapshot.paying_subscribers - prev_snapshot.paying_subscribers) /
                    prev_snapshot.paying_subscribers * 100
                )
        
        # Default values if no snapshot
        if not current_snapshot:
            return DashboardSummary(
                period=period,
                total_revenue=Decimal('0'),
                revenue_change=0,
                total_subscribers=0,
                subscriber_change=0,
                paying_subscribers=0,
                paying_subscriber_change=0,
                avg_revenue_per_subscriber=Decimal('0'),
                conversion_rate=0
            )
        
        return DashboardSummary(
            period=period,
            total_revenue=current_snapshot.total_revenue,
            revenue_change=float(revenue_change),
            total_subscribers=current_snapshot.total_subscribers,
            subscriber_change=float(subscriber_change),
            paying_subscribers=current_snapshot.paying_subscribers,
            paying_subscriber_change=float(paying_subscriber_change),
            avg_revenue_per_subscriber=current_snapshot.avg_fan_spend,
            conversion_rate=current_snapshot.conversion_rate
        )
    
    async def _get_metric_snapshots(
        self,
        model_id: str,
        start_dt: datetime,
        end_dt: datetime,
        granularity: TimeGranularity
    ) -> List[MetricSnapshot]:
        """Get metric snapshots for a time range."""
        result = await self.db.execute(
            select(MetricSnapshot)
            .where(
                and_(
                    MetricSnapshot.model_id == model_id,
                    MetricSnapshot.timestamp >= start_dt,
                    MetricSnapshot.timestamp <= end_dt
                )
            )
            .order_by(MetricSnapshot.timestamp)
        )
        
        return result.scalars().all()
    
    async def _get_revenue_time_series(
        self,
        model_id: str,
        start_dt: datetime,
        end_dt: datetime,
        granularity: TimeGranularity
    ) -> Dict[str, List[TimeSeriesDataPoint]]:
        """Get revenue time series data."""
        # Determine time bucket based on granularity
        if granularity == TimeGranularity.HOUR:
            time_bucket = "date_trunc('hour', transaction_date)"
        elif granularity == TimeGranularity.DAY:
            time_bucket = "date_trunc('day', transaction_date)"
        elif granularity == TimeGranularity.WEEK:
            time_bucket = "date_trunc('week', transaction_date)"
        else:  # MONTH
            time_bucket = "date_trunc('month', transaction_date)"
        
        # Query revenue by type and time
        query = text(f"""
            SELECT 
                {time_bucket} as time_bucket,
                transaction_type,
                SUM(amount) as total
            FROM revenue_transactions
            WHERE model_id = :model_id
                AND transaction_date >= :start_date
                AND transaction_date <= :end_date
            GROUP BY time_bucket, transaction_type
            ORDER BY time_bucket
        """)
        
        result = await self.db.execute(
            query,
            {
                'model_id': model_id,
                'start_date': start_dt,
                'end_date': end_dt
            }
        )
        
        # Organize data by type
        data_by_type = {
            'total': {},
            'subscription': {},
            'tip': {},
            'ppv': {}
        }
        
        for row in result:
            timestamp = row.time_bucket
            amount = float(row.total or 0)
            
            # Add to specific type
            if row.transaction_type == 'subscription':
                data_by_type['subscription'][timestamp] = amount
            elif row.transaction_type == 'tip':
                data_by_type['tip'][timestamp] = amount
            elif row.transaction_type in ['ppv_message', 'ppv_post']:
                data_by_type['ppv'][timestamp] = data_by_type['ppv'].get(timestamp, 0) + amount
            
            # Add to total
            data_by_type['total'][timestamp] = data_by_type['total'].get(timestamp, 0) + amount
        
        # Convert to time series format
        result = {}
        for type_name, data in data_by_type.items():
            result[type_name] = [
                TimeSeriesDataPoint(timestamp=ts, value=value)
                for ts, value in sorted(data.items())
            ]
        
        return result
    
    async def _get_fan_revenue_time_series(
        self,
        fan_id: str,
        start_dt: datetime,
        end_dt: datetime,
        granularity: TimeGranularity
    ) -> List[TimeSeriesDataPoint]:
        """Get revenue time series for a specific fan."""
        # Determine time bucket
        if granularity == TimeGranularity.HOUR:
            time_bucket = "date_trunc('hour', transaction_date)"
        elif granularity == TimeGranularity.DAY:
            time_bucket = "date_trunc('day', transaction_date)"
        elif granularity == TimeGranularity.WEEK:
            time_bucket = "date_trunc('week', transaction_date)"
        else:  # MONTH
            time_bucket = "date_trunc('month', transaction_date)"
        
        query = text(f"""
            SELECT 
                {time_bucket} as time_bucket,
                SUM(amount) as total
            FROM revenue_transactions
            WHERE fan_id = :fan_id
                AND transaction_date >= :start_date
                AND transaction_date <= :end_date
            GROUP BY time_bucket
            ORDER BY time_bucket
        """)
        
        result = await self.db.execute(
            query,
            {
                'fan_id': fan_id,
                'start_date': start_dt,
                'end_date': end_dt
            }
        )
        
        return [
            TimeSeriesDataPoint(
                timestamp=row.time_bucket,
                value=float(row.total or 0)
            )
            for row in result
        ]
    
    async def _get_fans_by_ids(self, fan_ids: List[str]) -> List[Fan]:
        """Get fan records by IDs."""
        result = await self.db.execute(
            select(Fan).where(Fan.id.in_(fan_ids))
        )
        return result.scalars().all()
    
    async def _get_latest_snapshot_in_range(
        self,
        model_id: str,
        start_dt: datetime,
        end_dt: datetime
    ) -> Optional[MetricSnapshot]:
        """Get the latest snapshot in a date range."""
        result = await self.db.execute(
            select(MetricSnapshot)
            .where(
                and_(
                    MetricSnapshot.model_id == model_id,
                    MetricSnapshot.timestamp >= start_dt,
                    MetricSnapshot.timestamp <= end_dt
                )
            )
            .order_by(MetricSnapshot.timestamp.desc())
            .limit(1)
        )
        
        return result.scalar_one_or_none()
    
    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache."""
        try:
            data = await redis_client.get(f"analytics:{key}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    async def _save_to_cache(self, key: str, data: Dict[str, Any], ttl: int):
        """Save data to cache."""
        try:
            await redis_client.setex(
                f"analytics:{key}",
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"Cache save error: {e}")