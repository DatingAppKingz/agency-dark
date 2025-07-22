from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from core.config import settings
from core.database import engine, create_tables
from core.redis import redis_client
# from api.v1.router import api_router
from core.middleware.tenant import TenantMiddleware
from core.middleware.logging import LoggingMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    await create_tables()
    
    await redis_client.initialize()
    
    yield
    
    logger.info("Shutting down AgencyDark API...")
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
app.add_middleware(TenantMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(api_router, prefix="/api/v1")


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