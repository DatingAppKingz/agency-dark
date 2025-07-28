"""
Retry policies with various backoff strategies
"""
import asyncio
import random
import functools
from typing import Callable, Any, Optional, Union, Type, Tuple, List
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod

from core.logging import logger


class RetryDecision(Enum):
    """Decision on whether to retry"""
    RETRY = "retry"
    FAIL = "fail"
    IGNORE = "ignore"


class BackoffStrategy(ABC):
    """Abstract base class for backoff strategies"""
    
    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay in seconds for the given attempt number"""
        pass


class ExponentialBackoff(BackoffStrategy):
    """
    Exponential backoff with jitter
    
    delay = base * (multiplier ^ attempt) + random_jitter
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        multiplier: float = 2.0,
        max_delay: float = 300.0,  # 5 minutes
        jitter: bool = True,
        jitter_range: Tuple[float, float] = (0.5, 1.5)
    ):
        self.base_delay = base_delay
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.jitter = jitter
        self.jitter_range = jitter_range
    
    def get_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = self.base_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            jitter_factor = random.uniform(*self.jitter_range)
            delay *= jitter_factor
        
        return delay


class LinearBackoff(BackoffStrategy):
    """
    Linear backoff with optional jitter
    
    delay = base + (increment * attempt)
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        increment: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        self.base_delay = base_delay
        self.increment = increment
        self.max_delay = max_delay
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate linear backoff delay"""
        delay = self.base_delay + (self.increment * (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            jitter = random.uniform(-0.1, 0.1) * delay
            delay += jitter
        
        return max(0, delay)


class FibonacciBackoff(BackoffStrategy):
    """
    Fibonacci sequence backoff
    
    delay = fibonacci(attempt) * base_delay
    """
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._fib_cache = {1: 1, 2: 1}
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number with memoization"""
        if n in self._fib_cache:
            return self._fib_cache[n]
        
        self._fib_cache[n] = self._fibonacci(n - 1) + self._fibonacci(n - 2)
        return self._fib_cache[n]
    
    def get_delay(self, attempt: int) -> float:
        """Calculate fibonacci backoff delay"""
        fib_value = self._fibonacci(min(attempt, 20))  # Cap at 20 to avoid huge delays
        delay = fib_value * self.base_delay
        return min(delay, self.max_delay)


class DecorrelatedJitterBackoff(BackoffStrategy):
    """
    AWS-style decorrelated jitter backoff
    
    More even distribution of retry times to avoid thundering herd
    """
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.previous_delay = 0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate decorrelated jitter delay"""
        if attempt == 1:
            self.previous_delay = self.base_delay
        else:
            temp = min(self.max_delay, self.base_delay * 3)
            self.previous_delay = random.uniform(self.base_delay, temp)
        
        return self.previous_delay


class RetryPolicy:
    """
    Configurable retry policy
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_strategy: Optional[BackoffStrategy] = None,
        retriable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        non_retriable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        retriable_status_codes: Optional[List[int]] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        timeout: Optional[float] = None,
        deadline: Optional[datetime] = None
    ):
        self.max_attempts = max_attempts
        self.backoff_strategy = backoff_strategy or ExponentialBackoff()
        self.retriable_exceptions = retriable_exceptions or (Exception,)
        self.non_retriable_exceptions = non_retriable_exceptions or ()
        self.retriable_status_codes = retriable_status_codes or [429, 500, 502, 503, 504]
        self.on_retry = on_retry
        self.timeout = timeout
        self.deadline = deadline
    
    def should_retry(self, exception: Exception, attempt: int) -> RetryDecision:
        """Determine if we should retry based on the exception and attempt"""
        # Check if we've exceeded max attempts
        if attempt >= self.max_attempts:
            return RetryDecision.FAIL
        
        # Check deadline if set
        if self.deadline and datetime.utcnow() >= self.deadline:
            logger.warning("Retry deadline exceeded")
            return RetryDecision.FAIL
        
        # Check non-retriable exceptions first
        if isinstance(exception, self.non_retriable_exceptions):
            return RetryDecision.FAIL
        
        # Check retriable exceptions
        if not isinstance(exception, self.retriable_exceptions):
            return RetryDecision.FAIL
        
        # Check status codes for HTTP exceptions
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            if exception.response.status_code not in self.retriable_status_codes:
                return RetryDecision.FAIL
        
        return RetryDecision.RETRY
    
    def get_delay(self, attempt: int) -> float:
        """Get delay for the given attempt"""
        return self.backoff_strategy.get_delay(attempt)
    
    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry policy"""
        attempt = 0
        last_exception = None
        start_time = datetime.utcnow()
        
        while True:
            attempt += 1
            
            try:
                # Apply timeout if specified
                if self.timeout:
                    if asyncio.iscoroutinefunction(func):
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=self.timeout
                        )
                    else:
                        # For sync functions, we'd need a different approach
                        result = func(*args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                
                # Success - return result
                if attempt > 1:
                    logger.info(
                        f"Operation succeeded after {attempt} attempts "
                        f"(total time: {(datetime.utcnow() - start_time).total_seconds():.2f}s)"
                    )
                
                return result
                
            except Exception as exc:
                last_exception = exc
                decision = self.should_retry(exc, attempt)
                
                if decision == RetryDecision.FAIL:
                    logger.error(
                        f"Operation failed after {attempt} attempts: {exc}"
                    )
                    raise
                
                elif decision == RetryDecision.IGNORE:
                    logger.warning(
                        f"Ignoring exception after {attempt} attempts: {exc}"
                    )
                    return None
                
                # RETRY decision
                delay = self.get_delay(attempt)
                
                logger.warning(
                    f"Attempt {attempt} failed: {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                # Call retry callback if provided
                if self.on_retry:
                    self.on_retry(exc, attempt)
                
                # Wait before retrying
                await asyncio.sleep(delay)
        
        # Should never reach here
        if last_exception:
            raise last_exception


# Retry decorator
def retry_with_backoff(
    max_attempts: int = 3,
    backoff: Optional[Union[BackoffStrategy, str]] = None,
    exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to add retry with backoff to functions
    
    Args:
        max_attempts: Maximum number of attempts
        backoff: Backoff strategy instance or string ('exponential', 'linear', 'fibonacci')
        exceptions: Tuple of exceptions to retry on
        on_retry: Callback function called on each retry
    
    Usage:
        @retry_with_backoff(max_attempts=5, backoff='exponential')
        async def flaky_api_call():
            ...
    """
    # Create backoff strategy
    if isinstance(backoff, str):
        backoff_strategies = {
            'exponential': ExponentialBackoff(),
            'linear': LinearBackoff(),
            'fibonacci': FibonacciBackoff(),
            'decorrelated': DecorrelatedJitterBackoff()
        }
        backoff_strategy = backoff_strategies.get(backoff, ExponentialBackoff())
    else:
        backoff_strategy = backoff or ExponentialBackoff()
    
    def decorator(func: Callable) -> Callable:
        policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff_strategy=backoff_strategy,
            retriable_exceptions=exceptions,
            on_retry=on_retry
        )
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await policy.execute_with_retry(func, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, create a simple retry loop
            attempt = 0
            last_exception = None
            
            while attempt < max_attempts:
                attempt += 1
                
                try:
                    return func(*args, **kwargs)
                except (exceptions or Exception) as exc:
                    last_exception = exc
                    
                    if attempt >= max_attempts:
                        raise
                    
                    delay = backoff_strategy.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed: {exc}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    if on_retry:
                        on_retry(exc, attempt)
                    
                    import time
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Specialized retry policies
class RetryPolicies:
    """Pre-configured retry policies for common scenarios"""
    
    @staticmethod
    def aggressive() -> RetryPolicy:
        """Aggressive retry for critical operations"""
        return RetryPolicy(
            max_attempts=10,
            backoff_strategy=ExponentialBackoff(
                base_delay=0.1,
                multiplier=2,
                max_delay=30
            )
        )
    
    @staticmethod
    def conservative() -> RetryPolicy:
        """Conservative retry to avoid overload"""
        return RetryPolicy(
            max_attempts=3,
            backoff_strategy=ExponentialBackoff(
                base_delay=5,
                multiplier=3,
                max_delay=300
            )
        )
    
    @staticmethod
    def rate_limit_aware() -> RetryPolicy:
        """Retry policy for rate-limited APIs"""
        def on_rate_limit(exc: Exception, attempt: int):
            # Extract retry-after header if available
            if hasattr(exc, 'response') and hasattr(exc.response, 'headers'):
                retry_after = exc.response.headers.get('Retry-After')
                if retry_after:
                    logger.info(f"Rate limited. Server says retry after: {retry_after}s")
        
        return RetryPolicy(
            max_attempts=5,
            backoff_strategy=DecorrelatedJitterBackoff(
                base_delay=60,  # Start with 1 minute for rate limits
                max_delay=600   # Max 10 minutes
            ),
            retriable_status_codes=[429],  # Only retry on rate limit
            on_retry=on_rate_limit
        )
    
    @staticmethod
    def network_aware() -> RetryPolicy:
        """Retry policy for network errors"""
        import aiohttp
        import requests
        
        return RetryPolicy(
            max_attempts=5,
            backoff_strategy=ExponentialBackoff(
                base_delay=1,
                multiplier=2,
                max_delay=60
            ),
            retriable_exceptions=(
                aiohttp.ClientError,
                requests.RequestException,
                ConnectionError,
                TimeoutError
            )
        )


# Circuit breaker integration
def retry_with_circuit_breaker(
    circuit_breaker_name: str,
    retry_policy: Optional[RetryPolicy] = None
):
    """
    Decorator that combines retry policy with circuit breaker
    """
    from .circuit_breaker import CircuitBreakerRegistry
    
    def decorator(func: Callable) -> Callable:
        policy = retry_policy or RetryPolicies.aggressive()
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get circuit breaker
            breaker = CircuitBreakerRegistry.get(circuit_breaker_name)
            if not breaker:
                # No circuit breaker, just use retry policy
                return await policy.execute_with_retry(func, *args, **kwargs)
            
            # Execute with both circuit breaker and retry
            async def wrapped_call():
                return await breaker.call(func, *args, **kwargs)
            
            return await policy.execute_with_retry(wrapped_call)
        
        return wrapper
    
    return decorator