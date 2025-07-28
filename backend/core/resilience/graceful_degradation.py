"""
Graceful degradation strategies for handling service failures
"""
import asyncio
import functools
from typing import Callable, Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from enum import Enum

from core.logging import logger
from core.redis import redis_client
from core.config import settings


class DegradationLevel(Enum):
    """Service degradation levels"""
    NORMAL = "normal"          # Full functionality
    DEGRADED = "degraded"      # Reduced functionality
    ESSENTIAL = "essential"    # Essential features only
    MAINTENANCE = "maintenance" # Maintenance mode


class FeatureFlag:
    """Feature flag for controlling service features"""
    
    def __init__(
        self,
        name: str,
        default_enabled: bool = True,
        degradation_levels: Optional[List[DegradationLevel]] = None
    ):
        self.name = name
        self.default_enabled = default_enabled
        self.degradation_levels = degradation_levels or [DegradationLevel.NORMAL]
    
    async def is_enabled(self, current_level: DegradationLevel = DegradationLevel.NORMAL) -> bool:
        """Check if feature is enabled at current degradation level"""
        # Check Redis for override
        override_key = f"feature_flag:{self.name}"
        override = await redis_client.get(override_key)
        
        if override is not None:
            return override.lower() == "true"
        
        # Check degradation level
        if current_level not in self.degradation_levels:
            return False
        
        return self.default_enabled
    
    async def enable(self, ttl: Optional[int] = None):
        """Enable feature flag"""
        override_key = f"feature_flag:{self.name}"
        if ttl:
            await redis_client.setex(override_key, ttl, "true")
        else:
            await redis_client.set(override_key, "true")
    
    async def disable(self, ttl: Optional[int] = None):
        """Disable feature flag"""
        override_key = f"feature_flag:{self.name}"
        if ttl:
            await redis_client.setex(override_key, ttl, "false")
        else:
            await redis_client.set(override_key, "false")


class ServiceDegradation:
    """
    Manages graceful degradation of services
    """
    
    def __init__(self):
        self.current_level = DegradationLevel.NORMAL
        self.feature_flags: Dict[str, FeatureFlag] = {}
        self._health_checks: Dict[str, Callable] = {}
        self._fallback_handlers: Dict[str, Callable] = {}
        self._cached_responses: Dict[str, Any] = {}
        self._monitoring_task = None
    
    def register_feature(
        self,
        name: str,
        default_enabled: bool = True,
        available_in: Optional[List[DegradationLevel]] = None
    ) -> FeatureFlag:
        """Register a feature with degradation levels"""
        feature = FeatureFlag(name, default_enabled, available_in)
        self.feature_flags[name] = feature
        return feature
    
    def register_health_check(
        self,
        service_name: str,
        health_check: Callable[[], bool]
    ):
        """Register a health check for a service"""
        self._health_checks[service_name] = health_check
    
    def register_fallback(
        self,
        operation: str,
        fallback_handler: Callable[..., Any]
    ):
        """Register a fallback handler for an operation"""
        self._fallback_handlers[operation] = fallback_handler
    
    async def start_monitoring(self, interval: int = 30):
        """Start monitoring services and adjust degradation level"""
        self._monitoring_task = asyncio.create_task(
            self._monitor_loop(interval)
        )
        logger.info("Service degradation monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            await asyncio.gather(self._monitoring_task, return_exceptions=True)
    
    async def _monitor_loop(self, interval: int):
        """Monitor service health and adjust degradation level"""
        while True:
            try:
                await self._check_and_adjust_level()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in degradation monitoring: {exc}")
                await asyncio.sleep(interval)
    
    async def _check_and_adjust_level(self):
        """Check service health and adjust degradation level"""
        # Run health checks
        health_results = {}
        for service, check in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    health_results[service] = await check()
                else:
                    health_results[service] = check()
            except Exception as exc:
                logger.error(f"Health check failed for {service}: {exc}")
                health_results[service] = False
        
        # Calculate health score
        healthy_services = sum(1 for healthy in health_results.values() if healthy)
        total_services = len(health_results)
        health_score = healthy_services / total_services if total_services > 0 else 1.0
        
        # Determine appropriate degradation level
        new_level = self._calculate_degradation_level(health_score, health_results)
        
        if new_level != self.current_level:
            await self.set_degradation_level(new_level)
            logger.warning(
                f"Degradation level changed from {self.current_level.value} "
                f"to {new_level.value} (health score: {health_score:.2f})"
            )
    
    def _calculate_degradation_level(
        self,
        health_score: float,
        health_results: Dict[str, bool]
    ) -> DegradationLevel:
        """Calculate appropriate degradation level based on health"""
        # Check for critical services
        critical_services = ['database', 'redis', 'authentication']
        critical_healthy = all(
            health_results.get(service, True) 
            for service in critical_services
        )
        
        if not critical_healthy:
            return DegradationLevel.MAINTENANCE
        
        if health_score >= 0.9:
            return DegradationLevel.NORMAL
        elif health_score >= 0.7:
            return DegradationLevel.DEGRADED
        elif health_score >= 0.5:
            return DegradationLevel.ESSENTIAL
        else:
            return DegradationLevel.MAINTENANCE
    
    async def set_degradation_level(self, level: DegradationLevel):
        """Manually set degradation level"""
        self.current_level = level
        
        # Store in Redis for distributed systems
        await redis_client.set(
            "degradation:level",
            level.value,
            ex=3600  # 1 hour expiry
        )
        
        # Clear caches if entering maintenance mode
        if level == DegradationLevel.MAINTENANCE:
            self._cached_responses.clear()
        
        # Notify about level change
        await self._notify_level_change(level)
    
    async def get_degradation_level(self) -> DegradationLevel:
        """Get current degradation level"""
        # Check Redis for distributed level
        level_str = await redis_client.get("degradation:level")
        if level_str:
            try:
                return DegradationLevel(level_str)
            except ValueError:
                pass
        
        return self.current_level
    
    async def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled at current degradation level"""
        feature = self.feature_flags.get(feature_name)
        if not feature:
            return True  # Unknown features are enabled by default
        
        current_level = await self.get_degradation_level()
        return await feature.is_enabled(current_level)
    
    async def execute_with_degradation(
        self,
        operation: str,
        func: Callable[..., Any],
        *args,
        cache_key: Optional[str] = None,
        cache_ttl: int = 300,
        **kwargs
    ) -> Any:
        """
        Execute operation with graceful degradation
        """
        current_level = await self.get_degradation_level()
        
        # Check if operation is allowed at current level
        if not await self.is_feature_enabled(operation):
            # Use fallback if available
            fallback = self._fallback_handlers.get(operation)
            if fallback:
                logger.info(f"Using fallback for {operation} due to degradation")
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                else:
                    return fallback(*args, **kwargs)
            
            # Return cached response if available
            if cache_key and cache_key in self._cached_responses:
                logger.info(f"Returning cached response for {operation}")
                return self._cached_responses[cache_key]
            
            raise Exception(f"Operation {operation} not available at degradation level {current_level.value}")
        
        try:
            # Execute the operation
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Cache successful response
            if cache_key:
                self._cached_responses[cache_key] = result
                # Also store in Redis for distributed caching
                await redis_client.setex(
                    f"degradation:cache:{cache_key}",
                    cache_ttl,
                    json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                )
            
            return result
            
        except Exception as exc:
            # Try fallback on error
            fallback = self._fallback_handlers.get(operation)
            if fallback:
                logger.warning(f"Primary operation {operation} failed, using fallback: {exc}")
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                else:
                    return fallback(*args, **kwargs)
            
            # Return cached response as last resort
            if cache_key:
                # Check local cache
                if cache_key in self._cached_responses:
                    logger.warning(f"Returning stale cached response for {operation}")
                    return self._cached_responses[cache_key]
                
                # Check Redis cache
                cached = await redis_client.get(f"degradation:cache:{cache_key}")
                if cached:
                    logger.warning(f"Returning stale Redis cached response for {operation}")
                    try:
                        return json.loads(cached)
                    except:
                        return cached
            
            raise
    
    async def _notify_level_change(self, new_level: DegradationLevel):
        """Notify about degradation level change"""
        notification = {
            'event': 'degradation_level_changed',
            'new_level': new_level.value,
            'timestamp': datetime.utcnow().isoformat(),
            'affected_features': [
                name for name, feature in self.feature_flags.items()
                if new_level not in feature.degradation_levels
            ]
        }
        
        # Store notification
        await redis_client.lpush(
            "degradation:notifications",
            json.dumps(notification)
        )
        await redis_client.ltrim("degradation:notifications", 0, 99)  # Keep last 100


# Global degradation manager
degradation_manager = ServiceDegradation()


# Decorator for degradable operations
def degradable(
    operation: str,
    cache_key: Optional[Union[str, Callable]] = None,
    cache_ttl: int = 300,
    fallback: Optional[Callable] = None,
    available_in: Optional[List[DegradationLevel]] = None
):
    """
    Decorator to make operations degradable
    
    Args:
        operation: Operation name
        cache_key: Cache key or function to generate cache key
        cache_ttl: Cache TTL in seconds
        fallback: Fallback function
        available_in: Degradation levels where operation is available
    
    Usage:
        @degradable(
            "expensive_analytics",
            cache_key=lambda user_id: f"analytics:{user_id}",
            fallback=get_cached_analytics,
            available_in=[DegradationLevel.NORMAL, DegradationLevel.DEGRADED]
        )
        async def get_user_analytics(user_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Register feature
        degradation_manager.register_feature(
            operation,
            default_enabled=True,
            available_in=available_in or [DegradationLevel.NORMAL]
        )
        
        # Register fallback if provided
        if fallback:
            degradation_manager.register_fallback(operation, fallback)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if callable(cache_key):
                actual_cache_key = cache_key(*args, **kwargs)
            else:
                actual_cache_key = cache_key
            
            return await degradation_manager.execute_with_degradation(
                operation,
                func,
                *args,
                cache_key=actual_cache_key,
                cache_ttl=cache_ttl,
                **kwargs
            )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Predefined feature sets for different degradation levels
class DegradationProfiles:
    """Predefined degradation profiles"""
    
    @staticmethod
    def setup_default_profile():
        """Setup default degradation profile"""
        # Essential features (available in all levels except maintenance)
        essential_features = [
            'authentication',
            'view_dashboard',
            'view_balance',
            'emergency_contact'
        ]
        
        for feature in essential_features:
            degradation_manager.register_feature(
                feature,
                default_enabled=True,
                available_in=[
                    DegradationLevel.NORMAL,
                    DegradationLevel.DEGRADED,
                    DegradationLevel.ESSENTIAL
                ]
            )
        
        # Normal features (available in normal and degraded)
        normal_features = [
            'create_content',
            'send_message',
            'process_payment',
            'generate_report',
            'sync_data'
        ]
        
        for feature in normal_features:
            degradation_manager.register_feature(
                feature,
                default_enabled=True,
                available_in=[
                    DegradationLevel.NORMAL,
                    DegradationLevel.DEGRADED
                ]
            )
        
        # Premium features (only in normal mode)
        premium_features = [
            'advanced_analytics',
            'bulk_operations',
            'ml_predictions',
            'real_time_sync',
            'webhook_processing'
        ]
        
        for feature in premium_features:
            degradation_manager.register_feature(
                feature,
                default_enabled=True,
                available_in=[DegradationLevel.NORMAL]
            )


# Example fallback handlers
async def static_data_fallback(*args, **kwargs):
    """Return static data when service is degraded"""
    return {
        'status': 'degraded',
        'message': 'Service is currently operating in degraded mode',
        'data': None
    }


async def cached_response_fallback(cache_key: str):
    """Return cached response as fallback"""
    cached = await redis_client.get(f"fallback:cache:{cache_key}")
    if cached:
        return json.loads(cached)
    return None


# Health check examples
async def database_health_check() -> bool:
    """Check database health"""
    try:
        from core.database import get_db_context
        async with get_db_context() as db:
            await db.execute("SELECT 1")
        return True
    except:
        return False


async def redis_health_check() -> bool:
    """Check Redis health"""
    try:
        await redis_client.ping()
        return True
    except:
        return False


async def external_api_health_check() -> bool:
    """Check external API health"""
    from core.resilience import CircuitBreakerRegistry
    
    # Check circuit breakers
    breakers = CircuitBreakerRegistry.get_all()
    if not breakers:
        return True
    
    # If more than 50% of circuit breakers are open, consider unhealthy
    open_count = sum(1 for b in breakers.values() if b.state.value == 'open')
    return open_count / len(breakers) < 0.5


# Setup default health checks
def setup_default_health_checks():
    """Setup default health checks"""
    degradation_manager.register_health_check('database', database_health_check)
    degradation_manager.register_health_check('redis', redis_health_check)
    degradation_manager.register_health_check('external_apis', external_api_health_check)