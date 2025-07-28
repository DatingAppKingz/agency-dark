"""
Real-time analytics engine for processing live metrics
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics

from core.redis import redis_client
from core.logging import get_logger
from core.database import get_db
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .aggregator import MetricsAggregator
from .stream_processor import StreamProcessor
from ..domain.models import Analytics, AnalyticsEvent

logger = get_logger(__name__)


class RealtimeAnalyticsEngine:
    """Real-time analytics processing engine"""
    
    def __init__(self):
        self.aggregator = MetricsAggregator()
        self.stream_processor = StreamProcessor()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._metric_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
    async def start(self):
        """Start the analytics engine"""
        if self._running:
            return
            
        self._running = True
        logger.info("Starting real-time analytics engine")
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._process_events()),
            asyncio.create_task(self._aggregate_metrics()),
            asyncio.create_task(self._publish_updates()),
            asyncio.create_task(self._cleanup_old_data())
        ]
        
    async def stop(self):
        """Stop the analytics engine"""
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("Stopped real-time analytics engine")
        
    async def track_event(
        self,
        event_type: str,
        agency_id: str,
        model_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """Track an analytics event"""
        event = AnalyticsEvent(
            event_type=event_type,
            agency_id=agency_id,
            model_id=model_id,
            data=data or {},
            timestamp=datetime.utcnow()
        )
        
        # Publish to Redis for processing
        await redis_client.publish(
            "analytics:events",
            event.json()
        )
        
        # Add to buffer for immediate processing
        self._metric_buffers[f"{agency_id}:{event_type}"].append(event)
        
    async def get_realtime_metrics(
        self,
        agency_id: str,
        model_id: Optional[str] = None,
        metric_types: Optional[List[str]] = None,
        time_range: int = 3600  # Default 1 hour
    ) -> Dict[str, Any]:
        """Get real-time metrics"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=time_range)
        
        # Get from aggregator
        metrics = await self.aggregator.get_metrics(
            agency_id=agency_id,
            model_id=model_id,
            metric_types=metric_types,
            since=cutoff_time
        )
        
        # Add real-time calculations
        realtime_stats = await self._calculate_realtime_stats(
            agency_id, model_id, cutoff_time
        )
        
        return {
            "metrics": metrics,
            "realtime": realtime_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def subscribe_to_updates(
        self,
        client_id: str,
        agency_id: str,
        model_id: Optional[str] = None
    ):
        """Subscribe client to real-time updates"""
        channel = f"{agency_id}:{model_id or 'all'}"
        self._subscribers[channel].add(client_id)
        
        logger.info(f"Client {client_id} subscribed to {channel}")
        
    async def unsubscribe_from_updates(
        self,
        client_id: str,
        agency_id: str,
        model_id: Optional[str] = None
    ):
        """Unsubscribe client from updates"""
        channel = f"{agency_id}:{model_id or 'all'}"
        self._subscribers[channel].discard(client_id)
        
        logger.info(f"Client {client_id} unsubscribed from {channel}")
        
    async def _process_events(self):
        """Process incoming analytics events"""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("analytics:events")
        
        try:
            while self._running:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                
                if message and message['type'] == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        event = AnalyticsEvent(**event_data)
                        
                        # Process through stream processor
                        await self.stream_processor.process_event(event)
                        
                        # Update aggregations
                        await self.aggregator.add_event(event)
                        
                    except Exception as e:
                        logger.error(f"Error processing event: {e}")
                        
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
        finally:
            await pubsub.unsubscribe("analytics:events")
            await pubsub.close()
            
    async def _aggregate_metrics(self):
        """Periodically aggregate metrics"""
        while self._running:
            try:
                # Run aggregations every 10 seconds
                await asyncio.sleep(10)
                
                # Get pending aggregations
                pending = await self.aggregator.get_pending_aggregations()
                
                for aggregation in pending:
                    await self._perform_aggregation(aggregation)
                    
            except Exception as e:
                logger.error(f"Error in metric aggregation: {e}")
                
    async def _publish_updates(self):
        """Publish updates to subscribed clients"""
        while self._running:
            try:
                # Publish updates every 5 seconds
                await asyncio.sleep(5)
                
                # Get updated metrics for each channel
                for channel, clients in self._subscribers.items():
                    if not clients:
                        continue
                        
                    agency_id, model_id = channel.split(':', 1)
                    model_id = None if model_id == 'all' else model_id
                    
                    # Get latest metrics
                    metrics = await self.get_realtime_metrics(
                        agency_id=agency_id,
                        model_id=model_id,
                        time_range=300  # Last 5 minutes
                    )
                    
                    # Publish to Redis channel for WebSocket delivery
                    await redis_client.publish(
                        f"analytics:updates:{channel}",
                        json.dumps(metrics)
                    )
                    
            except Exception as e:
                logger.error(f"Error publishing updates: {e}")
                
    async def _cleanup_old_data(self):
        """Clean up old data periodically"""
        while self._running:
            try:
                # Run cleanup every hour
                await asyncio.sleep(3600)
                
                # Clean up old events
                cutoff = datetime.utcnow() - timedelta(days=7)
                await self.aggregator.cleanup_old_data(cutoff)
                
                # Clear old metric buffers
                for key in list(self._metric_buffers.keys()):
                    buffer = self._metric_buffers[key]
                    if buffer:
                        # Remove events older than 1 hour
                        hour_ago = datetime.utcnow() - timedelta(hours=1)
                        while buffer and buffer[0].timestamp < hour_ago:
                            buffer.popleft()
                            
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                
    async def _calculate_realtime_stats(
        self,
        agency_id: str,
        model_id: Optional[str],
        since: datetime
    ) -> Dict[str, Any]:
        """Calculate real-time statistics"""
        stats = {
            "active_users": 0,
            "messages_per_minute": 0,
            "revenue_per_minute": 0,
            "engagement_rate": 0,
            "response_time_avg": 0,
            "trending_metrics": []
        }
        
        # Calculate from buffers
        for key, buffer in self._metric_buffers.items():
            if not key.startswith(agency_id):
                continue
                
            recent_events = [e for e in buffer if e.timestamp >= since]
            
            if recent_events:
                # Calculate metrics based on event types
                event_types = [e.event_type for e in recent_events]
                
                if "message_sent" in event_types:
                    messages_count = event_types.count("message_sent")
                    time_span = (datetime.utcnow() - since).total_seconds() / 60
                    stats["messages_per_minute"] = messages_count / max(time_span, 1)
                    
                if "payment_received" in event_types:
                    revenue_events = [e for e in recent_events if e.event_type == "payment_received"]
                    total_revenue = sum(e.data.get("amount", 0) for e in revenue_events)
                    time_span = (datetime.utcnow() - since).total_seconds() / 60
                    stats["revenue_per_minute"] = total_revenue / max(time_span, 1)
                    
        # Get from database for more accurate stats
        async with get_db() as db:
            # Active users
            active_users_query = select(func.count(func.distinct(Analytics.fan_id))).where(
                and_(
                    Analytics.agency_id == agency_id,
                    Analytics.created_at >= since
                )
            )
            
            if model_id:
                active_users_query = active_users_query.where(Analytics.model_id == model_id)
                
            stats["active_users"] = await db.scalar(active_users_query) or 0
            
        return stats
        
    async def _perform_aggregation(self, aggregation: Dict[str, Any]):
        """Perform a specific aggregation"""
        agg_type = aggregation["type"]
        
        if agg_type == "hourly":
            await self._aggregate_hourly_metrics(aggregation)
        elif agg_type == "daily":
            await self._aggregate_daily_metrics(aggregation)
        elif agg_type == "custom":
            await self._aggregate_custom_metrics(aggregation)
            
    async def _aggregate_hourly_metrics(self, aggregation: Dict[str, Any]):
        """Aggregate hourly metrics"""
        agency_id = aggregation["agency_id"]
        hour_start = aggregation["hour_start"]
        
        async with get_db() as db:
            # Aggregate various metrics for the hour
            metrics = await db.execute(
                select(
                    func.count(Analytics.id).label("total_events"),
                    func.count(func.distinct(Analytics.fan_id)).label("unique_users"),
                    func.sum(Analytics.value).label("total_value")
                ).where(
                    and_(
                        Analytics.agency_id == agency_id,
                        Analytics.created_at >= hour_start,
                        Analytics.created_at < hour_start + timedelta(hours=1)
                    )
                )
            )
            
            result = metrics.one()
            
            # Store aggregated result
            await self.aggregator.store_aggregation(
                agency_id=agency_id,
                aggregation_type="hourly",
                timestamp=hour_start,
                data={
                    "total_events": result.total_events,
                    "unique_users": result.unique_users,
                    "total_value": float(result.total_value or 0)
                }
            )
            
    async def _aggregate_daily_metrics(self, aggregation: Dict[str, Any]):
        """Aggregate daily metrics"""
        # Similar to hourly but for full day
        pass
        
    async def _aggregate_custom_metrics(self, aggregation: Dict[str, Any]):
        """Aggregate custom metrics based on configuration"""
        # Custom aggregation logic
        pass


# Global engine instance
realtime_engine = RealtimeAnalyticsEngine()
