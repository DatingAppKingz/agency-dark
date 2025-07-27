"""
API request/response logging
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union
import asyncio
from functools import wraps

from core.config.logging_config import get_logger


class APILogger:
    """Logger for API requests and responses"""
    
    def __init__(self, api_name: str, log_level: str = "INFO"):
        self.api_name = api_name
        self.logger = get_logger(f"api.{api_name}")
        self.log_level = log_level
        
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive headers"""
        sensitive_headers = {
            'authorization', 'api-key', 'x-api-key', 'cookie', 
            'x-auth-token', 'x-csrf-token', 'x-session-id'
        }
        
        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in sensitive_headers:
                # Mask sensitive values
                if len(value) > 8:
                    sanitized[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    sanitized[key] = "***"
            else:
                sanitized[key] = value
                
        return sanitized
        
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data fields"""
        if not isinstance(data, dict):
            return data
            
        sensitive_fields = {
            'password', 'token', 'secret', 'api_key', 'private_key',
            'credit_card', 'ssn', 'bank_account'
        }
        
        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                if isinstance(value, str) and len(value) > 8:
                    sanitized[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            else:
                sanitized[key] = value
                
        return sanitized
        
    def log_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """Log outgoing API request"""
        log_data = {
            'api': self.api_name,
            'type': 'request',
            'method': method,
            'url': url,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if params:
            log_data['params'] = params
            
        if data:
            log_data['data'] = self._sanitize_data(data)
            
        if headers:
            log_data['headers'] = self._sanitize_headers(headers)
            
        self.logger.info(f"API Request: {method} {url}", **log_data)
        
    def log_response(
        self,
        method: str,
        url: str,
        status_code: int,
        response_data: Optional[Union[str, Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        duration_ms: Optional[float] = None
    ):
        """Log API response"""
        log_data = {
            'api': self.api_name,
            'type': 'response',
            'method': method,
            'url': url,
            'status_code': status_code,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if duration_ms is not None:
            log_data['duration_ms'] = round(duration_ms, 2)
            
        if headers:
            log_data['headers'] = self._sanitize_headers(headers)
            
        # Parse response data if it's a string
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                # Keep as string if not JSON
                pass
                
        if response_data:
            log_data['data'] = self._sanitize_data(response_data)
            
        # Choose log level based on status code
        if status_code < 400:
            self.logger.info(f"API Response: {method} {url} - {status_code}", **log_data)
        elif status_code < 500:
            self.logger.warning(f"API Client Error: {method} {url} - {status_code}", **log_data)
        else:
            self.logger.error(f"API Server Error: {method} {url} - {status_code}", **log_data)
            
    def log_retry(self, attempt: int, delay: float, reason: str):
        """Log retry attempt"""
        log_data = {
            'api': self.api_name,
            'type': 'retry',
            'attempt': attempt,
            'delay_seconds': round(delay, 2),
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.warning(f"API Retry: Attempt {attempt}, waiting {delay:.2f}s", **log_data)
        
    def log_error(self, method: str, url: str, error: Exception):
        """Log API error"""
        log_data = {
            'api': self.api_name,
            'type': 'error',
            'method': method,
            'url': url,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.error(
            f"API Error: {method} {url} - {type(error).__name__}: {str(error)}",
            exc_info=True,
            **log_data
        )
        
    def log_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Log API metric"""
        log_data = {
            'api': self.api_name,
            'type': 'metric',
            'metric_name': metric_name,
            'value': value,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if tags:
            log_data['tags'] = tags
            
        self.logger.info(f"API Metric: {metric_name} = {value}", **log_data)


def log_api_call(logger: APILogger):
    """Decorator to log API method calls"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = asyncio.get_event_loop().time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                
                logger.log_metric(
                    f"{func.__name__}_duration",
                    duration_ms,
                    tags={'status': 'success'}
                )
                
                return result
                
            except Exception as e:
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                
                logger.log_metric(
                    f"{func.__name__}_duration",
                    duration_ms,
                    tags={'status': 'error', 'error_type': type(e).__name__}
                )
                
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_metric(
                    f"{func.__name__}_duration",
                    duration_ms,
                    tags={'status': 'success'}
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_metric(
                    f"{func.__name__}_duration",
                    duration_ms,
                    tags={'status': 'error', 'error_type': type(e).__name__}
                )
                
                raise
                
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator