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
from api.v1.endpoints.websocket import router as websocket_router
from api.v1.endpoints.realtime_dashboard import router as dashboard_ws_router

# Import simple routers for missing endpoints
from api.v1.endpoints.simple_users import router as users_router
from api.v1.endpoints.simple_agencies import router as agencies_router
from api.v1.endpoints.simple_conversations import router as simple_conversations_router
from api.v1.endpoints.simple_transactions import router as transactions_router
from api.v1.endpoints.simple_messages import router as messages_router
from api.v1.endpoints.simple_content import router as content_router

app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(models_router, prefix="/api/v1/models", tags=["models"])
app.include_router(conversations_router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(financial_router, prefix="/api/v1/financial", tags=["financial"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(websocket_router, prefix="/api/v1/ws", tags=["websocket"])
app.include_router(dashboard_ws_router, prefix="/api/v1/ws", tags=["websocket"])

# Add the missing endpoints
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(agencies_router, prefix="/api/v1/agencies", tags=["agencies"])
app.include_router(simple_conversations_router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(transactions_router, prefix="/api/v1/transactions", tags=["transactions"])
app.include_router(messages_router, prefix="/api/v1/messages", tags=["messages"])
app.include_router(content_router, prefix="/api/v1/content", tags=["content"])
app.include_router(content_router, prefix="/api/v1/media", tags=["media"])

# Import and include secondary functionality routers
from api.v1.endpoints.api_keys import router as api_keys_router
app.include_router(api_keys_router, prefix="/api/v1/api-keys", tags=["api-keys"])

from api.v1.endpoints.sessions import router as sessions_router
app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["sessions"])

try:
    from api.v1.endpoints.bulk_operations import router as bulk_router
    app.include_router(bulk_router, prefix="/api/v1/bulk", tags=["bulk"])
except ImportError:
    pass

from api.v1.endpoints.media_upload import router as media_upload_router
app.include_router(media_upload_router, prefix="/api/v1/media", tags=["media-upload"])

from api.v1.endpoints.reports import router as reports_router
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])

try:
    from api.v1.endpoints.ml_analytics import router as ml_router
    app.include_router(ml_router, prefix="/api/v1/ml", tags=["ml-analytics"])
except ImportError:
    pass

from api.v1.endpoints.fraud_detection import router as fraud_router
app.include_router(fraud_router, prefix="/api/v1/fraud", tags=["fraud"])

try:
    from api.v1.endpoints.rate_limits import router as rate_limits_router
    app.include_router(rate_limits_router, prefix="/api/v1/rate-limits", tags=["rate-limits"])
except ImportError:
    pass

try:
    from api.v1.endpoints.push_notifications import router as notifications_router
    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
except ImportError:
    pass

try:
    from api.v1.endpoints.monitoring import router as monitoring_router
    app.include_router(monitoring_router, prefix="/api/v1/monitoring", tags=["monitoring"])
except ImportError:
    pass

try:
    from api.v1.endpoints.sync_status import router as sync_router
    app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])
except ImportError:
    pass

try:
    from api.v1.endpoints.query_performance import router as performance_router
    app.include_router(performance_router, prefix="/api/v1/performance", tags=["performance"])
except ImportError:
    pass


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