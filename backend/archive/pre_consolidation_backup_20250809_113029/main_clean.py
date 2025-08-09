"""
Clean main.py using only security_v2 module
This replaces the old main.py with all security functionality from security_v2
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
from core.middleware.tenant import TenantMiddleware
from core.middleware.logging import LoggingMiddleware

# Use security_v2 for all security needs
from core.security_v2.authentication.jwt_handler import JWTHandler
from core.security_v2.authorization.rbac import RBACManager
from core.security_v2.config import SecurityConfig

# Other middleware (non-security)
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

# Configure structured logging
configure_structured_logging()

# Use our enhanced logger instead of basic logging
logger = get_logger(__name__)

# Initialize security components
security_config = SecurityConfig()
jwt_handler = JWTHandler(security_config)
rbac_manager = RBACManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown operations.
    """
    # Startup
    logger.info("Starting up AgencyDark API...")
    
    # Initialize Redis
    await redis_client.initialize()
    logger.info("Redis initialized")
    
    # Initialize Cache
    await initialize_cache()
    logger.info("Cache initialized")
    
    # Create database tables
    await create_tables()
    logger.info("Database tables created/verified")
    
    # Start monitoring service
    await monitoring_service.start()
    logger.info("Monitoring service started")
    
    # Start sync scheduler
    await start_sync_scheduler()
    logger.info("Sync scheduler started")
    
    # Start webhook processor
    processor = await get_webhook_processor()
    await processor.start()
    logger.info("Webhook processor started")
    
    # Start sync scheduler service
    scheduler = await get_sync_scheduler()
    await scheduler.start()
    logger.info("Sync scheduler service started")
    
    logger.info("✅ AgencyDark API startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AgencyDark API...")
    
    # Stop sync scheduler service
    scheduler = await get_sync_scheduler()
    await scheduler.stop()
    logger.info("Sync scheduler service stopped")
    
    # Stop webhook processor
    processor = await get_webhook_processor()
    await processor.stop()
    await shutdown_processor()
    logger.info("Webhook processor stopped")
    
    # Stop sync scheduler
    await stop_sync_scheduler()
    logger.info("Sync scheduler stopped")
    
    # Stop monitoring service
    await monitoring_service.stop()
    logger.info("Monitoring service stopped")
    
    # Shutdown Cache
    await shutdown_cache()
    logger.info("Cache shutdown")
    
    # Close Redis
    await redis_client.close()
    logger.info("Redis connection closed")
    
    logger.info("✅ AgencyDark API shutdown complete")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="AgencyDark API",
    description="Comprehensive agency management platform with security_v2",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"]
)

# Add non-security middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(ValidationMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(APIUsageMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(LoggingContextMiddleware)
app.add_middleware(UserContextMiddleware)

# Add debugging middleware (only in development)
if settings.DEBUG:
    app.add_middleware(RequestBodyMiddleware)
    app.add_middleware(DatabaseQueryLoggingMiddleware)
    app.add_middleware(PerformanceProfilingMiddleware)
    app.add_middleware(DebuggingMiddleware)

# Add monitoring middleware
app = monitoring_middleware(app)

# Setup custom OpenAPI
app.openapi = custom_openapi
setup_api_docs(app)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Mount Socket.IO app
app.mount("/socket.io", socket_app)

# Error handlers
app.add_exception_handler(Exception, error_handler)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API information."""
    html_content = """
    <html>
        <head>
            <title>AgencyDark API v2</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                }
                .container {
                    text-align: center;
                    padding: 2rem;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
                }
                h1 { 
                    font-size: 3rem; 
                    margin-bottom: 1rem;
                    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
                }
                .version {
                    font-size: 1.2rem;
                    opacity: 0.9;
                    margin-bottom: 2rem;
                }
                .links {
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    flex-wrap: wrap;
                }
                a {
                    color: white;
                    text-decoration: none;
                    padding: 0.8rem 1.5rem;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    transition: all 0.3s ease;
                    display: inline-block;
                }
                a:hover {
                    background: rgba(255, 255, 255, 0.3);
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
                }
                .status {
                    margin-top: 2rem;
                    padding: 1rem;
                    background: rgba(0, 255, 0, 0.2);
                    border-radius: 10px;
                    font-weight: 600;
                }
                .security-badge {
                    background: rgba(255, 215, 0, 0.3);
                    padding: 0.5rem 1rem;
                    border-radius: 5px;
                    margin-top: 1rem;
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 AgencyDark API</h1>
                <div class="version">Version 2.0.0 - Powered by Security_v2</div>
                <div class="status">✅ API is running</div>
                <div class="security-badge">🔒 Enhanced Security with RBAC</div>
                <div class="links">
                    <a href="/api/docs">📚 API Documentation</a>
                    <a href="/api/redoc">📖 ReDoc</a>
                    <a href="/health">🏥 Health Status</a>
                    <a href="/metrics">📊 Metrics</a>
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "security": "security_v2",
        "features": {
            "rbac": security_config.ENABLE_RBAC,
            "jwt": True,
            "session_management": True
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main_clean:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )