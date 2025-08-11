"""
Comprehensive security headers middleware for OAuth implementation.
Includes CSP, CORS, rate limiting, and CSRF protection.
"""
from typing import Optional, Dict, Any, List, Set, Callable
from datetime import datetime, timezone
import hashlib
import secrets
import logging
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import redis.asyncio as redis
from urllib.parse import urlparse

from core.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security headers middleware.
    Adds security headers to all responses for protection against common attacks.
    """
    
    def __init__(
        self,
        app,
        strict_mode: bool = True,
        csp_report_uri: Optional[str] = None,
        enable_hsts: bool = True,
        enable_csp: bool = True
    ):
        """
        Initialize security headers middleware.
        
        Args:
            app: FastAPI application
            strict_mode: Enable strict security policies
            csp_report_uri: URI for CSP violation reports
            enable_hsts: Enable HSTS header
            enable_csp: Enable Content Security Policy
        """
        super().__init__(app)
        self.strict_mode = strict_mode
        self.csp_report_uri = csp_report_uri
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp
        
        # Build CSP policy
        self.csp_policy = self._build_csp_policy()
    
    def _build_csp_policy(self) -> str:
        """
        Build Content Security Policy based on configuration.
        """
        directives = []
        
        # Default source
        directives.append("default-src 'self'")
        
        # Script sources
        if self.strict_mode:
            # Strict: no inline scripts
            directives.append("script-src 'self' 'strict-dynamic'")
        else:
            # Permissive: allow inline scripts for development
            directives.append(
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdn.jsdelivr.net https://unpkg.com"
            )
        
        # Style sources
        if self.strict_mode:
            directives.append("style-src 'self' 'nonce-{nonce}'")
        else:
            directives.append(
                "style-src 'self' 'unsafe-inline' "
                "https://fonts.googleapis.com https://cdn.jsdelivr.net"
            )
        
        # Font sources
        directives.append("font-src 'self' https://fonts.gstatic.com data:")
        
        # Image sources
        directives.append("img-src 'self' data: https: blob:")
        
        # Connect sources (API, WebSocket)
        connect_sources = [
            "'self'",
            "https://*.googleapis.com",
            "https://graph.instagram.com",
            "https://graph.microsoft.com",
            "wss://localhost:*",
            "ws://localhost:*"
        ]
        
        # Add OAuth provider APIs
        if hasattr(settings, 'OAUTH_PROVIDERS'):
            for provider in settings.OAUTH_PROVIDERS:
                if provider == 'google':
                    connect_sources.append("https://accounts.google.com")
                elif provider == 'instagram':
                    connect_sources.append("https://api.instagram.com")
                elif provider == 'microsoft':
                    connect_sources.append("https://login.microsoftonline.com")
        
        directives.append(f"connect-src {' '.join(connect_sources)}")
        
        # Frame ancestors (clickjacking protection)
        directives.append("frame-ancestors 'none'")
        
        # Base URI
        directives.append("base-uri 'self'")
        
        # Form action
        directives.append("form-action 'self'")
        
        # Object source
        directives.append("object-src 'none'")
        
        # Media sources
        directives.append("media-src 'self'")
        
        # Worker sources
        directives.append("worker-src 'self' blob:")
        
        # Manifest source
        directives.append("manifest-src 'self'")
        
        # Upgrade insecure requests in production
        if settings.ENVIRONMENT == "production":
            directives.append("upgrade-insecure-requests")
        
        # Report URI if configured
        if self.csp_report_uri:
            directives.append(f"report-uri {self.csp_report_uri}")
        
        return "; ".join(directives)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Add security headers to response.
        """
        # Generate nonce for CSP if needed
        csp_nonce = None
        if self.strict_mode and self.enable_csp:
            csp_nonce = secrets.token_urlsafe(16)
            request.state.csp_nonce = csp_nonce
        
        # Process request
        response = await call_next(request)
        
        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (Feature Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), ambient-light-sensor=(), autoplay=(), "
            "battery=(), camera=(), cross-origin-isolated=(), "
            "display-capture=(), document-domain=(), encrypted-media=(), "
            "execution-while-not-rendered=(), execution-while-out-of-viewport=(), "
            "fullscreen=(self), geolocation=(), gyroscope=(), keyboard-map=(), "
            "magnetometer=(), microphone=(), midi=(), navigation-override=(), "
            "payment=(), picture-in-picture=(), publickey-credentials-get=(), "
            "screen-wake-lock=(), sync-xhr=(), usb=(), web-share=(), "
            "xr-spatial-tracking=()"
        )
        
        # Content Security Policy
        if self.enable_csp:
            csp = self.csp_policy
            if csp_nonce:
                csp = csp.format(nonce=csp_nonce)
            response.headers["Content-Security-Policy"] = csp
        
        # Strict Transport Security (only for HTTPS)
        if self.enable_hsts and request.url.scheme == "https":
            max_age = 31536000  # 1 year
            response.headers["Strict-Transport-Security"] = (
                f"max-age={max_age}; includeSubDomains; preload"
            )
        
        # Additional security headers
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-DNS-Prefetch-Control"] = "off"
        
        # Remove server identification headers
        headers_to_remove = ["Server", "X-Powered-By", "X-AspNet-Version"]
        for header in headers_to_remove:
            response.headers.pop(header, None)
        
        # Add custom security header
        response.headers["X-Security-Policy"] = "oauth2-enabled"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    """
    
    def __init__(
        self,
        app,
        redis_client: Optional[redis.Redis] = None,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            redis_client: Redis client for distributed rate limiting
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            burst_size: Max burst requests
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        # Endpoints with different rate limits
        self.endpoint_limits = {
            "/api/v1/auth/login": {"per_minute": 5, "per_hour": 20},
            "/api/v1/auth/register": {"per_minute": 3, "per_hour": 10},
            "/api/v1/oauth/token": {"per_minute": 10, "per_hour": 100},
            "/api/v1/oauth/authorize": {"per_minute": 10, "per_hour": 50},
        }
        
        # Exempt paths
        self.exempt_paths = {
            "/health",
            "/docs",
            "/openapi.json",
            "/favicon.ico",
            "/.well-known",
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply rate limiting to requests.
        """
        # Skip rate limiting for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Skip if no Redis client
        if not self.redis_client:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limits
        try:
            allowed = await self._check_rate_limit(client_id, request.url.path)
            
            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": 60
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(datetime.now(timezone.utc).timestamp()) + 60)
                    }
                )
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Allow request on error to avoid blocking legitimate traffic
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        # TODO: Add actual remaining count
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Window"] = "60"
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier for rate limiting.
        """
        # Try to get authenticated user ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Try to get API key
        if "x-api-key" in request.headers:
            api_key = request.headers["x-api-key"]
            # Hash the API key for storage
            return f"api:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"
        
        return f"ip:{client_ip}"
    
    async def _check_rate_limit(self, client_id: str, path: str) -> bool:
        """
        Check if request is within rate limits.
        """
        # Get limits for this endpoint
        limits = self.endpoint_limits.get(path, {
            "per_minute": self.requests_per_minute,
            "per_hour": self.requests_per_hour
        })
        
        now = datetime.now(timezone.utc)
        
        # Check minute limit
        minute_key = f"rate_limit:{client_id}:minute:{now.minute}"
        minute_count = await self.redis_client.incr(minute_key)
        
        if minute_count == 1:
            await self.redis_client.expire(minute_key, 60)
        
        if minute_count > limits["per_minute"]:
            logger.warning(f"Rate limit exceeded for {client_id} on {path}")
            return False
        
        # Check hour limit
        hour_key = f"rate_limit:{client_id}:hour:{now.hour}"
        hour_count = await self.redis_client.incr(hour_key)
        
        if hour_count == 1:
            await self.redis_client.expire(hour_key, 3600)
        
        if hour_count > limits["per_hour"]:
            logger.warning(f"Hourly rate limit exceeded for {client_id} on {path}")
            return False
        
        return True


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware for state-changing operations.
    """
    
    def __init__(
        self,
        app,
        secret_key: Optional[str] = None,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        exempt_paths: Optional[Set[str]] = None
    ):
        """
        Initialize CSRF protection middleware.
        
        Args:
            app: FastAPI application
            secret_key: Secret key for token generation
            cookie_name: Name of CSRF cookie
            header_name: Name of CSRF header
            exempt_paths: Paths to exempt from CSRF protection
        """
        super().__init__(app)
        self.secret_key = secret_key or settings.SECRET_KEY
        self.cookie_name = cookie_name
        self.header_name = header_name
        
        # Paths that don't need CSRF protection
        self.exempt_paths = exempt_paths or {
            "/api/v1/oauth/callback",  # OAuth callbacks
            "/api/v1/webhooks",  # Webhook endpoints
            "/health",
            "/docs",
            "/openapi.json",
        }
        
        # Methods that need CSRF protection
        self.protected_methods = {"POST", "PUT", "PATCH", "DELETE"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply CSRF protection to state-changing requests.
        """
        # Skip CSRF for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Skip CSRF for safe methods
        if request.method not in self.protected_methods:
            response = await call_next(request)
            # Set CSRF token for GET requests
            await self._set_csrf_token(request, response)
            return response
        
        # Validate CSRF token for protected methods
        if not await self._validate_csrf_token(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "csrf_validation_failed",
                    "message": "CSRF token validation failed"
                }
            )
        
        # Process request
        response = await call_next(request)
        
        return response
    
    async def _set_csrf_token(self, request: Request, response: Response) -> None:
        """
        Set CSRF token in response cookie.
        """
        # Check if token already exists
        existing_token = request.cookies.get(self.cookie_name)
        
        if not existing_token:
            # Generate new token
            token = secrets.token_urlsafe(32)
            
            # Set cookie
            response.set_cookie(
                key=self.cookie_name,
                value=token,
                max_age=3600,  # 1 hour
                httponly=False,  # Must be readable by JavaScript
                samesite="strict",
                secure=request.url.scheme == "https"
            )
            
            # Also add to response header for SPA
            response.headers["X-CSRF-Token"] = token
    
    async def _validate_csrf_token(self, request: Request) -> bool:
        """
        Validate CSRF token from request.
        """
        # Get token from cookie
        cookie_token = request.cookies.get(self.cookie_name)
        
        if not cookie_token:
            logger.warning("CSRF validation failed: No cookie token")
            return False
        
        # Get token from header or form
        header_token = request.headers.get(self.header_name)
        
        # Try to get from form data if not in header
        if not header_token and request.method == "POST":
            try:
                form = await request.form()
                header_token = form.get("csrf_token")
            except:
                pass
        
        if not header_token:
            logger.warning("CSRF validation failed: No header/form token")
            return False
        
        # Compare tokens
        return secrets.compare_digest(cookie_token, header_token)


def configure_cors(
    app,
    allowed_origins: Optional[List[str]] = None,
    allowed_methods: Optional[List[str]] = None,
    allowed_headers: Optional[List[str]] = None,
    allow_credentials: bool = True
) -> None:
    """
    Configure CORS for the application.
    
    Args:
        app: FastAPI application
        allowed_origins: List of allowed origins
        allowed_methods: List of allowed HTTP methods
        allowed_headers: List of allowed headers
        allow_credentials: Whether to allow credentials
    """
    # Default allowed origins
    if allowed_origins is None:
        allowed_origins = []
        
        # Add configured origins
        if hasattr(settings, 'CORS_ORIGINS'):
            allowed_origins.extend(settings.CORS_ORIGINS)
        
        # Add localhost for development
        if settings.ENVIRONMENT == "development":
            allowed_origins.extend([
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
            ])
        
        # Add production domain
        if hasattr(settings, 'FRONTEND_URL'):
            allowed_origins.append(settings.FRONTEND_URL)
    
    # Default allowed methods
    if allowed_methods is None:
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    
    # Default allowed headers
    if allowed_headers is None:
        allowed_headers = [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",
            "X-Requested-With",
            "X-API-Key",
        ]
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-CSRF-Token",
        ]
    )
    
    logger.info(f"CORS configured with origins: {allowed_origins}")


def add_security_middleware(
    app,
    enable_rate_limiting: bool = True,
    enable_csrf: bool = True,
    enable_security_headers: bool = True,
    redis_url: Optional[str] = None
) -> None:
    """
    Add all security middleware to the application.
    
    Args:
        app: FastAPI application
        enable_rate_limiting: Whether to enable rate limiting
        enable_csrf: Whether to enable CSRF protection
        enable_security_headers: Whether to enable security headers
        redis_url: Redis URL for rate limiting
    """
    # Configure CORS first (needs to be before other middleware)
    configure_cors(app)
    
    # Add security headers
    if enable_security_headers:
        app.add_middleware(
            SecurityHeadersMiddleware,
            strict_mode=settings.ENVIRONMENT == "production",
            enable_hsts=settings.ENVIRONMENT == "production",
            enable_csp=True
        )
        logger.info("Security headers middleware added")
    
    # Add rate limiting
    if enable_rate_limiting:
        redis_client = None
        if redis_url or hasattr(settings, 'REDIS_URL'):
            try:
                redis_client = redis.from_url(
                    redis_url or settings.REDIS_URL,
                    decode_responses=True
                )
                logger.info("Rate limiting middleware added with Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
        
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=redis_client,
            requests_per_minute=60,
            requests_per_hour=1000
        )
    
    # Add CSRF protection
    if enable_csrf:
        app.add_middleware(
            CSRFProtectionMiddleware,
            exempt_paths={
                "/api/v1/oauth/callback",
                "/api/v1/webhooks",
                "/health",
                "/docs",
                "/openapi.json",
            }
        )
        logger.info("CSRF protection middleware added")