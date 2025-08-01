"""
Enhanced logging configuration with structured output and debugging features.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback
from contextvars import ContextVar

from core.config import settings

# Context variable for request tracking
request_context: ContextVar[Dict[str, Any]] = ContextVar('request_context', default={})


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request context if available
        context = request_context.get()
        if context:
            log_data["request"] = {
                "id": context.get("request_id"),
                "method": context.get("method"),
                "path": context.get("path"),
                "user_id": context.get("user_id"),
                "agency_id": context.get("agency_id"),
            }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data["extra"] = record.extra
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add custom fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'exc_info', 
                          'exc_text', 'stack_info', 'pathname', 'processName', 
                          'process', 'threadName', 'thread', 'getMessage']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Format message
        message = super().format(record)
        
        # Add context if available
        context = request_context.get()
        if context and context.get("request_id"):
            message = f"[{context['request_id']}] {message}"
        
        # Add exception details in debug mode
        if record.exc_info and settings.DEBUG:
            exc_text = '\n'.join(traceback.format_exception(*record.exc_info))
            message += f"\n{self.COLORS.get('ERROR', '')}{exc_text}{self.RESET}"
        
        return message


class AgencyDarkLogger:
    """Custom logger with enhanced debugging features."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure logger based on environment."""
        # Set log level
        level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if settings.DEBUG:
            # Use colored formatter for development
            formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # Use structured formatter for production
            formatter = StructuredFormatter()
        
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for errors
        if settings.LOG_FILE:
            log_dir = Path(settings.LOG_FILE).parent
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(settings.LOG_FILE)
            file_handler.setLevel(logging.ERROR)
            file_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(file_handler)
    
    def _add_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Add request context to log kwargs."""
        context = request_context.get()
        if context:
            kwargs.setdefault('extra', {}).update(context)
        return kwargs
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **self._add_context(kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **self._add_context(kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **self._add_context(kwargs))
    
    def error(self, message: str, exc_info: bool = True, **kwargs):
        """Log error message with context and exception info."""
        self.logger.error(message, exc_info=exc_info, **self._add_context(kwargs))
    
    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """Log critical message with context."""
        self.logger.critical(message, exc_info=exc_info, **self._add_context(kwargs))
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration_ms: float, **kwargs):
        """Log HTTP request with standardized format."""
        message = f"{method} {path} - {status_code} ({duration_ms:.2f}ms)"
        
        extra_data = {
            "http": {
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms
            }
        }
        extra_data.update(kwargs)
        
        if status_code >= 500:
            self.error(message, exc_info=False, extra=extra_data)
        elif status_code >= 400:
            self.warning(message, extra=extra_data)
        else:
            self.info(message, extra=extra_data)
    
    def log_database_query(self, query: str, duration_ms: float, 
                          rows_affected: Optional[int] = None, **kwargs):
        """Log database query with performance metrics."""
        # Truncate long queries in message
        query_preview = query[:100] + "..." if len(query) > 100 else query
        message = f"DB Query ({duration_ms:.2f}ms): {query_preview}"
        
        extra_data = {
            "database": {
                "query": query,
                "duration_ms": duration_ms,
                "rows_affected": rows_affected
            }
        }
        extra_data.update(kwargs)
        
        if duration_ms > 1000:  # Slow query threshold
            self.warning(f"Slow query detected: {message}", extra=extra_data)
        else:
            self.debug(message, extra=extra_data)
    
    def log_external_api_call(self, service: str, endpoint: str, 
                             status_code: Optional[int] = None, 
                             duration_ms: Optional[float] = None, 
                             error: Optional[str] = None, **kwargs):
        """Log external API calls with details."""
        message = f"External API: {service} {endpoint}"
        
        extra_data = {
            "external_api": {
                "service": service,
                "endpoint": endpoint,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error": error
            }
        }
        extra_data.update(kwargs)
        
        if error:
            self.error(f"{message} - Failed: {error}", exc_info=False, extra=extra_data)
        elif status_code and status_code >= 400:
            self.warning(f"{message} - {status_code}", extra=extra_data)
        else:
            self.info(f"{message} - {status_code or 'OK'}", extra=extra_data)
    
    def log_business_event(self, event: str, entity_type: str, 
                          entity_id: Any, **kwargs):
        """Log business domain events."""
        message = f"Business Event: {event} - {entity_type}:{entity_id}"
        
        extra_data = {
            "business_event": {
                "event": event,
                "entity_type": entity_type,
                "entity_id": str(entity_id)
            }
        }
        extra_data.update(kwargs)
        
        self.info(message, extra=extra_data)


# Logger factory
_loggers: Dict[str, AgencyDarkLogger] = {}


def get_logger(name: str) -> AgencyDarkLogger:
    """Get or create a logger instance."""
    if name not in _loggers:
        _loggers[name] = AgencyDarkLogger(name)
    return _loggers[name]


# Convenience function to set request context
def set_request_context(**kwargs):
    """Set request context for logging."""
    context = request_context.get()
    context.update(kwargs)
    request_context.set(context)


def clear_request_context():
    """Clear request context."""
    request_context.set({})


# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

# Add handler to root logger to catch third-party logs
if settings.DEBUG:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(handler)