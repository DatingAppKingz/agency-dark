"""
Background tasks for fraud detection system

Includes:
- Pattern analysis and learning
- Behavioral profile updates
- Fraud trend monitoring
- Alert generation
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np

from core.database import get_db_context
from core.redis import redis_client
from core.security.fraud_detector import fraud_detector, FraudRiskLevel
from core.logging import get_logger
from core.notifications import notification_service

logger = get_logger(__name__)


@shared_task(name="fraud_detection.analyze_patterns")
def analyze_fraud_patterns():
    """Analyze fraud patterns for improved detection"""
    asyncio.run(_analyze_patterns())


async def _analyze_patterns():
    """Async implementation of pattern analysis"""
    try:
        logger.info("Analyzing fraud patterns")
        
        async with get_db_context() as db:
            # Get recent fraud checks
            result = await db.execute(text("""
                SELECT 
                    user_id,
                    action,
                    score,
                    risk_level,
                    indicators,
                    created_at
                FROM fraud_checks
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC
            """))
            
            fraud_checks = result.fetchall()
            
            if not fraud_checks:
                return
            
            # Analyze patterns by action
            action_patterns = {}
            for check in fraud_checks:
                action = check.action
                if action not in action_patterns:
                    action_patterns[action] = {
                        "scores": [],
                        "high_risk_count": 0,
                        "blocked_count": 0,
                        "indicators": {}
                    }
                
                action_patterns[action]["scores"].append(check.score)
                
                if check.risk_level in ["high", "critical"]:
                    action_patterns[action]["high_risk_count"] += 1
                
                if check.score >= 90:
                    action_patterns[action]["blocked_count"] += 1
                
                # Count indicators
                for indicator in check.indicators:
                    ind_type = indicator.get("type")
                    if ind_type:
                        if ind_type not in action_patterns[action]["indicators"]:
                            action_patterns[action]["indicators"][ind_type] = 0
                        action_patterns[action]["indicators"][ind_type] += 1
            
            # Store pattern analysis
            for action, data in action_patterns.items():
                if data["scores"]:
                    avg_score = np.mean(data["scores"])
                    std_score = np.std(data["scores"])
                    
                    pattern_key = f"fraud_pattern:{action}"
                    await redis_client.hset(pattern_key, mapping={
                        "avg_score": str(avg_score),
                        "std_score": str(std_score),
                        "high_risk_rate": str(data["high_risk_count"] / len(data["scores"])),
                        "block_rate": str(data["blocked_count"] / len(data["scores"])),
                        "top_indicators": json.dumps(
                            sorted(
                                data["indicators"].items(), 
                                key=lambda x: x[1], 
                                reverse=True
                            )[:5]
                        ),
                        "updated_at": datetime.now().isoformat()
                    })
                    await redis_client.expire(pattern_key, 86400 * 7)  # 7 days
            
            # Detect anomalous patterns
            alerts = []
            
            for action, data in action_patterns.items():
                if data["scores"] and data["blocked_count"] > 10:
                    block_rate = data["blocked_count"] / len(data["scores"])
                    if block_rate > 0.3:  # 30% block rate
                        alerts.append({
                            "type": "high_block_rate",
                            "action": action,
                            "block_rate": round(block_rate * 100, 2),
                            "total_checks": len(data["scores"])
                        })
            
            if alerts:
                await notification_service.send_admin_notification(
                    subject="Fraud Pattern Alert",
                    template="fraud_pattern_alert",
                    context={
                        "alerts": alerts,
                        "timestamp": datetime.now().isoformat()
                    }
                )
        
    except Exception as e:
        logger.error(f"Error analyzing fraud patterns: {e}")


@shared_task(name="fraud_detection.update_behavioral_profiles")
def update_behavioral_profiles():
    """Update user behavioral profiles based on recent activity"""
    asyncio.run(_update_profiles())


async def _update_profiles():
    """Async implementation of profile updates"""
    try:
        logger.info("Updating behavioral profiles")
        
        async with get_db_context() as db:
            # Get users with recent activity
            result = await db.execute(text("""
                SELECT DISTINCT user_id
                FROM user_activities
                WHERE created_at >= NOW() - INTERVAL '1 day'
                LIMIT 1000
            """))
            
            user_ids = [row.user_id for row in result]
            
            for user_id in user_ids:
                # Get user's activity patterns
                result = await db.execute(text("""
                    SELECT 
                        EXTRACT(HOUR FROM created_at) as hour,
                        EXTRACT(DOW FROM created_at) as day_of_week,
                        activity_type,
                        COUNT(*) as count
                    FROM user_activities
                    WHERE user_id = :user_id
                        AND created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY hour, day_of_week, activity_type
                """), {"user_id": user_id})
                
                # Build profile
                activity_hours = []
                activity_days = []
                activity_types = {}
                
                for row in result:
                    activity_hours.append(int(row.hour))
                    activity_days.append(int(row.day_of_week))
                    
                    if row.activity_type not in activity_types:
                        activity_types[row.activity_type] = 0
                    activity_types[row.activity_type] += row.count
                
                # Calculate usual patterns
                if activity_hours:
                    # Get most common hours (top 25%)
                    hour_counts = {}
                    for hour in activity_hours:
                        hour_counts[hour] = hour_counts.get(hour, 0) + 1
                    
                    sorted_hours = sorted(
                        hour_counts.items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )
                    usual_hours = [h[0] for h in sorted_hours[:6]]  # Top 6 hours
                    
                    # Update profile
                    profile_key = f"user_behavior:{user_id}"
                    await redis_client.hset(profile_key, mapping={
                        "usual_hours": json.dumps(usual_hours),
                        "usual_days": json.dumps(list(set(activity_days))),
                        "activity_types": json.dumps(activity_types),
                        "profile_updated": datetime.now().isoformat()
                    })
                    await redis_client.expire(profile_key, 2592000)  # 30 days
        
        logger.info(f"Updated behavioral profiles for {len(user_ids)} users")
        
    except Exception as e:
        logger.error(f"Error updating behavioral profiles: {e}")


@shared_task(name="fraud_detection.monitor_trends")
def monitor_fraud_trends():
    """Monitor fraud trends and generate alerts"""
    asyncio.run(_monitor_trends())


async def _monitor_trends():
    """Async implementation of trend monitoring"""
    try:
        logger.info("Monitoring fraud trends")
        
        async with get_db_context() as db:
            # Get trend data for last 7 days
            result = await db.execute(text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as total_checks,
                    AVG(score) as avg_score,
                    COUNT(CASE WHEN score >= 90 THEN 1 END) as blocked_count,
                    COUNT(CASE WHEN risk_level IN ('high', 'critical') THEN 1 END) as high_risk_count
                FROM fraud_checks
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY date
            """))
            
            daily_stats = []
            for row in result:
                daily_stats.append({
                    "date": row.date,
                    "total": row.total_checks,
                    "avg_score": float(row.avg_score),
                    "blocked": row.blocked_count,
                    "high_risk": row.high_risk_count
                })
            
            if len(daily_stats) < 2:
                return
            
            # Detect trends
            alerts = []
            
            # Check for sudden increases
            latest = daily_stats[-1]
            previous = daily_stats[-2]
            
            if latest["total"] > 0 and previous["total"] > 0:
                # Check blocked rate increase
                latest_block_rate = latest["blocked"] / latest["total"]
                prev_block_rate = previous["blocked"] / previous["total"]
                
                if latest_block_rate > prev_block_rate * 2 and latest["blocked"] > 10:
                    alerts.append({
                        "type": "blocked_rate_spike",
                        "current_rate": round(latest_block_rate * 100, 2),
                        "previous_rate": round(prev_block_rate * 100, 2),
                        "date": latest["date"].isoformat()
                    })
                
                # Check average score increase
                if latest["avg_score"] > previous["avg_score"] * 1.5:
                    alerts.append({
                        "type": "risk_score_increase",
                        "current_avg": round(latest["avg_score"], 2),
                        "previous_avg": round(previous["avg_score"], 2),
                        "date": latest["date"].isoformat()
                    })
            
            # Check weekly trends
            if len(daily_stats) == 7:
                weekly_avg_score = np.mean([d["avg_score"] for d in daily_stats])
                weekly_blocked = sum(d["blocked"] for d in daily_stats)
                weekly_total = sum(d["total"] for d in daily_stats)
                
                # Store weekly metrics
                await db.execute(text("""
                    INSERT INTO system_metrics (metric_name, metric_value, metric_type, component, metadata)
                    VALUES 
                        ('fraud_weekly_avg_score', :avg_score, 'gauge', 'fraud_detection', :metadata),
                        ('fraud_weekly_blocked', :blocked, 'counter', 'fraud_detection', :metadata),
                        ('fraud_weekly_total', :total, 'counter', 'fraud_detection', :metadata)
                """), {
                    "avg_score": str(weekly_avg_score),
                    "blocked": str(weekly_blocked),
                    "total": str(weekly_total),
                    "metadata": json.dumps({
                        "week_ending": daily_stats[-1]["date"].isoformat()
                    })
                })
                await db.commit()
            
            # Send alerts if any
            if alerts:
                await notification_service.send_admin_notification(
                    subject="Fraud Trend Alert",
                    template="fraud_trend_alert",
                    context={
                        "alerts": alerts,
                        "daily_stats": daily_stats,
                        "timestamp": datetime.now().isoformat()
                    }
                )
        
    except Exception as e:
        logger.error(f"Error monitoring fraud trends: {e}")


@shared_task(name="fraud_detection.cleanup_old_data")
def cleanup_old_fraud_data():
    """Clean up old fraud detection data"""
    asyncio.run(_cleanup_data())


async def _cleanup_data():
    """Async implementation of data cleanup"""
    try:
        logger.info("Cleaning up old fraud data")
        
        async with get_db_context() as db:
            # Delete old fraud checks (keep 90 days)
            result = await db.execute(text("""
                DELETE FROM fraud_checks
                WHERE created_at < NOW() - INTERVAL '90 days'
                RETURNING id
            """))
            
            deleted_count = result.rowcount
            
            if deleted_count > 0:
                await db.commit()
                logger.info(f"Deleted {deleted_count} old fraud checks")
            
            # Clean up old Redis data
            patterns = [
                "user_behavior:*",
                "fraud_pattern:*",
                "user_locations:*"
            ]
            
            total_cleaned = 0
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(
                        cursor, match=pattern, count=1000
                    )
                    
                    if keys:
                        # Check expiry
                        for key in keys:
                            ttl = await redis_client.ttl(key)
                            if ttl == -1:  # No expiry set
                                # Set expiry to 30 days
                                await redis_client.expire(key, 2592000)
                                total_cleaned += 1
                    
                    if cursor == 0:
                        break
            
            logger.info(f"Set expiry for {total_cleaned} Redis keys")
        
    except Exception as e:
        logger.error(f"Error cleaning up fraud data: {e}")


@shared_task(name="fraud_detection.generate_report")
def generate_fraud_report():
    """Generate daily fraud detection report"""
    asyncio.run(_generate_report())


async def _generate_report():
    """Async implementation of report generation"""
    try:
        logger.info("Generating fraud detection report")
        
        async with get_db_context() as db:
            # Get yesterday's data
            yesterday = datetime.now().date() - timedelta(days=1)
            
            # Get summary statistics
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_checks,
                    AVG(score) as avg_score,
                    COUNT(CASE WHEN score >= 90 THEN 1 END) as blocked,
                    COUNT(CASE WHEN risk_level = 'low' THEN 1 END) as low_risk,
                    COUNT(CASE WHEN risk_level = 'medium' THEN 1 END) as medium_risk,
                    COUNT(CASE WHEN risk_level = 'high' THEN 1 END) as high_risk,
                    COUNT(CASE WHEN risk_level = 'critical' THEN 1 END) as critical_risk
                FROM fraud_checks
                WHERE DATE(created_at) = :date
            """), {"date": yesterday})
            
            stats = result.fetchone()
            
            # Get top blocked users
            result = await db.execute(text("""
                SELECT 
                    fc.user_id,
                    u.email,
                    COUNT(*) as block_count,
                    AVG(fc.score) as avg_score
                FROM fraud_checks fc
                LEFT JOIN users u ON fc.user_id = u.id::text
                WHERE DATE(fc.created_at) = :date
                    AND fc.score >= 90
                GROUP BY fc.user_id, u.email
                ORDER BY block_count DESC
                LIMIT 10
            """), {"date": yesterday})
            
            top_blocked = []
            for row in result:
                top_blocked.append({
                    "user_id": row.user_id,
                    "email": row.email,
                    "blocks": row.block_count,
                    "avg_score": round(row.avg_score, 2)
                })
            
            # Get most common fraud indicators
            result = await db.execute(text("""
                SELECT 
                    jsonb_array_elements(indicators)->>'type' as indicator,
                    COUNT(*) as count
                FROM fraud_checks
                WHERE DATE(created_at) = :date
                    AND jsonb_array_length(indicators) > 0
                GROUP BY indicator
                ORDER BY count DESC
                LIMIT 10
            """), {"date": yesterday})
            
            top_indicators = []
            for row in result:
                top_indicators.append({
                    "type": row.indicator,
                    "count": row.count
                })
            
            # Create report
            report = {
                "report_date": yesterday.isoformat(),
                "summary": {
                    "total_checks": stats.total_checks or 0,
                    "average_score": round(stats.avg_score or 0, 2),
                    "blocked_count": stats.blocked or 0,
                    "block_rate": round((stats.blocked or 0) / (stats.total_checks or 1) * 100, 2)
                },
                "risk_distribution": {
                    "low": stats.low_risk or 0,
                    "medium": stats.medium_risk or 0,
                    "high": stats.high_risk or 0,
                    "critical": stats.critical_risk or 0
                },
                "top_blocked_users": top_blocked,
                "top_indicators": top_indicators
            }
            
            # Send report
            await notification_service.send_admin_notification(
                subject=f"Fraud Detection Report - {yesterday}",
                template="fraud_daily_report",
                context=report
            )
            
            logger.info("Fraud report generated and sent")
        
    except Exception as e:
        logger.error(f"Error generating fraud report: {e}")


# Schedule periodic tasks
from celery.schedules import crontab
from core.tasks import celery_app

celery_app.conf.beat_schedule.update({
    "fraud_pattern_analysis": {
        "task": "fraud_detection.analyze_patterns",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "fraud_profile_update": {
        "task": "fraud_detection.update_behavioral_profiles",
        "schedule": crontab(minute=0, hour=3),  # Daily at 3 AM
    },
    "fraud_trend_monitoring": {
        "task": "fraud_detection.monitor_trends",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "fraud_data_cleanup": {
        "task": "fraud_detection.cleanup_old_data",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),  # Weekly on Sunday
    },
    "fraud_daily_report": {
        "task": "fraud_detection.generate_report",
        "schedule": crontab(minute=0, hour=8),  # Daily at 8 AM
    }
})