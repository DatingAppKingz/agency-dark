"""
Retry policies for API requests
"""
from abc import ABC, abstractmethod
from typing import Optional
import random


class RetryPolicy(ABC):
    """Abstract base class for retry policies"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        
    @abstractmethod
    def get_retry_delay(self, attempt: int) -> float:
        """Get delay before next retry attempt"""
        pass


class ExponentialBackoff(RetryPolicy):
    """Exponential backoff retry policy"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        super().__init__(max_retries)
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff"""
        # Calculate exponential delay
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
            
        return delay


class LinearBackoff(RetryPolicy):
    """Linear backoff retry policy"""
    
    def __init__(
        self,
        max_retries: int = 3,
        delay_increment: float = 5.0,
        max_delay: float = 30.0
    ):
        super().__init__(max_retries)
        self.delay_increment = delay_increment
        self.max_delay = max_delay
        
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate delay with linear backoff"""
        return min(
            self.delay_increment * (attempt + 1),
            self.max_delay
        )


class FixedDelay(RetryPolicy):
    """Fixed delay retry policy"""
    
    def __init__(self, max_retries: int = 3, delay: float = 5.0):
        super().__init__(max_retries)
        self.delay = delay
        
    def get_retry_delay(self, attempt: int) -> float:
        """Return fixed delay"""
        return self.delay