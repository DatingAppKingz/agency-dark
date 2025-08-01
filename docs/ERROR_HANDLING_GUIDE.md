# Error Handling Guide

This guide explains the comprehensive error handling system implemented in AgencyDark.

## Overview

The error handling system provides:
- Standardized error codes for frontend handling
- Detailed debugging information in development mode
- Request tracking with unique IDs
- Structured logging with context
- Performance profiling capabilities
- Automatic error response formatting

## Error Classes

### Base Error Class

All application errors inherit from `AppError`:

```python
from core.errors import AppError, ErrorCode

raise AppError(
    message="Internal error message for debugging",
    code=ErrorCode.INTERNAL_ERROR,
    status_code=500,
    details={"additional": "context"},
    user_message="User-friendly error message"
)
```

### Specific Error Classes

1. **ValidationError** - For input validation failures
```python
from core.errors import ValidationError

raise ValidationError(
    message="Validation failed",
    fields={"email": "Invalid email format", "age": "Must be 18 or older"}
)
```

2. **NotFoundError** - For missing resources
```python
from core.errors import NotFoundError

raise NotFoundError("Model", model_id)
# Or without identifier
raise NotFoundError("Configuration")
```

3. **AuthenticationError** - For authentication failures
```python
from core.errors import AuthenticationError

raise AuthenticationError("Invalid credentials")
```

4. **AuthorizationError** - For permission issues
```python
from core.errors import AuthorizationError

raise AuthorizationError("Insufficient permissions", required_role="admin")
```

5. **DuplicateError** - For unique constraint violations
```python
from core.errors import DuplicateError

raise DuplicateError("User", "email", "user@example.com")
```

6. **RateLimitError** - For rate limit exceeded
```python
from core.errors import RateLimitError

raise RateLimitError(limit=100, window=3600, retry_after=60)
```

7. **ExternalServiceError** - For third-party API failures
```python
from core.errors import ExternalServiceError

raise ExternalServiceError("OnlyFans API", "Connection timeout", original_error=str(e))
```

8. **DatabaseError** - For database operation failures
```python
from core.errors import DatabaseError

raise DatabaseError("insert", "Connection lost", original_error=str(e))
```

## Error Codes

Standard error codes are defined in `ErrorCode` class:

### Authentication & Authorization
- `AUTH001` - Unauthorized
- `AUTH002` - Forbidden
- `AUTH003` - Token expired
- `AUTH004` - Token invalid
- `AUTH005` - Session expired

### Validation
- `VAL001` - Validation error
- `VAL002` - Missing field
- `VAL003` - Invalid format
- `VAL004` - Out of range

### Database
- `DB001` - Not found
- `DB002` - Duplicate entry
- `DB003` - Constraint violation
- `DB004` - Connection error
- `DB005` - Transaction error

### Business Logic
- `BIZ001` - Insufficient permissions
- `BIZ002` - Resource locked
- `BIZ003` - Quota exceeded
- `BIZ004` - Invalid state
- `BIZ005` - Operation failed

### External Services
- `EXT001` - External service error
- `EXT002` - API rate limited
- `EXT003` - Webhook failed
- `EXT004` - Sync failed

### System
- `SYS001` - Internal error
- `SYS002` - Service unavailable
- `SYS003` - Timeout
- `SYS004` - Configuration error

## Response Format

Error responses follow a consistent format:

```json
{
  "error": {
    "code": "VAL001",
    "message": "User-friendly error message",
    "timestamp": "2024-01-31T12:34:56.789Z",
    "details": {
      "fields": {
        "email": "This field is required"
      }
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

In debug mode, additional information is included:

```json
{
  "error": {
    "code": "DB001",
    "message": "User-friendly message",
    "timestamp": "2024-01-31T12:34:56.789Z"
  },
  "debug": {
    "message": "Detailed internal error message",
    "stack_trace": "Full stack trace...",
    "details": {
      "query": "SELECT * FROM users WHERE id = $1",
      "params": ["invalid-uuid"]
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Logging

The enhanced logging system provides:

### Structured Logging

```python
from core.logger import get_logger

logger = get_logger(__name__)

# Basic logging with automatic context
logger.info("User logged in", extra={"user_id": user.id})
logger.error("Payment failed", exc_info=True, extra={"amount": 100})

# Specialized logging methods
logger.log_request("POST", "/api/v1/users", 201, 45.2)
logger.log_database_query("SELECT * FROM users", 120.5, rows_affected=10)
logger.log_external_api_call("OnlyFans", "/v1/messages", 200, 350.5)
logger.log_business_event("subscription_created", "Subscription", subscription_id)
```

### Request Context

Request context is automatically included in all logs:

```python
from core.logger import set_request_context, clear_request_context

# Middleware automatically sets context
set_request_context(
    request_id="uuid",
    method="POST",
    path="/api/v1/users",
    user_id="user-123",
    agency_id="agency-456"
)
```

## Middleware

### DebuggingMiddleware

Automatically tracks requests and handles errors:
- Generates request IDs
- Logs request/response details
- Measures request duration
- Handles uncaught exceptions

### RequestBodyMiddleware

In debug mode, logs request bodies (with sensitive data masking):
- Masks fields: password, token, secret, api_key
- Only logs bodies under 10KB

### DatabaseQueryLoggingMiddleware

Logs slow database queries:
- Configurable threshold (default 1 second)
- Includes query text and parameters in debug mode

### PerformanceProfilingMiddleware

Enables profiling with `X-Profile: true` header:
- Returns top 20 slow functions
- Useful for performance debugging

## Migration from HTTPException

Replace FastAPI's HTTPException with our error classes:

```python
# Before
raise HTTPException(
    status_code=404,
    detail="User not found"
)

# After
raise NotFoundError("User", user_id)
```

```python
# Before
raise HTTPException(
    status_code=400,
    detail="Email already exists"
)

# After
raise DuplicateError("User", "email", email)
```

## Best Practices

1. **Use specific error classes** instead of generic AppError
2. **Include context** in error details for debugging
3. **Log errors** with appropriate severity levels
4. **Provide user-friendly messages** separate from technical details
5. **Use error codes** consistently for frontend handling
6. **Include request IDs** in error responses for tracking

## Configuration

Error handling can be configured via environment variables:

```env
# Logging
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=/var/log/app.log  # Optional file logging
LOG_FORMAT=json         # json or text

# Debug mode
DEBUG=true              # Enable debug information in responses
```

## Testing Error Handling

```python
# Test with custom headers
curl -X POST http://localhost:8000/api/v1/users \
  -H "X-Request-ID: test-123" \
  -H "X-Profile: true" \
  -d '{"invalid": "data"}'

# Response includes:
# - Request ID for tracking
# - Validation errors with field details
# - Performance profile (if X-Profile header set)
```

## Frontend Integration

Frontend can handle errors based on error codes:

```typescript
try {
  const response = await api.post('/users', data);
} catch (error) {
  switch (error.response?.data?.error?.code) {
    case 'AUTH001':
      // Redirect to login
      break;
    case 'VAL001':
      // Show validation errors
      const fields = error.response.data.error.details.fields;
      break;
    case 'DB002':
      // Handle duplicate entry
      break;
    default:
      // Generic error handling
  }
}
```