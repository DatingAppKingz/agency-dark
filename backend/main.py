from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from core.tasks.sync_tasks import start_sync_scheduler, stop_sync_scheduler
from core.realtime.server import socket_app
from core.cache import initialize_cache, shutdown_cache
from core.monitoring import monitoring_service
from core.middleware.monitoring import monitoring_middleware
from core.openapi import custom_openapi, setup_api_docs
from core.errors import error_handler
from core.logger import get_logger
from services.webhook_queue import get_webhook_processor, shutdown_processor

# Use our enhanced logger instead of basic logging
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    # await create_tables()  # Commented out for PgBouncer compatibility
    
    await redis_client.initialize()
    
    # Initialize cache system
    await initialize_cache()
    
    # Start background sync scheduler
    await start_sync_scheduler()
    
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
    
    yield
    
    logger.info("Shutting down AgencyDark API...")
    
    # Stop webhook processor
    await shutdown_processor()
    logger.info("Webhook processor stopped")
    
    # Stop real-time analytics engine
    await realtime_engine.stop()
    
    # Stop monitoring service
    await monitoring_service.stop()
    
    # Stop background sync scheduler
    await stop_sync_scheduler()
    
    # Shutdown cache system
    await shutdown_cache()
    
    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title="AgencyDark API",
    description="White-label SaaS portal for OnlyFans marketing agencies",
    version="1.0.0",
    docs_url=None,  # We'll use custom docs
    redoc_url=None,  # We'll use custom redoc
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# Setup custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)

# Setup custom API documentation
setup_api_docs(app)

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
app.add_middleware(LoggingMiddleware)
app.add_middleware(monitoring_middleware)
app.add_middleware(AdvancedRateLimitMiddleware)  # New advanced rate limiting
app.add_middleware(APIKeyRateLimitMiddleware)  # API key specific rate limiting
app.add_middleware(FraudDetectionMiddleware)
app.add_middleware(EnhancedAPIKeyMiddleware)  # Enhanced API key validation
app.add_middleware(SecurityHeadersMiddleware)  # Security headers
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
    from core.monitoring import HealthChecker
    from core.dependencies import get_db
    
    async for db in get_db():
        try:
            health_data = await HealthChecker.full_health_check(db)
            return health_data
        finally:
            await db.close()


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