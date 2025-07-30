"""Main application with database authentication."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from core.config import settings
from core.database import engine
from api.v1.endpoints.auth_simple import router as auth_router
from models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("Starting up...")
    # Tables are already created via create_tables.py
    
    # Initialize Redis
    from core.redis import redis_manager
    await redis_manager.connect()
    print("Redis connected")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    await redis_manager.disconnect()
    await engine.dispose()


app = FastAPI(
    title="AgencyDark API",
    description="Backend API for AgencyDark OnlyFans management platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# Import and include new routers
from api.v1.endpoints.analytics import router as analytics_router
from api.v1.endpoints.models import router as models_router
from api.v1.endpoints.conversations import router as conversations_router
from api.v1.endpoints.financial import router as financial_router
from api.v1.endpoints.tasks import router as tasks_router

app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(models_router, prefix="/api/v1/models", tags=["models"])
app.include_router(conversations_router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(financial_router, prefix="/api/v1/financial", tags=["financial"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AgencyDark API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        from sqlalchemy import text
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint."""
    return {
        "message": "API is working!",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    uvicorn.run(
        "main_with_auth:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )