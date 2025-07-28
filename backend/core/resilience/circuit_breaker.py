"""
Circuit breaker implementation for external API calls
"""
import asyncio
import time
from typing import Callable, Any, Optional, Dict, List
from enum import Enum
from datetime import datetime, timedelta
import functools
from collections import deque

from core.logging import logger
from core.redis import redis_client


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    
    Prevents cascading failures by failing fast when a service is down
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2,
        half_open_timeout: int = 30
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name (for monitoring)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
            success_threshold: Successes needed to close circuit
            half_open_timeout: Max time in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.half_open_timeout = half_open_timeout
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_start = None
        
        # Metrics
        self._call_history = deque(maxlen=100)
        self._state_changes = deque(maxlen=50)
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        self._update_state()
        return self._state
    
    def _update_state(self):
        """Update circuit state based on current conditions"""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time and \
               time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition_to_half_open()
        
        elif self._state == CircuitState.HALF_OPEN:
            # Check if half-open timeout exceeded
            if self._half_open_start and \
               time.time() - self._half_open_start >= self.half_open_timeout:
                self._transition_to_open("Half-open timeout exceeded")
    
    def _transition_to_open(self, reason: str = "Failure threshold exceeded"):
        """Transition to OPEN state"""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        self._record_state_change(CircuitState.OPEN, reason)
        logger.warning(f"Circuit breaker '{self.name}' opened: {reason}")
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_start = None
        self._record_state_change(CircuitState.CLOSED, "Service recovered")
        logger.info(f"Circuit breaker '{self.name}' closed")
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._failure_count = 0
        self._half_open_start = time.time()
        self._record_state_change(CircuitState.HALF_OPEN, "Testing recovery")
        logger.info(f"Circuit breaker '{self.name}' half-open")
    
    def _record_state_change(self, new_state: CircuitState, reason: str):
        """Record state change for monitoring"""
        self._state_changes.append({
            'timestamp': datetime.utcnow(),
            'from_state': self._state.value if hasattr(self, '_state') else None,
            'to_state': new_state.value,
            'reason': reason
        })
    
    def _record_call(self, success: bool, duration: float, error: Optional[str] = None):
        """Record call metrics"""
        self._call_history.append({
            'timestamp': datetime.utcnow(),
            'success': success,
            'duration': duration,
            'error': error,
            'state': self._state.value
        })
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        # Update state before checking
        self._update_state()
        
        # Check if circuit is open
        if self._state == CircuitState.OPEN:
            self._record_call(False, 0, "Circuit breaker open")
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
            )
        
        # Attempt the call
        start_time = time.time()
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            duration = time.time() - start_time
            self._record_call(True, duration)
            self._on_success()
            
            return result
            
        except self.expected_exception as exc:
            # Record failure
            duration = time.time() - start_time
            self._record_call(False, duration, str(exc))
            self._on_failure()
            
            raise
    
    def _on_success(self):
        """Handle successful call"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to_closed()
        
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        if self._state == CircuitState.HALF_OPEN:
            # Single failure in half-open state opens circuit
            self._transition_to_open("Failure in half-open state")
        
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._transition_to_open()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        total_calls = len(self._call_history)
        successful_calls = sum(1 for call in self._call_history if call['success'])
        
        return {
            'name': self.name,
            'state': self._state.value,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'total_calls': total_calls,
            'success_rate': successful_calls / total_calls if total_calls > 0 else 0,
            'recent_failures': [
                call for call in self._call_history 
                if not call['success']
            ][-5:],  # Last 5 failures
            'state_changes': list(self._state_changes)[-5:]  # Last 5 state changes
        }
    
    async def reset(self):
        """Manually reset circuit breaker"""
        self._transition_to_closed()
        logger.info(f"Circuit breaker '{self.name}' manually reset")


# Circuit breaker decorator
def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    success_threshold: int = 2
):
    """
    Decorator to add circuit breaker protection to functions
    
    Usage:
        @circuit_breaker(name="external_api", failure_threshold=3)
        async def call_external_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Use function name if no name provided
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        
        # Create circuit breaker instance
        breaker = CircuitBreaker(
            name=breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold
        )
        
        # Store breaker in registry
        CircuitBreakerRegistry.register(breaker)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Run async call in sync context
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                breaker.call(func, *args, **kwargs)
            )
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreakerRegistry:
    """Registry for all circuit breakers"""
    _breakers: Dict[str, CircuitBreaker] = {}
    
    @classmethod
    def register(cls, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        cls._breakers[breaker.name] = breaker
    
    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return cls._breakers.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, CircuitBreaker]:
        """Get all registered circuit breakers"""
        return cls._breakers.copy()
    
    @classmethod
    def get_metrics(cls) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        return {
            name: breaker.get_metrics()
            for name, breaker in cls._breakers.items()
        }
    
    @classmethod
    async def reset_all(cls):
        """Reset all circuit breakers"""
        for breaker in cls._breakers.values():
            await breaker.reset()


# Distributed circuit breaker using Redis
class DistributedCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker that shares state across multiple instances using Redis
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis_prefix = f"circuit_breaker:{self.name}"
    
    async def _get_state(self) -> CircuitState:
        """Get state from Redis"""
        state_key = f"{self._redis_prefix}:state"
        state_value = await redis_client.get(state_key)
        
        if state_value:
            return CircuitState(state_value)
        return CircuitState.CLOSED
    
    async def _set_state(self, state: CircuitState, ttl: Optional[int] = None):
        """Set state in Redis"""
        state_key = f"{self._redis_prefix}:state"
        
        if ttl:
            await redis_client.setex(state_key, ttl, state.value)
        else:
            await redis_client.set(state_key, state.value)
    
    async def _increment_counter(self, counter: str) -> int:
        """Increment counter in Redis"""
        counter_key = f"{self._redis_prefix}:{counter}"
        value = await redis_client.incr(counter_key)
        await redis_client.expire(counter_key, 300)  # 5 minute expiry
        return value
    
    async def _reset_counter(self, counter: str):
        """Reset counter in Redis"""
        counter_key = f"{self._redis_prefix}:{counter}"
        await redis_client.delete(counter_key)
    
    async def _get_counter(self, counter: str) -> int:
        """Get counter value from Redis"""
        counter_key = f"{self._redis_prefix}:{counter}"
        value = await redis_client.get(counter_key)
        return int(value) if value else 0
    
    @property
    async def state(self) -> CircuitState:
        """Get current circuit state from Redis"""
        return await self._get_state()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with distributed circuit breaker protection"""
        current_state = await self._get_state()
        
        # Check if circuit is open
        if current_state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure_key = f"{self._redis_prefix}:last_failure"
            last_failure = await redis_client.get(last_failure_key)
            
            if last_failure:
                last_failure_time = float(last_failure)
                if time.time() - last_failure_time >= self.recovery_timeout:
                    await self._set_state(CircuitState.HALF_OPEN)
                    current_state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
                    )
        
        # Attempt the call
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Handle success
            if current_state == CircuitState.HALF_OPEN:
                success_count = await self._increment_counter("success_count")
                if success_count >= self.success_threshold:
                    await self._set_state(CircuitState.CLOSED)
                    await self._reset_counter("failure_count")
                    await self._reset_counter("success_count")
                    logger.info(f"Distributed circuit breaker '{self.name}' closed")
            
            elif current_state == CircuitState.CLOSED:
                await self._reset_counter("failure_count")
            
            return result
            
        except self.expected_exception as exc:
            # Handle failure
            if current_state == CircuitState.HALF_OPEN:
                await self._set_state(CircuitState.OPEN, self.recovery_timeout)
                await redis_client.set(
                    f"{self._redis_prefix}:last_failure",
                    str(time.time())
                )
                logger.warning(f"Distributed circuit breaker '{self.name}' opened")
            
            elif current_state == CircuitState.CLOSED:
                failure_count = await self._increment_counter("failure_count")
                if failure_count >= self.failure_threshold:
                    await self._set_state(CircuitState.OPEN, self.recovery_timeout)
                    await redis_client.set(
                        f"{self._redis_prefix}:last_failure",
                        str(time.time())
                    )
                    logger.warning(f"Distributed circuit breaker '{self.name}' opened")
            
            raise