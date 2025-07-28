"""
Stream processor for real-time event processing
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from scipy import stats

from core.redis import redis_client
from core.logging import get_logger
from ..domain.models import AnalyticsEvent

logger = get_logger(__name__)


class StreamProcessor:
    """Process analytics events in real-time"""
    
    def __init__(self):
        self._processors: Dict[str, Callable] = {
            "message_sent": self._process_message_event,
            "message_received": self._process_message_event,
            "payment_received": self._process_payment_event,
            "fan_subscribed": self._process_fan_event,
            "fan_unsubscribed": self._process_fan_event,
            "profile_view": self._process_engagement_event,
            "photo_unlock": self._process_engagement_event,
            "video_play": self._process_engagement_event
        }
        
        self._anomaly_detectors: Dict[str, AnomalyDetector] = {}
        self._trend_analyzers: Dict[str, TrendAnalyzer] = {}
        
    async def process_event(self, event: AnalyticsEvent):
        """Process a single analytics event"""
        # Get processor for event type
        processor = self._processors.get(event.event_type)
        
        if processor:
            try:
                await processor(event)
                
                # Check for anomalies
                await self._detect_anomalies(event)
                
                # Update trends
                await self._update_trends(event)
                
                # Trigger alerts if needed
                await self._check_alerts(event)
                
            except Exception as e:
                logger.error(f"Error processing event {event.event_type}: {e}")
        else:
            logger.warning(f"No processor for event type: {event.event_type}")
            
    async def _process_message_event(self, event: AnalyticsEvent):
        """Process message events"""
        # Update message counters
        counter_key = f"counter:messages:{event.agency_id}:{event.model_id or 'all'}"
        await redis_client.hincrby(counter_key, event.event_type, 1)
        
        # Update response time metrics if applicable
        if event.event_type == "message_sent" and event.data.get("response_time"):
            response_time = event.data["response_time"]
            await self._update_response_time_metrics(event.agency_id, event.model_id, response_time)
            
        # Track conversation metrics
        if event.data.get("fan_id"):
            await self._update_conversation_metrics(event)
            
    async def _process_payment_event(self, event: AnalyticsEvent):
        """Process payment events"""
        amount = event.data.get("amount", 0)
        currency = event.data.get("currency", "USD")
        
        # Update revenue counters
        counter_key = f"counter:revenue:{event.agency_id}:{event.model_id or 'all'}"
        await redis_client.hincrbyfloat(counter_key, currency, amount)
        
        # Update payment type breakdown
        payment_type = event.data.get("payment_type", "unknown")
        breakdown_key = f"breakdown:payments:{event.agency_id}:{event.model_id or 'all'}"
        await redis_client.hincrby(breakdown_key, payment_type, 1)
        
        # Track high-value transactions
        if amount >= 100:  # High-value threshold
            await self._track_high_value_transaction(event)
            
    async def _process_fan_event(self, event: AnalyticsEvent):
        """Process fan-related events"""
        # Update fan counters
        counter_key = f"counter:fans:{event.agency_id}:{event.model_id or 'all'}"
        
        if event.event_type == "fan_subscribed":
            await redis_client.hincrby(counter_key, "total", 1)
            await redis_client.hincrby(counter_key, "new_today", 1)
        elif event.event_type == "fan_unsubscribed":
            await redis_client.hincrby(counter_key, "total", -1)
            await redis_client.hincrby(counter_key, "churned_today", 1)
            
        # Update fan lifetime value if available
        if event.data.get("lifetime_value"):
            await self._update_fan_ltv_metrics(event)
            
    async def _process_engagement_event(self, event: AnalyticsEvent):
        """Process engagement events"""
        # Update engagement counters
        counter_key = f"counter:engagement:{event.agency_id}:{event.model_id or 'all'}"
        await redis_client.hincrby(counter_key, event.event_type, 1)
        
        # Track unique engaged users
        if event.data.get("fan_id"):
            engaged_key = f"engaged_users:{event.agency_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
            await redis_client.sadd(engaged_key, event.data["fan_id"])
            await redis_client.expire(engaged_key, 86400 * 2)  # Keep for 2 days
            
    async def _detect_anomalies(self, event: AnalyticsEvent):
        """Detect anomalies in event patterns"""
        detector_key = f"{event.agency_id}:{event.event_type}"
        
        if detector_key not in self._anomaly_detectors:
            self._anomaly_detectors[detector_key] = AnomalyDetector()
            
        detector = self._anomaly_detectors[detector_key]
        
        # Add event to detector
        is_anomaly = await detector.add_event(event)
        
        if is_anomaly:
            await self._trigger_anomaly_alert(event, detector.get_anomaly_score())
            
    async def _update_trends(self, event: AnalyticsEvent):
        """Update trend analysis"""
        analyzer_key = f"{event.agency_id}:{event.event_type}"
        
        if analyzer_key not in self._trend_analyzers:
            self._trend_analyzers[analyzer_key] = TrendAnalyzer()
            
        analyzer = self._trend_analyzers[analyzer_key]
        
        # Update trend
        trend = await analyzer.add_event(event)
        
        # Store trend data
        if trend:
            trend_key = f"trend:{event.agency_id}:{event.event_type}"
            await redis_client.setex(
                trend_key,
                3600,  # 1 hour TTL
                json.dumps(trend)
            )
            
    async def _check_alerts(self, event: AnalyticsEvent):
        """Check if event should trigger alerts"""
        # Check for milestone achievements
        if event.event_type == "payment_received":
            await self._check_revenue_milestones(event)
        elif event.event_type == "fan_subscribed":
            await self._check_fan_milestones(event)
            
    async def _update_response_time_metrics(
        self,
        agency_id: str,
        model_id: Optional[str],
        response_time: float
    ):
        """Update response time metrics"""
        key = f"response_times:{agency_id}:{model_id or 'all'}"
        
        # Add to sorted set with timestamp score
        await redis_client.zadd(
            key,
            {str(datetime.utcnow().timestamp()): response_time}
        )
        
        # Keep only recent entries (last hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        await redis_client.zremrangebyscore(key, 0, one_hour_ago.timestamp())
        
        # Calculate statistics
        all_times = await redis_client.zrange(key, 0, -1)
        if all_times:
            times = [float(t) for t in all_times]
            stats_key = f"stats:response_time:{agency_id}:{model_id or 'all'}"
            
            await redis_client.hset(stats_key, mapping={
                "avg": np.mean(times),
                "median": np.median(times),
                "p95": np.percentile(times, 95),
                "min": min(times),
                "max": max(times)
            })
            
    async def _update_conversation_metrics(self, event: AnalyticsEvent):
        """Update conversation-level metrics"""
        fan_id = event.data.get("fan_id")
        if not fan_id:
            return
            
        conv_key = f"conversation:{event.agency_id}:{event.model_id}:{fan_id}"
        
        # Update conversation stats
        await redis_client.hincrby(conv_key, "message_count", 1)
        await redis_client.hset(conv_key, "last_activity", datetime.utcnow().isoformat())
        
        # Set expiration
        await redis_client.expire(conv_key, 86400 * 7)  # Keep for 7 days
        
    async def _track_high_value_transaction(self, event: AnalyticsEvent):
        """Track high-value transactions"""
        key = f"high_value_transactions:{event.agency_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        
        transaction_data = {
            "amount": event.data.get("amount"),
            "currency": event.data.get("currency"),
            "fan_id": event.data.get("fan_id"),
            "payment_type": event.data.get("payment_type"),
            "timestamp": event.timestamp.isoformat()
        }
        
        await redis_client.lpush(key, json.dumps(transaction_data))
        await redis_client.ltrim(key, 0, 99)  # Keep top 100
        await redis_client.expire(key, 86400 * 30)  # Keep for 30 days
        
    async def _update_fan_ltv_metrics(self, event: AnalyticsEvent):
        """Update fan lifetime value metrics"""
        fan_id = event.data.get("fan_id")
        ltv = event.data.get("lifetime_value", 0)
        
        if fan_id:
            key = f"fan_ltv:{event.agency_id}"
            await redis_client.zadd(key, {fan_id: ltv})
            
            # Calculate LTV segments
            all_ltvs = await redis_client.zrange(key, 0, -1, withscores=True)
            if all_ltvs:
                values = [score for _, score in all_ltvs]
                
                segments_key = f"ltv_segments:{event.agency_id}"
                await redis_client.hset(segments_key, mapping={
                    "high_value": len([v for v in values if v >= 1000]),
                    "medium_value": len([v for v in values if 100 <= v < 1000]),
                    "low_value": len([v for v in values if v < 100]),
                    "average_ltv": np.mean(values)
                })
                
    async def _trigger_anomaly_alert(self, event: AnalyticsEvent, score: float):
        """Trigger alert for detected anomaly"""
        alert_data = {
            "type": "anomaly",
            "event_type": event.event_type,
            "agency_id": event.agency_id,
            "model_id": event.model_id,
            "score": score,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }
        
        # Publish alert
        await redis_client.publish(
            f"alerts:{event.agency_id}",
            json.dumps(alert_data)
        )
        
        # Store alert
        alerts_key = f"alerts:history:{event.agency_id}"
        await redis_client.lpush(alerts_key, json.dumps(alert_data))
        await redis_client.ltrim(alerts_key, 0, 999)  # Keep last 1000 alerts
        
    async def _check_revenue_milestones(self, event: AnalyticsEvent):
        """Check for revenue milestone achievements"""
        amount = event.data.get("amount", 0)
        
        # Get current daily revenue
        counter_key = f"counter:revenue:{event.agency_id}:{event.model_id or 'all'}"
        daily_revenue = await redis_client.hget(counter_key, "USD") or 0
        daily_revenue = float(daily_revenue)
        
        # Check milestones
        milestones = [100, 500, 1000, 5000, 10000]
        for milestone in milestones:
            if daily_revenue >= milestone and (daily_revenue - amount) < milestone:
                # Milestone reached!
                await self._trigger_milestone_alert(event, "daily_revenue", milestone)
                
    async def _check_fan_milestones(self, event: AnalyticsEvent):
        """Check for fan count milestones"""
        # Get current fan count
        counter_key = f"counter:fans:{event.agency_id}:{event.model_id or 'all'}"
        fan_count = await redis_client.hget(counter_key, "total") or 0
        fan_count = int(fan_count)
        
        # Check milestones
        milestones = [10, 50, 100, 500, 1000, 5000]
        for milestone in milestones:
            if fan_count == milestone:
                await self._trigger_milestone_alert(event, "fan_count", milestone)
                
    async def _trigger_milestone_alert(self, event: AnalyticsEvent, milestone_type: str, value: Any):
        """Trigger milestone achievement alert"""
        from core.webhooks.webhook_integration import webhook_integration
        
        # Send webhook event
        await webhook_integration.milestone_reached(
            agency_id=event.agency_id,
            model_id=event.model_id or "",
            milestone_type=milestone_type,
            milestone_value=value,
            previous_value=value - 1,
            reached_at=event.timestamp,
            details=event.data
        )


class AnomalyDetector:
    """Detect anomalies in event patterns"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.events: List[float] = []
        self.timestamps: List[datetime] = []
        
    async def add_event(self, event: AnalyticsEvent) -> bool:
        """Add event and check for anomaly"""
        # Extract numeric value from event
        value = self._extract_value(event)
        
        self.events.append(value)
        self.timestamps.append(event.timestamp)
        
        # Keep window size
        if len(self.events) > self.window_size:
            self.events.pop(0)
            self.timestamps.pop(0)
            
        # Need minimum events for detection
        if len(self.events) < 10:
            return False
            
        # Check for anomaly using z-score
        if len(self.events) > 1:
            z_score = abs(stats.zscore(self.events)[-1])
            return z_score > 3  # 3 standard deviations
            
        return False
        
    def get_anomaly_score(self) -> float:
        """Get anomaly score for last event"""
        if len(self.events) > 1:
            return abs(stats.zscore(self.events)[-1])
        return 0
        
    def _extract_value(self, event: AnalyticsEvent) -> float:
        """Extract numeric value from event"""
        if event.event_type in ["payment_received", "tip_received"]:
            return event.data.get("amount", 0)
        elif event.event_type in ["message_sent", "message_received"]:
            return 1  # Count
        else:
            return event.data.get("value", 1)


class TrendAnalyzer:
    """Analyze trends in event data"""
    
    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self.time_buckets: Dict[str, List[float]] = defaultdict(list)
        
    async def add_event(self, event: AnalyticsEvent) -> Optional[Dict[str, Any]]:
        """Add event and analyze trend"""
        # Create time bucket
        bucket_time = event.timestamp.replace(second=0, microsecond=0)
        bucket_key = bucket_time.isoformat()
        
        # Extract value
        value = self._extract_value(event)
        self.time_buckets[bucket_key].append(value)
        
        # Clean old buckets
        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        old_keys = [k for k in self.time_buckets.keys() 
                   if datetime.fromisoformat(k) < cutoff]
        for key in old_keys:
            del self.time_buckets[key]
            
        # Analyze trend if enough data
        if len(self.time_buckets) >= 5:
            return self._calculate_trend()
            
        return None
        
    def _calculate_trend(self) -> Dict[str, Any]:
        """Calculate trend metrics"""
        # Sort buckets by time
        sorted_buckets = sorted(self.time_buckets.items())
        
        # Calculate values per bucket
        bucket_totals = [(datetime.fromisoformat(k), sum(v)) 
                        for k, v in sorted_buckets]
        
        if len(bucket_totals) < 2:
            return None
            
        # Calculate trend
        times = [i for i in range(len(bucket_totals))]
        values = [v for _, v in bucket_totals]
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(times, values)
        
        # Calculate percentage change
        first_value = values[0] if values[0] > 0 else 1
        last_value = values[-1]
        pct_change = ((last_value - first_value) / first_value) * 100
        
        return {
            "slope": slope,
            "direction": "up" if slope > 0 else "down" if slope < 0 else "stable",
            "strength": abs(r_value),
            "pct_change": pct_change,
            "current_value": last_value,
            "values": values[-10:]  # Last 10 values
        }
        
    def _extract_value(self, event: AnalyticsEvent) -> float:
        """Extract numeric value from event"""
        if event.event_type in ["payment_received", "tip_received"]:
            return event.data.get("amount", 0)
        else:
            return 1  # Count events
