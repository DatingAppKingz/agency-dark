"""
Connection pooling optimization for database and external services.
"""

from typing import Any, Dict, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import time

from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import event
import asyncpg
import aioredis

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ConnectionPoolManager:
    """Manage and optimize connection pools."""
    
    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.stats: Dict[str, Dict[str, Any]] = {}
        self.health_check_interval = 60  # seconds
        self._health_check_task = None
    
    async def initialize(self):
        """Initialize connection pools."""
        # Create optimized database pool
        self.pools["database"] = await self._create_db_pool()
        
        # Create Redis pool
        self.pools["redis"] = await self._create_redis_pool()
        
        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._monitor_pools())
        
        logger.info("Connection pools initialized")
    
    async def close(self):
        """Close all connection pools."""
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # Close database pool
        if "database" in self.pools:
            await self.pools["database"].dispose()
        
        # Close Redis pool
        if "redis" in self.pools:
            self.pools["redis"].close()
            await self.pools["redis"].wait_closed()
        
        logger.info("Connection pools closed")
    
    async def _create_db_pool(self) -> AsyncEngine:
        """Create optimized database connection pool."""
        # Pool configuration based on environment
        pool_config = {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
            "pool_timeout": 30,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_pre_ping": True,  # Verify connections before use
            "echo_pool": settings.DEBUG,
        }
        
        # Create engine with optimized settings
        engine = create_async_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            **pool_config,
            connect_args={
                "server_settings": {
                    "application_name": "agency_backend",
                    "jit": "off"  # Disable JIT for consistent performance
                },
                "command_timeout": 60,
                "prepared_statement_cache_size": 0,  # Disable to prevent memory issues
                "prepared_statement_name_func": lambda *_: None,
            }
        )
        
        # Add event listeners for monitoring
        @event.listens_for(engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            connection_record.info['connect_time'] = time.time()
        
        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            checkout_time = time.time()
            connection_record.info['checkout_time'] = checkout_time
            
            # Track pool statistics
            pool_stats = self.stats.setdefault("database", {
                "checkouts": 0,
                "checkins": 0,
                "connects": 0,
                "disconnects": 0,
                "total_checkout_time": 0,
                "max_checkout_time": 0
            })
            pool_stats["checkouts"] += 1
        
        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            if 'checkout_time' in connection_record.info:
                checkout_duration = time.time() - connection_record.info['checkout_time']
                
                pool_stats = self.stats["database"]
                pool_stats["checkins"] += 1
                pool_stats["total_checkout_time"] += checkout_duration
                pool_stats["max_checkout_time"] = max(
                    pool_stats["max_checkout_time"],
                    checkout_duration
                )
        
        return engine
    
    async def _create_redis_pool(self) -> aioredis.Redis:
        """Create optimized Redis connection pool."""
        pool = await aioredis.create_redis_pool(
            settings.REDIS_URL,
            minsize=settings.REDIS_POOL_MIN_SIZE,
            maxsize=settings.REDIS_POOL_MAX_SIZE,
            timeout=10,
            encoding='utf-8'
        )
        
        # Initialize statistics
        self.stats["redis"] = {
            "commands": 0,
            "errors": 0,
            "total_response_time": 0,
            "max_response_time": 0
        }
        
        return pool
    
    async def _monitor_pools(self):
        """Monitor connection pool health."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check database pool
                if "database" in self.pools:
                    await self._check_db_pool_health()
                
                # Check Redis pool
                if "redis" in self.pools:
                    await self._check_redis_pool_health()
                
                # Log statistics
                self._log_pool_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring pools: {e}")
    
    async def _check_db_pool_health(self):
        """Check database pool health."""
        engine = self.pools["database"]
        pool = engine.pool
        
        # Get pool status
        pool_status = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "overflow": pool.overflow(),
            "total": pool.total()
        }
        
        # Test connection
        try:
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
            pool_status["healthy"] = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            pool_status["healthy"] = False
        
        self.stats["database"]["status"] = pool_status
    
    async def _check_redis_pool_health(self):
        """Check Redis pool health."""
        pool = self.pools["redis"]
        
        # Get pool status
        pool_status = {
            "size": pool.size,
            "free_connections": pool.freesize,
            "active_connections": pool.size - pool.freesize
        }
        
        # Test connection
        try:
            await pool.ping()
            pool_status["healthy"] = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            pool_status["healthy"] = False
        
        self.stats["redis"]["status"] = pool_status
    
    def _log_pool_stats(self):
        """Log connection pool statistics."""
        for pool_name, stats in self.stats.items():
            logger.info(
                f"Pool stats - {pool_name}",
                extra={"pool_stats": stats}
            )
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get current pool statistics."""
        return {
            pool_name: {
                **stats,
                "avg_checkout_time": (
                    stats.get("total_checkout_time", 0) / stats.get("checkouts", 1)
                    if pool_name == "database" and stats.get("checkouts", 0) > 0
                    else 0
                )
            }
            for pool_name, stats in self.stats.items()
        }
    
    @asynccontextmanager
    async def get_db_connection(self):
        """Get database connection from pool."""
        engine = self.pools.get("database")
        if not engine:
            raise RuntimeError("Database pool not initialized")
        
        async with engine.connect() as conn:
            yield conn
    
    @asynccontextmanager
    async def get_redis_connection(self):
        """Get Redis connection from pool."""
        pool = self.pools.get("redis")
        if not pool:
            raise RuntimeError("Redis pool not initialized")
        
        conn = await pool.acquire()
        try:
            yield conn
        finally:
            pool.release(conn)


class ConnectionPoolOptimizer:
    """Optimize connection pool settings based on usage patterns."""
    
    def __init__(self, pool_manager: ConnectionPoolManager):
        self.pool_manager = pool_manager
        self.optimization_interval = 300  # 5 minutes
        self.optimization_history = []
    
    async def start_optimization(self):
        """Start automatic pool optimization."""
        while True:
            await asyncio.sleep(self.optimization_interval)
            await self.optimize_pools()
    
    async def optimize_pools(self):
        """Optimize pool settings based on metrics."""
        stats = self.pool_manager.get_pool_stats()
        
        # Analyze database pool
        if "database" in stats:
            db_stats = stats["database"]
            recommendations = self._analyze_db_pool(db_stats)
            
            if recommendations:
                logger.info(
                    "Database pool optimization recommendations",
                    extra={"recommendations": recommendations}
                )
        
        # Analyze Redis pool
        if "redis" in stats:
            redis_stats = stats["redis"]
            recommendations = self._analyze_redis_pool(redis_stats)
            
            if recommendations:
                logger.info(
                    "Redis pool optimization recommendations",
                    extra={"recommendations": recommendations}
                )
        
        # Store optimization history
        self.optimization_history.append({
            "timestamp": datetime.utcnow(),
            "stats": stats,
            "recommendations": recommendations
        })
        
        # Keep only last 24 hours of history
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.optimization_history = [
            h for h in self.optimization_history
            if h["timestamp"] > cutoff
        ]
    
    def _analyze_db_pool(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze database pool performance."""
        recommendations = {}
        
        # Check if pool is exhausted frequently
        status = stats.get("status", {})
        pool_size = status.get("size", 0)
        overflow = status.get("overflow", 0)
        
        if pool_size > 0 and overflow > pool_size * 0.5:
            recommendations["increase_pool_size"] = {
                "current": pool_size,
                "recommended": pool_size * 2,
                "reason": "Pool frequently using overflow connections"
            }
        
        # Check average checkout time
        avg_checkout_time = stats.get("avg_checkout_time", 0)
        if avg_checkout_time > 1.0:  # 1 second
            recommendations["optimize_queries"] = {
                "avg_checkout_time": avg_checkout_time,
                "reason": "Long connection checkout times indicate slow queries"
            }
        
        return recommendations
    
    def _analyze_redis_pool(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze Redis pool performance."""
        recommendations = {}
        
        # Check error rate
        commands = stats.get("commands", 0)
        errors = stats.get("errors", 0)
        
        if commands > 0:
            error_rate = errors / commands
            if error_rate > 0.01:  # 1% error rate
                recommendations["investigate_errors"] = {
                    "error_rate": f"{error_rate * 100:.2f}%",
                    "reason": "High Redis error rate detected"
                }
        
        # Check response times
        avg_response_time = (
            stats.get("total_response_time", 0) / commands
            if commands > 0
            else 0
        )
        
        if avg_response_time > 0.01:  # 10ms
            recommendations["optimize_redis_usage"] = {
                "avg_response_time": f"{avg_response_time * 1000:.2f}ms",
                "reason": "High Redis response times"
            }
        
        return recommendations


# Connection pool middleware
class ConnectionPoolMiddleware:
    """Middleware to manage connection pool lifecycle."""
    
    def __init__(self, app, pool_manager: ConnectionPoolManager):
        self.app = app
        self.pool_manager = pool_manager
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            async def lifespan(receive, send):
                message = await receive()
                
                if message["type"] == "lifespan.startup":
                    await self.pool_manager.initialize()
                    await send({"type": "lifespan.startup.complete"})
                
                elif message["type"] == "lifespan.shutdown":
                    await self.pool_manager.close()
                    await send({"type": "lifespan.shutdown.complete"})
            
            await lifespan(receive, send)
        else:
            await self.app(scope, receive, send)