"""
CSRF middleware for automatic CSRF protection.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.security_v2.csrf import csrf_protection, SAFE_METHODS, CSRF_COOKIE_NAME
from core.logger import get_logger
from typing import Callable

logger = get_logger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically handle CSRF protection for all routes.
    
    This middleware:
    1. Generates CSRF tokens for safe requests (GET, etc.)
    2. Validates CSRF tokens for unsafe requests (POST, PUT, DELETE, etc.)
    3. Refreshes CSRF tokens periodically
    """
    
    def __init__(self, app, exclude_paths: list[str] = None):
        """
        Initialize CSRF middleware.
        
        Args:
            app: FastAPI application
            exclude_paths: List of path prefixes to exclude from CSRF protection
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/api/v1/auth/login",  # Login needs to work without existing CSRF
            "/api/v1/auth/register",  # Registration needs to work without existing CSRF
            "/api/v1/auth/refresh",  # Token refresh should work with just cookies
            "/api/v1/external/",  # External API endpoints use API keys
            "/api/v1/webhooks/",  # Webhooks can't provide CSRF tokens
            "/docs",  # Documentation
            "/redoc",  # Documentation
            "/openapi.json",  # OpenAPI schema
            "/health",  # Health check
            "/"  # Root endpoint
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and handle CSRF protection.
        
        Args:
            request: Incoming request
            call_next: Next middleware or route handler
            
        Returns:
            Response object
        """
        # Check if path is excluded
        for exclude_path in self.exclude_paths:
            if request.url.path.startswith(exclude_path):
                response = await call_next(request)
                return response
        
        # For safe methods, ensure CSRF cookie is set
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            
            # Check if CSRF cookie exists
            if CSRF_COOKIE_NAME not in request.cookies:
                # Generate new CSRF token
                token, _ = csrf_protection.generate_csrf_token()
                csrf_protection.set_csrf_cookie(response, token)
                
                # Also add it to response body if it's a JSON response
                if hasattr(response, "body"):
                    try:
                        # This is a bit hacky but works for JSON responses
                        import json
                        body = response.body
                        if body:
                            data = json.loads(body)
                            if isinstance(data, dict):
                                data["csrf_token"] = token
                                response.body = json.dumps(data).encode()
                    except:
                        # If we can't modify the response, that's okay
                        pass
            
            return response
        
        # For unsafe methods, validate CSRF token
        try:
            # Use our existing CSRF validation
            await csrf_protection.verify_csrf_token(request)
            
            # Process the request
            response = await call_next(request)
            
            # Optionally refresh CSRF token on successful requests
            # This enhances security by rotating tokens
            if response.status_code < 400:
                # Check if token should be refreshed (e.g., if it's older than 1 hour)
                current_token = request.cookies.get(CSRF_COOKIE_NAME)
                if current_token and csrf_protection.validate_csrf_token(current_token):
                    # Token is still valid, no need to refresh yet
                    pass
                else:
                    # Generate new token
                    token, _ = csrf_protection.generate_csrf_token()
                    csrf_protection.set_csrf_cookie(response, token)
            
            return response
            
        except Exception as e:
            logger.error(f"CSRF validation failed: {e}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed", "error": str(e)}
            )


def get_csrf_middleware(exclude_paths: list[str] = None) -> type:
    """
    Factory function to create CSRF middleware with custom exclude paths.
    
    Args:
        exclude_paths: List of path prefixes to exclude from CSRF protection
        
    Returns:
        CSRFMiddleware class configured with exclude paths
    """
    class ConfiguredCSRFMiddleware(CSRFMiddleware):
        def __init__(self, app):
            super().__init__(app, exclude_paths=exclude_paths)
    
    return ConfiguredCSRFMiddleware