"""
Request debugging middleware for enhanced error tracking.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logger import get_logger, set_request_context, clear_request_context
from core.errors import error_handler
from core.config import settings

logger = get_logger(__name__)


class DebuggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking and debugging."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.app = app
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Set logging context
        set_request_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_host=request.client.host if request.client else None,
        )
        
        # Log incoming request
        logger.debug(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "headers": dict(request.headers) if settings.DEBUG else None,
                "query_params": dict(request.query_params),
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            # Log response
            logger.log_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=response.headers.get("content-length"),
            )
            
            return response
            
        except Exception as exc:
            # Calculate duration even for errors
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            
            # Handle error with our error handler
            return await error_handler(request, exc)
            
        finally:
            # Clear context
            clear_request_context()


class RequestBodyMiddleware(BaseHTTPMiddleware):
    """Middleware to capture request body for debugging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only capture body in debug mode and for non-GET requests
        if settings.DEBUG and request.method != "GET":
            # Read body
            body = await request.body()
            
            # Store in request state for later use
            request.state.body = body
            
            # Log request body (be careful with sensitive data)
            if body and len(body) < 10000:  # Only log small bodies
                try:
                    import json
                    body_data = json.loads(body)
                    # Mask sensitive fields
                    for field in ["password", "token", "secret", "api_key"]:
                        if field in body_data:
                            body_data[field] = "***MASKED***"
                    
                    logger.debug(
                        f"Request body: {request.method} {request.url.path}",
                        extra={"body": body_data}
                    )
                except:
                    # Not JSON, log as text if small
                    if len(body) < 1000:
                        logger.debug(
                            f"Request body (raw): {request.method} {request.url.path}",
                            extra={"body": body.decode('utf-8', errors='ignore')}
                        )
            
            # Create new receive function that returns the stored body
            async def receive():
                return {"type": "http.request", "body": body}
            
            # Replace request.receive with our version
            request._receive = receive
        
        return await call_next(request)


class DatabaseQueryLoggingMiddleware:
    """Middleware to log slow database queries."""
    
    def __init__(self, app: ASGIApp, slow_query_threshold: float = 1.0):
        self.app = app
        self.slow_query_threshold = slow_query_threshold
        self.logger = get_logger("database")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Import here to avoid circular imports
            from sqlalchemy import event
            from core.database import engine
            
            queries = []
            
            def receive_before_execute(conn, clauseelement, multiparams, params, execution_options):
                queries.append({
                    "query": str(clauseelement),
                    "params": params,
                    "start_time": time.time()
                })
            
            def receive_after_execute(conn, clauseelement, multiparams, params, execution_options, result):
                if queries:
                    query_info = queries[-1]
                    duration = time.time() - query_info["start_time"]
                    
                    if duration > self.slow_query_threshold:
                        self.logger.log_database_query(
                            query=query_info["query"],
                            duration_ms=duration * 1000,
                            rows_affected=result.rowcount if hasattr(result, 'rowcount') else None,
                            params=query_info["params"] if settings.DEBUG else None
                        )
            
            # Attach listeners
            event.listen(engine.sync_engine, "before_execute", receive_before_execute)
            event.listen(engine.sync_engine, "after_execute", receive_after_execute)
            
            try:
                await self.app(scope, receive, send)
            finally:
                # Remove listeners
                event.remove(engine.sync_engine, "before_execute", receive_before_execute)
                event.remove(engine.sync_engine, "after_execute", receive_after_execute)
        else:
            await self.app(scope, receive, send)


class PerformanceProfilingMiddleware(BaseHTTPMiddleware):
    """Middleware for performance profiling in debug mode."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if settings.DEBUG and request.headers.get("X-Profile") == "true":
            import cProfile
            import pstats
            import io
            
            profiler = cProfile.Profile()
            profiler.enable()
            
            try:
                response = await call_next(request)
                
                profiler.disable()
                
                # Get profile stats
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
                ps.print_stats(20)  # Top 20 functions
                
                # Add profile data to response headers (truncated)
                profile_data = s.getvalue()
                if len(profile_data) > 1000:
                    profile_data = profile_data[:1000] + "..."
                
                # Log profile data
                logger.debug(
                    f"Performance profile: {request.method} {request.url.path}",
                    extra={"profile": profile_data}
                )
                
                return response
            except Exception as e:
                profiler.disable()
                raise
        else:
            return await call_next(request)