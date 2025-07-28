"""
Optimized database connection pooling configuration
"""
import os
import logging
from typing import Optional, Dict, Any
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from core.config import settings

logger = logging.getLogger(__name__)


class DatabasePoolConfig:
    """Database connection pool configuration"""
    
    @staticmethod
    def get_pool_config() -> Dict[str, Any]:
        """
        Get optimized pool configuration based on environment
        
        Returns:
            Dict with pool configuration parameters
        """
        # Base configuration
        config = {
            "pool_pre_ping": True,  # Verify connections before use
            "echo": settings.DEBUG,
            "future": True,
            "query_cache_size": 1200,  # Cache parsed SQL statements
        }
        
        # Environment-specific configuration
        if settings.ENVIRONMENT == "test":
            # Test environment: Use NullPool for isolation
            config.update({
                "poolclass": NullPool,
            })
        elif settings.ENVIRONMENT == "development":
            # Development: Smaller pool for local development
            config.update({
                "poolclass": QueuePool,
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            })
        else:
            # Production: Optimized for high concurrency
            config.update({
                "poolclass": QueuePool,
                "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "30")),
                "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
                "pool_timeout": 30,
                "pool_recycle": 1800,  # Recycle connections after 30 minutes
                "connect_args": {
                    "server_settings": {
                        "jit": "off"  # Disable JIT for more predictable performance
                    },
                    "command_timeout": 60,
                    "connection_timeout": 10,
                }
            })
        
        return config
    
    @staticmethod
    def get_read_replica_config() -> Dict[str, Any]:
        """
        Get configuration for read replica connections
        
        Returns:
            Dict with read replica pool configuration
        """
        config = DatabasePoolConfig.get_pool_config()
        
        # Optimize for read-heavy workloads
        if settings.ENVIRONMENT != "test":
            config.update({
                "pool_size": int(os.getenv("READ_POOL_SIZE", "40")),
                "max_overflow": int(os.getenv("READ_MAX_OVERFLOW", "30")),
                "connect_args": {
                    **config.get("connect_args", {}),
                    "server_settings": {
                        **config.get("connect_args", {}).get("server_settings", {}),
                        "statement_timeout": "30s",  # Shorter timeout for reads
                    }
                }
            })
        
        return config
    
    @staticmethod
    def get_analytics_config() -> Dict[str, Any]:
        """
        Get configuration for analytics/reporting connections
        
        Returns:
            Dict with analytics pool configuration
        """
        config = DatabasePoolConfig.get_pool_config()
        
        # Optimize for long-running analytics queries
        if settings.ENVIRONMENT != "test":
            config.update({
                "pool_size": int(os.getenv("ANALYTICS_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("ANALYTICS_MAX_OVERFLOW", "5")),
                "pool_recycle": 7200,  # Recycle after 2 hours
                "connect_args": {
                    **config.get("connect_args", {}),
                    "server_settings": {
                        **config.get("connect_args", {}).get("server_settings", {}),
                        "statement_timeout": "300s",  # Longer timeout for analytics
                        "work_mem": "256MB",  # More memory for sorts/joins
                    }
                }
            })
        
        return config


class ConnectionPoolManager:
    """Manages multiple connection pools for different workloads"""
    
    def __init__(self):
        self._engines: Dict[str, AsyncEngine] = {}
        self._initialized = False
    
    async def initialize(self, database_url: str):
        """Initialize all connection pools"""
        if self._initialized:
            return
        
        # Main pool for writes and general queries
        self._engines["main"] = create_async_engine(
            database_url,
            **DatabasePoolConfig.get_pool_config()
        )
        
        # Read replica pool (if configured)
        read_replica_url = os.getenv("READ_REPLICA_URL", database_url)
        if read_replica_url != database_url:
            self._engines["read"] = create_async_engine(
                read_replica_url,
                **DatabasePoolConfig.get_read_replica_config()
            )
            logger.info("Read replica pool initialized")
        
        # Analytics pool (if configured)
        analytics_url = os.getenv("ANALYTICS_DATABASE_URL", database_url)
        if analytics_url != database_url:
            self._engines["analytics"] = create_async_engine(
                analytics_url,
                **DatabasePoolConfig.get_analytics_config()
            )
            logger.info("Analytics pool initialized")
        
        self._initialized = True
        logger.info("Connection pools initialized successfully")
    
    def get_engine(self, pool_type: str = "main") -> AsyncEngine:
        """Get engine for specific pool type"""
        # Fallback to main pool if requested pool doesn't exist
        return self._engines.get(pool_type, self._engines["main"])
    
    async def dispose_all(self):
        """Dispose all connection pools"""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
        self._initialized = False
        logger.info("All connection pools disposed")
    
    async def get_pool_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all connection pools"""
        status = {}
        for name, engine in self._engines.items():
            pool = engine.pool
            status[name] = {
                "size": getattr(pool, "size", None),
                "checked_in": getattr(pool, "checkedin", None),
                "overflow": getattr(pool, "overflow", None),
                "total": getattr(pool, "total", None),
            }
        return status


# Global pool manager instance
pool_manager = ConnectionPoolManager()