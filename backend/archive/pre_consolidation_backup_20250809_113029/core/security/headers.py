"""
Security headers middleware for FastAPI applications.
"""

from typing import Dict, Optional, Union, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


# Default security headers configuration
DEFAULT_SECURITY_HEADERS = {
    # Prevent XSS attacks
    "X-XSS-Protection": "1; mode=block",
    
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    
    # Clickjacking protection
    "X-Frame-Options": "DENY",
    
    # Force HTTPS
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    
    # Referrer policy
    "Referrer-Policy": "strict-origin-when-cross-origin",
    
    # Permissions policy (formerly Feature Policy)
    "Permissions-Policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "accelerometer=()"
    ),
}


def get_csp_header(nonce: Optional[str] = None) -> str:
    """Generate Content Security Policy header."""
    # Base CSP directives
    csp_directives = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'" if settings.DEBUG else f"'nonce-{nonce}'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "https:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'", settings.FRONTEND_URL],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "object-src": ["'none'"],
        "upgrade-insecure-requests": [],
    }
    
    # Build CSP string
    csp_parts = []
    for directive, values in csp_directives.items():
        if values:
            csp_parts.append(f"{directive} {' '.join(values)}")
        else:
            csp_parts.append(directive)
    
    return "; ".join(csp_parts)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    def __init__(
        self,
        app: ASGIApp,
        headers: Optional[Dict[str, str]] = None,
        csp_enabled: bool = True,
        nonce_generator: Optional[callable] = None
    ):
        super().__init__(app)
        self.security_headers = headers or DEFAULT_SECURITY_HEADERS.copy()
        self.csp_enabled = csp_enabled
        self.nonce_generator = nonce_generator or self._generate_nonce
        
        # Add CORS headers if configured
        if settings.CORS_ORIGINS:
            self.security_headers["Access-Control-Allow-Origin"] = ",".join(settings.CORS_ORIGINS)
            self.security_headers["Access-Control-Allow-Credentials"] = "true"
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        # Generate nonce for CSP
        nonce = self.nonce_generator() if self.csp_enabled else None
        
        # Store nonce in request state for use in templates
        if nonce:
            request.state.csp_nonce = nonce
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add CSP header
        if self.csp_enabled:
            response.headers["Content-Security-Policy"] = get_csp_header(nonce)
        
        # Add cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        # Remove sensitive headers
        sensitive_headers = ["Server", "X-Powered-By"]
        for header in sensitive_headers:
            response.headers.pop(header, None)
        
        return response
    
    @staticmethod
    def _generate_nonce() -> str:
        """Generate a random nonce for CSP."""
        import secrets
        return secrets.token_urlsafe(16)
    
    @staticmethod
    def _is_sensitive_endpoint(path: str) -> bool:
        """Check if endpoint handles sensitive data."""
        sensitive_patterns = [
            "/auth/",
            "/users/",
            "/admin/",
            "/api/v1/auth/",
            "/api/v1/users/",
        ]
        return any(pattern in path for pattern in sensitive_patterns)


def security_headers_config(
    environment: str = "production",
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Get security headers configuration for environment."""
    headers = DEFAULT_SECURITY_HEADERS.copy()
    
    # Environment-specific adjustments
    if environment == "development":
        # Relax some policies for development
        headers["X-Frame-Options"] = "SAMEORIGIN"
        headers.pop("Strict-Transport-Security", None)  # No HTTPS in dev
    
    elif environment == "staging":
        # Staging configuration
        headers["X-Robots-Tag"] = "noindex, nofollow"  # Prevent indexing
    
    elif environment == "production":
        # Strict production configuration
        headers["X-Frame-Options"] = "DENY"
        headers["X-Robots-Tag"] = "index, follow"
    
    # Apply custom headers
    if custom_headers:
        headers.update(custom_headers)
    
    return headers


class SecurityHeadersConfig:
    """Configuration for security headers."""
    
    def __init__(self):
        self.headers = DEFAULT_SECURITY_HEADERS.copy()
        self.csp_directives = {}
        self.cors_enabled = False
        self.cors_origins = []
    
    def set_header(self, name: str, value: str) -> "SecurityHeadersConfig":
        """Set a security header."""
        self.headers[name] = value
        return self
    
    def enable_cors(self, origins: list) -> "SecurityHeadersConfig":
        """Enable CORS with specified origins."""
        self.cors_enabled = True
        self.cors_origins = origins
        return self
    
    def set_csp_directive(self, directive: str, values: list) -> "SecurityHeadersConfig":
        """Set a CSP directive."""
        self.csp_directives[directive] = values
        return self
    
    def build(self) -> Dict[str, str]:
        """Build final headers configuration."""
        headers = self.headers.copy()
        
        # Add CORS headers
        if self.cors_enabled and self.cors_origins:
            headers["Access-Control-Allow-Origin"] = ",".join(self.cors_origins)
            headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            headers["Access-Control-Allow-Credentials"] = "true"
        
        # Build CSP
        if self.csp_directives:
            csp_parts = []
            for directive, values in self.csp_directives.items():
                csp_parts.append(f"{directive} {' '.join(values)}")
            headers["Content-Security-Policy"] = "; ".join(csp_parts)
        
        return headers


# Security headers validation
def validate_security_headers(headers: Dict[str, str]) -> Dict[str, Union[bool, str]]:
    """Validate security headers configuration."""
    validation_results = {}
    
    # Check required headers
    required_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Strict-Transport-Security",
        "Content-Security-Policy",
    ]
    
    for header in required_headers:
        if header in headers:
            validation_results[header] = True
        else:
            validation_results[header] = f"Missing required header: {header}"
    
    # Validate header values
    if headers.get("X-Frame-Options") not in ["DENY", "SAMEORIGIN"]:
        validation_results["X-Frame-Options"] = "Invalid value, should be DENY or SAMEORIGIN"
    
    if headers.get("X-Content-Type-Options") != "nosniff":
        validation_results["X-Content-Type-Options"] = "Should be set to 'nosniff'"
    
    # Check HSTS configuration
    hsts = headers.get("Strict-Transport-Security", "")
    if "max-age=" not in hsts:
        validation_results["Strict-Transport-Security"] = "Missing max-age directive"
    elif "includeSubDomains" not in hsts:
        validation_results["Strict-Transport-Security"] = "Consider adding includeSubDomains"
    
    return validation_results


# OWASP secure headers check
OWASP_HEADERS = {
    "X-Content-Type-Options": {
        "required": True,
        "recommended_value": "nosniff",
        "description": "Prevents MIME type sniffing"
    },
    "X-Frame-Options": {
        "required": True,
        "recommended_value": "DENY",
        "description": "Prevents clickjacking attacks"
    },
    "X-XSS-Protection": {
        "required": True,
        "recommended_value": "1; mode=block",
        "description": "Enables XSS filter in browsers"
    },
    "Strict-Transport-Security": {
        "required": True,
        "recommended_value": "max-age=31536000; includeSubDomains; preload",
        "description": "Forces HTTPS connections"
    },
    "Content-Security-Policy": {
        "required": True,
        "recommended_value": "default-src 'self'",
        "description": "Controls resource loading"
    },
    "Referrer-Policy": {
        "required": False,
        "recommended_value": "strict-origin-when-cross-origin",
        "description": "Controls referrer information"
    },
    "Permissions-Policy": {
        "required": False,
        "recommended_value": "geolocation=(), microphone=(), camera=()",
        "description": "Controls browser features"
    },
    "Cache-Control": {
        "required": False,
        "recommended_value": "no-store",
        "description": "Controls caching for sensitive data"
    }
}


def check_owasp_compliance(headers: Dict[str, str]) -> Dict[str, Any]:
    """Check headers against OWASP recommendations."""
    compliance_report = {
        "compliant": True,
        "score": 0,
        "max_score": len(OWASP_HEADERS),
        "issues": [],
        "recommendations": []
    }
    
    for header_name, config in OWASP_HEADERS.items():
        if header_name in headers:
            compliance_report["score"] += 1
            
            # Check recommended value
            if headers[header_name] != config["recommended_value"]:
                compliance_report["recommendations"].append({
                    "header": header_name,
                    "current": headers[header_name],
                    "recommended": config["recommended_value"],
                    "description": config["description"]
                })
        else:
            if config["required"]:
                compliance_report["compliant"] = False
                compliance_report["issues"].append({
                    "header": header_name,
                    "severity": "high",
                    "description": f"Missing required header: {header_name}"
                })
            else:
                compliance_report["recommendations"].append({
                    "header": header_name,
                    "recommended": config["recommended_value"],
                    "description": config["description"]
                })
    
    compliance_report["percentage"] = (
        compliance_report["score"] / compliance_report["max_score"] * 100
    )
    
    return compliance_report