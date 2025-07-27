"""
External API Integration Framework
"""
from .base import (
    BaseAPIClient,
    APIError,
    APIConnectionError,
    APITimeoutError,
    APIAuthenticationError,
    APIRateLimitError,
    APIValidationError
)
from .retry import RetryPolicy, ExponentialBackoff
from .logging import APILogger
from .config import APIConfig, APICredentials

__all__ = [
    'BaseAPIClient',
    'APIError',
    'APIConnectionError',
    'APITimeoutError',
    'APIAuthenticationError',
    'APIRateLimitError',
    'APIValidationError',
    'RetryPolicy',
    'ExponentialBackoff',
    'APILogger',
    'APIConfig',
    'APICredentials'
]