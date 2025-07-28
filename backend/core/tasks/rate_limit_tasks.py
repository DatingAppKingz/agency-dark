"""
Background tasks for rate limit management

Includes:
- Cleanup of expired rate limit data
- Monitoring for suspicious patterns
- Auto-unblocking after time periods
- Rate limit analytics
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db_context
from core.redis import redis_client
from core.security.rate_limiter import rate_limiter, RateLimitStrategy
from core.logging import get_logger
from core.notifications import notification_service

logger = get_logger(__name__)


@shared_task(name="rate_limit.cleanup_expired_data")
def cleanup_expired_rate_limit_data():
    """Clean up expired rate limit data from Redis"""
    asyncio.run(_cleanup_expired_data())


async def _cleanup_expired_data():
    """Async implementation of cleanup"""
    try:
        logger.info("Starting rate limit data cleanup")
        
        # Pattern for rate limit keys
        patterns = [
            "rate_limit:*",
            "rate_limit:violations:*",
            "api_key_fail:*"
        ]
        
        total_cleaned = 0
        
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=pattern, count=1000
                )
                
                if keys:
                    # Check TTL for each key
                    for key in keys:
                        ttl = await redis_client.ttl(key)
                        # If no TTL set or very long TTL, check if data is stale
                        if ttl == -1 or ttl > 86400:  # No TTL or > 1 day
                            # Parse key to check age
                            members = await redis_client.zrange(key, 0, -1, withscores=True)
                            if members:
                                latest_score = max(score for _, score in members)
                                age = datetime.now().timestamp() - latest_score
                                
                                # If data is older than 7 days, remove it
                                if age > 604800:  # 7 days
                                    await redis_client.delete(key)
                                    total_cleaned += 1
                
                if cursor == 0:
                    break
        
        logger.info(f"Cleaned up {total_cleaned} expired rate limit keys")
        
    except Exception as e:
        logger.error(f"Error cleaning up rate limit data: {e}")


@shared_task(name="rate_limit.monitor_violations")
def monitor_rate_limit_violations():
    """Monitor for patterns of rate limit violations"""
    asyncio.run(_monitor_violations())


async def _monitor_violations():
    """Async implementation of violation monitoring"""
    try:
        logger.info("Monitoring rate limit violations")
        
        # Get all blocked identifiers
        blocked = await rate_limiter.get_blocked_identifiers()
        
        # Group by strategy
        blocked_by_strategy: Dict[str, List[Dict[str, Any]]] = {}
        for item in blocked:
            strategy = item["strategy"]
            if strategy not in blocked_by_strategy:
                blocked_by_strategy[strategy] = []
            blocked_by_strategy[strategy].append(item)
        
        # Check for suspicious patterns
        alerts = []
        
        # High number of blocked IPs might indicate DDoS
        if len(blocked_by_strategy.get("ip", [])) > 100:
            alerts.append({
                "type": "high_blocked_ips",
                "count": len(blocked_by_strategy["ip"]),
                "message": f"High number of blocked IPs: {len(blocked_by_strategy['ip'])}"
            })
        
        # Multiple blocked users might indicate coordinated attack
        if len(blocked_by_strategy.get("user", [])) > 20:
            alerts.append({
                "type": "high_blocked_users",
                "count": len(blocked_by_strategy["user"]),
                "message": f"High number of blocked users: {len(blocked_by_strategy['user'])}"
            })
        
        # Check for patterns in blocked identifiers
        ip_subnets: Dict[str, int] = {}
        for item in blocked_by_strategy.get("ip", []):
            identifier = item["identifier"]
            # Extract subnet (first 3 octets)
            parts = identifier.split(".")
            if len(parts) >= 3:
                subnet = ".".join(parts[:3])
                ip_subnets[subnet] = ip_subnets.get(subnet, 0) + 1
        
        # Alert if many IPs from same subnet
        for subnet, count in ip_subnets.items():
            if count > 10:
                alerts.append({
                    "type": "subnet_attack",
                    "subnet": subnet,
                    "count": count,
                    "message": f"Multiple blocked IPs from subnet {subnet}.x: {count}"
                })
        
        # Send alerts if any
        if alerts:
            logger.warning(f"Rate limit alerts: {alerts}")
            
            # Send notification to admins
            await notification_service.send_admin_notification(
                subject="Rate Limit Security Alert",
                template="rate_limit_alert",
                context={
                    "alerts": alerts,
                    "total_blocked": len(blocked),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Store metrics
        async with get_db_context() as db:
            await db.execute(text("""
                INSERT INTO system_metrics (metric_name, metric_value, metadata, created_at)
                VALUES 
                    ('rate_limit_blocked_total', :total_blocked, :metadata, NOW()),
                    ('rate_limit_blocked_ips', :blocked_ips, :metadata, NOW()),
                    ('rate_limit_blocked_users', :blocked_users, :metadata, NOW()),
                    ('rate_limit_blocked_api_keys', :blocked_api_keys, :metadata, NOW())
            """), {
                "total_blocked": len(blocked),
                "blocked_ips": len(blocked_by_strategy.get("ip", [])),
                "blocked_users": len(blocked_by_strategy.get("user", [])),
                "blocked_api_keys": len(blocked_by_strategy.get("api_key", [])),
                "metadata": {
                    "alerts": len(alerts),
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            await db.commit()
        
    except Exception as e:
        logger.error(f"Error monitoring rate limit violations: {e}")


@shared_task(name="rate_limit.auto_unblock")
def auto_unblock_expired_blocks():
    """Automatically unblock identifiers after block period expires"""
    asyncio.run(_auto_unblock())


async def _auto_unblock():
    """Async implementation of auto-unblocking"""
    try:
        logger.info("Checking for expired blocks to remove")
        
        # Get all blocked identifiers
        blocked = await rate_limiter.get_blocked_identifiers()
        
        current_time = datetime.now().timestamp()
        unblocked_count = 0
        
        for item in blocked:
            # Check if block has expired
            if item["blocked_until"] <= current_time:
                # This shouldn't happen as Redis should auto-expire,
                # but clean up just in case
                strategy = RateLimitStrategy(item["strategy"])
                identifier = item["identifier"]
                
                await rate_limiter.reset_rate_limit(
                    identifier=identifier,
                    strategy=strategy
                )
                
                logger.info(f"Auto-unblocked expired: {strategy}:{identifier}")
                unblocked_count += 1
        
        if unblocked_count > 0:
            logger.info(f"Auto-unblocked {unblocked_count} expired blocks")
        
    except Exception as e:
        logger.error(f"Error in auto-unblock task: {e}")


@shared_task(name="rate_limit.generate_report")
def generate_rate_limit_report():
    """Generate daily rate limit report"""
    asyncio.run(_generate_report())


async def _generate_report():
    """Async implementation of report generation"""
    try:
        logger.info("Generating rate limit report")
        
        # Get metrics from last 24 hours
        async with get_db_context() as db:
            # Get rate limit violation metrics
            result = await db.execute(text("""
                SELECT 
                    metric_name,
                    AVG(CAST(metric_value AS FLOAT)) as avg_value,
                    MAX(CAST(metric_value AS FLOAT)) as max_value,
                    MIN(CAST(metric_value AS FLOAT)) as min_value,
                    COUNT(*) as data_points
                FROM system_metrics
                WHERE metric_name LIKE 'rate_limit_%'
                    AND created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY metric_name
            """))
            
            metrics = {}
            for row in result:
                metrics[row.metric_name] = {
                    "avg": round(row.avg_value, 2),
                    "max": row.max_value,
                    "min": row.min_value,
                    "data_points": row.data_points
                }
            
            # Get top violated endpoints
            result = await db.execute(text("""
                SELECT 
                    endpoint,
                    COUNT(*) as violation_count,
                    COUNT(DISTINCT identifier) as unique_violators
                FROM rate_limit_violations
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY endpoint
                ORDER BY violation_count DESC
                LIMIT 10
            """))
            
            top_endpoints = []
            for row in result:
                top_endpoints.append({
                    "endpoint": row.endpoint,
                    "violations": row.violation_count,
                    "unique_violators": row.unique_violators
                })
            
            # Get currently blocked count
            blocked = await rate_limiter.get_blocked_identifiers()
            blocked_summary = {
                "total": len(blocked),
                "by_strategy": {}
            }
            
            for item in blocked:
                strategy = item["strategy"]
                if strategy not in blocked_summary["by_strategy"]:
                    blocked_summary["by_strategy"][strategy] = 0
                blocked_summary["by_strategy"][strategy] += 1
            
            # Create report
            report = {
                "report_date": datetime.utcnow().isoformat(),
                "period": "24_hours",
                "metrics": metrics,
                "currently_blocked": blocked_summary,
                "top_violated_endpoints": top_endpoints,
                "recommendations": []
            }
            
            # Add recommendations based on data
            if metrics.get("rate_limit_blocked_total", {}).get("max", 0) > 1000:
                report["recommendations"].append(
                    "High number of blocks detected. Consider reviewing rate limit thresholds."
                )
            
            if len(top_endpoints) > 0 and top_endpoints[0]["violations"] > 1000:
                report["recommendations"].append(
                    f"Endpoint {top_endpoints[0]['endpoint']} has high violation rate. "
                    "Consider adjusting limits or investigating abuse."
                )
            
            # Send report to admins
            await notification_service.send_admin_notification(
                subject="Daily Rate Limit Report",
                template="rate_limit_report",
                context=report
            )
            
            logger.info("Rate limit report generated and sent")
            
    except Exception as e:
        logger.error(f"Error generating rate limit report: {e}")


# Schedule periodic tasks
from celery.schedules import crontab
from core.tasks import celery_app

celery_app.conf.beat_schedule.update({
    "rate_limit_cleanup": {
        "task": "rate_limit.cleanup_expired_data",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "rate_limit_monitoring": {
        "task": "rate_limit.monitor_violations",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "rate_limit_auto_unblock": {
        "task": "rate_limit.auto_unblock",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "rate_limit_daily_report": {
        "task": "rate_limit.generate_report",
        "schedule": crontab(minute=0, hour=9),  # Daily at 9 AM
    }
})