"""
Request validation middleware for comprehensive input validation.

This middleware automatically validates all incoming requests
to prevent injection attacks and ensure data integrity.
"""

import json
import re
from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.logger import get_logger
from core.validation.validators import (
    validate_no_sql_injection,
    validate_no_xss,
    ValidationError as CustomValidationError
)

logger = get_logger(__name__)

# Headers to validate
VALIDATED_HEADERS = [
    'user-agent',
    'referer',
    'x-forwarded-for',
    'x-real-ip',
    'x-original-uri'
]

# Maximum request size (10MB)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# Suspicious patterns in URLs
SUSPICIOUS_URL_PATTERNS = [
    r'\.\./|\.\.//',  # Path traversal
    r'<script|<iframe|javascript:',  # XSS attempts
    r'union\s+select|drop\s+table',  # SQL injection
    r'/etc/passwd|/windows/system32',  # System file access
    r'\.env|\.git|\.svn',  # Sensitive files
]


class ValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate all incoming requests for security threats.
    
    This middleware:
    1. Validates request size
    2. Checks headers for injection attempts
    3. Validates URL parameters
    4. Validates request body content
    5. Prevents common attack vectors
    """
    
    def __init__(self, app, max_request_size: int = MAX_REQUEST_SIZE):
        """
        Initialize validation middleware.
        
        Args:
            app: FastAPI application
            max_request_size: Maximum allowed request size in bytes
        """
        super().__init__(app)
        self.max_request_size = max_request_size
        self.suspicious_patterns = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_URL_PATTERNS]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process and validate the request.
        
        Args:
            request: Incoming request
            call_next: Next middleware or route handler
            
        Returns:
            Response object or validation error
        """
        try:
            # 1. Validate request size
            content_length = request.headers.get('content-length')
            if content_length and int(content_length) > self.max_request_size:
                logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request too large"}
                )
            
            # 2. Validate URL and path
            if not self._validate_url(str(request.url)):
                logger.warning(f"Suspicious URL detected: {request.url} from {request.client.host}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request URL"}
                )
            
            # 3. Validate headers
            validation_error = self._validate_headers(dict(request.headers))
            if validation_error:
                logger.warning(f"Header validation failed: {validation_error} from {request.client.host}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Invalid header: {validation_error}"}
                )
            
            # 4. Validate query parameters
            validation_error = self._validate_query_params(dict(request.query_params))
            if validation_error:
                logger.warning(f"Query param validation failed: {validation_error} from {request.client.host}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Invalid query parameter: {validation_error}"}
                )
            
            # 5. For requests with body, validate content
            if request.method in ["POST", "PUT", "PATCH"]:
                # Store original body for later use
                body = await request.body()
                
                # Validate body content
                validation_error = await self._validate_body(body, request.headers.get('content-type'))
                if validation_error:
                    logger.warning(f"Body validation failed: {validation_error} from {request.client.host}")
                    return JSONResponse(
                        status_code=400,
                        content={"detail": f"Invalid request body: {validation_error}"}
                    )
                
                # Create new request with stored body
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
            
            # Process the request
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Validation middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal validation error"}
            )
    
    def _validate_url(self, url: str) -> bool:
        """
        Validate URL for suspicious patterns.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        for pattern in self.suspicious_patterns:
            if pattern.search(url):
                return False
        return True
    
    def _validate_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Validate request headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Error message if validation fails, None otherwise
        """
        for header_name in VALIDATED_HEADERS:
            header_value = headers.get(header_name, '')
            if header_value:
                try:
                    # Check for SQL injection
                    validate_no_sql_injection(header_value, header_name)
                    # Check for XSS
                    validate_no_xss(header_value, header_name)
                except CustomValidationError as e:
                    return str(e)
        
        # Validate content-type if present
        content_type = headers.get('content-type', '')
        if content_type and not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\/\-\+\.\s;=]+$', content_type):
            return "Invalid content-type header"
        
        return None
    
    def _validate_query_params(self, params: Dict[str, str]) -> Optional[str]:
        """
        Validate query parameters.
        
        Args:
            params: Query parameters
            
        Returns:
            Error message if validation fails, None otherwise
        """
        for key, value in params.items():
            # Validate parameter name
            if not re.match(r'^[a-zA-Z0-9_\-\[\]]+$', key):
                return f"Invalid parameter name: {key}"
            
            # Validate parameter value
            try:
                validate_no_sql_injection(value, f"query.{key}")
                validate_no_xss(value, f"query.{key}")
            except CustomValidationError as e:
                return str(e)
        
        return None
    
    async def _validate_body(self, body: bytes, content_type: Optional[str]) -> Optional[str]:
        """
        Validate request body content.
        
        Args:
            body: Request body
            content_type: Content-Type header
            
        Returns:
            Error message if validation fails, None otherwise
        """
        if not body:
            return None
        
        # Check body size
        if len(body) > self.max_request_size:
            return "Request body too large"
        
        # Validate based on content type
        if content_type and 'application/json' in content_type:
            return self._validate_json_body(body)
        elif content_type and 'application/x-www-form-urlencoded' in content_type:
            return self._validate_form_body(body)
        elif content_type and 'multipart/form-data' in content_type:
            # Multipart validation is complex, skip detailed validation
            # FastAPI's UploadFile handles most security concerns
            return None
        
        # For other content types, do basic validation
        try:
            body_str = body.decode('utf-8')
            validate_no_sql_injection(body_str, "body")
            validate_no_xss(body_str, "body")
        except (UnicodeDecodeError, CustomValidationError) as e:
            return str(e)
        
        return None
    
    def _validate_json_body(self, body: bytes) -> Optional[str]:
        """
        Validate JSON request body.
        
        Args:
            body: Request body
            
        Returns:
            Error message if validation fails, None otherwise
        """
        try:
            data = json.loads(body)
            
            # Recursively validate all string values
            def validate_json_recursive(obj: Any, path: str = "") -> Optional[str]:
                if isinstance(obj, str):
                    try:
                        validate_no_sql_injection(obj, f"body{path}")
                        validate_no_xss(obj, f"body{path}")
                    except CustomValidationError as e:
                        return str(e)
                elif isinstance(obj, dict):
                    for key, value in obj.items():
                        # Validate key
                        if not isinstance(key, str) or len(key) > 100:
                            return f"Invalid key at {path}: {key}"
                        
                        error = validate_json_recursive(value, f"{path}.{key}")
                        if error:
                            return error
                elif isinstance(obj, list):
                    for i, value in enumerate(obj):
                        error = validate_json_recursive(value, f"{path}[{i}]")
                        if error:
                            return error
                
                return None
            
            return validate_json_recursive(data)
            
        except json.JSONDecodeError:
            return "Invalid JSON"
        except Exception as e:
            return f"JSON validation error: {str(e)}"
    
    def _validate_form_body(self, body: bytes) -> Optional[str]:
        """
        Validate form-encoded request body.
        
        Args:
            body: Request body
            
        Returns:
            Error message if validation fails, None otherwise
        """
        try:
            from urllib.parse import parse_qs
            
            body_str = body.decode('utf-8')
            params = parse_qs(body_str)
            
            for key, values in params.items():
                # Validate key
                if not re.match(r'^[a-zA-Z0-9_\-\[\]]+$', key):
                    return f"Invalid form field name: {key}"
                
                # Validate values
                for value in values:
                    try:
                        validate_no_sql_injection(value, f"form.{key}")
                        validate_no_xss(value, f"form.{key}")
                    except CustomValidationError as e:
                        return str(e)
            
            return None
            
        except Exception as e:
            return f"Form validation error: {str(e)}"


def get_validation_middleware(max_request_size: int = MAX_REQUEST_SIZE) -> type:
    """
    Factory function to create validation middleware with custom settings.
    
    Args:
        max_request_size: Maximum allowed request size in bytes
        
    Returns:
        ValidationMiddleware class configured with settings
    """
    class ConfiguredValidationMiddleware(ValidationMiddleware):
        def __init__(self, app):
            super().__init__(app, max_request_size=max_request_size)
    
    return ConfiguredValidationMiddleware