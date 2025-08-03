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

from core.redis import redis_client
from models.analytics import MetricSnapshot
from modules.analytics.domain.models import (\n    RevenueTransaction,\n    ContentPerformance,\n    FanSpendingHistory,\n    CategoryPerformance,\n    AnalyticsCache,\n    AggregationPeriod\n)
from modules.analytics.domain.schemas import (
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
from modules.analytics.application.analytics_aggregator import AnalyticsAggregator
from modules.analytics.application.time_series_calculator import TimeSeriesCalculator
from modules.analytics.infrastructure.cache_strategy import cache_strategy, CacheTier
from core.domain.models import ModelProfile
from models.subscriber import Subscriber as Fan


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
        Get subscriber growth chart data using real-time aggregated data.
        
        Returns data for:
        - Total subscribers
        - Paying subscribers
        - Non-paying fans
        """
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Map granularity to aggregation period
        period_map = {
            TimeGranularity.HOUR: AggregationPeriod.HOURLY,
            TimeGranularity.DAY: AggregationPeriod.DAILY,
            TimeGranularity.WEEK: AggregationPeriod.WEEKLY,
            TimeGranularity.MONTH: AggregationPeriod.MONTHLY
        }
        aggregation_period = period_map.get(granularity, AggregationPeriod.DAILY)
        
        # Check cache
        cache_key = cache_strategy.generate_cache_key(
            'subscriber_growth',
            str(agency_id),
            model_id,
            start_dt,
            end_dt,
            aggregation_period
        )
        
        cached = await cache_strategy.get(cache_key, CacheTier.HOT)
        if cached:
            return ChartResponse(**cached)
            
        # Get aggregated metrics using AnalyticsAggregator
        aggregator = AnalyticsAggregator(self.db)
        metrics = await aggregator.aggregate_metrics(
            agency_id=str(agency_id),
            model_id=model_id,
            start_date=start_dt,
            end_date=end_dt,
            period=aggregation_period
        )
        
        # Extract fan time series
        fan_data = metrics.get('fans', {})
        time_series_data = fan_data.get('time_series', [])
        
        # Build chart series
        total_series_data = []
        paying_series_data = []
        non_paying_series_data = []
        
        for point in time_series_data:
            timestamp = datetime.fromisoformat(point['period'])
            total = point.get('total_fans', 0)
            paying = point.get('subscribers', 0)
            non_paying = total - paying
            
            total_series_data.append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=total
                )
            )
            paying_series_data.append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=paying
                )
            )
            non_paying_series_data.append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=non_paying
                )
            )
        
        # Use TimeSeriesCalculator for trend analysis
        if total_series_data:
            calculator = TimeSeriesCalculator()
            trend = calculator.calculate_trend(total_series_data)
            growth = calculator.calculate_growth_rate(total_series_data)
        
        # Build chart series
        total_series = ChartSeries(
            name="Total Subscribers",
            data=total_series_data,
            color="#8884d8"
        )
        
        paying_series = ChartSeries(
            name="Paying Subscribers",
            data=paying_series_data,
            color="#82ca9d"
        )
        
        non_paying_series = ChartSeries(
            name="Non-Paying Fans",
            data=non_paying_series_data,
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
            },
            metadata={
                'trend': trend.direction if 'trend' in locals() else None,
                'growth_rate': growth.percentage_growth if 'growth' in locals() else None,
                'total_growth': fan_data.get('subscriber_growth', 0),
                'churn_rate': fan_data.get('churn_rate', 0)
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
        await cache_strategy.set(
            cache_key,
            response.model_dump(),
            CacheTier.HOT,
            period=aggregation_period
        )
        
        return response
    
    async def get_revenue_timeline_chart(
        self,
        model_id: str,
        period_start: date,
        period_end: date,
        granularity: TimeGranularity = TimeGranularity.DAY
    ) -> ChartResponse:
        """
        Get revenue timeline chart data using real-time aggregated data.
        
        Returns data for:
        - Total revenue
        - Subscription revenue
        - Tip revenue
        - PPV revenue
        """
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Map granularity to aggregation period
        period_map = {
            TimeGranularity.HOUR: AggregationPeriod.HOURLY,
            TimeGranularity.DAY: AggregationPeriod.DAILY,
            TimeGranularity.WEEK: AggregationPeriod.WEEKLY,
            TimeGranularity.MONTH: AggregationPeriod.MONTHLY
        }
        aggregation_period = period_map.get(granularity, AggregationPeriod.DAILY)
        
        # Check cache
        cache_key = cache_strategy.generate_cache_key(
            'revenue_timeline',
            str(agency_id),
            model_id,
            start_dt,
            end_dt,
            aggregation_period
        )
        
        cached = await cache_strategy.get(cache_key, CacheTier.HOT)
        if cached:
            return ChartResponse(**cached)
            
        # Get aggregated metrics using AnalyticsAggregator
        aggregator = AnalyticsAggregator(self.db)
        metrics = await aggregator.aggregate_metrics(
            agency_id=str(agency_id),
            model_id=model_id,
            start_date=start_dt,
            end_date=end_dt,
            period=aggregation_period
        )
        
        # Extract revenue time series
        revenue_data = metrics.get('revenue', {})
        time_series_data = revenue_data.get('time_series', [])
        
        # Organize data by revenue type
        revenue_by_type = {
            'total': [],
            'subscription': [],
            'tip': [],
            'ppv': []
        }
        
        for point in time_series_data:
            timestamp = datetime.fromisoformat(point['period'])
            
            # Total revenue
            revenue_by_type['total'].append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=float(point.get('revenue', 0))
                )
            )
            
            # Revenue by type
            by_type = point.get('revenue_by_type', {})
            revenue_by_type['subscription'].append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=float(by_type.get('subscription', 0))
                )
            )
            revenue_by_type['tip'].append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=float(by_type.get('tip', 0))
                )
            )
            revenue_by_type['ppv'].append(
                TimeSeriesDataPoint(
                    timestamp=timestamp,
                    value=float(by_type.get('ppv_message', 0) + by_type.get('ppv_post', 0))
                )
            )
        
        # Build chart series
        series = []
        
        # Total revenue
        series.append(ChartSeries(
            name="Total Revenue",
            data=revenue_by_type['total'],
            color="#8884d8",
            type=ChartType.AREA
        ))
        
        # Subscription revenue
        series.append(ChartSeries(
            name="Subscriptions",
            data=revenue_by_type['subscription'],
            color="#82ca9d"
        ))
        
        # Tip revenue
        series.append(ChartSeries(
            name="Tips",
            data=revenue_by_type['tip'],
            color="#ffc658"
        ))
        
        # PPV revenue
        series.append(ChartSeries(
            name="PPV",
            data=revenue_by_type['ppv'],
            color="#ff7c7c"
        ))
        
        # Use TimeSeriesCalculator for trend analysis
        if revenue_by_type['total']:
            calculator = TimeSeriesCalculator()
            trend = calculator.calculate_trend(revenue_by_type['total'])
            growth = calculator.calculate_growth_rate(revenue_by_type['total'])
        
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
            },
            metadata={
                'trend': trend.direction if 'trend' in locals() else None,
                'growth_rate': growth.percentage_growth if 'growth' in locals() else None
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
        await cache_strategy.set(
            cache_key,
            response.model_dump(),
            CacheTier.HOT,
            period=aggregation_period
        )
        
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
        Get revenue chart for specific fans using real-time aggregated data.
        
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
        
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Map granularity to aggregation period
        period_map = {
            TimeGranularity.HOUR: AggregationPeriod.HOURLY,
            TimeGranularity.DAY: AggregationPeriod.DAILY,
            TimeGranularity.WEEK: AggregationPeriod.WEEKLY,
            TimeGranularity.MONTH: AggregationPeriod.MONTHLY
        }
        aggregation_period = period_map.get(granularity, AggregationPeriod.DAILY)
        
        # Check cache
        cache_key = cache_strategy.generate_cache_key(
            'fan_revenue',
            str(agency_id),
            model_id,
            start_dt,
            end_dt,
            aggregation_period,
            fan_ids=','.join(sorted(fan_ids))
        )
        
        cached = await cache_strategy.get(cache_key, CacheTier.HOT)
        if cached:
            return ChartResponse(**cached)
            
        # Get fan details
        fans = await self._get_fans_by_ids(fan_ids)
        
        # Get aggregated metrics using AnalyticsAggregator
        aggregator = AnalyticsAggregator(self.db)
        
        # Build series for each fan
        series = []
        colors = [
            "#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1",
            "#d084d0", "#ffb347", "#79d2a6", "#ff91a4", "#a4a4ff"
        ]
        
        for i, fan in enumerate(fans):
            # Get aggregated data for this specific fan
            # Use aggregate_metrics with model_id filter
            fan_metrics = await aggregator.aggregate_metrics(
                agency_id=str(agency_id),
                model_id=model_id,
                start_date=start_dt,
                end_date=end_dt,
                period=aggregation_period
            )
            
            # Extract time series data
            time_series_data = fan_metrics.get('time_series', [])
            revenue_data = [
                TimeSeriesDataPoint(
                    timestamp=datetime.fromisoformat(point['period']),
                    value=float(point.get('total_spent', 0))
                )
                for point in time_series_data
            ]
            
            series.append(ChartSeries(
                name=fan.username,
                data=revenue_data,
                color=colors[i % len(colors)],
                metadata={
                    'total_spent': fan_metrics.get('total_spent', 0),
                    'subscription_months': fan_metrics.get('subscription_months', 0),
                    'average_monthly_spend': fan_metrics.get('average_monthly_spend', 0)
                }
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
        await cache_strategy.set(
            cache_key,
            response.model_dump(),
            CacheTier.HOT,
            period=aggregation_period
        )
        
        return response
    
    async def get_category_popularity_data(
        self,
        model_id: str,
        period_start: date,
        period_end: date
    ) -> CategoryPopularityData:
        """
        Get content category popularity metrics using real-time aggregated data.
        
        Returns:
        - Category performance metrics
        - Most profitable/viewed/engaging categories
        """
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Check cache
        cache_key = cache_strategy.generate_cache_key(
            'category_popularity',
            str(agency_id),
            model_id,
            start_dt,
            end_dt
        )
        
        cached = await cache_strategy.get(cache_key, CacheTier.WARM)
        if cached:
            return CategoryPopularityData(**cached)
            
        # Get aggregated metrics using AnalyticsAggregator
        aggregator = AnalyticsAggregator(self.db)
        metrics = await aggregator.aggregate_metrics(
            agency_id=str(agency_id),
            model_id=model_id,
            start_date=start_dt,
            end_date=end_dt,
            period=AggregationPeriod.DAILY
        )
        
        # Get content performance data from aggregated metrics
        content_data = metrics.get('content', {})
        category_metrics = content_data.get('by_category', {})
        
        # Build category performance list
        categories = []
        for category_name, data in category_metrics.items():
            total_views = data.get('views', 0)
            total_likes = data.get('likes', 0)
            total_comments = data.get('comments', 0)
            
            engagement_rate = 0.0
            if total_views > 0:
                engagement_rate = ((total_likes + total_comments) / total_views) * 100
            
            categories.append(ContentCategoryPerformance(
                category_name=category_name,
                content_count=data.get('count', 0),
                total_revenue=Decimal(str(data.get('revenue', 0))),
                avg_revenue_per_content=Decimal(str(
                    data.get('revenue', 0) / max(1, data.get('count', 0))
                )),
                total_views=total_views,
                total_likes=total_likes,
                engagement_rate=engagement_rate,
                top_performing_content=data.get('top_content', [])
            ))
        
        # Sort to find top categories
        by_revenue = sorted(categories, key=lambda x: x.total_revenue, reverse=True)
        by_views = sorted(categories, key=lambda x: x.total_views, reverse=True)
        by_engagement = sorted(categories, key=lambda x: x.engagement_rate, reverse=True)
        
        response = CategoryPopularityData(
            period_start=start_dt,
            period_end=end_dt,
            categories=categories,
            most_profitable_category=by_revenue[0].category_name if by_revenue else "",
            most_viewed_category=by_views[0].category_name if by_views else "",
            highest_engagement_category=by_engagement[0].category_name if by_engagement else ""
        )
        
        # Cache the response
        await cache_strategy.set(
            cache_key,
            response.model_dump(),
            CacheTier.WARM,
            period=AggregationPeriod.DAILY
        )
        
        return response
    
    async def get_content_performance_data(
        self,
        model_id: str,
        content_ids: List[str]
    ) -> List[ContentPerformanceData]:
        """Get performance data for specific content pieces using real-time data."""
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Check cache for each content
        performance_data = []
        uncached_ids = []
        
        for content_id in content_ids:
            cache_key = f"content_performance:{agency_id}:{model_id}:{content_id}"
            cached = await cache_strategy.get(cache_key, CacheTier.HOT)
            if cached:
                performance_data.append(ContentPerformanceData(**cached))
            else:
                uncached_ids.append(content_id)
        
        # Get uncached content performance from database
        if uncached_ids:
            result = await self.db.execute(
                select(ContentPerformance)
                .where(
                    and_(
                        ContentPerformance.model_id == model_id,
                        ContentPerformance.content_id.in_(uncached_ids)
                    )
                )
            )
            
            performances = result.scalars().all()
            
            for perf in performances:
                data = ContentPerformanceData(
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
                performance_data.append(data)
                
                # Cache the data
                cache_key = f"content_performance:{agency_id}:{model_id}:{perf.content_id}"
                await cache_strategy.set(
                    cache_key,
                    data.model_dump(),
                    CacheTier.HOT,
                    ttl=300  # 5 minutes
                )
        
        return performance_data
    
    async def get_dashboard_summary(
        self,
        model_id: str,
        period: str = "today"
    ) -> DashboardSummary:
        """
        Get high-level dashboard metrics using real-time aggregated data.
        
        Args:
            model_id: Model ID
            period: Period to show (today, week, month)
            
        Returns:
            Dashboard summary data
        """
        # Get model's agency ID
        result = await self.db.execute(
            select(ModelProfile.agency_id).where(ModelProfile.id == model_id)
        )
        agency_id = result.scalar_one_or_none()
        if not agency_id:
            raise ValueError(f"Model {model_id} not found")
            
        # Calculate date ranges
        now = datetime.utcnow()
        if period == "today":
            current_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = current_start - timedelta(days=1)
            prev_end = current_start
            aggregation_period = AggregationPeriod.HOURLY
        elif period == "week":
            current_start = now - timedelta(days=now.weekday())
            current_start = current_start.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = current_start - timedelta(days=7)
            prev_end = current_start
            aggregation_period = AggregationPeriod.DAILY
        else:  # month
            current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_start = (current_start - timedelta(days=1)).replace(day=1)
            prev_end = current_start
            aggregation_period = AggregationPeriod.DAILY
            
        # Check cache
        cache_key = cache_strategy.generate_cache_key(
            'dashboard',
            str(agency_id),
            model_id,
            current_start,
            now,
            aggregation_period
        )
        
        cached = await cache_strategy.get(cache_key, CacheTier.HOT)
        if cached:
            return DashboardSummary(**cached)
            
        # Get aggregated metrics using AnalyticsAggregator
        aggregator = AnalyticsAggregator(self.db)
        
        # Get current period metrics
        current_metrics = await aggregator.aggregate_metrics(
            agency_id=str(agency_id),
            model_id=model_id,
            start_date=current_start,
            end_date=now,
            period=aggregation_period
        )
        
        # Get previous period metrics for comparison
        prev_metrics = await aggregator.aggregate_metrics(
            agency_id=str(agency_id),
            model_id=model_id,
            start_date=prev_start,
            end_date=prev_end,
            period=aggregation_period
        )
        
        # Extract values with defaults
        current_revenue = current_metrics.get('revenue', {}).get('total_revenue', 0)
        prev_revenue = prev_metrics.get('revenue', {}).get('total_revenue', 0)
        
        current_fans = current_metrics.get('fans', {})
        prev_fans = prev_metrics.get('fans', {})
        
        current_subscribers = current_fans.get('subscribers', 0)
        prev_subscribers = prev_fans.get('subscribers', 0)
        
        current_total_fans = current_fans.get('total_fans', 0)
        prev_total_fans = prev_fans.get('total_fans', 0)
        
        # Calculate changes
        revenue_change = 0.0
        if prev_revenue > 0:
            revenue_change = ((current_revenue - prev_revenue) / prev_revenue) * 100
            
        subscriber_change = 0.0
        if prev_total_fans > 0:
            subscriber_change = ((current_total_fans - prev_total_fans) / prev_total_fans) * 100
            
        paying_subscriber_change = 0.0
        if prev_subscribers > 0:
            paying_subscriber_change = ((current_subscribers - prev_subscribers) / prev_subscribers) * 100
            
        # Calculate average revenue per subscriber
        avg_revenue_per_subscriber = Decimal('0')
        if current_subscribers > 0:
            avg_revenue_per_subscriber = Decimal(str(current_revenue)) / current_subscribers
            
        # Calculate conversion rate
        conversion_rate = 0.0
        if current_total_fans > 0:
            conversion_rate = (current_subscribers / current_total_fans) * 100
            
        summary = DashboardSummary(
            period=period,
            total_revenue=Decimal(str(current_revenue)),
            revenue_change=float(revenue_change),
            total_subscribers=current_total_fans,
            subscriber_change=float(subscriber_change),
            paying_subscribers=current_subscribers,
            paying_subscriber_change=float(paying_subscriber_change),
            avg_revenue_per_subscriber=avg_revenue_per_subscriber,
            conversion_rate=float(conversion_rate)
        )
        
        # Cache the result
        await cache_strategy.set(
            cache_key,
            summary.model_dump(),
            CacheTier.HOT,
            period=aggregation_period
        )
        
        return summary
    
    async def _get_metric_snapshots(
        self,
        model_id: str,
        start_dt: datetime,
        end_dt: datetime,
        granularity: TimeGranularity
    ) -> List[MetricSnapshot]:
        """Get metric snapshots for a time range.
        
        Note: This method is kept for backwards compatibility but should be replaced
        with AnalyticsAggregator calls in the future.
        """
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
        """Get revenue time series data.
        
        Note: This method is kept for backwards compatibility but should be replaced
        with AnalyticsAggregator calls in the future.
        """
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
        """Get data from cache.
        
        Note: This method is deprecated. Use cache_strategy directly instead.
        """
        try:
            data = await redis_client.get(f"analytics:{key}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    async def _save_to_cache(self, key: str, data: Dict[str, Any], ttl: int):
        """Save data to cache.
        
        Note: This method is deprecated. Use cache_strategy directly instead.
        """
        try:
            await redis_client.setex(
                f"analytics:{key}",
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"Cache save error: {e}")