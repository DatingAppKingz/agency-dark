"""
Advanced rate limiting middleware with dynamic configuration.
"""
import time
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import asyncio

from core.rate_limit.service import rate_limit_service
from models.rate_limit import RateLimitType
from core.database import get_db
from core.logger import get_logger
from core.geo import get_country_from_ip  # Assuming we have geo-location service

logger = get_logger(__name__)


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware with dynamic configuration and cost-based throttling.
    """
    
    # Endpoints to exclude from rate limiting
    EXCLUDED_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/csrf-token",
        "/api/v1/auth/password-reset/request",
        "/api/v1/auth/password-reset/confirm"
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request with advanced rate limiting."""
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Skip OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Extract rate limit information
        rate_limit_info = await self._extract_rate_limit_info(request)
        
        if not rate_limit_info["identifier"]:
            # No identifier found, allow request
            return await call_next(request)
        
        # Get database session
        db = None
        try:
            async for session in get_db():
                db = session
                break
            
            if not db:
                logger.error("Could not get database session for rate limiting")
                return await call_next(request)
            
            # Check rate limit
            allowed, info = await rate_limit_service.check_rate_limit(
                db=db,
                identifier=rate_limit_info["identifier"],
                identifier_type=rate_limit_info["type"],
                endpoint=request.url.path,
                method=request.method,
                user=rate_limit_info.get("user"),
                api_key=rate_limit_info.get("api_key"),
                ip_address=rate_limit_info["ip_address"],
                country_code=rate_limit_info.get("country_code"),
                request_size=rate_limit_info.get("request_size", 0),
                user_agent=rate_limit_info.get("user_agent")
            )
            
            if not allowed:
                # Rate limit exceeded
                return self._rate_limit_exceeded_response(info)
            
            # Add rate limit headers
            response = await call_next(request)
            
            # Add rate limit info to headers
            if info.get("all_checks"):
                for check in info["all_checks"]:
                    if check[1].get("allowed"):
                        # Add headers for successful checks
                        limit_info = check[1]
                        if "tokens_remaining" in limit_info:
                            response.headers[f"X-RateLimit-{limit_info['period']}-Remaining"] = str(
                                int(limit_info["tokens_remaining"])
                            )
                        elif "current_count" in limit_info:
                            remaining = limit_info["limit"] - limit_info["current_count"]
                            response.headers[f"X-RateLimit-{limit_info['period']}-Remaining"] = str(
                                max(0, remaining)
                            )
            
            # Add cost header if applicable
            if info.get("cost", 1) > 1:
                response.headers["X-Request-Cost"] = str(info["cost"])
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request on error
            return await call_next(request)
        finally:
            if db:
                await db.close()
    
    async def _extract_rate_limit_info(self, request: Request) -> Dict[str, Any]:
        """Extract rate limiting information from request."""
        info = {
            "identifier": None,
            "type": None,
            "ip_address": None,
            "country_code": None,
            "user": None,
            "api_key": None,
            "request_size": 0,
            "user_agent": None
        }
        
        # Get IP address
        if request.client:
            info["ip_address"] = request.client.host
            
            # Get country code (if geo service available)
            try:
                info["country_code"] = await get_country_from_ip(info["ip_address"])
            except:
                pass
        
        # Get user agent
        info["user_agent"] = request.headers.get("user-agent")
        
        # Get request size
        if request.headers.get("content-length"):
            try:
                info["request_size"] = int(request.headers["content-length"])
            except:
                pass
        
        # Check for authenticated user
        if hasattr(request.state, "user"):
            user = request.state.user
            info["identifier"] = str(user.id)
            info["type"] = RateLimitType.USER
            info["user"] = user
        
        # Check for API key
        elif hasattr(request.state, "api_key"):
            api_key = request.state.api_key
            info["identifier"] = str(api_key.id)
            info["type"] = RateLimitType.API_KEY
            info["api_key"] = api_key
        
        # Fall back to IP-based limiting
        elif info["ip_address"]:
            info["identifier"] = info["ip_address"]
            info["type"] = RateLimitType.IP
        
        return info
    
    def _rate_limit_exceeded_response(self, info: Dict[str, Any]) -> Response:
        """Create rate limit exceeded response."""
        # Find the violated limit info
        violated_limit = info.get("violated_limit", {})
        retry_after = violated_limit.get("retry_after_seconds", 60)
        
        # Create error response
        error_detail = {
            "error": "Rate limit exceeded",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "limit_type": violated_limit.get("period", "unknown"),
            "retry_after_seconds": retry_after
        }
        
        # Add additional info for debugging (in non-production)
        if violated_limit.get("config_name"):
            error_detail["limit_config"] = violated_limit["config_name"]
        
        if violated_limit.get("cost"):
            error_detail["request_cost"] = violated_limit["cost"]
        
        response = JSONResponse(
            status_code=429,
            content=error_detail
        )
        
        # Add standard rate limit headers
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(violated_limit.get("limit", "unknown"))
        
        # Add remaining tokens/count if available
        if "tokens_remaining" in violated_limit:
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(
                int(time.time()) + retry_after
            )
        
        return response


class CostBasedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Specialized middleware for cost-based rate limiting.
    
    This can be used in addition to the main rate limit middleware
    for endpoints that need special cost calculation.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Apply cost-based rate limiting."""
        # Measure request processing time
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        process_time = (time.time() - start_time) * 1000  # in ms
        
        # Add processing time header
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # If this was an expensive operation, log it
        if process_time > 1000:  # More than 1 second
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}ms"
            )
        
        return response


class GeographicRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Geographic-based rate limiting middleware.
    
    Applies different rate limits based on request origin.
    """
    
    # High-risk countries (example list)
    HIGH_RISK_COUNTRIES = {"CN", "RU", "KP", "IR"}
    
    # Blocked countries (sanctions, legal requirements)
    BLOCKED_COUNTRIES = {"KP", "IR"}
    
    async def dispatch(self, request: Request, call_next):
        """Apply geographic rate limiting."""
        # Get client IP
        if not request.client:
            return await call_next(request)
        
        ip_address = request.client.host
        
        try:
            # Get country code
            country_code = await get_country_from_ip(ip_address)
            
            if not country_code:
                # Could not determine country, apply default limits
                return await call_next(request)
            
            # Check if country is blocked
            if country_code in self.BLOCKED_COUNTRIES:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Access denied",
                        "error_code": "COUNTRY_BLOCKED",
                        "message": "Service is not available in your region"
                    }
                )
            
            # Add country code to request state for rate limiter
            request.state.country_code = country_code
            
            # Add country header to response
            response = await call_next(request)
            response.headers["X-Country-Code"] = country_code
            
            # Add warning header for high-risk countries
            if country_code in self.HIGH_RISK_COUNTRIES:
                response.headers["X-Risk-Level"] = "high"
            
            return response
            
        except Exception as e:
            logger.error(f"Geographic rate limit error: {e}")
            # Fail open
            return await call_next(request)


class AdaptiveRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Adaptive rate limiting based on system load and user behavior.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self._system_load = 0.5  # Default medium load
        self._last_load_check = 0
        self._load_check_interval = 60  # seconds
    
    async def dispatch(self, request: Request, call_next):
        """Apply adaptive rate limiting."""
        # Update system load periodically
        await self._update_system_load()
        
        # Add system load to request state
        request.state.system_load = self._system_load
        
        # Get user reputation if available
        user_reputation = 1.0  # Default
        
        if hasattr(request.state, "user"):
            user = request.state.user
            # Calculate reputation based on user history
            user_reputation = await self._calculate_user_reputation(user)
            request.state.user_reputation = user_reputation
        
        # Process request
        response = await call_next(request)
        
        # Add adaptive headers
        response.headers["X-System-Load"] = f"{self._system_load:.2f}"
        
        if user_reputation != 1.0:
            response.headers["X-User-Reputation"] = f"{user_reputation:.2f}"
        
        return response
    
    async def _update_system_load(self):
        """Update system load metric."""
        current_time = time.time()
        
        if current_time - self._last_load_check > self._load_check_interval:
            try:
                # Get system metrics (CPU, memory, request queue, etc.)
                # This is a simplified example
                import psutil
                
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_percent = psutil.virtual_memory().percent
                
                # Calculate load (0.0 to 1.0)
                self._system_load = (cpu_percent + memory_percent) / 200.0
                self._system_load = min(1.0, max(0.0, self._system_load))
                
                self._last_load_check = current_time
                
            except Exception as e:
                logger.error(f"Failed to update system load: {e}")
    
    async def _calculate_user_reputation(self, user) -> float:
        """
        Calculate user reputation based on behavior.
        
        Returns value between 0.0 (bad) and 2.0 (excellent).
        """
        # This is a simplified example
        # In production, this would query user history, violations, etc.
        
        # Check if user has recent violations
        async for db in get_db():
            try:
                from sqlalchemy import select, func
                from models.rate_limit import RateLimitViolation
                from datetime import datetime, timedelta
                
                # Count recent violations
                result = await db.execute(
                    select(func.count(RateLimitViolation.id)).where(
                        and_(
                            RateLimitViolation.user_id == user.id,
                            RateLimitViolation.timestamp >= datetime.utcnow() - timedelta(days=7)
                        )
                    )
                )
                violation_count = result.scalar() or 0
                
                # Calculate reputation
                if violation_count == 0:
                    return 1.5  # Good reputation
                elif violation_count < 5:
                    return 1.0  # Normal
                elif violation_count < 20:
                    return 0.7  # Reduced
                else:
                    return 0.5  # Poor reputation
                    
            except Exception as e:
                logger.error(f"Failed to calculate user reputation: {e}")
                return 1.0
            finally:
                await db.close()
        
        return 1.0