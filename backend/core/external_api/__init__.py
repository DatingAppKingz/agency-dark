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
from .logging import APILogger, log_api_call
from .config import APIConfig, APICredentials, APIConfigManager

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
    'log_api_call',
    'APIConfig',
    'APICredentials',
    'APIConfigManager'
]