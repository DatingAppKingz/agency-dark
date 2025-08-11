"""
Security middleware for content protection.
Implements geo-blocking and security headers.
"""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone
import logging
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import geoip2.database
import geoip2.errors
from starlette.middleware.base import BaseHTTPMiddleware
import os

from core.config import settings

logger = logging.getLogger(__name__)


class ContentSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for content security and compliance.
    Handles geo-blocking and security headers.
    """
    
    # Countries where content is restricted
    RESTRICTED_COUNTRIES: Set[str] = {
        "KP",  # North Korea
        # Add other restricted countries as needed
    }
    
    # Paths that bypass security checks (public endpoints)
    BYPASS_PATHS: Set[str] = {
        "/health",
        "/docs",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/public",
        "/.well-known",
        "/robots.txt",
        "/favicon.ico",
        "/blocked",
        "/terms",
        "/privacy",
    }
    
    def __init__(
        self,
        app,
        geoip_database_path: Optional[str] = None,
        strict_mode: bool = True,
        bypass_for_testing: bool = False
    ):
        """
        Initialize the middleware.
        
        Args:
            app: FastAPI application
            geoip_database_path: Path to GeoIP2 database
            strict_mode: Enable strict compliance mode
            bypass_for_testing: Bypass checks for testing
        """
        super().__init__(app)
        self.strict_mode = strict_mode
        self.bypass_for_testing = bypass_for_testing
        
        # Initialize GeoIP reader
        self.geoip_reader = None
        if geoip_database_path and os.path.exists(geoip_database_path):
            try:
                self.geoip_reader = geoip2.database.Reader(geoip_database_path)
                logger.info(f"GeoIP database loaded from {geoip_database_path}")
            except Exception as e:
                logger.error(f"Failed to load GeoIP database: {e}")
        else:
            logger.warning("GeoIP database not available. Geo-blocking disabled.")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process the request through security checks.
        """
        # Check if path should bypass security
        if self._should_bypass(request.url.path):
            return await call_next(request)
        
        # Bypass all checks if in testing mode
        if self.bypass_for_testing:
            return await call_next(request)
        
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Perform geo-blocking check
            country_code, region_code = await self._get_location(client_ip)
            
            if country_code:
                # Check if country is blocked
                if country_code in self.RESTRICTED_COUNTRIES:
                    logger.warning(f"Blocked access from restricted country: {country_code}")
                    return self._create_blocked_response(country_code)
                
                # Store location in request state
                request.state.country_code = country_code
                request.state.region_code = region_code
            
            # Process request
            response = await call_next(request)
            
            # Add security headers to response
            response = self._add_security_headers(response, country_code)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # In case of error, allow request but log it
            return await call_next(request)
    
    def _should_bypass(self, path: str) -> bool:
        """
        Check if the path should bypass security checks.
        """
        # Check exact matches
        if path in self.BYPASS_PATHS:
            return True
        
        # Check prefixes
        for bypass_path in self.BYPASS_PATHS:
            if path.startswith(bypass_path):
                return True
        
        return False
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get the real client IP address.
        Handles proxies and load balancers.
        """
        # Check for proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check for other proxy headers
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "127.0.0.1"
    
    async def _get_location(self, ip_address: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get country and region code from IP address.
        
        Returns:
            Tuple of (country_code, region_code)
        """
        if not self.geoip_reader:
            return None, None
        
        try:
            response = self.geoip_reader.city(ip_address)
            country_code = response.country.iso_code
            
            # For US, get state code
            region_code = None
            if country_code == "US" and response.subdivisions:
                region_code = response.subdivisions[0].iso_code
            
            return country_code, region_code
            
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP {ip_address} not found in GeoIP database")
            return None, None
        except Exception as e:
            logger.error(f"GeoIP lookup error: {e}")
            return None, None
    
    def _create_blocked_response(self, country_code: str) -> JSONResponse:
        """
        Create response for blocked countries.
        """
        return JSONResponse(
            status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            content={
                "error": "content_unavailable",
                "message": "This content is not available in your region",
                "country_code": country_code,
                "support_url": "https://support.agencydark.com/geo-restrictions"
            }
        )
    
    def _add_security_headers(self, response: Response, country_code: Optional[str]) -> Response:
        """
        Add security headers to the response.
        """
        # Add geo-location header if available
        if country_code:
            response.headers["X-Geo-Country"] = country_code
        
        return response