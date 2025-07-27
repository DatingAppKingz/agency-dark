"""
Intelligent API routing service.

Determines the best API to use based on various factors like availability,
rate limits, cost, and historical performance.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from core.redis import redis_client
from core.domain.models import ModelProfile, Fan
from modules.analytics.domain.models import AnalyticsEvent

from ..domain.schemas import DataSource, ConflictResolution


logger = logging.getLogger(__name__)


class RoutingFactor(str, Enum):
    """Factors to consider for routing decisions."""
    AVAILABILITY = "availability"
    RATE_LIMIT = "rate_limit"
    COST = "cost"
    PERFORMANCE = "performance"
    FEATURE_SUPPORT = "feature_support"
    USER_PREFERENCE = "user_preference"


class RouteScore:
    """Score for a routing decision."""
    def __init__(self, source: DataSource, score: float, factors: Dict[RoutingFactor, float]):
        self.source = source
        self.score = score
        self.factors = factors
        

class IntelligentRouter:
    """Intelligent routing for API calls."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._route_cache: Dict[str, RouteScore] = {}
        
    async def determine_best_source(
        self,
        model_profile: ModelProfile,
        operation_type: str,
        fan: Optional[Fan] = None,
        payload_size: Optional[int] = None,
        features_required: Optional[List[str]] = None
    ) -> DataSource:
        """Determine the best API source for an operation."""
        # Check cache first
        cache_key = self._get_cache_key(model_profile.id, operation_type, fan.id if fan else None)
        cached_score = await self._get_cached_route(cache_key)
        if cached_score:
            return cached_score.source
            
        # Calculate scores for each available source
        scores = []
        
        if model_profile.onlyfans_api_key:
            score = await self._calculate_source_score(
                model_profile,
                DataSource.ONLYFANS,
                operation_type,
                fan,
                payload_size,
                features_required
            )
            scores.append(score)
            
        if model_profile.inflow_api_key:
            score = await self._calculate_source_score(
                model_profile,
                DataSource.INFLOW,
                operation_type,
                fan,
                payload_size,
                features_required
            )
            scores.append(score)
            
        # Select best score
        if not scores:
            raise ValueError("No API sources configured")
            
        best_score = max(scores, key=lambda s: s.score)
        
        # Cache the result
        await self._cache_route(cache_key, best_score, ttl=300)  # 5 minute cache
        
        logger.info(
            f"Selected {best_score.source} for {operation_type} "
            f"(score: {best_score.score:.2f})"
        )
        
        return best_score.source
        
    async def _calculate_source_score(
        self,
        model_profile: ModelProfile,
        source: DataSource,
        operation_type: str,
        fan: Optional[Fan],
        payload_size: Optional[int],
        features_required: Optional[List[str]]
    ) -> RouteScore:
        """Calculate routing score for a specific source."""
        factors = {}
        
        # 1. Availability (30% weight)
        availability_score = await self._check_availability(source)
        factors[RoutingFactor.AVAILABILITY] = availability_score * 0.3
        
        # 2. Rate limit status (25% weight)
        rate_limit_score = await self._check_rate_limits(model_profile, source)
        factors[RoutingFactor.RATE_LIMIT] = rate_limit_score * 0.25
        
        # 3. Cost efficiency (15% weight)
        cost_score = await self._calculate_cost_score(source, operation_type, payload_size)
        factors[RoutingFactor.COST] = cost_score * 0.15
        
        # 4. Historical performance (15% weight)
        performance_score = await self._get_performance_score(model_profile, source, operation_type)
        factors[RoutingFactor.PERFORMANCE] = performance_score * 0.15
        
        # 5. Feature support (10% weight)
        feature_score = self._check_feature_support(source, features_required)
        factors[RoutingFactor.FEATURE_SUPPORT] = feature_score * 0.1
        
        # 6. User preference (5% weight)
        preference_score = self._get_user_preference_score(model_profile, source)
        factors[RoutingFactor.USER_PREFERENCE] = preference_score * 0.05
        
        # Calculate total score
        total_score = sum(factors.values())
        
        return RouteScore(source, total_score, factors)
        
    async def _check_availability(self, source: DataSource) -> float:
        """Check if API is available (not down or maintenance)."""
        # Check recent error rates
        error_key = f"api_errors:{source.value}"
        error_count = await redis_client.get(error_key)
        
        if error_count and int(error_count) > 10:
            # High error rate in last hour
            return 0.2
            
        # Check maintenance status
        maintenance_key = f"api_maintenance:{source.value}"
        is_maintenance = await redis_client.get(maintenance_key)
        
        if is_maintenance:
            return 0.0
            
        return 1.0
        
    async def _check_rate_limits(self, model_profile: ModelProfile, source: DataSource) -> float:
        """Check current rate limit status."""
        # Get current usage from Redis
        rate_key = f"rate_limit:{source.value}:{model_profile.id}"
        current_usage = await redis_client.get(rate_key)
        
        if not current_usage:
            return 1.0
            
        usage = int(current_usage)
        
        # Define limits per source
        limits = {
            DataSource.ONLYFANS: 60,  # per minute
            DataSource.INFLOW: 60
        }
        
        limit = limits.get(source, 60)
        remaining_ratio = 1 - (usage / limit)
        
        # Scale score based on remaining capacity
        if remaining_ratio > 0.5:
            return 1.0
        elif remaining_ratio > 0.2:
            return 0.7
        elif remaining_ratio > 0:
            return 0.3
        else:
            return 0.0
            
    async def _calculate_cost_score(
        self,
        source: DataSource,
        operation_type: str,
        payload_size: Optional[int]
    ) -> float:
        """Calculate cost efficiency score."""
        # Base costs per operation (hypothetical)
        costs = {
            DataSource.ONLYFANS: {
                "message": 0.001,
                "content_post": 0.002,
                "mass_message": 0.01,
                "sync": 0.0001
            },
            DataSource.INFLOW: {
                "message": 0.0008,
                "content_post": 0.0015,
                "mass_message": 0.008,
                "sync": 0.0001
            }
        }
        
        source_costs = costs.get(source, {})
        operation_cost = source_costs.get(operation_type, 0.001)
        
        # Adjust for payload size if provided
        if payload_size and payload_size > 1000:
            operation_cost *= (1 + payload_size / 10000)
            
        # Invert cost for score (lower cost = higher score)
        if operation_cost == 0:
            return 1.0
        else:
            return min(1.0, 0.001 / operation_cost)
            
    async def _get_performance_score(
        self,
        model_profile: ModelProfile,
        source: DataSource,
        operation_type: str
    ) -> float:
        """Get historical performance score."""
        # Query recent performance metrics
        since = datetime.utcnow() - timedelta(hours=24)
        
        result = await self.db.execute(
            select(
                func.avg(AnalyticsEvent.metadata['response_time'].as_float()),
                func.count(AnalyticsEvent.id)
            ).where(
                and_(
                    AnalyticsEvent.event_type == "api_call",
                    AnalyticsEvent.metadata['source'].astext == source.value,
                    AnalyticsEvent.metadata['operation'].astext == operation_type,
                    AnalyticsEvent.metadata['model_id'].astext == str(model_profile.id),
                    AnalyticsEvent.timestamp > since
                )
            )
        )
        
        avg_response_time, call_count = result.one()
        
        if not call_count or call_count < 10:
            # Not enough data, return neutral score
            return 0.7
            
        # Score based on response time (lower is better)
        if avg_response_time < 500:  # < 500ms
            return 1.0
        elif avg_response_time < 1000:  # < 1s
            return 0.8
        elif avg_response_time < 2000:  # < 2s
            return 0.6
        elif avg_response_time < 5000:  # < 5s
            return 0.4
        else:
            return 0.2
            
    def _check_feature_support(
        self,
        source: DataSource,
        features_required: Optional[List[str]]
    ) -> float:
        """Check if source supports required features."""
        if not features_required:
            return 1.0
            
        # Define feature support matrix
        feature_support = {
            DataSource.ONLYFANS: {
                "ppv_messages", "mass_messages", "media_upload", 
                "tips", "subscriptions", "posts", "stories",
                "live_streaming", "vault", "lists"
            },
            DataSource.INFLOW: {
                "ppv_messages", "mass_messages", "media_upload",
                "tips", "subscriptions", "analytics", "webhooks",
                "automation", "campaigns"
            }
        }
        
        source_features = feature_support.get(source, set())
        required_set = set(features_required)
        
        if required_set.issubset(source_features):
            return 1.0
        else:
            # Partial support
            supported = len(required_set.intersection(source_features))
            return supported / len(required_set)
            
    def _get_user_preference_score(
        self,
        model_profile: ModelProfile,
        source: DataSource
    ) -> float:
        """Get user preference score."""
        # Check if model has preferred source in metadata
        if model_profile.metadata:
            preferred = model_profile.metadata.get("preferred_api_source")
            if preferred == source.value:
                return 1.0
            elif preferred:
                return 0.5
                
        # No preference
        return 0.7
        
    def _get_cache_key(
        self,
        model_id: str,
        operation_type: str,
        fan_id: Optional[str]
    ) -> str:
        """Generate cache key for routing decision."""
        parts = [f"route:{model_id}:{operation_type}"]
        if fan_id:
            parts.append(fan_id)
        return ":".join(parts)
        
    async def _get_cached_route(self, cache_key: str) -> Optional[RouteScore]:
        """Get cached routing decision."""
        data = await redis_client.get(cache_key)
        if data:
            import json
            route_data = json.loads(data)
            return RouteScore(
                source=DataSource(route_data["source"]),
                score=route_data["score"],
                factors=route_data["factors"]
            )
        return None
        
    async def _cache_route(self, cache_key: str, route_score: RouteScore, ttl: int):
        """Cache routing decision."""
        import json
        data = {
            "source": route_score.source.value,
            "score": route_score.score,
            "factors": {k.value: v for k, v in route_score.factors.items()}
        }
        await redis_client.setex(cache_key, ttl, json.dumps(data))
        
    async def record_api_call(
        self,
        model_profile: ModelProfile,
        source: DataSource,
        operation_type: str,
        response_time: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record API call metrics for future routing decisions."""
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="api_call",
            user_id=str(model_profile.user_id),
            metadata={
                "model_id": str(model_profile.id),
                "source": source.value,
                "operation": operation_type,
                "response_time": response_time,
                "success": success,
                "error": error
            },
            timestamp=datetime.utcnow()
        )
        self.db.add(analytics_event)
        
        # Update error counter if failed
        if not success:
            error_key = f"api_errors:{source.value}"
            await redis_client.incr(error_key)
            await redis_client.expire(error_key, 3600)  # 1 hour expiry
            
        # Update rate limit counter
        rate_key = f"rate_limit:{source.value}:{model_profile.id}"
        await redis_client.incr(rate_key)
        await redis_client.expire(rate_key, 60)  # 1 minute expiry
        
        await self.db.commit()