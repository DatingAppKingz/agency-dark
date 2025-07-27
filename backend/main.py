from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
from core.middleware.security import SecurityMiddleware, RateLimitMiddleware, APIKeyMiddleware
from core.tasks.sync_tasks import start_sync_scheduler, stop_sync_scheduler
from core.realtime.server import socket_app
from core.cache import initialize_cache, shutdown_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    # await create_tables()  # Commented out for PgBouncer compatibility
    
    await redis_client.initialize()
    
    # Initialize cache system
    await initialize_cache()
    
    # Start background sync scheduler
    await start_sync_scheduler()
    
    yield
    
    logger.info("Shutting down AgencyDark API...")
    
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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Add middleware in reverse order (last added is first executed)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)
app.add_middleware(APIKeyMiddleware)
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