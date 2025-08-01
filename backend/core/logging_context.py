"""Structured logging context utilities."""

import contextvars
from typing import Dict, Any, Optional, Union
import uuid
from datetime import datetime
import json
import logging
from functools import wraps

# Context variables for request tracking
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)
agency_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("agency_id", default=None)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)


class StructuredLogger:
    """Logger with structured context support."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Add context variables to extra data."""
        context = {
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "agency_id": agency_id_var.get(),
            "correlation_id": correlation_id_var.get(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Remove None values
        context = {k: v for k, v in context.items() if v is not None}
        
        # Merge with provided extra
        if extra:
            context.update(extra)
        
        return {"extra": context}
    
    def debug(self, msg: str, **kwargs):
        """Log debug message with context."""
        extra = kwargs.pop("extra", {})
        self.logger.debug(msg, **self._add_context(extra), **kwargs)
    
    def info(self, msg: str, **kwargs):
        """Log info message with context."""
        extra = kwargs.pop("extra", {})
        self.logger.info(msg, **self._add_context(extra), **kwargs)
    
    def warning(self, msg: str, **kwargs):
        """Log warning message with context."""
        extra = kwargs.pop("extra", {})
        self.logger.warning(msg, **self._add_context(extra), **kwargs)
    
    def error(self, msg: str, **kwargs):
        """Log error message with context."""
        extra = kwargs.pop("extra", {})
        exc_info = kwargs.pop("exc_info", True)
        self.logger.error(msg, exc_info=exc_info, **self._add_context(extra), **kwargs)
    
    def critical(self, msg: str, **kwargs):
        """Log critical message with context."""
        extra = kwargs.pop("extra", {})
        self.logger.critical(msg, **self._add_context(extra), **kwargs)
    
    def log_event(self, event: str, data: Optional[Dict[str, Any]] = None, level: int = logging.INFO):
        """Log a structured event."""
        extra = {
            "event": event,
            "event_data": data or {}
        }
        self.logger.log(level, f"Event: {event}", **self._add_context(extra))
    
    def log_api_call(self, method: str, endpoint: str, status_code: int, duration_ms: float, **kwargs):
        """Log API call details."""
        extra = {
            "api_method": method,
            "api_endpoint": endpoint,
            "api_status_code": status_code,
            "api_duration_ms": duration_ms,
            **kwargs
        }
        
        msg = f"API {method} {endpoint} -> {status_code} ({duration_ms:.2f}ms)"
        if status_code >= 400:
            self.logger.warning(msg, **self._add_context(extra))
        else:
            self.logger.info(msg, **self._add_context(extra))
    
    def log_database_query(self, query: str, duration_ms: float, **kwargs):
        """Log database query details."""
        extra = {
            "db_query": query[:200],  # Truncate long queries
            "db_duration_ms": duration_ms,
            **kwargs
        }
        
        msg = f"DB Query ({duration_ms:.2f}ms)"
        if duration_ms > 1000:  # Slow query threshold
            self.logger.warning(f"Slow {msg}", **self._add_context(extra))
        else:
            self.logger.debug(msg, **self._add_context(extra))


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    logger = logging.getLogger(name)
    return StructuredLogger(logger)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """Set context variables for the current request."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if agency_id:
        agency_id_var.set(agency_id)
    if correlation_id:
        correlation_id_var.set(correlation_id)


def clear_request_context():
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    agency_id_var.set(None)
    correlation_id_var.set(None)


def with_logging_context(**context_kwargs):
    """Decorator to add logging context to a function."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Set context
            for key, value in context_kwargs.items():
                if key == "request_id":
                    request_id_var.set(value)
                elif key == "user_id":
                    user_id_var.set(value)
                elif key == "agency_id":
                    agency_id_var.set(value)
                elif key == "correlation_id":
                    correlation_id_var.set(value)
            
            try:
                return await func(*args, **kwargs)
            finally:
                # Clear context
                clear_request_context()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Set context
            for key, value in context_kwargs.items():
                if key == "request_id":
                    request_id_var.set(value)
                elif key == "user_id":
                    user_id_var.set(value)
                elif key == "agency_id":
                    agency_id_var.set(value)
                elif key == "correlation_id":
                    correlation_id_var.set(value)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Clear context
                clear_request_context()
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


import asyncio


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_obj)