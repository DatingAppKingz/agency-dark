"""
Monitoring middleware for API request tracking.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.monitoring.collectors.api_collector import api_collector
from core.monitoring.models import PerformanceProfile
from core.database import get_db
from core.config import settings

logger = logging.getLogger(__name__)


class MonitoringRoute(APIRoute):
    """Custom route class for monitoring."""
    
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        
        async def monitoring_route_handler(request: Request) -> Response:
            # Generate request ID
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            
            # Track performance
            start_time = time.time()
            request.state.start_time = start_time
            
            # Increment active requests
            api_collector.increment_active_requests()
            
            try:
                # Call the actual route handler
                response: Response = await original_route_handler(request)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Track metrics
                endpoint = request.url.path
                method = request.method
                status_code = response.status_code
                
                api_collector.track_request(endpoint, method, status_code, duration_ms)
                
                # Add response headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                
                # Log slow requests
                if duration_ms > 1000:  # Log requests taking more than 1 second
                    logger.warning(
                        f"Slow request: {method} {endpoint} took {duration_ms:.2f}ms"
                    )
                
                return response
                
            except Exception as e:
                # Track error
                duration_ms = (time.time() - start_time) * 1000
                endpoint = request.url.path
                method = request.method
                
                api_collector.track_request(endpoint, method, 500, duration_ms)
                
                # Re-raise the exception
                raise
                
            finally:
                # Decrement active requests
                api_collector.decrement_active_requests()
        
        return monitoring_route_handler


async def monitoring_middleware(request: Request, call_next):
    """Monitoring middleware for request tracking."""
    # Generate request ID if not already set
    if not hasattr(request.state, 'request_id'):
        request.state.request_id = str(uuid.uuid4())
    
    # Start timing
    start_time = time.time()
    request.state.start_time = start_time
    
    # Track performance profile
    profile = PerformanceProfile(
        request_id=request.state.request_id,
        endpoint=request.url.path,
        method=request.method
    )
    
    # Initialize timing
    request.state.db_time = 0
    request.state.cache_time = 0
    request.state.external_api_time = 0
    request.state.query_count = 0
    request.state.cache_hits = 0
    request.state.cache_misses = 0
    request.state.slow_queries = []
    
    # Increment active requests
    api_collector.increment_active_requests()
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate total duration
        total_duration = time.time() - start_time
        duration_ms = total_duration * 1000
        
        # Update profile
        profile.total_duration_ms = duration_ms
        profile.db_duration_ms = getattr(request.state, 'db_time', 0) * 1000
        profile.cache_duration_ms = getattr(request.state, 'cache_time', 0) * 1000
        profile.external_api_duration_ms = getattr(request.state, 'external_api_time', 0) * 1000
        profile.processing_duration_ms = duration_ms - profile.db_duration_ms - profile.cache_duration_ms - profile.external_api_duration_ms
        profile.query_count = getattr(request.state, 'query_count', 0)
        profile.cache_hits = getattr(request.state, 'cache_hits', 0)
        profile.cache_misses = getattr(request.state, 'cache_misses', 0)
        profile.slow_queries = getattr(request.state, 'slow_queries', [])
        profile.status_code = response.status_code
        
        # Get user and agency info if available
        if hasattr(request.state, 'user'):
            profile.user_id = request.state.user.id
            profile.agency_id = request.state.user.agency_id
        
        # Track in API collector
        api_collector.track_request(
            request.url.path,
            request.method,
            response.status_code,
            duration_ms
        )
        
        # Save performance profile for detailed requests
        if duration_ms > 100 or profile.query_count > 10:  # Save profiles for slow or complex requests
            try:
                async for db in get_db():
                    db.add(profile)
                    await db.commit()
                    break
            except Exception as e:
                logger.error(f"Error saving performance profile: {e}")
        
        # Add response headers
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        # Log slow requests
        if duration_ms > 1000:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms (DB: {profile.db_duration_ms:.2f}ms, "
                f"Cache: {profile.cache_duration_ms:.2f}ms)"
            )
        
        return response
        
    except Exception as e:
        # Track error
        duration_ms = (time.time() - start_time) * 1000
        
        api_collector.track_request(
            request.url.path,
            request.method,
            500,
            duration_ms
        )
        
        # Update profile with error
        profile.total_duration_ms = duration_ms
        profile.status_code = 500
        profile.error_details = {"error": str(e), "type": type(e).__name__}
        
        # Save error profile
        try:
            async for db in get_db():
                db.add(profile)
                await db.commit()
                break
        except Exception as save_error:
            logger.error(f"Error saving error profile: {save_error}")
        
        raise
        
    finally:
        # Decrement active requests
        api_collector.decrement_active_requests()


def track_db_query(request: Request, query_time: float, query: str = None):
    """Track database query time."""
    if hasattr(request.state, 'db_time'):
        request.state.db_time += query_time
        request.state.query_count = getattr(request.state, 'query_count', 0) + 1
        
        # Track slow queries
        if query_time > 0.1 and query:  # Queries taking more than 100ms
            if not hasattr(request.state, 'slow_queries'):
                request.state.slow_queries = []
            request.state.slow_queries.append({
                "query": query[:200],  # Truncate long queries
                "duration_ms": query_time * 1000
            })


def track_cache_operation(request: Request, operation_time: float, hit: bool = True):
    """Track cache operation time."""
    if hasattr(request.state, 'cache_time'):
        request.state.cache_time += operation_time
        
        if hit:
            request.state.cache_hits = getattr(request.state, 'cache_hits', 0) + 1
        else:
            request.state.cache_misses = getattr(request.state, 'cache_misses', 0) + 1


def track_external_api_call(request: Request, api_time: float):
    """Track external API call time."""
    if hasattr(request.state, 'external_api_time'):
        request.state.external_api_time += api_time