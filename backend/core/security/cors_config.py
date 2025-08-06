"""
CORS (Cross-Origin Resource Sharing) configuration and policies
"""
from typing import List, Optional, Dict, Set
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import re
import json
from urllib.parse import urlparse

from core.config import settings
from core.logging import logger
from core.redis import redis_client


class CORSConfig:
    """CORS configuration management"""
    
    def __init__(self):
        # Load allowed origins from settings
        self.allowed_origins = self._load_allowed_origins()
        self.allowed_origin_patterns = self._load_origin_patterns()
        
        # Default CORS settings
        self.allow_credentials = True
        self.allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allow_headers = [
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-API-Key",
            "X-Timestamp",
            "X-Signature"
        ]
        self.expose_headers = [
            "X-Total-Count",
            "X-Page-Count",
            "X-Current-Page",
            "X-Per-Page",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
        self.max_age = 3600  # 1 hour
        
        # Environment-specific settings
        self.strict_mode = settings.ENVIRONMENT == "production"
        
    def _load_allowed_origins(self) -> Set[str]:
        """Load allowed origins from configuration"""
        origins = set()
        
        # Add configured origins
        if hasattr(settings, 'CORS_ALLOWED_ORIGINS'):
            origins.update(settings.CORS_ALLOWED_ORIGINS)
        
        # Add default origins based on environment
        if settings.ENVIRONMENT == "development":
            origins.update([
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8000"
            ])
        
        # Add frontend URL if configured
        if hasattr(settings, 'FRONTEND_URL'):
            origins.add(settings.FRONTEND_URL)
        
        return origins
    
    def _load_origin_patterns(self) -> List[re.Pattern]:
        """Load regex patterns for dynamic origin validation"""
        patterns = []
        
        if hasattr(settings, 'CORS_ALLOWED_ORIGIN_PATTERNS'):
            for pattern in settings.CORS_ALLOWED_ORIGIN_PATTERNS:
                try:
                    patterns.append(re.compile(pattern))
                except re.error as e:
                    logger.error(f"Invalid CORS origin pattern '{pattern}': {e}")
        
        # Add subdomain pattern if configured
        if hasattr(settings, 'ALLOWED_DOMAIN'):
            # Allow all subdomains of the main domain
            domain = settings.ALLOWED_DOMAIN.replace('.', r'\.')
            patterns.append(re.compile(f"^https?://([a-zA-Z0-9-]+\\.)?{domain}$"))
        
        return patterns
    
    def is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed"""
        if not origin:
            return False
        
        # Check exact match
        if origin in self.allowed_origins:
            return True
        
        # Check patterns
        for pattern in self.allowed_origin_patterns:
            if pattern.match(origin):
                return True
        
        # In development, be more permissive
        if settings.ENVIRONMENT == "development":
            parsed = urlparse(origin)
            if parsed.hostname in ["localhost", "127.0.0.1"]:
                return True
        
        return False
    
    def get_cors_headers(self, origin: Optional[str] = None) -> Dict[str, str]:
        """Get CORS headers for response"""
        headers = {}
        
        if origin and self.is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
        elif not self.strict_mode and origin:
            # In non-strict mode, allow the origin but log it
            logger.warning(f"Allowing non-whitelisted origin in non-strict mode: {origin}")
            headers["Access-Control-Allow-Origin"] = origin
        
        if headers.get("Access-Control-Allow-Origin"):
            headers["Access-Control-Allow-Credentials"] = str(self.allow_credentials).lower()
            headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
            headers["Access-Control-Max-Age"] = str(self.max_age)
        
        return headers


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Enhanced CORS middleware with dynamic origin validation"""
    
    def __init__(self, app, cors_config: Optional[CORSConfig] = None):
        super().__init__(app)
        self.cors_config = cors_config or CORSConfig()
        self._origin_cache = {}
        self._cache_size = 1000
    
    async def dispatch(self, request: Request, call_next):
        """Handle CORS with enhanced security"""
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            return self._handle_preflight(request, origin)
        
        # Check origin for non-preflight requests
        if origin:
            # Check cache first
            if origin in self._origin_cache:
                is_allowed = self._origin_cache[origin]
            else:
                is_allowed = self.cors_config.is_origin_allowed(origin)
                
                # Cache result
                if len(self._origin_cache) < self._cache_size:
                    self._origin_cache[origin] = is_allowed
            
            # Log suspicious origins
            if not is_allowed and self.cors_config.strict_mode:
                logger.warning(
                    f"Blocked request from unauthorized origin: {origin} "
                    f"to {request.url.path}"
                )
                # In strict mode, you might want to block the request
                # return Response(status_code=403)
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers to response
        if origin:
            cors_headers = self.cors_config.get_cors_headers(origin)
            for header, value in cors_headers.items():
                response.headers[header] = value
        
        # Add security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
    
    def _handle_preflight(self, request: Request, origin: Optional[str]) -> Response:
        """Handle CORS preflight requests"""
        if not origin:
            return Response(status_code=400)
        
        # Get requested method and headers
        requested_method = request.headers.get("Access-Control-Request-Method")
        requested_headers = request.headers.get("Access-Control-Request-Headers")
        
        # Validate origin
        if not self.cors_config.is_origin_allowed(origin):
            if self.cors_config.strict_mode:
                return Response(status_code=403)
            else:
                logger.warning(f"Preflight request from non-whitelisted origin: {origin}")
        
        # Validate method
        if requested_method and requested_method not in self.cors_config.allow_methods:
            return Response(status_code=403)
        
        # Validate headers
        if requested_headers:
            headers = [h.strip() for h in requested_headers.split(",")]
            for header in headers:
                if header not in self.cors_config.allow_headers:
                    logger.warning(f"Preflight request with non-allowed header: {header}")
                    if self.cors_config.strict_mode:
                        return Response(status_code=403)
        
        # Build response
        response = Response(status_code=204)
        cors_headers = self.cors_config.get_cors_headers(origin)
        
        for header, value in cors_headers.items():
            response.headers[header] = value
        
        return response


class OriginWhitelist:
    """Manage dynamic origin whitelist"""
    
    def __init__(self, db=None):
        self.db = db
        self._cache_ttl = 300  # 5 minutes
    
    async def add_origin(
        self,
        origin: str,
        description: str,
        agency_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Add origin to whitelist"""
        # Validate origin format
        try:
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid origin format")
        except Exception:
            return False
        
        # Store in database (if available) or Redis
        key = f"cors_whitelist:{origin}"
        data = {
            "origin": origin,
            "description": description,
            "agency_id": agency_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await redis_client.setex(
            key,
            self._cache_ttl,
            json.dumps(data)
        )
        
        logger.info(f"Added origin to whitelist: {origin}")
        return True
    
    async def remove_origin(self, origin: str) -> bool:
        """Remove origin from whitelist"""
        key = f"cors_whitelist:{origin}"
        result = await redis_client.delete(key)
        
        if result:
            logger.info(f"Removed origin from whitelist: {origin}")
        
        return bool(result)
    
    async def is_whitelisted(self, origin: str) -> bool:
        """Check if origin is in whitelist"""
        key = f"cors_whitelist:{origin}"
        data = await redis_client.get(key)
        
        if not data:
            return False
        
        try:
            whitelist_entry = json.loads(data)
            
            # Check expiration
            if whitelist_entry.get("expires_at"):
                expires_at = datetime.fromisoformat(whitelist_entry["expires_at"])
                if expires_at < datetime.utcnow():
                    await self.remove_origin(origin)
                    return False
            
            return True
        except Exception:
            return False
    
    async def get_whitelisted_origins(self) -> List[Dict[str, Any]]:
        """Get all whitelisted origins"""
        pattern = "cors_whitelist:*"
        origins = []
        
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern)
            
            for key in keys:
                data = await redis_client.get(key)
                if data:
                    try:
                        origins.append(json.loads(data))
                    except Exception:
                        pass
            
            if cursor == 0:
                break
        
        return origins


def get_cors_middleware(app) -> CORSMiddleware:
    """Get configured CORS middleware for FastAPI"""
    cors_config = CORSConfig()
    
    # Use FastAPI's built-in CORS middleware with our configuration
    return CORSMiddleware(
        app,
        allow_origins=list(cors_config.allowed_origins),
        allow_credentials=cors_config.allow_credentials,
        allow_methods=cors_config.allow_methods,
        allow_headers=cors_config.allow_headers,
        expose_headers=cors_config.expose_headers,
        max_age=cors_config.max_age
    )


def get_dynamic_cors_middleware(app) -> DynamicCORSMiddleware:
    """Get dynamic CORS middleware with pattern matching"""
    return DynamicCORSMiddleware(app)


# Utility functions
def validate_origin(origin: str) -> bool:
    """Validate origin format"""
    try:
        parsed = urlparse(origin)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def get_origin_info(origin: str) -> Dict[str, Any]:
    """Get information about an origin"""
    try:
        parsed = urlparse(origin)
        return {
            "origin": origin,
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "is_secure": parsed.scheme == "https",
            "is_localhost": parsed.hostname in ["localhost", "127.0.0.1"]
        }
    except Exception:
        return {"origin": origin, "error": "Invalid origin"}


# Example configuration for different environments
CORS_CONFIGS = {
    "development": {
        "allowed_origins": [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173"
        ],
        "allowed_origin_patterns": [
            r"^http://localhost:\d+$",
            r"^http://127\.0\.0\.1:\d+$"
        ],
        "strict_mode": False
    },
    "staging": {
        "allowed_origins": [
            "https://staging.example.com",
            "https://app-staging.example.com"
        ],
        "allowed_origin_patterns": [
            r"^https://[a-zA-Z0-9-]+\.staging\.example\.com$"
        ],
        "strict_mode": True
    },
    "production": {
        "allowed_origins": [
            "https://app.example.com",
            "https://www.example.com"
        ],
        "allowed_origin_patterns": [
            r"^https://[a-zA-Z0-9-]+\.example\.com$"
        ],
        "strict_mode": True
    }
}