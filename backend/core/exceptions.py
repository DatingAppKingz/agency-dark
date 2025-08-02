"""Custom exceptions for the application."""


class BaseError(Exception):
    """Base error class."""
    pass


class NotFoundError(BaseError):
    """Resource not found error."""
    pass


class ValidationError(BaseError):
    """Validation error."""
    pass


class PermissionError(BaseError):
    """Permission denied error."""
    pass


class AuthenticationError(BaseError):
    """Authentication failed error."""
    pass


class ConflictError(BaseError):
    """Resource conflict error."""
    pass


class RateLimitError(BaseError):
    """Rate limit exceeded error."""
    pass


class ExternalServiceError(BaseError):
    """External service error."""
    pass


class BusinessLogicError(BaseError):
    """Business logic error."""
    pass