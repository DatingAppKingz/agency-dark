"""
Optimized FastAPI application with security hardening.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn

from core.config import settings
from core.logging import setup_logging, get_logger
from app.api.v1.api import api_router

# Import optimization modules
from core.optimization import (
    ConnectionPoolManager,
    CacheManager,
    MemoryProfiler,
    CompressionMiddleware as CustomCompressionMiddleware
)

# Import security modules
from core.security_v2 import (
    SecurityHeadersMiddleware,
    security_headers_config,
    audit_logger,
    SecretsManager
)

logger = get_logger(__name__)


# Global instances
connection_pool_manager = ConnectionPoolManager()
cache_manager = None
memory_profiler = MemoryProfiler()
secrets_manager = SecretsManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting optimized application...")
    
    # Initialize logging
    setup_logging()
    
    # Initialize connection pools
    await connection_pool_manager.initialize()
    
    # Initialize cache manager
    global cache_manager
    cache_manager = await CacheManager.create()
    
    # Start memory profiler
    memory_profiler.start_monitoring()
    
    # Start audit logger
    await audit_logger.start()
    
    # Log startup
    logger.info(
        "Application started successfully",
        extra={
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "version": settings.APP_VERSION
        }
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop audit logger
    await audit_logger.stop()
    
    # Stop memory profiler
    memory_profiler.stop_monitoring()
    
    # Close cache manager
    if cache_manager:
        await cache_manager.close()
    
    # Close connection pools
    await connection_pool_manager.close()
    
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create optimized FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan
    )
    
    # Security headers middleware
    app.add_middleware(
        SecurityHeadersMiddleware,
        headers=security_headers_config(settings.ENVIRONMENT),
        csp_enabled=True
    )
    
    # Custom compression middleware
    app.add_middleware(
        CustomCompressionMiddleware,
        minimum_size=1024,
        compression_level=6,
        excluded_paths={"/health", "/metrics"},
        excluded_media_types={"image/jpeg", "image/png", "application/pdf"}
    )
    
    # Standard Gzip middleware as fallback
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # CORS middleware
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": settings.APP_VERSION,
            "pools": connection_pool_manager.get_pool_stats(),
            "cache": cache_manager.get_stats() if cache_manager else {},
            "memory": memory_profiler.collect_memory_stats()
        }
    
    # Metrics endpoint
    @app.get("/metrics")
    async def metrics():
        """Prometheus-compatible metrics endpoint."""
        metrics_data = []
        
        # Connection pool metrics
        pool_stats = connection_pool_manager.get_pool_stats()
        for pool_name, stats in pool_stats.items():
            metrics_data.append(
                f'pool_connections_active{{pool="{pool_name}"}} {stats.get("active_connections", 0)}'
            )
            metrics_data.append(
                f'pool_connections_total{{pool="{pool_name}"}} {stats.get("total", 0)}'
            )
        
        # Cache metrics
        if cache_manager:
            cache_stats = cache_manager.get_stats()
            metrics_data.append(f'cache_hits_total {cache_stats["hits"]}')
            metrics_data.append(f'cache_misses_total {cache_stats["misses"]}')
            metrics_data.append(f'cache_hit_rate {cache_stats.get("hit_rate", "0")}')
        
        # Memory metrics
        memory_stats = memory_profiler.collect_memory_stats()
        metrics_data.append(f'memory_usage_bytes {memory_stats["rss_mb"] * 1024 * 1024}')
        metrics_data.append(f'memory_usage_percent {memory_stats["percent"]}')
        
        return "\n".join(metrics_data)
    
    # Security scan endpoint (admin only)
    @app.post("/admin/security/scan")
    async def security_scan(request: Request):
        """Run security vulnerability scan."""
        from core.security_v2 import vulnerability_scanner
        
        # TODO: Add authentication check
        
        results = await vulnerability_scanner.scan_dependencies()
        report = vulnerability_scanner.generate_vulnerability_report(results)
        
        return report
    
    # Cache warmup endpoint
    @app.post("/admin/cache/warmup")
    async def warmup_cache():
        """Warm up application cache."""
        from core.optimization.cache_manager import warm_user_cache, warm_config_cache
        
        # TODO: Add authentication check
        
        if cache_manager:
            await warm_user_cache(cache_manager)
            await warm_config_cache(cache_manager)
            
            return {"status": "success", "message": "Cache warmed up"}
        
        return {"status": "error", "message": "Cache manager not initialized"}
    
    # Memory optimization endpoint
    @app.post("/admin/memory/optimize")
    async def optimize_memory():
        """Run memory optimization."""
        # TODO: Add authentication check
        
        result = memory_profiler.optimize_memory()
        return result
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    # Run with optimized settings
    uvicorn.run(
        "app.main_optimized:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_config=None,  # Use custom logging
        access_log=True,
        # Performance optimizations
        loop="uvloop",
        http="httptools",
        # Connection settings
        limit_concurrency=1000,
        limit_max_requests=10000,
        timeout_keep_alive=5,
    )