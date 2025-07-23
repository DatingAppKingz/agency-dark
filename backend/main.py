from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn
from backend.core.config import settings
from backend.core.database import engine, create_tables
from backend.core.redis import redis_client
from backend.api.v1.api import api_router
from backend.core.middleware.tenant import TenantMiddleware
from backend.core.middleware.logging import LoggingMiddleware
from backend.core.middleware.auth import AuthenticationMiddleware
from backend.core.tasks.sync_tasks import start_sync_scheduler, stop_sync_scheduler
from backend.core.realtime.server import socket_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    await create_tables()
    
    await redis_client.initialize()
    
    # Start background sync scheduler
    await start_sync_scheduler()
    
    yield
    
    logger.info("Shutting down AgencyDark API...")
    
    # Stop background sync scheduler
    await stop_sync_scheduler()
    
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

app.add_middleware(LoggingMiddleware)
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
    try:
        await redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"
    
    return {
        "status": "healthy",
        "services": {
            "api": "healthy",
            "redis": redis_status,
        }
    }


# Mount Socket.IO app
app.mount("/", socket_app)


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )