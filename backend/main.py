from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import logging
import uvicorn
from core.config import settings
from core.database import engine, create_tables
from core.redis import redis_client
from api.v1.api import api_router
from core.middleware.tenant import TenantMiddleware
from core.middleware.logging import LoggingMiddleware
from core.middleware.auth import AuthenticationMiddleware
from core.middleware.security import SecurityMiddleware, APIKeyMiddleware
from core.middleware.enhanced_security import EnhancedAPIKeyMiddleware, APIKeyRateLimitMiddleware, SecurityHeadersMiddleware
from core.middleware.rate_limit import AdvancedRateLimitMiddleware
from core.middleware.fraud_detection import FraudDetectionMiddleware
from core.middleware.debugging import DebuggingMiddleware, RequestBodyMiddleware, DatabaseQueryLoggingMiddleware, PerformanceProfilingMiddleware
from core.middleware.api_usage import APIUsageMiddleware
from core.middleware.csrf import CSRFMiddleware
from core.middleware.validation import ValidationMiddleware
from core.tasks.sync_tasks import start_sync_scheduler, stop_sync_scheduler
from core.realtime.server import socket_app
from core.cache import initialize_cache, shutdown_cache
from core.monitoring import monitoring_service
from core.middleware.monitoring import monitoring_middleware
from core.openapi import custom_openapi, setup_api_docs
from core.errors import error_handler
from core.logger import get_logger
from services.webhook_queue import get_webhook_processor, shutdown_processor
from services.sync_scheduler import get_sync_scheduler, shutdown_scheduler
from middleware.i18n import I18nMiddleware
from middleware.logging_context import LoggingContextMiddleware, UserContextMiddleware
from logging_config import configure_structured_logging
from core.security.api_keys.auth_middleware import log_api_key_usage
from core.middleware.audit import AuditLoggingMiddleware, ComplianceAuditMiddleware

# Configure structured logging
configure_structured_logging()

# Use our enhanced logger instead of basic logging
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    # await create_tables()  # Commented out for PgBouncer compatibility
    
    # Initialize Redis connection
    await redis_client.connect()
    logger.info("Redis connected")
    
    # Initialize cache system
    await initialize_cache()
    
    # Initialize advanced cache manager
    from core.cache_manager import cache_manager
    await cache_manager.initialize()
    logger.info("Advanced cache manager initialized")
    
    # Start background services
    # Start background sync scheduler
    await start_sync_scheduler()
    logger.info("Sync scheduler started")
    
    # Start monitoring service
    await monitoring_service.start()
    logger.info("Monitoring service started")
    
    # Start real-time analytics engine
    from modules.analytics.realtime.engine import realtime_engine
    await realtime_engine.start()
    logger.info("Real-time analytics engine started")
    
    # Initialize webhook processor
    processor = await get_webhook_processor()
    app.state.webhook_processor = processor
    logger.info("Webhook processor initialized")
    
    # Initialize sync scheduler
    scheduler = await get_sync_scheduler()
    app.state.sync_scheduler = scheduler
    logger.info("Sync scheduler initialized")
    
    yield
    
    logger.info("Shutting down AgencyDark API...")
    
    # Shutdown services
    # Stop sync scheduler
    await shutdown_scheduler()
    logger.info("Sync scheduler stopped")
    
    # Stop webhook processor
    await shutdown_processor()
    logger.info("Webhook processor stopped")
    
    # Stop real-time analytics engine
    await realtime_engine.stop()
    logger.info("Real-time analytics engine stopped")
    
    # Stop monitoring service
    await monitoring_service.stop()
    logger.info("Monitoring service stopped")
    
    # Stop background sync scheduler
    await stop_sync_scheduler()
    logger.info("Background sync scheduler stopped")
    
    # Shutdown cache system
    await shutdown_cache()
    logger.info("Cache system shut down")
    
    # Shutdown advanced cache manager
    await cache_manager.close()
    logger.info("Advanced cache manager closed")
    
    await redis_client.close()
    logger.info("Redis connection closed")
    await engine.dispose()


app = FastAPI(
    title="AgencyDark API",
    description="White-label SaaS portal for OnlyFans marketing agencies",
    version="1.0.0",
    # docs_url=None,  # We'll use custom docs
    redoc_url=None,  # Disable default redoc to use our custom one
    # openapi_url="/api/v1/openapi.json",  # Temporarily use default URL
    lifespan=lifespan
)

# Setup custom OpenAPI schema
def get_custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title="AgencyDark API",
        version="1.0.0",
        description="""
        ## AgencyDark - White-label OnlyFans Marketing Agency Platform
        
        A comprehensive SaaS platform designed for marketing agencies managing OnlyFans creators.
        
        ### Features:
        - 🔐 JWT-based authentication
        - 📊 Advanced analytics and reporting
        - 💬 Bulk messaging and automation
        - 💰 Financial management and commission tracking
        - 🔄 Multi-platform support
        
        ### Authentication
        Most endpoints require a JWT token. Include it in the Authorization header:
        ```
        Authorization: Bearer <your-token>
        ```
        """,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Add default security to all operations
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = get_custom_openapi

# Setup custom API documentation
# TODO: Fix setup_api_docs imports
# setup_api_docs(app)

# Add global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    return await error_handler(request, exc)

# Add middleware in reverse order (last added is first executed)
# Debugging middleware (only in debug mode)
if settings.DEBUG:
    app.add_middleware(PerformanceProfilingMiddleware)
    app.add_middleware(RequestBodyMiddleware)
    app.add_middleware(DatabaseQueryLoggingMiddleware, slow_query_threshold=1.0)

app.add_middleware(DebuggingMiddleware)  # Request tracking and error handling
app.add_middleware(I18nMiddleware)  # Internationalization
app.add_middleware(LoggingContextMiddleware)  # Structured logging context
app.add_middleware(LoggingMiddleware)
app.add_middleware(UserContextMiddleware)  # User context for logging
# app.add_middleware(monitoring_middleware)  # TODO: Fix this - needs to be a proper middleware class

# Add platform API key usage logging middleware
@app.middleware("http")
async def api_key_usage_logging_middleware(request: Request, call_next):
    return await log_api_key_usage(request, call_next)

# Add audit logging middlewares
app.add_middleware(ComplianceAuditMiddleware)  # Compliance-specific audit logging
app.add_middleware(AuditLoggingMiddleware)  # General audit logging

app.add_middleware(APIUsageMiddleware)  # API usage tracking and limits
app.add_middleware(AdvancedRateLimitMiddleware)  # New advanced rate limiting
app.add_middleware(APIKeyRateLimitMiddleware)  # API key specific rate limiting
app.add_middleware(FraudDetectionMiddleware)
app.add_middleware(EnhancedAPIKeyMiddleware)  # Enhanced API key validation
app.add_middleware(SecurityHeadersMiddleware)  # Security headers
app.add_middleware(CSRFMiddleware)  # CSRF protection
app.add_middleware(ValidationMiddleware)  # Input validation
app.add_middleware(SecurityMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(TenantMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Welcome to AgencyDark API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    from datetime import datetime
    # Simplified health check without Redis dependency
    return {
        "status": "healthy",
        "service": "AgencyDark API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/test-openapi")
async def test_openapi():
    """Test OpenAPI generation"""
    try:
        schema = app.openapi()
        return {"status": "success", "schema_keys": list(schema.keys()) if schema else []}
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


@app.get("/redoc", include_in_schema=False, response_class=HTMLResponse)
async def custom_redoc_html():
    """Custom ReDoc with debugging"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <title>AgencyDark API - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
    <style>
      body {
        margin: 0;
        padding: 0;
      }
      #loading {
        text-align: center;
        padding: 50px;
        font-family: Arial, sans-serif;
      }
    </style>
    </head>
    <body>
    <div id="loading">Loading API documentation...</div>
    <redoc spec-url="/openapi.json" 
           suppress-warnings="true"
           native-scrollbars="true"
           path-in-middle-panel="true"
           theme='{
             "colors": {
               "primary": {
                 "main": "#6B5B95"
               }
             },
             "typography": {
               "fontSize": "14px",
               "fontFamily": "Roboto, sans-serif"
             }
           }'>
    </redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
    <script>
      // Add error handling
      window.addEventListener('error', function(e) {
        console.error('ReDoc Error:', e);
        document.getElementById('loading').innerHTML = 
          '<div style="color: red;">Error loading documentation: ' + e.message + '</div>';
      });
      
      // Check if ReDoc loaded
      setTimeout(function() {
        if (!window.Redoc) {
          document.getElementById('loading').innerHTML = 
            '<div style="color: red;">Failed to load ReDoc library</div>';
        }
      }, 5000);
    </script>
    </body>
    </html>
    """


@app.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    from core.monitoring import HealthChecker
    return await HealthChecker.liveness_check()


@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    from core.monitoring import HealthChecker
    return await HealthChecker.readiness_check()


@app.get("/metrics")
async def get_prometheus_metrics():
    """Prometheus metrics endpoint."""
    from core.monitoring import get_metrics
    from starlette.responses import Response
    
    metrics = get_metrics()
    return Response(content=metrics, media_type="text/plain")


# Mount Socket.IO app
app.mount("/", socket_app)


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )