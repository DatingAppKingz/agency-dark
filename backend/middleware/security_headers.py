"""Security headers middleware for FastAPI."""

from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    def __init__(
        self,
        app,
        strict: bool = True,
        allow_frame_ancestors: str = "'none'",
        content_security_policy: str = None
    ):
        super().__init__(app)
        self.strict = strict
        self.allow_frame_ancestors = allow_frame_ancestors
        self.content_security_policy = content_security_policy or self._default_csp()
    
    def _default_csp(self) -> str:
        """Generate default Content Security Policy."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://api.stripe.com wss://localhost:* ws://localhost:*; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # Content Security Policy
        if self.strict:
            response.headers["Content-Security-Policy"] = self.content_security_policy
        
        # Strict Transport Security (only for HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Remove potentially dangerous headers
        headers_to_remove = ["Server", "X-Powered-By"]
        for header in headers_to_remove:
            response.headers.pop(header, None)
        
        return response


def add_security_headers(
    app: FastAPI,
    strict: bool = True,
    allow_frame_ancestors: str = "'none'",
    content_security_policy: str = None
) -> None:
    """Add security headers middleware to FastAPI app.
    
    Args:
        app: FastAPI application instance
        strict: Whether to enforce strict CSP (may break some features)
        allow_frame_ancestors: CSP frame-ancestors directive
        content_security_policy: Custom CSP string (overrides default)
    """
    app.add_middleware(
        SecurityHeadersMiddleware,
        strict=strict,
        allow_frame_ancestors=allow_frame_ancestors,
        content_security_policy=content_security_policy
    )
    logger.info("Security headers middleware added")