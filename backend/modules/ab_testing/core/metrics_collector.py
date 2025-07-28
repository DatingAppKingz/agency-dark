"""
Metrics Collector - Collects and aggregates experiment metrics
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict
import numpy as np

from core.redis import redis_client
from core.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collects and aggregates metrics for experiments"""
    
    def __init__(self):
        self._collection_tasks = {}
        self._metric_buffers = defaultdict(list)
        self._aggregation_interval = 60  # seconds
        
    async def start_collection(self, experiment_id: UUID):
        """Start collecting metrics for an experiment"""
        if experiment_id in self._collection_tasks:
            logger.warning(f"Collection already running for experiment {experiment_id}")
            return
            
        # Create collection task
        task = asyncio.create_task(
            self._collect_metrics_loop(experiment_id)
        )
        
        self._collection_tasks[experiment_id] = task
        logger.info(f"Started metrics collection for experiment {experiment_id}")
        
    async def stop_collection(self, experiment_id: UUID):
        """Stop collecting metrics for an experiment"""
        if experiment_id in self._collection_tasks:
            task = self._collection_tasks[experiment_id]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
                
            del self._collection_tasks[experiment_id]
            
            # Flush any remaining metrics
            await self._flush_metrics(experiment_id)
            
            logger.info(f"Stopped metrics collection for experiment {experiment_id}")
            
    async def track_event(
        self,
        experiment_id: UUID,
        participant_id: str,
        variant_id: UUID,
        event_type: str,
        event_value: Optional[float] = None,
        event_data: Optional[Dict[str, Any]] = None
    ):
        """Track an event for an experiment"""
        event = {
            "experiment_id": str(experiment_id),
            "participant_id": participant_id,
            "variant_id": str(variant_id),
            "event_type": event_type,
            "event_value": event_value,
            "event_data": event_data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add to buffer
        self._metric_buffers[experiment_id].append(event)
        
        # Also publish to Redis for real-time processing
        await redis_client.publish(
            f"experiment:events:{experiment_id}",
            json.dumps(event)
        )
        
        # Store in time-series data
        await self._store_event(event)
        
    async def get_experiment_metrics(
        self,
        experiment_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        segment_by: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get aggregated metrics for an experiment"""
        # Default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Get raw events
        events = await self._get_events(
            experiment_id, start_date, end_date
        )
        
        # Aggregate metrics
        metrics = self._aggregate_metrics(events, segment_by)
        
        # Add time series data
        metrics["time_series"] = await self._get_time_series(
            experiment_id, start_date, end_date
        )
        
        # Add real-time stats
        metrics["real_time"] = await self._get_real_time_stats(experiment_id)
        
        return metrics
        
    async def get_variant_metrics(
        self,
        experiment_id: UUID,
        variant_id: UUID,
        metric_type: str = "all"
    ) -> Dict[str, Any]:
        """Get metrics for a specific variant"""
        # Get from cache first
        cache_key = f"variant_metrics:{experiment_id}:{variant_id}:{metric_type}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        # Calculate metrics
        events = await self._get_variant_events(experiment_id, variant_id)
        
        metrics = {
            "variant_id": str(variant_id),
            "participant_count": len(set(e["participant_id"] for e in events)),
            "event_count": len(events),
            "conversion_count": sum(
                1 for e in events 
                if e["event_type"] == "conversion" or 
                e.get("event_data", {}).get("is_conversion")
            )
        }
        
        # Calculate conversion rate
        if metrics["participant_count"] > 0:
            metrics["conversion_rate"] = (
                metrics["conversion_count"] / metrics["participant_count"]
            )
        else:
            metrics["conversion_rate"] = 0
            
        # Calculate revenue metrics
        revenue_events = [e for e in events if e.get("event_value") is not None]
        if revenue_events:
            values = [e["event_value"] for e in revenue_events]
            metrics["total_revenue"] = sum(values)
            metrics["average_revenue_per_user"] = (
                metrics["total_revenue"] / metrics["participant_count"]
                if metrics["participant_count"] > 0 else 0
            )
            metrics["average_order_value"] = np.mean(values)
            
        # Calculate engagement metrics
        engagement_events = [
            e for e in events 
            if e["event_type"] in ["click", "view", "interaction"]
        ]
        
        if engagement_events:
            participant_engagement = defaultdict(int)
            for event in engagement_events:
                participant_engagement[event["participant_id"]] += 1
                
            engagement_values = list(participant_engagement.values())
            metrics["average_engagement"] = np.mean(engagement_values)
            metrics["engagement_std"] = np.std(engagement_values)
            
        # Cache results
        await redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps(metrics)
        )
        
        return metrics
        
    async def _collect_metrics_loop(self, experiment_id: UUID):
        """Background task to collect and aggregate metrics"""
        try:
            while True:
                await asyncio.sleep(self._aggregation_interval)
                
                # Flush buffered metrics
                await self._flush_metrics(experiment_id)
                
                # Update aggregated metrics
                await self._update_aggregations(experiment_id)
                
        except asyncio.CancelledError:
            logger.info(f"Metrics collection cancelled for experiment {experiment_id}")
            raise
        except Exception as e:
            logger.error(f"Error in metrics collection for experiment {experiment_id}: {e}")
            
    async def _flush_metrics(self, experiment_id: UUID):
        """Flush buffered metrics to storage"""
        if experiment_id not in self._metric_buffers:
            return
            
        events = self._metric_buffers[experiment_id]
        if not events:
            return
            
        # Clear buffer
        self._metric_buffers[experiment_id] = []
        
        # Store events in batches
        batch_size = 100
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            await self._store_events_batch(batch)
            
        logger.debug(f"Flushed {len(events)} events for experiment {experiment_id}")
        
    async def _store_event(self, event: Dict[str, Any]):
        """Store a single event"""
        # Store in Redis sorted set for time-series queries
        key = f"experiment:events:{event['experiment_id']}"
        
        # Use timestamp as score for sorting
        timestamp = datetime.fromisoformat(event["timestamp"])
        score = timestamp.timestamp()
        
        await redis_client.zadd(
            key,
            {json.dumps(event): score}
        )
        
        # Set expiration (30 days)
        await redis_client.expire(key, 86400 * 30)
        
        # Update variant counters
        variant_key = f"variant:stats:{event['experiment_id']}:{event['variant_id']}"
        
        await redis_client.hincrby(variant_key, "event_count", 1)
        
        if event["event_type"] == "conversion" or event.get("event_data", {}).get("is_conversion"):
            await redis_client.hincrby(variant_key, "conversion_count", 1)
            
        if event.get("event_value") is not None:
            await redis_client.hincrbyfloat(
                variant_key, "total_value", event["event_value"]
            )
            
    async def _store_events_batch(self, events: List[Dict[str, Any]]):
        """Store multiple events efficiently"""
        # Group by experiment
        by_experiment = defaultdict(list)
        for event in events:
            by_experiment[event["experiment_id"]].append(event)
            
        # Store each experiment's events
        for experiment_id, exp_events in by_experiment.items():
            key = f"experiment:events:{experiment_id}"
            
            # Prepare batch
            batch_data = {}
            for event in exp_events:
                timestamp = datetime.fromisoformat(event["timestamp"])
                score = timestamp.timestamp()
                batch_data[json.dumps(event)] = score
                
            if batch_data:
                await redis_client.zadd(key, batch_data)
                await redis_client.expire(key, 86400 * 30)
                
    async def _get_events(
        self,
        experiment_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get events within date range"""
        key = f"experiment:events:{experiment_id}"
        
        # Get events by score (timestamp)
        start_score = start_date.timestamp()
        end_score = end_date.timestamp()
        
        events_data = await redis_client.zrangebyscore(
            key,
            start_score,
            end_score
        )
        
        # Parse events
        events = []
        for event_json in events_data:
            try:
                event = json.loads(event_json)
                events.append(event)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse event: {event_json}")
                
        return events
        
    async def _get_variant_events(
        self,
        experiment_id: UUID,
        variant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all events for a variant"""
        # Get all experiment events
        key = f"experiment:events:{experiment_id}"
        all_events = await redis_client.zrange(key, 0, -1)
        
        # Filter by variant
        variant_events = []
        for event_json in all_events:
            try:
                event = json.loads(event_json)
                if event["variant_id"] == str(variant_id):
                    variant_events.append(event)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse event: {event_json}")
                
        return variant_events
        
    def _aggregate_metrics(
        self,
        events: List[Dict[str, Any]],
        segment_by: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Aggregate events into metrics"""
        metrics = {
            "total_participants": len(set(e["participant_id"] for e in events)),
            "total_events": len(events),
            "variants": {}
        }
        
        # Group by variant
        by_variant = defaultdict(list)
        for event in events:
            by_variant[event["variant_id"]].append(event)
            
        # Calculate metrics per variant
        for variant_id, variant_events in by_variant.items():
            variant_metrics = {
                "participant_count": len(set(e["participant_id"] for e in variant_events)),
                "event_count": len(variant_events),
                "conversions": sum(
                    1 for e in variant_events
                    if e["event_type"] == "conversion" or
                    e.get("event_data", {}).get("is_conversion")
                ),
                "revenue": sum(
                    e.get("event_value", 0) for e in variant_events
                    if e.get("event_value") is not None
                )
            }
            
            # Calculate rates
            if variant_metrics["participant_count"] > 0:
                variant_metrics["conversion_rate"] = (
                    variant_metrics["conversions"] / variant_metrics["participant_count"]
                )
                variant_metrics["revenue_per_user"] = (
                    variant_metrics["revenue"] / variant_metrics["participant_count"]
                )
            else:
                variant_metrics["conversion_rate"] = 0
                variant_metrics["revenue_per_user"] = 0
                
            metrics["variants"][variant_id] = variant_metrics
            
        # Segment analysis if requested
        if segment_by:
            metrics["segments"] = self._segment_analysis(events, segment_by)
            
        return metrics
        
    def _segment_analysis(
        self,
        events: List[Dict[str, Any]],
        segment_by: List[str]
    ) -> Dict[str, Any]:
        """Perform segmentation analysis"""
        segments = {}
        
        for segment_field in segment_by:
            segment_data = defaultdict(lambda: {
                "participants": set(),
                "conversions": 0,
                "revenue": 0,
                "events": 0
            })
            
            for event in events:
                # Get segment value from event data
                segment_value = event.get("event_data", {}).get(segment_field, "unknown")
                
                segment_data[segment_value]["participants"].add(event["participant_id"])
                segment_data[segment_value]["events"] += 1
                
                if event["event_type"] == "conversion" or event.get("event_data", {}).get("is_conversion"):
                    segment_data[segment_value]["conversions"] += 1
                    
                if event.get("event_value") is not None:
                    segment_data[segment_value]["revenue"] += event["event_value"]
                    
            # Convert to metrics
            segment_metrics = {}
            for segment_value, data in segment_data.items():
                participant_count = len(data["participants"])
                
                segment_metrics[segment_value] = {
                    "participant_count": participant_count,
                    "conversion_rate": (
                        data["conversions"] / participant_count
                        if participant_count > 0 else 0
                    ),
                    "revenue_per_user": (
                        data["revenue"] / participant_count
                        if participant_count > 0 else 0
                    ),
                    "events_per_user": (
                        data["events"] / participant_count
                        if participant_count > 0 else 0
                    )
                }
                
            segments[segment_field] = segment_metrics
            
        return segments
        
    async def _get_time_series(
        self,
        experiment_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get time series data for visualization"""
        # Get hourly aggregations
        time_series = []
        
        current = start_date.replace(minute=0, second=0, microsecond=0)
        
        while current <= end_date:
            next_hour = current + timedelta(hours=1)
            
            # Get events for this hour
            events = await self._get_events(
                experiment_id,
                current,
                next_hour
            )
            
            # Aggregate
            hour_metrics = self._aggregate_metrics(events)
            
            time_series.append({
                "timestamp": current.isoformat(),
                "participants": hour_metrics["total_participants"],
                "events": hour_metrics["total_events"],
                "variants": hour_metrics["variants"]
            })
            
            current = next_hour
            
        return time_series
        
    async def _get_real_time_stats(
        self,
        experiment_id: UUID
    ) -> Dict[str, Any]:
        """Get real-time statistics"""
        # Get last 5 minutes of data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)
        
        events = await self._get_events(
            experiment_id,
            start_time,
            end_time
        )
        
        return {
            "events_per_minute": len(events) / 5,
            "active_participants": len(set(e["participant_id"] for e in events)),
            "last_event": events[-1]["timestamp"] if events else None
        }
        
    async def _update_aggregations(self, experiment_id: UUID):
        """Update pre-aggregated metrics"""
        # Get variant stats
        variant_pattern = f"variant:stats:{experiment_id}:*"
        variant_keys = await redis_client.keys(variant_pattern)
        
        for variant_key in variant_keys:
            stats = await redis_client.hgetall(variant_key)
            
            if stats:
                # Calculate derived metrics
                event_count = int(stats.get("event_count", 0))
                conversion_count = int(stats.get("conversion_count", 0))
                total_value = float(stats.get("total_value", 0))
                
                # Get unique participants (approximation)
                participants_key = variant_key.replace("stats", "participants")
                participant_count = await redis_client.scard(participants_key)
                
                if participant_count > 0:
                    conversion_rate = conversion_count / participant_count
                    revenue_per_user = total_value / participant_count
                    
                    # Store calculated metrics
                    await redis_client.hset(
                        variant_key,
                        mapping={
                            "participant_count": participant_count,
                            "conversion_rate": conversion_rate,
                            "revenue_per_user": revenue_per_user
                        }
                    )
