"""
Comprehensive Error Handling System

Provides production-ready error handling including:
- Custom exception hierarchy
- Error tracking and reporting
- User-friendly error messages
- Detailed error logging
- Error recovery strategies
- Circuit breaker pattern
- Error aggregation and analytics
"""
import traceback
import sys
from typing import Dict, Any, Optional, List, Callable, Union, Type
from datetime import datetime, timedelta
from functools import wraps
import asyncio
from enum import Enum
import uuid

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import sentry_sdk

from core.logger import get_logger
from core.redis import redis_client

logger = get_logger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


# Custom Exception Hierarchy

class AgencyDarkException(Exception):
    """Base exception for all custom exceptions."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.user_message = user_message or "An error occurred"
        self.error_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)


class ValidationException(AgencyDarkException):
    """Validation errors."""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            details={"field": field} if field else {},
            user_message="Invalid input provided",
            **kwargs
        )


class AuthenticationException(AgencyDarkException):
    """Authentication errors."""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUTHENTICATION,
            user_message="Authentication required",
            **kwargs
        )


class AuthorizationException(AgencyDarkException):
    """Authorization errors."""
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUTHORIZATION,
            user_message="You don't have permission to access this resource",
            **kwargs
        )


class ResourceNotFoundException(AgencyDarkException):
    """Resource not found errors."""
    def __init__(self, resource_type: str, resource_id: Any, **kwargs):
        super().__init__(
            message=f"{resource_type} with id {resource_id} not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.BUSINESS_LOGIC,
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
            user_message=f"{resource_type} not found",
            **kwargs
        )


class BusinessLogicException(AgencyDarkException):
    """Business logic errors."""
    def __init__(self, message: str, rule: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            status_code=422,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.BUSINESS_LOGIC,
            details={"rule": rule} if rule else {},
            **kwargs
        )


class ExternalServiceException(AgencyDarkException):
    """External service errors."""
    def __init__(self, service: str, message: str, **kwargs):
        super().__init__(
            message=f"External service error: {service} - {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            details={"service": service},
            user_message="Service temporarily unavailable",
            **kwargs
        )


class DatabaseException(AgencyDarkException):
    """Database errors."""
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            details={"operation": operation} if operation else {},
            user_message="A database error occurred",
            **kwargs
        )


class RateLimitException(AgencyDarkException):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int, **kwargs):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.SYSTEM,
            details={"retry_after": retry_after},
            user_message=f"Too many requests. Please try again in {retry_after} seconds",
            **kwargs
        )


class ErrorHandler:
    """Comprehensive error handling system."""
    
    def __init__(self):
        self.error_callbacks: Dict[str, List[Callable]] = {}
        self.circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        self.error_stats: Dict[str, int] = {}
        self.sentry_enabled = False
        
    def init_sentry(self, dsn: str, environment: str = "production"):
        """Initialize Sentry error tracking."""
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1,
            attach_stacktrace=True,
            send_default_pii=False
        )
        self.sentry_enabled = True
        logger.info("Sentry error tracking initialized")
    
    async def handle_error(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Main error handler for all exceptions."""
        # Convert to AgencyDarkException if needed
        if isinstance(exc, AgencyDarkException):
            error = exc
        elif isinstance(exc, HTTPException):
            error = self._convert_http_exception(exc)
        elif isinstance(exc, ValidationError):
            error = self._convert_validation_error(exc)
        elif isinstance(exc, SQLAlchemyError):
            error = self._convert_database_error(exc)
        else:
            error = self._convert_unknown_error(exc)
        
        # Log the error
        await self._log_error(error, request)
        
        # Track error statistics
        await self._track_error_stats(error)
        
        # Send to Sentry if enabled
        if self.sentry_enabled and error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._send_to_sentry(error, request)
        
        # Execute callbacks
        await self._execute_callbacks(error)
        
        # Build response
        response = self._build_error_response(error, request)
        
        return response
    
    def _convert_http_exception(self, exc: HTTPException) -> AgencyDarkException:
        """Convert HTTPException to AgencyDarkException."""
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.MEDIUM
        
        if exc.status_code == 401:
            category = ErrorCategory.AUTHENTICATION
        elif exc.status_code == 403:
            category = ErrorCategory.AUTHORIZATION
        elif exc.status_code == 404:
            category = ErrorCategory.BUSINESS_LOGIC
            severity = ErrorSeverity.LOW
        elif exc.status_code >= 500:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.HIGH
        
        return AgencyDarkException(
            message=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            status_code=exc.status_code,
            severity=severity,
            category=category,
            user_message=exc.detail
        )
    
    def _convert_validation_error(self, exc: ValidationError) -> ValidationException:
        """Convert Pydantic ValidationError."""
        errors = exc.errors()
        if errors:
            first_error = errors[0]
            field = ".".join(str(loc) for loc in first_error["loc"])
            message = first_error["msg"]
            
            return ValidationException(
                message=f"Validation error in {field}: {message}",
                field=field,
                details={"errors": errors}
            )
        
        return ValidationException("Validation error")
    
    def _convert_database_error(self, exc: SQLAlchemyError) -> DatabaseException:
        """Convert SQLAlchemy errors."""
        if isinstance(exc, IntegrityError):
            return DatabaseException(
                message="Database integrity constraint violated",
                operation="write",
                user_message="The operation violates data constraints"
            )
        elif isinstance(exc, OperationalError):
            return DatabaseException(
                message="Database operation failed",
                operation="query",
                user_message="Database temporarily unavailable"
            )
        
        return DatabaseException(str(exc))
    
    def _convert_unknown_error(self, exc: Exception) -> AgencyDarkException:
        """Convert unknown errors."""
        return AgencyDarkException(
            message=str(exc),
            error_code="INTERNAL_ERROR",
            status_code=500,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.UNKNOWN,
            user_message="An unexpected error occurred"
        )
    
    async def _log_error(self, error: AgencyDarkException, request: Request):
        """Log error with context."""
        log_data = {
            "error_id": error.error_id,
            "error_code": error.error_code,
            "message": error.message,
            "severity": error.severity,
            "category": error.category,
            "status_code": error.status_code,
            "request_id": getattr(request.state, "request_id", None),
            "user_id": getattr(request.state, "user_id", None),
            "path": str(request.url),
            "method": request.method,
            "details": error.details,
            "traceback": traceback.format_exc() if error.severity == ErrorSeverity.HIGH else None
        }
        
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {log_data}")
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"Error: {log_data}")
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Warning: {log_data}")
        else:
            logger.info(f"Info: {log_data}")
    
    async def _track_error_stats(self, error: AgencyDarkException):
        """Track error statistics."""
        # In-memory stats
        key = f"{error.category}:{error.error_code}"
        self.error_stats[key] = self.error_stats.get(key, 0) + 1
        
        # Redis stats for persistence
        stats_key = f"error_stats:{key}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        await redis_client.incr(stats_key)
        await redis_client.expire(stats_key, 86400 * 30)  # Keep 30 days
    
    def _send_to_sentry(self, error: AgencyDarkException, request: Request):
        """Send error to Sentry."""
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_id", error.error_id)
            scope.set_tag("error_code", error.error_code)
            scope.set_tag("category", error.category)
            scope.set_context("error_details", error.details)
            scope.set_user({
                "id": getattr(request.state, "user_id", None),
                "ip_address": request.client.host if request.client else None
            })
            
            sentry_sdk.capture_exception(error)
    
    async def _execute_callbacks(self, error: AgencyDarkException):
        """Execute registered error callbacks."""
        callbacks = self.error_callbacks.get(error.category, [])
        callbacks.extend(self.error_callbacks.get("*", []))
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
    
    def _build_error_response(
        self,
        error: AgencyDarkException,
        request: Request
    ) -> JSONResponse:
        """Build error response."""
        # Check if debug mode
        debug_mode = getattr(request.app.state, "debug", False)
        
        response_data = {
            "error": {
                "code": error.error_code,
                "message": error.user_message,
                "error_id": error.error_id,
                "timestamp": error.timestamp.isoformat()
            }
        }
        
        # Add details in debug mode
        if debug_mode:
            response_data["error"]["details"] = error.details
            response_data["error"]["debug_message"] = error.message
            if error.severity == ErrorSeverity.HIGH:
                response_data["error"]["traceback"] = traceback.format_exc()
        
        # Add retry information for rate limits
        if isinstance(error, RateLimitException):
            response_data["error"]["retry_after"] = error.details.get("retry_after")
        
        return JSONResponse(
            status_code=error.status_code,
            content=response_data,
            headers={"X-Error-ID": error.error_id}
        )
    
    def register_callback(
        self,
        category: Union[ErrorCategory, str],
        callback: Callable
    ):
        """Register error callback."""
        category_str = category.value if isinstance(category, ErrorCategory) else category
        if category_str not in self.error_callbacks:
            self.error_callbacks[category_str] = []
        self.error_callbacks[category_str].append(callback)
    
    def with_error_handling(
        self,
        fallback_value: Any = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        catch_exceptions: Optional[List[Type[Exception]]] = None
    ):
        """Decorator for error handling with retry logic."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        # Check if we should catch this exception
                        if catch_exceptions and not any(
                            isinstance(e, exc_type) for exc_type in catch_exceptions
                        ):
                            raise
                        
                        # Log retry attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for "
                            f"{func.__name__}: {str(e)}"
                        )
                        
                        # Wait before retry
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                
                # All retries failed
                logger.error(
                    f"All {max_retries} attempts failed for {func.__name__}: "
                    f"{str(last_exception)}"
                )
                
                if fallback_value is not None:
                    return fallback_value
                raise last_exception
            
            return wrapper
        return decorator
    
    def create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Optional[Type[Exception]] = None
    ) -> 'CircuitBreaker':
        """Create a circuit breaker for external services."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
        return self.circuit_breakers[name]
    
    async def get_error_analytics(
        self,
        days: int = 7,
        category: Optional[ErrorCategory] = None
    ) -> Dict[str, Any]:
        """Get error analytics."""
        analytics = {
            "total_errors": sum(self.error_stats.values()),
            "errors_by_category": {},
            "errors_by_code": {},
            "trend": []
        }
        
        # Group by category
        for key, count in self.error_stats.items():
            cat, code = key.split(":", 1)
            if category and cat != category.value:
                continue
            
            if cat not in analytics["errors_by_category"]:
                analytics["errors_by_category"][cat] = 0
            analytics["errors_by_category"][cat] += count
            
            analytics["errors_by_code"][code] = count
        
        # Get trend from Redis
        for day_offset in range(days):
            date = (datetime.utcnow() - timedelta(days=day_offset)).strftime('%Y-%m-%d')
            day_total = 0
            
            # Scan Redis for that day's stats
            pattern = f"error_stats:*:{date}"
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    count = await redis_client.get(key)
                    day_total += int(count or 0)
                if cursor == 0:
                    break
            
            analytics["trend"].append({
                "date": date,
                "count": day_total
            })
        
        return analytics


class CircuitBreaker:
    """Circuit breaker pattern for external services."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Optional[Type[Exception]] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception or Exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise ExternalServiceException(
                    service=self.name,
                    message="Circuit breaker is open"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise ExternalServiceException(
                service=self.name,
                message=str(e)
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        return (
            self.last_failure_time and
            datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
        )
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")


# Global error handler instance
error_handler = ErrorHandler()


# FastAPI exception handlers
async def custom_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for FastAPI."""
    return await error_handler.handle_error(request, exc)


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Validation error handler."""
    return await error_handler.handle_error(request, exc)


async def http_exception_handler_wrapper(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP exception handler."""
    return await error_handler.handle_error(request, exc)


# Utility functions
def handle_errors(
    fallback_value: Any = None,
    log_errors: bool = True,
    reraise: bool = False
):
    """Decorator for simple error handling."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {str(e)}")
                
                if reraise:
                    raise
                
                return fallback_value
        
        return wrapper
    return decorator