"""API usage tracking service for monitoring and limiting API key usage."""

import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import redis.asyncio as redis

from core.logger import get_logger
from core.redis import redis_manager
from core.database import get_db
from models.api_key import APIKey

logger = get_logger(__name__)


class UsageMetric(str, Enum):
    """Types of usage metrics to track."""
    REQUESTS = "requests"
    SYNC_OPERATIONS = "sync_operations"
    DATA_FETCHED = "data_fetched"
    WEBHOOKS_SENT = "webhooks_sent"
    ERRORS = "errors"


@dataclass
class UsageStats:
    """Usage statistics for an API key."""
    api_key_id: str
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "api_key_id": self.api_key_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics
        }


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    sync_operations_per_day: int = 100
    data_fetch_mb_per_day: int = 1000
    webhooks_per_hour: int = 500


class APIUsageTracker:
    """Tracks and limits API usage."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis_manager
        self._default_limits = RateLimitConfig()
    
    async def track_usage(
        self,
        api_key_id: str,
        metric: UsageMetric,
        value: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track API usage and check limits.
        
        Args:
            api_key_id: API key ID
            metric: Type of metric to track
            value: Value to increment by
            metadata: Additional metadata
            
        Returns:
            True if within limits, False if limit exceeded
        """
        # Generate keys for different time windows
        now = datetime.utcnow()
        minute_key = f"usage:{api_key_id}:{metric}:minute:{now.strftime('%Y%m%d%H%M')}"
        hour_key = f"usage:{api_key_id}:{metric}:hour:{now.strftime('%Y%m%d%H')}"
        day_key = f"usage:{api_key_id}:{metric}:day:{now.strftime('%Y%m%d')}"
        
        # Get current limits
        limits = await self._get_rate_limits(api_key_id)
        
        # Check limits based on metric type
        if metric == UsageMetric.REQUESTS:
            # Check all time windows
            minute_count = await self._increment_and_get(minute_key, value, 60)
            if minute_count > limits.requests_per_minute:
                logger.warning(
                    f"Rate limit exceeded for API key {api_key_id}",
                    extra={"metric": metric, "window": "minute", "count": minute_count}
                )
                return False
            
            hour_count = await self._increment_and_get(hour_key, value, 3600)
            if hour_count > limits.requests_per_hour:
                logger.warning(
                    f"Rate limit exceeded for API key {api_key_id}",
                    extra={"metric": metric, "window": "hour", "count": hour_count}
                )
                return False
            
            day_count = await self._increment_and_get(day_key, value, 86400)
            if day_count > limits.requests_per_day:
                logger.warning(
                    f"Rate limit exceeded for API key {api_key_id}",
                    extra={"metric": metric, "window": "day", "count": day_count}
                )
                return False
        
        elif metric == UsageMetric.SYNC_OPERATIONS:
            day_count = await self._increment_and_get(day_key, value, 86400)
            if day_count > limits.sync_operations_per_day:
                logger.warning(
                    f"Sync operations limit exceeded for API key {api_key_id}",
                    extra={"count": day_count, "limit": limits.sync_operations_per_day}
                )
                return False
        
        elif metric == UsageMetric.WEBHOOKS_SENT:
            hour_count = await self._increment_and_get(hour_key, value, 3600)
            if hour_count > limits.webhooks_per_hour:
                logger.warning(
                    f"Webhook limit exceeded for API key {api_key_id}",
                    extra={"count": hour_count, "limit": limits.webhooks_per_hour}
                )
                return False
        
        # Store detailed tracking data for reporting
        await self._store_usage_detail(api_key_id, metric, value, metadata)
        
        # Update API key last used timestamp
        await self._update_last_used(api_key_id)
        
        return True
    
    async def _increment_and_get(self, key: str, value: int, ttl: int) -> int:
        """Increment counter and get current value."""
        client = await self.redis.connect()
        pipe = client.pipeline()
        pipe.incrby(key, value)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]
    
    async def _get_rate_limits(self, api_key_id: str) -> RateLimitConfig:
        """Get rate limits for an API key."""
        # Try to get custom limits from cache
        limits_key = f"limits:{api_key_id}"
        cached = await self.redis.get(limits_key)
        
        if cached:
            import json
            data = json.loads(cached)
            return RateLimitConfig(**data)
        
        # Get from database
        async for db in get_db():
            try:
                result = await db.execute(
                    select(APIKey).where(APIKey.id == api_key_id)
                )
                api_key = result.scalar_one_or_none()
                
                if api_key and api_key.key_metadata.get("rate_limits"):
                    limits = RateLimitConfig(**api_key.key_metadata["rate_limits"])
                else:
                    limits = self._default_limits
                
                # Cache for 5 minutes
                await self.redis.set(
                    limits_key,
                    limits.__dict__,
                    expire=300
                )
                
                return limits
            finally:
                await db.close()
                break
        
        return self._default_limits
    
    async def _store_usage_detail(
        self,
        api_key_id: str,
        metric: UsageMetric,
        value: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store detailed usage data for reporting."""
        # Store in time-series format
        detail_key = f"usage:detail:{api_key_id}:{metric}:{datetime.utcnow().strftime('%Y%m%d')}"
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "value": value,
            "metadata": metadata or {}
        }
        
        # Add to sorted set with timestamp as score
        import json
        client = await self.redis.connect()
        await client.zadd(
            detail_key,
            {json.dumps(data): datetime.utcnow().timestamp()}
        )
        
        # Expire after 30 days
        await client.expire(detail_key, 30 * 86400)
    
    async def _update_last_used(self, api_key_id: str) -> None:
        """Update API key last used timestamp."""
        # Debounce updates to avoid too many DB writes
        debounce_key = f"last_used:{api_key_id}"
        client = await self.redis.connect()
        if await client.set(debounce_key, "1", ex=60, nx=True):
            # First update in the last minute
            async for db in get_db():
                try:
                    await db.execute(
                        update(APIKey)
                        .where(APIKey.id == api_key_id)
                        .values(last_used_at=datetime.utcnow())
                    )
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to update last_used_at: {e}")
                    await db.rollback()
                finally:
                    await db.close()
                    break
    
    async def get_usage_stats(
        self,
        api_key_id: str,
        period: str = "day",
        lookback_days: int = 7
    ) -> List[UsageStats]:
        """
        Get usage statistics for an API key.
        
        Args:
            api_key_id: API key ID
            period: Aggregation period (hour, day, week, month)
            lookback_days: Number of days to look back
            
        Returns:
            List of usage statistics
        """
        stats = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Determine period duration
        if period == "hour":
            delta = timedelta(hours=1)
        elif period == "week":
            delta = timedelta(weeks=1)
        elif period == "month":
            delta = timedelta(days=30)
        else:  # day
            delta = timedelta(days=1)
        
        current = start_date
        while current < end_date:
            period_end = current + delta
            
            # Get metrics for this period
            metrics = {}
            for metric in UsageMetric:
                total = await self._get_period_total(
                    api_key_id,
                    metric,
                    current,
                    period_end
                )
                if total > 0:
                    metrics[metric.value] = total
            
            if metrics:
                stats.append(UsageStats(
                    api_key_id=api_key_id,
                    period_start=current,
                    period_end=period_end,
                    metrics=metrics
                ))
            
            current = period_end
        
        return stats
    
    async def _get_period_total(
        self,
        api_key_id: str,
        metric: UsageMetric,
        start: datetime,
        end: datetime
    ) -> int:
        """Get total usage for a period."""
        total = 0
        current = start
        
        while current < end:
            # Check daily keys
            day_key = f"usage:detail:{api_key_id}:{metric}:{current.strftime('%Y%m%d')}"
            
            # Get all entries for this day
            client = await self.redis.connect()
            entries = await client.zrangebyscore(
                day_key,
                current.timestamp(),
                min(end.timestamp(), (current + timedelta(days=1)).timestamp())
            )
            
            # Sum values
            import json
            for entry in entries:
                try:
                    data = json.loads(entry)
                    total += data.get("value", 0)
                except:
                    pass
            
            current += timedelta(days=1)
        
        return total
    
    async def check_limit(
        self,
        api_key_id: str,
        metric: UsageMetric,
        value: int = 1
    ) -> bool:
        """
        Check if a usage would exceed limits without tracking.
        
        Args:
            api_key_id: API key ID
            metric: Type of metric
            value: Value to check
            
        Returns:
            True if within limits, False if would exceed
        """
        # Get current usage
        now = datetime.utcnow()
        limits = await self._get_rate_limits(api_key_id)
        
        if metric == UsageMetric.REQUESTS:
            # Check minute limit
            minute_key = f"usage:{api_key_id}:{metric}:minute:{now.strftime('%Y%m%d%H%M')}"
            current_val = await self.redis.get(minute_key)
            current = int(current_val) if current_val else 0
            if current + value > limits.requests_per_minute:
                return False
            
            # Check hour limit
            hour_key = f"usage:{api_key_id}:{metric}:hour:{now.strftime('%Y%m%d%H')}"
            current_val = await self.redis.get(hour_key)
            current = int(current_val) if current_val else 0
            if current + value > limits.requests_per_hour:
                return False
            
            # Check day limit
            day_key = f"usage:{api_key_id}:{metric}:day:{now.strftime('%Y%m%d')}"
            current_val = await self.redis.get(day_key)
            current = int(current_val) if current_val else 0
            if current + value > limits.requests_per_day:
                return False
        
        return True
    
    async def reset_usage(self, api_key_id: str, metric: Optional[UsageMetric] = None) -> None:
        """Reset usage counters for an API key."""
        pattern = f"usage:{api_key_id}:*"
        if metric:
            pattern = f"usage:{api_key_id}:{metric}:*"
        
        # Find and delete all matching keys
        cursor = 0
        while True:
            client = await self.redis.connect()
            cursor, keys = await client.scan(cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break
        
        logger.info(f"Reset usage counters for API key {api_key_id}")


# Global instance
_usage_tracker: Optional[APIUsageTracker] = None


def get_usage_tracker() -> APIUsageTracker:
    """Get or create usage tracker instance."""
    global _usage_tracker
    
    if not _usage_tracker:
        _usage_tracker = APIUsageTracker()
    
    return _usage_tracker