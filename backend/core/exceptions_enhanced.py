from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from pydantic import BaseModel
import traceback
import logging

logger = logging.getLogger(__name__)

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str
    message: str
    field: Optional[str] = None
    value: Optional[Any] = None
    constraint: Optional[str] = None

class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str
    error_code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None
    timestamp: str
    path: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "error_code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": [
                    {
                        "code": "required",
                        "message": "Field is required",
                        "field": "email"
                    }
                ],
                "request_id": "req_123456",
                "timestamp": "2024-01-01T00:00:00Z",
                "path": "/api/v1/users"
            }
        }

class AppException(HTTPException):
    """Base application exception."""
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[List[ErrorDetail]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.error_code = error_code
        self.details = details
        super().__init__(
            status_code=status_code,
            detail=message,
            headers=headers
        )

# Authentication & Authorization Exceptions
class UnauthorizedException(AppException):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message=message,
            headers={"WWW-Authenticate": "Bearer"}
        )

class ForbiddenException(AppException):
    """Raised when user lacks permission."""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            message=message
        )

class TokenExpiredException(AppException):
    """Raised when token has expired."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_EXPIRED",
            message="Token has expired"
        )

class InvalidTokenException(AppException):
    """Raised when token is invalid."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_TOKEN",
            message="Invalid token"
        )

# Resource Exceptions
class NotFoundException(AppException):
    """Raised when resource is not found."""
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            message=message
        )

class ConflictException(AppException):
    """Raised when there's a resource conflict."""
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            message=message
        )

class DuplicateException(AppException):
    """Raised when trying to create duplicate resource."""
    def __init__(self, resource: str, field: str, value: Any):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_RESOURCE",
            message=f"{resource} with {field} '{value}' already exists"
        )

# Validation Exceptions
class ValidationException(AppException):
    """Raised when validation fails."""
    def __init__(self, errors: List[ErrorDetail]):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            details=errors
        )

class BadRequestException(AppException):
    """Raised for bad requests."""
    def __init__(self, message: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BAD_REQUEST",
            message=message
        )

# Business Logic Exceptions
class BusinessLogicException(AppException):
    """Raised when business rules are violated."""
    def __init__(self, message: str, error_code: str = "BUSINESS_LOGIC_ERROR"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message
        )

class InsufficientFundsException(BusinessLogicException):
    """Raised when there are insufficient funds."""
    def __init__(self, available: float, required: float):
        super().__init__(
            message=f"Insufficient funds. Available: ${available:.2f}, Required: ${required:.2f}",
            error_code="INSUFFICIENT_FUNDS"
        )

class RateLimitException(AppException):
    """Raised when rate limit is exceeded."""
    def __init__(self, limit: int, window: str, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Limit: {limit} per {window}",
            headers={"Retry-After": str(retry_after)}
        )

# External Service Exceptions
class ExternalServiceException(AppException):
    """Raised when external service fails."""
    def __init__(self, service: str, message: str = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="EXTERNAL_SERVICE_ERROR",
            message=message or f"{service} service is temporarily unavailable"
        )

class PaymentException(AppException):
    """Raised when payment processing fails."""
    def __init__(self, message: str, error_code: str = "PAYMENT_ERROR"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            error_code=error_code,
            message=message
        )

# System Exceptions
class InternalServerException(AppException):
    """Raised for internal server errors."""
    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_ERROR",
            message=message
        )

class DatabaseException(InternalServerException):
    """Raised for database errors."""
    def __init__(self, operation: str = "database operation"):
        super().__init__(
            message=f"Failed to perform {operation}"
        )
        
class ConfigurationException(InternalServerException):
    """Raised for configuration errors."""
    def __init__(self, config_name: str):
        super().__init__(
            message=f"Invalid configuration: {config_name}"
        )

# Utility functions
def create_validation_error(field: str, message: str, code: str = "invalid") -> ErrorDetail:
    """Create a validation error detail."""
    return ErrorDetail(
        code=code,
        message=message,
        field=field
    )

def handle_database_error(error: Exception, operation: str = "database operation") -> None:
    """Handle database errors and raise appropriate exception."""
    error_str = str(error).lower()
    
    if "unique constraint" in error_str or "duplicate key" in error_str:
        # Extract field name if possible
        field = "unknown"
        if "key" in error_str:
            import re
            match = re.search(r'key \((.*?)\)', error_str)
            if match:
                field = match.group(1)
        raise ConflictException(f"Duplicate value for {field}")
    
    elif "foreign key" in error_str:
        raise BadRequestException("Referenced resource does not exist")
    
    elif "not null" in error_str:
        raise ValidationException([
            create_validation_error("unknown", "Required field is missing", "required")
        ])
    
    else:
        logger.error(f"Database error during {operation}: {error}")
        raise DatabaseException(operation)

def format_exception_response(
    exception: Exception,
    request_id: Optional[str] = None,
    path: Optional[str] = None
) -> Dict[str, Any]:
    """Format exception into standardized response."""
    from datetime import datetime
    
    if isinstance(exception, AppException):
        return ErrorResponse(
            error=exception.__class__.__name__,
            error_code=exception.error_code,
            message=exception.detail,
            details=exception.details,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
            path=path
        ).model_dump()
    
    # Handle non-app exceptions
    logger.error(f"Unhandled exception: {exception}", exc_info=True)
    return ErrorResponse(
        error="InternalServerError",
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
        path=path
    ).model_dump()