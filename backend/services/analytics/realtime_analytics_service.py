"""Enhanced real-time analytics service with WebSocket support."""

from typing import Dict, List, Any, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from collections import defaultdict, deque
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import redis.asyncio as redis

from core.logger import get_logger
from models.model import Model
from models.financial import Transaction
from models.subscriber import Subscriber
from models.content import Content

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics tracked."""
    REVENUE = "revenue"
    SUBSCRIBERS = "subscribers"
    CONTENT_VIEWS = "content_views"
    MESSAGES = "messages"
    CONVERSION_RATE = "conversion_rate"
    ENGAGEMENT_RATE = "engagement_rate"
    CHURN_RATE = "churn_rate"
    AVERAGE_ORDER_VALUE = "average_order_value"
    LIFETIME_VALUE = "lifetime_value"


class TimeWindow(Enum):
    """Time windows for aggregation."""
    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    HOUR = "1h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1mo"


@dataclass
class MetricUpdate:
    """Real-time metric update."""
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    dimensions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """Aggregated metric data."""
    metric_type: MetricType
    window: TimeWindow
    value: float
    count: int
    min_value: float
    max_value: float
    avg_value: float
    std_dev: float
    timestamp: datetime
    dimensions: Dict[str, Any] = field(default_factory=dict)


class RealtimeAnalyticsService:
    """Service for real-time analytics processing and distribution."""
    
    def __init__(self, redis_client: redis.Redis, db_session: AsyncSession):
        self.redis = redis_client
        self.db = db_session
        
        # Metric buffers for different time windows
        self.metric_buffers: Dict[str, Dict[TimeWindow, deque]] = defaultdict(
            lambda: {window: deque(maxlen=self._get_buffer_size(window)) 
                    for window in TimeWindow}
        )
        
        # WebSocket subscribers
        self.subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        
        # Background tasks
        self.tasks: List[asyncio.Task] = []
        self.running = False
        
        # Performance metrics
        self.processing_times = deque(maxlen=100)
        self.error_counts = defaultdict(int)
    
    def _get_buffer_size(self, window: TimeWindow) -> int:
        """Get buffer size for time window."""
        sizes = {
            TimeWindow.MINUTE: 60,
            TimeWindow.FIVE_MINUTES: 60,
            TimeWindow.FIFTEEN_MINUTES: 60,
            TimeWindow.HOUR: 48,
            TimeWindow.DAY: 30,
            TimeWindow.WEEK: 12,
            TimeWindow.MONTH: 12
        }
        return sizes.get(window, 60)
    
    async def start(self):
        """Start the real-time analytics service."""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting real-time analytics service")
        
        # Start background tasks
        self.tasks = [
            asyncio.create_task(self._process_metric_stream()),
            asyncio.create_task(self._aggregate_metrics()),
            asyncio.create_task(self._persist_metrics()),
            asyncio.create_task(self._broadcast_updates()),
            asyncio.create_task(self._cleanup_old_data())
        ]
    
    async def stop(self):
        """Stop the real-time analytics service."""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Real-time analytics service stopped")
    
    async def track_metric(self, update: MetricUpdate):
        """Track a new metric update."""
        start_time = datetime.utcnow()
        
        try:
            # Create metric key
            metric_key = self._create_metric_key(update)
            
            # Add to Redis stream
            await self.redis.xadd(
                f"metrics:{metric_key}",
                {
                    "value": update.value,
                    "timestamp": update.timestamp.isoformat(),
                    "dimensions": json.dumps(update.dimensions),
                    "metadata": json.dumps(update.metadata)
                },
                maxlen=10000  # Keep last 10k events
            )
            
            # Add to in-memory buffers
            for window in TimeWindow:
                self.metric_buffers[metric_key][window].append(update)
            
            # Track processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.processing_times.append(processing_time)
            
        except Exception as e:
            logger.error(f"Failed to track metric: {e}")
            self.error_counts["track_metric"] += 1
    
    def _create_metric_key(self, update: MetricUpdate) -> str:
        """Create a unique key for the metric."""
        dimensions_str = ":".join(
            f"{k}={v}" for k, v in sorted(update.dimensions.items())
        )
        return f"{update.metric_type.value}:{dimensions_str}"
    
    async def _process_metric_stream(self):
        """Process incoming metric stream from Redis."""
        while self.running:
            try:
                # Read from multiple streams
                streams = await self.redis.xread(
                    {"metrics:*": "$"},
                    block=1000,  # Block for 1 second
                    count=100
                )
                
                for stream_name, messages in streams:
                    for msg_id, data in messages:
                        await self._process_stream_message(stream_name, data)
                
            except Exception as e:
                logger.error(f"Error processing metric stream: {e}")
                self.error_counts["stream_processing"] += 1
                await asyncio.sleep(1)
    
    async def _process_stream_message(self, stream_name: str, data: Dict):
        """Process a single stream message."""
        try:
            # Parse message
            update = MetricUpdate(
                metric_type=MetricType(stream_name.split(":")[1]),
                value=float(data["value"]),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                dimensions=json.loads(data.get("dimensions", "{}")),
                metadata=json.loads(data.get("metadata", "{}"))
            )
            
            # Process based on metric type
            await self._process_metric_update(update)
            
        except Exception as e:
            logger.error(f"Failed to process stream message: {e}")
    
    async def _process_metric_update(self, update: MetricUpdate):
        """Process a metric update based on its type."""
        # Apply business logic based on metric type
        if update.metric_type == MetricType.REVENUE:
            await self._process_revenue_update(update)
        elif update.metric_type == MetricType.SUBSCRIBERS:
            await self._process_subscriber_update(update)
        # Add more metric-specific processing
    
    async def _process_revenue_update(self, update: MetricUpdate):
        """Process revenue metric update."""
        # Update derived metrics
        if "model_id" in update.dimensions:
            # Update model lifetime value
            await self._update_model_ltv(
                update.dimensions["model_id"],
                update.value
            )
    
    async def _process_subscriber_update(self, update: MetricUpdate):
        """Process subscriber metric update."""
        # Calculate churn rate if needed
        if update.metadata.get("event") == "unsubscribe":
            await self._update_churn_rate(update.dimensions.get("model_id"))
    
    async def _aggregate_metrics(self):
        """Aggregate metrics for different time windows."""
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                for metric_key, windows in self.metric_buffers.items():
                    for window, buffer in windows.items():
                        if self._should_aggregate(window, current_time):
                            aggregated = await self._aggregate_window(
                                metric_key, window, buffer
                            )
                            if aggregated:
                                await self._store_aggregated_metric(aggregated)
                
                await asyncio.sleep(5)  # Aggregate every 5 seconds
                
            except Exception as e:
                logger.error(f"Error aggregating metrics: {e}")
                self.error_counts["aggregation"] += 1
    
    def _should_aggregate(self, window: TimeWindow, current_time: datetime) -> bool:
        """Check if we should aggregate for this window."""
        intervals = {
            TimeWindow.MINUTE: 60,
            TimeWindow.FIVE_MINUTES: 300,
            TimeWindow.FIFTEEN_MINUTES: 900,
            TimeWindow.HOUR: 3600,
            TimeWindow.DAY: 86400,
            TimeWindow.WEEK: 604800,
            TimeWindow.MONTH: 2592000
        }
        
        interval = intervals.get(window, 60)
        return int(current_time.timestamp()) % interval < 5
    
    async def _aggregate_window(
        self,
        metric_key: str,
        window: TimeWindow,
        buffer: deque
    ) -> Optional[AggregatedMetric]:
        """Aggregate metrics for a time window."""
        if not buffer:
            return None
        
        # Filter metrics within window
        window_start = self._get_window_start(window)
        window_metrics = [
            m for m in buffer
            if m.timestamp >= window_start
        ]
        
        if not window_metrics:
            return None
        
        values = [m.value for m in window_metrics]
        
        # Parse metric key
        parts = metric_key.split(":")
        metric_type = MetricType(parts[0])
        dimensions = {}
        if len(parts) > 1:
            for dim in parts[1].split(","):
                if "=" in dim:
                    k, v = dim.split("=", 1)
                    dimensions[k] = v
        
        return AggregatedMetric(
            metric_type=metric_type,
            window=window,
            value=sum(values),
            count=len(values),
            min_value=min(values),
            max_value=max(values),
            avg_value=statistics.mean(values),
            std_dev=statistics.stdev(values) if len(values) > 1 else 0,
            timestamp=datetime.utcnow(),
            dimensions=dimensions
        )
    
    def _get_window_start(self, window: TimeWindow) -> datetime:
        """Get start time for a window."""
        now = datetime.utcnow()
        
        if window == TimeWindow.MINUTE:
            return now - timedelta(minutes=1)
        elif window == TimeWindow.FIVE_MINUTES:
            return now - timedelta(minutes=5)
        elif window == TimeWindow.FIFTEEN_MINUTES:
            return now - timedelta(minutes=15)
        elif window == TimeWindow.HOUR:
            return now - timedelta(hours=1)
        elif window == TimeWindow.DAY:
            return now - timedelta(days=1)
        elif window == TimeWindow.WEEK:
            return now - timedelta(weeks=1)
        elif window == TimeWindow.MONTH:
            return now - timedelta(days=30)
        
        return now - timedelta(minutes=1)
    
    async def _store_aggregated_metric(self, metric: AggregatedMetric):
        """Store aggregated metric in Redis."""
        key = f"aggregated:{metric.metric_type.value}:{metric.window.value}"
        
        # Add dimensions to key
        if metric.dimensions:
            dim_str = ":".join(
                f"{k}={v}" for k, v in sorted(metric.dimensions.items())
            )
            key = f"{key}:{dim_str}"
        
        # Store in Redis with expiration
        expire_seconds = {
            TimeWindow.MINUTE: 3600,  # 1 hour
            TimeWindow.FIVE_MINUTES: 7200,  # 2 hours
            TimeWindow.FIFTEEN_MINUTES: 14400,  # 4 hours
            TimeWindow.HOUR: 86400,  # 1 day
            TimeWindow.DAY: 604800,  # 1 week
            TimeWindow.WEEK: 2592000,  # 30 days
            TimeWindow.MONTH: 7776000  # 90 days
        }
        
        await self.redis.zadd(
            key,
            {json.dumps({
                "value": metric.value,
                "count": metric.count,
                "min": metric.min_value,
                "max": metric.max_value,
                "avg": metric.avg_value,
                "std_dev": metric.std_dev,
                "timestamp": metric.timestamp.isoformat()
            }): metric.timestamp.timestamp()}
        )
        
        await self.redis.expire(key, expire_seconds.get(metric.window, 3600))
    
    async def _persist_metrics(self):
        """Persist metrics to database periodically."""
        while self.running:
            try:
                # Persist aggregated metrics every minute
                await asyncio.sleep(60)
                
                # Get all aggregated metrics
                pattern = "aggregated:*"
                cursor = 0
                
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=pattern, count=100
                    )
                    
                    for key in keys:
                        await self._persist_metric_key(key)
                    
                    if cursor == 0:
                        break
                
            except Exception as e:
                logger.error(f"Error persisting metrics: {e}")
                self.error_counts["persistence"] += 1
    
    async def _persist_metric_key(self, key: str):
        """Persist a single metric key to database."""
        # Implementation depends on your analytics model
        pass
    
    async def _broadcast_updates(self):
        """Broadcast updates to WebSocket subscribers."""
        while self.running:
            try:
                # Get latest metrics for each subscriber
                for channel, callbacks in self.subscribers.items():
                    if callbacks:
                        updates = await self._get_channel_updates(channel)
                        if updates:
                            for callback in callbacks:
                                try:
                                    await callback(updates)
                                except Exception as e:
                                    logger.error(f"Error broadcasting to subscriber: {e}")
                
                await asyncio.sleep(1)  # Broadcast every second
                
            except Exception as e:
                logger.error(f"Error broadcasting updates: {e}")
                self.error_counts["broadcast"] += 1
    
    async def _get_channel_updates(self, channel: str) -> Dict[str, Any]:
        """Get updates for a specific channel."""
        # Parse channel to determine what metrics to send
        parts = channel.split(":")
        
        if parts[0] == "agency":
            return await self._get_agency_updates(parts[1])
        elif parts[0] == "model":
            return await self._get_model_updates(parts[1])
        
        return {}
    
    async def _get_agency_updates(self, agency_id: str) -> Dict[str, Any]:
        """Get real-time updates for an agency."""
        updates = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }
        
        # Get latest metrics for each type
        for metric_type in MetricType:
            key = f"aggregated:{metric_type.value}:{TimeWindow.MINUTE.value}:agency_id={agency_id}"
            
            # Get latest value
            result = await self.redis.zrange(key, -1, -1, withscores=True)
            if result:
                data = json.loads(result[0][0])
                updates["metrics"][metric_type.value] = data
        
        return updates
    
    async def _get_model_updates(self, model_id: str) -> Dict[str, Any]:
        """Get real-time updates for a model."""
        updates = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }
        
        # Similar to agency updates but for model
        for metric_type in MetricType:
            key = f"aggregated:{metric_type.value}:{TimeWindow.MINUTE.value}:model_id={model_id}"
            
            result = await self.redis.zrange(key, -1, -1, withscores=True)
            if result:
                data = json.loads(result[0][0])
                updates["metrics"][metric_type.value] = data
        
        return updates
    
    async def _cleanup_old_data(self):
        """Clean up old data periodically."""
        while self.running:
            try:
                # Clean up every hour
                await asyncio.sleep(3600)
                
                # Clean up old stream entries
                pattern = "metrics:*"
                cursor = 0
                
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=pattern, count=100
                    )
                    
                    for key in keys:
                        # Trim to last 10k entries
                        await self.redis.xtrim(key, maxlen=10000, approximate=True)
                    
                    if cursor == 0:
                        break
                
            except Exception as e:
                logger.error(f"Error cleaning up data: {e}")
                self.error_counts["cleanup"] += 1
    
    def subscribe(self, channel: str, callback: Callable):
        """Subscribe to real-time updates."""
        self.subscribers[channel].add(callback)
        logger.info(f"Added subscriber to channel: {channel}")
    
    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from real-time updates."""
        self.subscribers[channel].discard(callback)
        if not self.subscribers[channel]:
            del self.subscribers[channel]
        logger.info(f"Removed subscriber from channel: {channel}")
    
    async def get_realtime_metrics(
        self,
        metric_types: List[MetricType],
        dimensions: Dict[str, Any],
        window: TimeWindow = TimeWindow.MINUTE,
        limit: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get real-time metrics for display."""
        results = {}
        
        for metric_type in metric_types:
            # Build key
            key = f"aggregated:{metric_type.value}:{window.value}"
            if dimensions:
                dim_str = ":".join(
                    f"{k}={v}" for k, v in sorted(dimensions.items())
                )
                key = f"{key}:{dim_str}"
            
            # Get data from Redis
            data = await self.redis.zrange(
                key, -limit, -1, withscores=True
            )
            
            results[metric_type.value] = [
                {**json.loads(item[0]), "timestamp": item[1]}
                for item in data
            ]
        
        return results
    
    async def get_metric_summary(
        self,
        agency_id: str,
        time_range: Optional[Dict[str, datetime]] = None
    ) -> Dict[str, Any]:
        """Get metric summary for dashboard."""
        if not time_range:
            time_range = {
                "start": datetime.utcnow() - timedelta(days=1),
                "end": datetime.utcnow()
            }
        
        summary = {
            "revenue": await self._get_revenue_summary(agency_id, time_range),
            "subscribers": await self._get_subscriber_summary(agency_id, time_range),
            "engagement": await self._get_engagement_summary(agency_id, time_range),
            "performance": await self._get_performance_summary()
        }
        
        return summary
    
    async def _get_revenue_summary(
        self,
        agency_id: str,
        time_range: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """Get revenue summary."""
        # Query database for revenue data
        result = await self.db.execute(
            select(
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
                func.avg(Transaction.amount).label("average")
            ).join(
                Model, Transaction.model_id == Model.id
            ).where(
                and_(
                    Model.agency_id == agency_id,
                    Transaction.created_at >= time_range["start"],
                    Transaction.created_at <= time_range["end"],
                    Transaction.status == "completed"
                )
            )
        )
        
        row = result.first()
        
        return {
            "total": float(row.total or 0),
            "count": row.count or 0,
            "average": float(row.average or 0)
        }
    
    async def _get_subscriber_summary(
        self,
        agency_id: str,
        time_range: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """Get subscriber summary."""
        # Current subscribers
        current_result = await self.db.execute(
            select(func.count(Subscriber.id)).join(
                Model, Subscriber.model_id == Model.id
            ).where(
                and_(
                    Model.agency_id == agency_id,
                    Subscriber.is_active == True
                )
            )
        )
        current_count = current_result.scalar() or 0
        
        # New subscribers in time range
        new_result = await self.db.execute(
            select(func.count(Subscriber.id)).join(
                Model, Subscriber.model_id == Model.id
            ).where(
                and_(
                    Model.agency_id == agency_id,
                    Subscriber.created_at >= time_range["start"],
                    Subscriber.created_at <= time_range["end"]
                )
            )
        )
        new_count = new_result.scalar() or 0
        
        return {
            "total": current_count,
            "new": new_count,
            "growth_rate": (new_count / current_count * 100) if current_count > 0 else 0
        }
    
    async def _get_engagement_summary(
        self,
        agency_id: str,
        time_range: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """Get engagement summary."""
        # This would include message counts, content views, etc.
        return {
            "message_count": 0,  # Implement based on your message model
            "content_views": 0,  # Implement based on your content model
            "avg_response_time": 0
        }
    
    async def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of the analytics system."""
        return {
            "avg_processing_time": statistics.mean(self.processing_times) if self.processing_times else 0,
            "error_counts": dict(self.error_counts),
            "active_subscribers": sum(len(subs) for subs in self.subscribers.values()),
            "buffer_sizes": {
                metric_key: {
                    window.value: len(buffer)
                    for window, buffer in windows.items()
                }
                for metric_key, windows in list(self.metric_buffers.items())[:5]
            }
        }
    
    async def _update_model_ltv(self, model_id: str, revenue: float):
        """Update model lifetime value."""
        # Calculate and store LTV
        key = f"ltv:model:{model_id}"
        
        # Get existing LTV data
        ltv_data = await self.redis.get(key)
        if ltv_data:
            ltv = json.loads(ltv_data)
            ltv["total_revenue"] += revenue
            ltv["transaction_count"] += 1
            ltv["last_updated"] = datetime.utcnow().isoformat()
        else:
            ltv = {
                "total_revenue": revenue,
                "transaction_count": 1,
                "first_transaction": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }
        
        await self.redis.set(key, json.dumps(ltv), ex=86400 * 30)  # 30 days
    
    async def _update_churn_rate(self, model_id: Optional[str]):
        """Update churn rate metrics."""
        # Calculate churn rate for model or agency
        pass