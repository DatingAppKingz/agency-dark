"""
Analytics job scheduling and execution.

Provides background jobs for analytics data collection,
aggregation, and cleanup using Celery or similar task queue.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
from decimal import Decimal
import asyncio
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select, delete, and_
from celery import Celery, Task
from celery.schedules import crontab

from core.config import settings
from core.database import get_async_session_maker
from modules.analytics.application.analytics_aggregator import AnalyticsAggregator
from modules.analytics.application.time_series_calculator import TimeSeriesCalculator
from modules.analytics.domain.models import AnalyticsMetric, MetricType, AggregationPeriod, ModelAnalytics, FanAnalytics
from modules.analytics.domain.schemas import TimeSeriesData
from core.domain.models import Agency, ModelProfile
from core.cache import cache_manager


logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'analytics_jobs',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)


class AsyncTask(Task):
    """Base task class that handles async database sessions."""
    
    _session_maker = None
    
    @property
    def session_maker(self):
        if self._session_maker is None:
            engine = create_async_engine(settings.DATABASE_URL)
            self._session_maker = get_async_session_maker(engine)
        return self._session_maker


def async_task(func):
    """Decorator to run async functions in Celery."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


@celery_app.task(base=AsyncTask, name='analytics.aggregate_hourly_metrics')
@async_task
async def aggregate_hourly_metrics():
    """
    Aggregate metrics for the last hour.
    Runs every hour.
    """
    logger.info("Starting hourly metrics aggregation")
    
    async with aggregate_hourly_metrics.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        
        # Get all active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        for agency in agencies:
            try:
                # Aggregate agency-level metrics
                metrics = await aggregator.aggregate_metrics(
                    agency_id=str(agency.id),
                    start_date=start_time,
                    end_date=end_time,
                    period=AggregationPeriod.HOURLY
                )
                
                # Save aggregated metrics
                await aggregator.save_aggregated_metrics(
                    metrics,
                    agency_id=str(agency.id),
                    period=AggregationPeriod.HOURLY
                )
                
                # Also aggregate for each model
                model_result = await session.execute(
                    select(ModelProfile).where(ModelProfile.agency_id == agency.id)
                )
                models = model_result.scalars().all()
                
                for model in models:
                    model_metrics = await aggregator.aggregate_metrics(
                        agency_id=str(agency.id),
                        model_id=str(model.id),
                        start_date=start_time,
                        end_date=end_time,
                        period=AggregationPeriod.HOURLY
                    )
                    
                    await aggregator.save_aggregated_metrics(
                        model_metrics,
                        agency_id=str(agency.id),
                        model_id=str(model.id),
                        period=AggregationPeriod.HOURLY
                    )
                    
                logger.info(f"Completed hourly aggregation for agency {agency.id}")
                
            except Exception as e:
                logger.error(f"Failed hourly aggregation for agency {agency.id}: {e}")
                
        await session.commit()
        
    logger.info("Completed hourly metrics aggregation")
    return {"status": "completed", "agencies_processed": len(agencies)}


@celery_app.task(base=AsyncTask, name='analytics.aggregate_daily_metrics')
@async_task
async def aggregate_daily_metrics():
    """
    Aggregate metrics for the last day.
    Runs daily at midnight.
    """
    logger.info("Starting daily metrics aggregation")
    
    async with aggregate_daily_metrics.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        calculator = TimeSeriesCalculator()
        
        # Get all active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=1)
        
        for agency in agencies:
            try:
                # Aggregate daily metrics
                metrics = await aggregator.aggregate_metrics(
                    agency_id=str(agency.id),
                    start_date=datetime.combine(start_date, datetime.min.time()),
                    end_date=datetime.combine(end_date, datetime.min.time()),
                    period=AggregationPeriod.DAILY
                )
                
                # Calculate trends and growth
                await _calculate_daily_trends(
                    session,
                    calculator,
                    agency.id,
                    metrics
                )
                
                # Save aggregated metrics
                await aggregator.save_aggregated_metrics(
                    metrics,
                    agency_id=str(agency.id),
                    period=AggregationPeriod.DAILY
                )
                
                # Process models
                model_result = await session.execute(
                    select(ModelProfile).where(ModelProfile.agency_id == agency.id)
                )
                models = model_result.scalars().all()
                
                for model in models:
                    model_metrics = await aggregator.aggregate_metrics(
                        agency_id=str(agency.id),
                        model_id=str(model.id),
                        start_date=datetime.combine(start_date, datetime.min.time()),
                        end_date=datetime.combine(end_date, datetime.min.time()),
                        period=AggregationPeriod.DAILY
                    )
                    
                    await _calculate_daily_trends(
                        session,
                        calculator,
                        agency.id,
                        model_metrics,
                        model.id
                    )
                    
                    await aggregator.save_aggregated_metrics(
                        model_metrics,
                        agency_id=str(agency.id),
                        model_id=str(model.id),
                        period=AggregationPeriod.DAILY
                    )
                    
                    # Update model analytics summary
                    await _update_model_analytics(session, model.id, model_metrics)
                    
                logger.info(f"Completed daily aggregation for agency {agency.id}")
                
            except Exception as e:
                logger.error(f"Failed daily aggregation for agency {agency.id}: {e}")
                
        await session.commit()
        
    logger.info("Completed daily metrics aggregation")
    return {"status": "completed", "agencies_processed": len(agencies)}


@celery_app.task(base=AsyncTask, name='analytics.aggregate_weekly_metrics')
@async_task
async def aggregate_weekly_metrics():
    """
    Aggregate metrics for the last week.
    Runs weekly on Sunday night.
    """
    logger.info("Starting weekly metrics aggregation")
    
    async with aggregate_weekly_metrics.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        
        # Get all active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        for agency in agencies:
            try:
                # Aggregate weekly metrics
                metrics = await aggregator.aggregate_metrics(
                    agency_id=str(agency.id),
                    start_date=datetime.combine(start_date, datetime.min.time()),
                    end_date=datetime.combine(end_date, datetime.min.time()),
                    period=AggregationPeriod.WEEKLY
                )
                
                # Save aggregated metrics
                await aggregator.save_aggregated_metrics(
                    metrics,
                    agency_id=str(agency.id),
                    period=AggregationPeriod.WEEKLY
                )
                
                logger.info(f"Completed weekly aggregation for agency {agency.id}")
                
            except Exception as e:
                logger.error(f"Failed weekly aggregation for agency {agency.id}: {e}")
                
        await session.commit()
        
    logger.info("Completed weekly metrics aggregation")
    return {"status": "completed", "agencies_processed": len(agencies)}


@celery_app.task(base=AsyncTask, name='analytics.aggregate_monthly_metrics')
@async_task
async def aggregate_monthly_metrics():
    """
    Aggregate metrics for the last month.
    Runs monthly on the 1st.
    """
    logger.info("Starting monthly metrics aggregation")
    
    async with aggregate_monthly_metrics.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        calculator = TimeSeriesCalculator()
        
        # Get all active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        # Calculate last month's date range
        today = date.today()
        first_day_current_month = today.replace(day=1)
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        first_day_previous_month = last_day_previous_month.replace(day=1)
        
        for agency in agencies:
            try:
                # Aggregate monthly metrics
                metrics = await aggregator.aggregate_metrics(
                    agency_id=str(agency.id),
                    start_date=datetime.combine(first_day_previous_month, datetime.min.time()),
                    end_date=datetime.combine(today, datetime.min.time()),
                    period=AggregationPeriod.MONTHLY
                )
                
                # Generate monthly report data
                await _generate_monthly_report(
                    session,
                    calculator,
                    agency.id,
                    metrics
                )
                
                # Save aggregated metrics
                await aggregator.save_aggregated_metrics(
                    metrics,
                    agency_id=str(agency.id),
                    period=AggregationPeriod.MONTHLY
                )
                
                logger.info(f"Completed monthly aggregation for agency {agency.id}")
                
            except Exception as e:
                logger.error(f"Failed monthly aggregation for agency {agency.id}: {e}")
                
        await session.commit()
        
    logger.info("Completed monthly metrics aggregation")
    return {"status": "completed", "agencies_processed": len(agencies)}


@celery_app.task(base=AsyncTask, name='analytics.cleanup_old_metrics')
@async_task
async def cleanup_old_metrics():
    """
    Clean up old metrics data based on retention policy.
    Runs daily.
    """
    logger.info("Starting metrics cleanup")
    
    async with cleanup_old_metrics.session_maker() as session:
        # Define retention periods
        retention_policy = {
            AggregationPeriod.HOURLY: timedelta(days=7),      # Keep hourly for 1 week
            AggregationPeriod.DAILY: timedelta(days=90),      # Keep daily for 3 months
            AggregationPeriod.WEEKLY: timedelta(days=365),    # Keep weekly for 1 year
            AggregationPeriod.MONTHLY: timedelta(days=730),   # Keep monthly for 2 years
        }
        
        total_deleted = 0
        
        for period, retention_time in retention_policy.items():
            cutoff_date = datetime.utcnow() - retention_time
            
            # Delete old metrics
            result = await session.execute(
                delete(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.period == period,
                        AnalyticsMetric.timestamp < cutoff_date
                    )
                )
            )
            
            deleted_count = result.rowcount
            total_deleted += deleted_count
            
            logger.info(f"Deleted {deleted_count} {period.value} metrics older than {cutoff_date}")
            
        await session.commit()
        
    # Clear old cache entries
    await _cleanup_cache()
    
    logger.info(f"Completed metrics cleanup. Total deleted: {total_deleted}")
    return {"status": "completed", "total_deleted": total_deleted}


@celery_app.task(base=AsyncTask, name='analytics.warm_cache')
@async_task
async def warm_cache():
    """
    Pre-warm analytics cache for better performance.
    Runs every 4 hours.
    """
    logger.info("Starting cache warming")
    
    async with warm_cache.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        
        # Get active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        warmed_count = 0
        
        for agency in agencies:
            try:
                # Warm common date ranges
                date_ranges = [
                    # Last 7 days
                    (datetime.utcnow() - timedelta(days=7), datetime.utcnow()),
                    # Last 30 days
                    (datetime.utcnow() - timedelta(days=30), datetime.utcnow()),
                    # Current month
                    (datetime.utcnow().replace(day=1), datetime.utcnow()),
                ]
                
                for start_date, end_date in date_ranges:
                    # Agency-level metrics
                    await aggregator.aggregate_metrics(
                        agency_id=str(agency.id),
                        start_date=start_date,
                        end_date=end_date,
                        period=AggregationPeriod.DAILY
                    )
                    warmed_count += 1
                    
                # Warm top models
                model_result = await session.execute(
                    select(ModelProfile)
                    .join(ModelAnalytics)
                    .where(ModelProfile.agency_id == agency.id)
                    .order_by(ModelAnalytics.total_revenue.desc())
                    .limit(10)
                )
                top_models = model_result.scalars().all()
                
                for model in top_models:
                    await aggregator.aggregate_metrics(
                        agency_id=str(agency.id),
                        model_id=str(model.id),
                        start_date=datetime.utcnow() - timedelta(days=30),
                        end_date=datetime.utcnow(),
                        period=AggregationPeriod.DAILY
                    )
                    warmed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed cache warming for agency {agency.id}: {e}")
                
    logger.info(f"Completed cache warming. Warmed {warmed_count} cache entries")
    return {"status": "completed", "warmed_count": warmed_count}


@celery_app.task(base=AsyncTask, name='analytics.generate_alerts')
@async_task
async def generate_alerts():
    """
    Generate alerts based on analytics thresholds.
    Runs every hour.
    """
    logger.info("Starting alert generation")
    
    alerts_generated = []
    
    async with generate_alerts.session_maker() as session:
        aggregator = AnalyticsAggregator(session)
        calculator = TimeSeriesCalculator()
        
        # Get all active agencies
        result = await session.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        for agency in agencies:
            try:
                # Get recent metrics
                metrics = await aggregator.aggregate_metrics(
                    agency_id=str(agency.id),
                    start_date=datetime.utcnow() - timedelta(days=1),
                    end_date=datetime.utcnow(),
                    period=AggregationPeriod.HOURLY
                )
                
                # Check for anomalies
                if 'revenue' in metrics and metrics['revenue'].get('time_series'):
                    revenue_series = [
                        TimeSeriesData(
                            timestamp=datetime.fromisoformat(point['period']),
                            value=point['revenue']
                        )
                        for point in metrics['revenue']['time_series']
                    ]
                    
                    # Detect sudden drops
                    if len(revenue_series) >= 2:
                        recent_revenue = revenue_series[-1].value
                        previous_revenue = revenue_series[-2].value
                        
                        if previous_revenue > 0:
                            drop_percentage = ((previous_revenue - recent_revenue) / previous_revenue) * 100
                            
                            if drop_percentage > 50:  # 50% drop threshold
                                alert = {
                                    'agency_id': str(agency.id),
                                    'type': 'revenue_drop',
                                    'severity': 'high',
                                    'message': f"Revenue dropped by {drop_percentage:.1f}% in the last hour",
                                    'timestamp': datetime.utcnow()
                                }
                                alerts_generated.append(alert)
                                await _send_alert(alert)
                                
                # Check for engagement issues
                if 'engagement' in metrics:
                    response_time = metrics['engagement'].get('average_response_time', 0)
                    
                    if response_time > 24:  # 24 hours threshold
                        alert = {
                            'agency_id': str(agency.id),
                            'type': 'slow_response',
                            'severity': 'medium',
                            'message': f"Average response time is {response_time:.1f} hours",
                            'timestamp': datetime.utcnow()
                        }
                        alerts_generated.append(alert)
                        await _send_alert(alert)
                        
            except Exception as e:
                logger.error(f"Failed alert generation for agency {agency.id}: {e}")
                
    logger.info(f"Completed alert generation. Generated {len(alerts_generated)} alerts")
    return {"status": "completed", "alerts_count": len(alerts_generated)}


# Helper functions
async def _calculate_daily_trends(
    session: AsyncSession,
    calculator: TimeSeriesCalculator,
    agency_id: str,
    metrics: Dict[str, Any],
    model_id: Optional[str] = None
):
    """Calculate and store daily trend analysis."""
    # Get historical data for trend calculation
    lookback_days = 30
    
    result = await session.execute(
        select(AnalyticsMetric).where(
            and_(
                AnalyticsMetric.agency_id == agency_id,
                AnalyticsMetric.model_id == model_id,
                AnalyticsMetric.metric_type == MetricType.REVENUE,
                AnalyticsMetric.period == AggregationPeriod.DAILY,
                AnalyticsMetric.timestamp >= datetime.utcnow() - timedelta(days=lookback_days)
            )
        ).order_by(AnalyticsMetric.timestamp)
    )
    
    historical_metrics = result.scalars().all()
    
    if len(historical_metrics) >= 7:  # Need at least a week of data
        # Create time series
        revenue_series = [
            TimeSeriesData(
                timestamp=metric.timestamp,
                value=float(metric.metric_value)
            )
            for metric in historical_metrics
        ]
        
        # Calculate trend
        trend = calculator.calculate_trend(revenue_series)
        growth = calculator.calculate_growth_rate(revenue_series, 'daily')
        
        # Store trend metrics
        trend_metric = AnalyticsMetric(
            agency_id=agency_id,
            model_id=model_id,
            metric_type=MetricType.TREND,
            metric_name='revenue_trend',
            metric_value=trend.slope,
            period=AggregationPeriod.DAILY,
            timestamp=datetime.utcnow(),
            metadata={
                'direction': trend.direction,
                'r_squared': trend.r_squared,
                'growth_rate': growth.percentage_growth
            }
        )
        
        session.add(trend_metric)


async def _update_model_analytics(
    session: AsyncSession,
    model_id: str,
    metrics: Dict[str, Any]
):
    """Update model analytics summary."""
    # Get or create model analytics
    result = await session.execute(
        select(ModelAnalytics).where(ModelAnalytics.model_id == model_id)
    )
    model_analytics = result.scalar_one_or_none()
    
    if not model_analytics:
        model_analytics = ModelAnalytics(
            model_id=model_id,
            total_revenue=Decimal('0'),
            total_fans=0,
            active_fans=0,
            total_messages=0
        )
        session.add(model_analytics)
        
    # Update with latest metrics
    if 'revenue' in metrics:
        model_analytics.total_revenue += Decimal(str(metrics['revenue'].get('total_revenue', 0)))
        
    if 'fans' in metrics:
        model_analytics.total_fans = metrics['fans'].get('total_fans', 0)
        model_analytics.active_fans = metrics['fans'].get('active_fans', 0)
        
    if 'engagement' in metrics:
        model_analytics.total_messages = metrics['engagement'].get('total_messages', 0)
        model_analytics.avg_response_time = metrics['engagement'].get('average_response_time', 0)
        
    model_analytics.last_updated = datetime.utcnow()


async def _generate_monthly_report(
    session: AsyncSession,
    calculator: TimeSeriesCalculator,
    agency_id: str,
    metrics: Dict[str, Any]
):
    """Generate monthly analytics report data."""
    # This would generate detailed monthly reports
    # Could be extended to send email reports, create PDFs, etc.
    logger.info(f"Generating monthly report for agency {agency_id}")
    
    # Store report metadata
    report_metric = AnalyticsMetric(
        agency_id=agency_id,
        metric_type=MetricType.REPORT,
        metric_name='monthly_report',
        metric_value=1,
        period=AggregationPeriod.MONTHLY,
        timestamp=datetime.utcnow(),
        metadata={
            'report_type': 'monthly_summary',
            'metrics': metrics
        }
    )
    
    session.add(report_metric)


async def _cleanup_cache():
    """Clean up old cache entries."""
    # This would interface with the cache manager to remove old entries
    # Implementation depends on cache backend
    logger.info("Cleaning up old cache entries")


async def _send_alert(alert: Dict[str, Any]):
    """Send alert through notification system."""
    # This would integrate with notification service
    # Could send emails, push notifications, webhook calls, etc.
    logger.warning(f"Alert generated: {alert}")


# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    'aggregate-hourly-metrics': {
        'task': 'analytics.aggregate_hourly_metrics',
        'schedule': crontab(minute=5),  # Run at 5 minutes past every hour
    },
    'aggregate-daily-metrics': {
        'task': 'analytics.aggregate_daily_metrics',
        'schedule': crontab(hour=0, minute=30),  # Run at 00:30 daily
    },
    'aggregate-weekly-metrics': {
        'task': 'analytics.aggregate_weekly_metrics',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Run Sunday at 01:00
    },
    'aggregate-monthly-metrics': {
        'task': 'analytics.aggregate_monthly_metrics',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # Run 1st of month at 02:00
    },
    'cleanup-old-metrics': {
        'task': 'analytics.cleanup_old_metrics',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 03:00
    },
    'warm-cache': {
        'task': 'analytics.warm_cache',
        'schedule': crontab(minute=0, hour='*/4'),  # Run every 4 hours
    },
    'generate-alerts': {
        'task': 'analytics.generate_alerts',
        'schedule': crontab(minute=15),  # Run at 15 minutes past every hour
    },
}