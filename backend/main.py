"""
Main application entry point using security_v2 system.
"""
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

# Import only necessary middleware
from core.middleware.tenant import TenantMiddleware
from core.middleware.logging import LoggingMiddleware
from core.middleware.monitoring import monitoring_middleware
from middleware.i18n import I18nMiddleware
from middleware.logging_context import LoggingContextMiddleware, UserContextMiddleware

# Import from security_v2 for auth middleware
from core.security_v2.middleware import (
    AuthenticationMiddleware,
    SecurityMiddleware,
    RateLimitMiddleware
)

# Services
from core.cache import initialize_cache, shutdown_cache
from core.monitoring import monitoring_service
from core.openapi import custom_openapi, setup_api_docs
from core.errors import error_handler
from core.logger import get_logger
from services.webhook_queue import get_webhook_processor, shutdown_processor
from services.sync_scheduler import get_sync_scheduler, shutdown_scheduler
from logging_config import configure_structured_logging

# Configure structured logging
configure_structured_logging()

# Use our enhanced logger instead of basic logging
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AgencyDark API...")
    
    # Initialize database tables if needed
    # await create_tables()  # Commented out for PgBouncer compatibility
    
    # Initialize Redis connection
    await redis_client.connect()
    logger.info("Redis connected")
    
    # Initialize cache system
    await initialize_cache()
    logger.info("Cache system initialized")
    
    # Initialize advanced cache manager
    from core.cache_manager import cache_manager
    await cache_manager.initialize()
    logger.info("Advanced cache manager initialized")
    
    # Initialize security_v2 session manager
    from core.security_v2 import init_session_manager
    await init_session_manager()
    logger.info("Security session manager initialized")
    
    # Start monitoring service
    await monitoring_service.start()
    logger.info("Monitoring service started")
    
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
    
    # Shutdown services in reverse order
    await shutdown_scheduler()
    logger.info("Sync scheduler stopped")
    
    await shutdown_processor()
    logger.info("Webhook processor stopped")
    
    await monitoring_service.stop()
    logger.info("Monitoring service stopped")
    
    await shutdown_cache()
    logger.info("Cache system shut down")
    
    await cache_manager.close()
    logger.info("Advanced cache manager closed")
    
    await redis_client.close()
    logger.info("Redis connection closed")
    
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="AgencyDark API",
    description="White-label SaaS portal for OnlyFans marketing agencies",
    version="2.0.0",  # Updated version after consolidation
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# Setup custom OpenAPI schema
def get_custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title="AgencyDark API",
        version="2.0.0",
        description="White-label SaaS portal for OnlyFans marketing agencies",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "ApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = get_custom_openapi

# CORS settings
cors_origins = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# Add middleware in the correct order (from innermost to outermost)
# 1. Logging and monitoring (outermost)
app.add_middleware(LoggingMiddleware)
app.add_middleware(LoggingContextMiddleware)

# 2. Security and authentication
app.add_middleware(SecurityMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RateLimitMiddleware)

# 3. Tenant and user context
app.add_middleware(TenantMiddleware)
app.add_middleware(UserContextMiddleware)

# 4. Internationalization
app.add_middleware(I18nMiddleware)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API information."""
    html_content = """
    <html>
        <head>
            <title>AgencyDark API</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .container {
                    text-align: center;
                    padding: 2rem;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    backdrop-filter: blur(10px);
                }
                h1 {
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }
                .version {
                    font-size: 1.2rem;
                    opacity: 0.9;
                }
                .links {
                    margin-top: 2rem;
                }
                a {
                    color: white;
                    text-decoration: none;
                    padding: 0.75rem 1.5rem;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    margin: 0 0.5rem;
                    display: inline-block;
                    transition: background 0.3s;
                }
                a:hover {
                    background: rgba(255, 255, 255, 0.3);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 AgencyDark API</h1>
                <p class="version">Version 2.0.0</p>
                <p>White-label SaaS portal for OnlyFans marketing agencies</p>
                <div class="links">
                    <a href="/api/docs">📚 API Documentation</a>
                    <a href="/api/redoc">📖 ReDoc</a>
                    <a href="/health">❤️ Health Check</a>
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "AgencyDark API"
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The path {request.url.path} was not found",
            "path": request.url.path
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )