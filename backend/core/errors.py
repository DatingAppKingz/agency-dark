"""
Comprehensive error handling system with detailed debugging information.
"""
import traceback
import sys
from typing import Optional, Dict, Any, Union
from datetime import datetime
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from pydantic import ValidationError
import logging

from core.config import settings

logger = logging.getLogger(__name__)


class ErrorCode:
    """Standardized error codes for frontend handling."""
    # Authentication & Authorization
    UNAUTHORIZED = "AUTH001"
    FORBIDDEN = "AUTH002"
    TOKEN_EXPIRED = "AUTH003"
    TOKEN_INVALID = "AUTH004"
    SESSION_EXPIRED = "AUTH005"
    
    # Validation
    VALIDATION_ERROR = "VAL001"
    MISSING_FIELD = "VAL002"
    INVALID_FORMAT = "VAL003"
    OUT_OF_RANGE = "VAL004"
    
    # Database
    NOT_FOUND = "DB001"
    DUPLICATE_ENTRY = "DB002"
    CONSTRAINT_VIOLATION = "DB003"
    CONNECTION_ERROR = "DB004"
    TRANSACTION_ERROR = "DB005"
    
    # Business Logic
    INSUFFICIENT_PERMISSIONS = "BIZ001"
    RESOURCE_LOCKED = "BIZ002"
    QUOTA_EXCEEDED = "BIZ003"
    INVALID_STATE = "BIZ004"
    OPERATION_FAILED = "BIZ005"
    
    # External Services
    EXTERNAL_SERVICE_ERROR = "EXT001"
    API_RATE_LIMITED = "EXT002"
    WEBHOOK_FAILED = "EXT003"
    SYNC_FAILED = "EXT004"
    
    # System
    INTERNAL_ERROR = "SYS001"
    SERVICE_UNAVAILABLE = "SYS002"
    TIMEOUT = "SYS003"
    CONFIGURATION_ERROR = "SYS004"


class AppError(Exception):
    """Base application error with enhanced debugging."""
    
    def __init__(
        self,
        message: str,
        code: str = ErrorCode.INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.user_message = user_message or message
        self.timestamp = datetime.utcnow()
        
        # Capture stack trace for debugging
        if settings.DEBUG:
            self.stack_trace = traceback.format_exc()
        else:
            self.stack_trace = None
    
    def to_dict(self, include_debug: bool = False) -> Dict[str, Any]:
        """Convert error to dictionary response."""
        response = {
            "error": {
                "code": self.code,
                "message": self.user_message,
                "timestamp": self.timestamp.isoformat(),
            }
        }
        
        if self.details:
            response["error"]["details"] = self.details
        
        if include_debug and settings.DEBUG:
            response["debug"] = {
                "message": self.message,
                "stack_trace": self.stack_trace,
                "details": self.details
            }
        
        return response


# Specific error classes
class ValidationError(AppError):
    """Validation error with field details."""
    
    def __init__(self, message: str, fields: Optional[Dict[str, str]] = None):
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"fields": fields} if fields else None,
            user_message="Validation failed. Please check your input."
        )


class NotFoundError(AppError):
    """Resource not found error."""
    
    def __init__(self, resource: str, identifier: Optional[Union[str, int]] = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": str(identifier) if identifier else None},
            user_message=f"The requested {resource.lower()} was not found."
        )


class AuthenticationError(AppError):
    """Authentication failed error."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            user_message="Please log in to continue."
        )


class AuthorizationError(AppError):
    """Authorization failed error."""
    
    def __init__(self, message: str = "Insufficient permissions", required_role: Optional[str] = None):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            status_code=status.HTTP_403_FORBIDDEN,
            details={"required_role": required_role} if required_role else None,
            user_message="You don't have permission to perform this action."
        )


class DuplicateError(AppError):
    """Duplicate resource error."""
    
    def __init__(self, resource: str, field: str, value: Any):
        super().__init__(
            message=f"{resource} with {field}='{value}' already exists",
            code=ErrorCode.DUPLICATE_ENTRY,
            status_code=status.HTTP_409_CONFLICT,
            details={"resource": resource, "field": field, "value": str(value)},
            user_message=f"A {resource.lower()} with this {field} already exists."
        )


class RateLimitError(AppError):
    """Rate limit exceeded error."""
    
    def __init__(self, limit: int, window: int, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window} seconds",
            code=ErrorCode.API_RATE_LIMITED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"limit": limit, "window": window, "retry_after": retry_after},
            user_message="Too many requests. Please try again later."
        )


class ExternalServiceError(AppError):
    """External service error."""
    
    def __init__(self, service: str, message: str, original_error: Optional[str] = None):
        super().__init__(
            message=f"{service} error: {message}",
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service, "original_error": original_error},
            user_message=f"An error occurred with {service}. Please try again later."
        )


class DatabaseError(AppError):
    """Database operation error."""
    
    def __init__(self, operation: str, message: str, original_error: Optional[str] = None):
        super().__init__(
            message=f"Database {operation} failed: {message}",
            code=ErrorCode.TRANSACTION_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"operation": operation, "original_error": original_error},
            user_message="A database error occurred. Please try again."
        )


def handle_sqlalchemy_error(error: Exception) -> AppError:
    """Convert SQLAlchemy errors to AppError."""
    if isinstance(error, IntegrityError):
        # Parse integrity error for better messages
        error_str = str(error.orig)
        
        if "duplicate key" in error_str.lower():
            # Extract field name from error message
            import re
            match = re.search(r'Key \((\w+)\)=\(([^)]+)\)', error_str)
            if match:
                field, value = match.groups()
                return DuplicateError("Record", field, value)
            return AppError(
                message="Duplicate entry",
                code=ErrorCode.DUPLICATE_ENTRY,
                status_code=status.HTTP_409_CONFLICT,
                user_message="This record already exists."
            )
        
        if "foreign key" in error_str.lower():
            return AppError(
                message="Foreign key constraint violation",
                code=ErrorCode.CONSTRAINT_VIOLATION,
                status_code=status.HTTP_400_BAD_REQUEST,
                user_message="Cannot perform this operation due to related records."
            )
        
        if "not null" in error_str.lower():
            match = re.search(r'column "(\w+)" .*not null', error_str)
            field = match.group(1) if match else "unknown"
            return ValidationError(
                message=f"Required field missing: {field}",
                fields={field: "This field is required."}
            )
    
    elif isinstance(error, DataError):
        return ValidationError(
            message="Invalid data format",
            fields={"data": str(error.orig)}
        )
    
    elif isinstance(error, OperationalError):
        return DatabaseError(
            operation="connection",
            message="Database connection failed",
            original_error=str(error.orig)
        )
    
    # Default database error
    return DatabaseError(
        operation="query",
        message=str(error),
        original_error=str(error.orig) if hasattr(error, 'orig') else None
    )


def handle_pydantic_error(error: ValidationError) -> AppError:
    """Convert Pydantic validation errors to AppError."""
    fields = {}
    for err in error.errors():
        field_path = ".".join(str(loc) for loc in err["loc"])
        fields[field_path] = err["msg"]
    
    return ValidationError(
        message="Request validation failed",
        fields=fields
    )


async def error_handler(request: Request, error: Exception) -> JSONResponse:
    """Global error handler for FastAPI."""
    # Generate request ID for tracking
    request_id = request.headers.get("X-Request-ID", datetime.utcnow().isoformat())
    
    # Convert known exceptions to AppError
    if isinstance(error, AppError):
        app_error = error
    elif isinstance(error, ValidationError):
        app_error = handle_pydantic_error(error)
    elif isinstance(error, (IntegrityError, DataError, OperationalError)):
        app_error = handle_sqlalchemy_error(error)
    else:
        # Unknown error
        app_error = AppError(
            message=str(error),
            code=ErrorCode.INTERNAL_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="An unexpected error occurred."
        )
    
    # Log error with context
    log_context = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "user": getattr(request.state, "user", None),
        "error_code": app_error.code,
        "status_code": app_error.status_code,
    }
    
    if app_error.status_code >= 500:
        logger.error(
            f"Server error: {app_error.message}",
            extra=log_context,
            exc_info=True
        )
    else:
        logger.warning(
            f"Client error: {app_error.message}",
            extra=log_context
        )
    
    # Build response
    response_data = app_error.to_dict(include_debug=settings.DEBUG)
    response_data["request_id"] = request_id
    
    # Add rate limit headers if applicable
    if isinstance(app_error, RateLimitError) and app_error.details.get("retry_after"):
        headers = {
            "Retry-After": str(app_error.details["retry_after"]),
            "X-RateLimit-Limit": str(app_error.details["limit"]),
            "X-RateLimit-Window": str(app_error.details["window"])
        }
    else:
        headers = {}
    
    headers["X-Request-ID"] = request_id
    
    return JSONResponse(
        status_code=app_error.status_code,
        content=response_data,
        headers=headers
    )


# Decorator for automatic error handling
def handle_errors(include_debug: bool = False):
    """Decorator to automatically handle errors in endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Get request from args/kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                if not request:
                    for value in kwargs.values():
                        if isinstance(value, Request):
                            request = value
                            break
                
                if request:
                    return await error_handler(request, e)
                else:
                    # No request object, re-raise
                    raise
        
        return wrapper
    return decorator