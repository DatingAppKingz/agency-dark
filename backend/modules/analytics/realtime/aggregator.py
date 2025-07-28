"""
Metrics aggregator for real-time analytics
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from core.redis import redis_client
from core.logging import get_logger
from ..domain.models import AnalyticsEvent

logger = get_logger(__name__)


class MetricsAggregator:
    """Aggregate metrics in real-time"""
    
    def __init__(self):
        self._aggregations: Dict[str, Dict[str, Any]] = {}
        self._event_queues: Dict[str, List[AnalyticsEvent]] = defaultdict(list)
        self._aggregation_rules: Dict[str, Dict[str, Any]] = self._init_aggregation_rules()
        
    def _init_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize aggregation rules"""
        return {
            "message_metrics": {
                "events": ["message_sent", "message_received", "message_read"],
                "window": 300,  # 5 minutes
                "aggregations": ["count", "rate", "unique_users"]
            },
            "revenue_metrics": {
                "events": ["payment_received", "tip_received", "subscription_renewed"],
                "window": 3600,  # 1 hour
                "aggregations": ["sum", "count", "average", "max"]
            },
            "engagement_metrics": {
                "events": ["profile_view", "photo_unlock", "video_play"],
                "window": 1800,  # 30 minutes
                "aggregations": ["count", "unique_users", "engagement_rate"]
            },
            "fan_metrics": {
                "events": ["fan_subscribed", "fan_unsubscribed", "fan_reactivated"],
                "window": 86400,  # 24 hours
                "aggregations": ["count", "churn_rate", "growth_rate"]
            }
        }
        
    async def add_event(self, event: AnalyticsEvent):
        """Add event for aggregation"""
        # Add to appropriate queues based on event type
        for rule_name, rule in self._aggregation_rules.items():
            if event.event_type in rule["events"]:
                queue_key = f"{event.agency_id}:{rule_name}"
                self._event_queues[queue_key].append(event)
                
                # Trigger aggregation if needed
                await self._check_aggregation_trigger(queue_key, rule)
                
    async def get_metrics(
        self,
        agency_id: str,
        model_id: Optional[str] = None,
        metric_types: Optional[List[str]] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get aggregated metrics"""
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)
            
        metrics = {}
        
        # Get from Redis cache
        cache_keys = []
        if metric_types:
            for metric_type in metric_types:
                cache_key = f"metrics:{agency_id}:{model_id or 'all'}:{metric_type}"
                cache_keys.append(cache_key)
        else:
            # Get all metric types
            pattern = f"metrics:{agency_id}:{model_id or 'all'}:*"
            cache_keys = await redis_client.keys(pattern)
            
        # Fetch metrics from cache
        for key in cache_keys:
            metric_data = await redis_client.get(key)
            if metric_data:
                data = json.loads(metric_data)
                # Filter by time
                if datetime.fromisoformat(data["timestamp"]) >= since:
                    metric_type = key.split(":")[-1]
                    metrics[metric_type] = data
                    
        return metrics
        
    async def get_pending_aggregations(self) -> List[Dict[str, Any]]:
        """Get list of pending aggregations"""
        pending = []
        current_time = datetime.utcnow()
        
        # Check each aggregation schedule
        for agency_id in await self._get_active_agencies():
            # Hourly aggregations
            last_hour = current_time.replace(minute=0, second=0, microsecond=0)
            if not await self._is_aggregated(agency_id, "hourly", last_hour):
                pending.append({
                    "type": "hourly",
                    "agency_id": agency_id,
                    "hour_start": last_hour
                })
                
            # Daily aggregations
            last_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_time.hour >= 1 and not await self._is_aggregated(agency_id, "daily", last_day):
                pending.append({
                    "type": "daily",
                    "agency_id": agency_id,
                    "day_start": last_day
                })
                
        return pending
        
    async def store_aggregation(
        self,
        agency_id: str,
        aggregation_type: str,
        timestamp: datetime,
        data: Dict[str, Any]
    ):
        """Store aggregation result"""
        key = f"aggregation:{agency_id}:{aggregation_type}:{timestamp.isoformat()}"
        
        # Store in Redis with expiration
        ttl = 86400 * 7  # Keep for 7 days
        await redis_client.setex(
            key,
            ttl,
            json.dumps({
                "timestamp": timestamp.isoformat(),
                "data": data,
                "created_at": datetime.utcnow().isoformat()
            })
        )
        
    async def cleanup_old_data(self, cutoff: datetime):
        """Clean up old aggregation data"""
        # Clean up event queues
        for queue_key in list(self._event_queues.keys()):
            queue = self._event_queues[queue_key]
            # Remove old events
            self._event_queues[queue_key] = [
                event for event in queue
                if event.timestamp >= cutoff
            ]
            
            # Remove empty queues
            if not self._event_queues[queue_key]:
                del self._event_queues[queue_key]
                
    async def _check_aggregation_trigger(self, queue_key: str, rule: Dict[str, Any]):
        """Check if aggregation should be triggered"""
        queue = self._event_queues[queue_key]
        if not queue:
            return
            
        # Check if window has passed
        oldest_event = min(queue, key=lambda e: e.timestamp)
        window_seconds = rule["window"]
        
        if (datetime.utcnow() - oldest_event.timestamp).total_seconds() >= window_seconds:
            # Trigger aggregation
            await self._perform_aggregation(queue_key, rule)
            
    async def _perform_aggregation(self, queue_key: str, rule: Dict[str, Any]):
        """Perform aggregation on queued events"""
        queue = self._event_queues[queue_key]
        if not queue:
            return
            
        agency_id, metric_type = queue_key.split(":", 1)
        
        # Group events by model
        model_events = defaultdict(list)
        for event in queue:
            model_id = event.model_id or "all"
            model_events[model_id].append(event)
            
        # Perform aggregations for each model
        for model_id, events in model_events.items():
            aggregated_data = await self._aggregate_events(events, rule["aggregations"])
            
            # Store in cache
            cache_key = f"metrics:{agency_id}:{model_id}:{metric_type}"
            cache_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "window_seconds": rule["window"],
                "event_count": len(events),
                "metrics": aggregated_data
            }
            
            # Store with TTL
            ttl = rule["window"] * 2  # Keep for 2x the window period
            await redis_client.setex(cache_key, ttl, json.dumps(cache_data))
            
        # Clear processed events
        self._event_queues[queue_key] = [
            e for e in queue
            if (datetime.utcnow() - e.timestamp).total_seconds() < rule["window"]
        ]
        
    async def _aggregate_events(
        self,
        events: List[AnalyticsEvent],
        aggregation_types: List[str]
    ) -> Dict[str, Any]:
        """Aggregate events based on specified types"""
        results = {}
        
        if "count" in aggregation_types:
            results["count"] = len(events)
            
        if "unique_users" in aggregation_types:
            unique_users = set()
            for event in events:
                if event.data.get("fan_id"):
                    unique_users.add(event.data["fan_id"])
                elif event.data.get("user_id"):
                    unique_users.add(event.data["user_id"])
            results["unique_users"] = len(unique_users)
            
        if "sum" in aggregation_types:
            values = [e.data.get("amount", 0) for e in events]
            results["sum"] = sum(values)
            
        if "average" in aggregation_types:
            values = [e.data.get("amount", 0) for e in events]
            results["average"] = statistics.mean(values) if values else 0
            
        if "max" in aggregation_types:
            values = [e.data.get("amount", 0) for e in events]
            results["max"] = max(values) if values else 0
            
        if "rate" in aggregation_types:
            # Calculate rate per minute
            if events:
                time_span = (events[-1].timestamp - events[0].timestamp).total_seconds()
                if time_span > 0:
                    results["rate_per_minute"] = (len(events) / time_span) * 60
                else:
                    results["rate_per_minute"] = 0
            else:
                results["rate_per_minute"] = 0
                
        if "engagement_rate" in aggregation_types:
            # Calculate engagement rate
            total_users = results.get("unique_users", 0)
            engaged_users = sum(1 for e in events if e.data.get("engaged", False))
            results["engagement_rate"] = (engaged_users / total_users * 100) if total_users > 0 else 0
            
        if "churn_rate" in aggregation_types:
            # Calculate churn rate
            unsub_events = [e for e in events if e.event_type == "fan_unsubscribed"]
            sub_events = [e for e in events if e.event_type == "fan_subscribed"]
            if sub_events:
                results["churn_rate"] = (len(unsub_events) / len(sub_events)) * 100
            else:
                results["churn_rate"] = 0
                
        if "growth_rate" in aggregation_types:
            # Calculate growth rate
            sub_events = [e for e in events if e.event_type == "fan_subscribed"]
            unsub_events = [e for e in events if e.event_type == "fan_unsubscribed"]
            net_growth = len(sub_events) - len(unsub_events)
            results["growth_rate"] = net_growth
            
        return results
        
    async def _get_active_agencies(self) -> List[str]:
        """Get list of agencies with recent activity"""
        # Get from Redis - agencies that have sent events recently
        pattern = "metrics:*:*:*"
        keys = await redis_client.keys(pattern)
        
        agencies = set()
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 2:
                agencies.add(parts[1])
                
        return list(agencies)
        
    async def _is_aggregated(
        self,
        agency_id: str,
        aggregation_type: str,
        timestamp: datetime
    ) -> bool:
        """Check if aggregation has already been performed"""
        key = f"aggregation:{agency_id}:{aggregation_type}:{timestamp.isoformat()}"
        return await redis_client.exists(key)
