from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
import traceback
import logging
from typing import Union
from datetime import datetime
import uuid

from core.exceptions_enhanced import (
    AppException,
    format_exception_response,
    handle_database_error,
    ValidationException,
    create_validation_error,
    ErrorDetail
)

logger = logging.getLogger(__name__)

async def error_handler_middleware(request: Request, call_next):
    """Global error handler middleware."""
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    try:
        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
        
    except Exception as exc:
        # Log the error
        logger.error(
            f"Request {request_id} failed: {str(exc)}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            }
        )
        
        # Format and return error response
        error_response = format_exception_response(
            exc,
            request_id=request_id,
            path=str(request.url)
        )
        
        # Determine status code
        if isinstance(exc, AppException):
            status_code = exc.status_code
        elif isinstance(exc, StarletteHTTPException):
            status_code = exc.status_code
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={"X-Request-ID": request_id}
        )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=format_exception_response(
            exc,
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url)
        ),
        headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4()))}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions."""
    # Convert Pydantic validation errors to our format
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])  # Skip 'body'
        errors.append(
            ErrorDetail(
                code=error["type"],
                message=error["msg"],
                field=field_path,
                value=error.get("input")
            )
        )
    
    validation_exc = ValidationException(errors)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_exception_response(
            validation_exc,
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url)
        ),
        headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4()))}
    )

async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database exceptions."""
    try:
        # This will raise an appropriate AppException
        handle_database_error(exc)
    except AppException as app_exc:
        return JSONResponse(
            status_code=app_exc.status_code,
            content=format_exception_response(
                app_exc,
                request_id=getattr(request.state, "request_id", None),
                path=str(request.url)
            ),
            headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4()))}
        )

async def generic_exception_handler(request: Request, exc: Exception):
    """Handle generic exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4()))}
    )

def register_error_handlers(app):
    """Register all error handlers with the app."""
    app.middleware("http")(error_handler_middleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    # Register specific app exceptions
    from core.exceptions_enhanced import (
        UnauthorizedException,
        ForbiddenException,
        NotFoundException,
        ValidationException,
        ConflictException,
        RateLimitException,
        ExternalServiceException,
        PaymentException
    )
    
    for exc_class in [
        UnauthorizedException,
        ForbiddenException,
        NotFoundException,
        ValidationException,
        ConflictException,
        RateLimitException,
        ExternalServiceException,
        PaymentException
    ]:
        app.add_exception_handler(exc_class, http_exception_handler)