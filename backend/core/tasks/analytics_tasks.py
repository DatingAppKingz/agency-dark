"""
Analytics calculation tasks
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, func, and_

from core.database import get_db_context
from core.models import Agency, ModelProfile, Transaction, MetricSnapshot
from core.redis import redis_client

logger = get_task_logger(__name__)


@shared_task(bind=True)
def calculate_daily_metrics(self, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate daily metrics for agencies
    """
    try:
        results = {
            'agencies_processed': 0,
            'metrics_calculated': 0,
            'errors': []
        }
        
        async def _calculate():
            async with get_db_context() as db:
                # Get agencies to process
                query = select(Agency).where(Agency.is_active == True)
                if agency_id:
                    query = query.where(Agency.id == agency_id)
                
                result = await db.execute(query)
                agencies = result.scalars().all()
                
                today = datetime.utcnow().date()
                yesterday = today - timedelta(days=1)
                
                for agency in agencies:
                    try:
                        # Calculate revenue
                        revenue_result = await db.execute(
                            select(func.sum(Transaction.amount)).where(
                                and_(
                                    Transaction.agency_id == agency.id,
                                    func.date(Transaction.created_at) == yesterday,
                                    Transaction.type.in_(['payment', 'tip', 'subscription'])
                                )
                            )
                        )
                        daily_revenue = revenue_result.scalar() or 0
                        
                        # Calculate transaction count
                        tx_count_result = await db.execute(
                            select(func.count(Transaction.id)).where(
                                and_(
                                    Transaction.agency_id == agency.id,
                                    func.date(Transaction.created_at) == yesterday
                                )
                            )
                        )
                        transaction_count = tx_count_result.scalar() or 0
                        
                        # Calculate active models
                        active_models_result = await db.execute(
                            select(func.count(ModelProfile.id)).where(
                                and_(
                                    ModelProfile.agency_id == agency.id,
                                    ModelProfile.is_active == True
                                )
                            )
                        )
                        active_models = active_models_result.scalar() or 0
                        
                        # Create metric snapshot
                        snapshot = MetricSnapshot(
                            agency_id=agency.id,
                            date=yesterday,
                            revenue=daily_revenue,
                            transaction_count=transaction_count,
                            active_models=active_models,
                            metrics={
                                'avg_transaction_value': daily_revenue / transaction_count if transaction_count > 0 else 0,
                                'revenue_per_model': daily_revenue / active_models if active_models > 0 else 0
                            }
                        )
                        db.add(snapshot)
                        
                        results['agencies_processed'] += 1
                        results['metrics_calculated'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to calculate metrics for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                
                await db.commit()
        
        # Run async function
        import asyncio
        asyncio.run(_calculate())
        
        logger.info(f"Daily metrics calculation completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Daily metrics calculation failed: {exc}")
        raise


@shared_task
def update_cache_analytics() -> Dict[str, Any]:
    """
    Update cached analytics data
    """
    try:
        results = {
            'caches_updated': 0,
            'errors': []
        }
        
        async def _update():
            async with get_db_context() as db:
                # Get all agencies
                result = await db.execute(
                    select(Agency).where(Agency.is_active == True)
                )
                agencies = result.scalars().all()
                
                for agency in agencies:
                    try:
                        # Calculate real-time metrics
                        now = datetime.utcnow()
                        hour_ago = now - timedelta(hours=1)
                        
                        # Hourly revenue
                        revenue_result = await db.execute(
                            select(func.sum(Transaction.amount)).where(
                                and_(
                                    Transaction.agency_id == agency.id,
                                    Transaction.created_at >= hour_ago,
                                    Transaction.type.in_(['payment', 'tip', 'subscription'])
                                )
                            )
                        )
                        hourly_revenue = revenue_result.scalar() or 0
                        
                        # Active fans (users who made transactions)
                        fans_result = await db.execute(
                            select(func.count(func.distinct(Transaction.user_id))).where(
                                and_(
                                    Transaction.agency_id == agency.id,
                                    Transaction.created_at >= hour_ago
                                )
                            )
                        )
                        active_fans = fans_result.scalar() or 0
                        
                        # Cache the data
                        cache_key = f"analytics:{agency.id}:realtime"
                        cache_data = {
                            'hourly_revenue': float(hourly_revenue),
                            'active_fans': active_fans,
                            'last_updated': now.isoformat()
                        }
                        
                        await redis_client.setex(
                            cache_key,
                            300,  # 5 minutes TTL
                            json.dumps(cache_data)
                        )
                        
                        results['caches_updated'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to update cache for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
        
        # Run async function
        import asyncio
        asyncio.run(_update())
        
        return results
        
    except Exception as exc:
        logger.error(f"Cache update failed: {exc}")
        raise


@shared_task
def calculate_model_rankings() -> Dict[str, Any]:
    """
    Calculate model performance rankings
    """
    try:
        results = {
            'models_ranked': 0,
            'rankings_updated': 0
        }
        
        async def _calculate():
            async with get_db_context() as db:
                # Get all active models with their 30-day revenue
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                
                model_revenues = await db.execute(
                    select(
                        ModelProfile.id,
                        ModelProfile.username,
                        func.sum(Transaction.amount).label('total_revenue')
                    ).select_from(ModelProfile).join(
                        Transaction,
                        Transaction.model_id == ModelProfile.id
                    ).where(
                        and_(
                            ModelProfile.is_active == True,
                            Transaction.created_at >= thirty_days_ago,
                            Transaction.type.in_(['payment', 'tip', 'subscription'])
                        )
                    ).group_by(
                        ModelProfile.id,
                        ModelProfile.username
                    ).order_by(
                        func.sum(Transaction.amount).desc()
                    )
                )
                
                models = model_revenues.all()
                
                # Calculate rankings and percentiles
                total_models = len(models)
                for rank, (model_id, username, revenue) in enumerate(models, 1):
                    percentile = (total_models - rank + 1) / total_models * 100
                    
                    # Cache ranking data
                    cache_key = f"ranking:model:{model_id}"
                    ranking_data = {
                        'rank': rank,
                        'percentile': round(percentile, 2),
                        'revenue_30d': float(revenue) if revenue else 0,
                        'username': username,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    
                    await redis_client.setex(
                        cache_key,
                        3600,  # 1 hour TTL
                        json.dumps(ranking_data)
                    )
                    
                    results['models_ranked'] += 1
                
                # Store global rankings
                global_rankings = [
                    {
                        'model_id': str(model_id),
                        'username': username,
                        'revenue': float(revenue) if revenue else 0,
                        'rank': rank
                    }
                    for rank, (model_id, username, revenue) in enumerate(models[:100], 1)  # Top 100
                ]
                
                await redis_client.setex(
                    "rankings:global:top100",
                    3600,
                    json.dumps(global_rankings)
                )
                
                results['rankings_updated'] = 1
        
        # Run async function
        import asyncio
        asyncio.run(_calculate())
        
        logger.info(f"Model rankings calculated: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Model rankings calculation failed: {exc}")
        raise


@shared_task
def generate_trend_analysis(model_id: str) -> Dict[str, Any]:
    """
    Generate trend analysis for a specific model
    """
    try:
        async def _analyze():
            async with get_db_context() as db:
                # Get last 30 days of data
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=30)
                
                # Daily revenue data
                daily_revenue = await db.execute(
                    select(
                        func.date(Transaction.created_at).label('date'),
                        func.sum(Transaction.amount).label('revenue')
                    ).where(
                        and_(
                            Transaction.model_id == model_id,
                            Transaction.created_at >= start_date,
                            Transaction.type.in_(['payment', 'tip', 'subscription'])
                        )
                    ).group_by(
                        func.date(Transaction.created_at)
                    ).order_by(
                        func.date(Transaction.created_at)
                    )
                )
                
                revenue_data = daily_revenue.all()
                
                if not revenue_data:
                    return {
                        'status': 'no_data',
                        'message': 'No revenue data available for analysis'
                    }
                
                # Convert to numpy arrays for analysis
                dates = [row.date for row in revenue_data]
                revenues = np.array([float(row.revenue) for row in revenue_data])
                
                # Calculate trend metrics
                mean_revenue = np.mean(revenues)
                std_revenue = np.std(revenues)
                
                # Simple linear regression for trend
                x = np.arange(len(revenues))
                coefficients = np.polyfit(x, revenues, 1)
                trend_slope = coefficients[0]
                
                # Determine trend direction
                if trend_slope > mean_revenue * 0.01:  # 1% of mean
                    trend = 'increasing'
                elif trend_slope < -mean_revenue * 0.01:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
                
                # Calculate growth rate
                if len(revenues) >= 7:
                    last_week = np.mean(revenues[-7:])
                    prev_week = np.mean(revenues[-14:-7]) if len(revenues) >= 14 else mean_revenue
                    week_over_week_growth = ((last_week - prev_week) / prev_week * 100) if prev_week > 0 else 0
                else:
                    week_over_week_growth = 0
                
                analysis = {
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat(),
                        'days': len(revenue_data)
                    },
                    'revenue': {
                        'total': float(np.sum(revenues)),
                        'average_daily': float(mean_revenue),
                        'std_deviation': float(std_revenue),
                        'highest_day': {
                            'date': dates[np.argmax(revenues)].isoformat(),
                            'amount': float(np.max(revenues))
                        },
                        'lowest_day': {
                            'date': dates[np.argmin(revenues)].isoformat(),
                            'amount': float(np.min(revenues))
                        }
                    },
                    'trend': {
                        'direction': trend,
                        'slope': float(trend_slope),
                        'week_over_week_growth': float(week_over_week_growth)
                    },
                    'forecast': {
                        'next_7_days': float(mean_revenue * 7 + trend_slope * 3.5 * 7)  # Simple projection
                    }
                }
                
                # Cache the analysis
                cache_key = f"analysis:trend:{model_id}"
                await redis_client.setex(
                    cache_key,
                    3600,  # 1 hour TTL
                    json.dumps(analysis)
                )
                
                return analysis
        
        # Run async function
        import asyncio
        result = asyncio.run(_analyze())
        
        logger.info(f"Trend analysis generated for model {model_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Trend analysis failed for model {model_id}: {exc}")
        raise