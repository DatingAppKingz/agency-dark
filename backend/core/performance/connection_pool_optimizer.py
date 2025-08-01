"""
Database Connection Pool Optimization

Provides advanced connection pooling strategies:
- Dynamic pool sizing based on load
- Connection health monitoring
- Automatic reconnection with backoff
- Query timeout management
- Connection recycling
"""
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import psutil

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy import event, exc, pool
import sqlalchemy

from core.logger import get_logger
from core.monitoring import monitor_performance

logger = get_logger(__name__)


class ConnectionPoolOptimizer:
    """Advanced database connection pool optimization."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._engines: Dict[str, AsyncEngine] = {}
        self._session_makers: Dict[str, async_sessionmaker] = {}
        self._pool_stats: Dict[str, Dict[str, Any]] = {}
        self._last_optimization = time.time()
        self._optimization_interval = 60  # 1 minute
        
        # Pool configuration
        self.min_pool_size = 5
        self.max_pool_size = 20
        self.pool_recycle = 3600  # 1 hour
        self.pool_pre_ping = True
        self.pool_use_lifo = True  # Use LIFO to keep connections warm
        
        # Performance thresholds
        self.slow_query_threshold = 1.0  # seconds
        self.connection_timeout = 30.0
        self.query_timeout = 60.0
        
    async def create_optimized_engine(
        self,
        pool_name: str = "default",
        **engine_kwargs
    ) -> AsyncEngine:
        """
        Create an optimized database engine with advanced pooling.
        
        Args:
            pool_name: Name for this pool configuration
            **engine_kwargs: Additional engine arguments
        
        Returns:
            Configured AsyncEngine
        """
        if pool_name in self._engines:
            return self._engines[pool_name]
        
        # Determine optimal pool size based on system resources
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Calculate pool size (rough heuristic)
        calculated_max = min(
            cpu_count * 4,  # 4 connections per CPU
            int(memory_gb * 2),  # 2 connections per GB RAM
            self.max_pool_size
        )
        
        pool_config = {
            "pool_size": max(self.min_pool_size, calculated_max // 2),
            "max_overflow": calculated_max // 2,
            "pool_timeout": self.connection_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_use_lifo": self.pool_use_lifo,
        }
        
        # Create engine with optimized settings
        engine = create_async_engine(
            self.database_url,
            poolclass=QueuePool,
            echo_pool=False,
            **pool_config,
            **engine_kwargs,
            connect_args={
                "server_settings": {
                    "application_name": f"agency_dark_{pool_name}",
                    "jit": "off"
                },
                "command_timeout": self.query_timeout,
            }
        )
        
        # Set up event listeners
        self._setup_engine_events(engine, pool_name)
        
        # Store engine and create session maker
        self._engines[pool_name] = engine
        self._session_makers[pool_name] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Initialize stats
        self._pool_stats[pool_name] = {
            "created_at": datetime.utcnow(),
            "total_connections": 0,
            "active_connections": 0,
            "slow_queries": 0,
            "errors": 0,
            "last_optimized": datetime.utcnow()
        }
        
        logger.info(
            f"Created optimized engine '{pool_name}' with pool_size="
            f"{pool_config['pool_size']}, max_overflow={pool_config['max_overflow']}"
        )
        
        return engine
    
    @asynccontextmanager
    async def get_session(
        self,
        pool_name: str = "default",
        read_only: bool = False
    ) -> AsyncSession:
        """
        Get an optimized database session.
        
        Args:
            pool_name: Pool to use
            read_only: Whether this is a read-only session
        
        Yields:
            AsyncSession
        """
        if pool_name not in self._engines:
            await self.create_optimized_engine(pool_name)
        
        session_maker = self._session_makers[pool_name]
        
        async with session_maker() as session:
            # Set session options for read-only
            if read_only:
                await session.execute("SET TRANSACTION READ ONLY")
            
            # Track connection
            self._pool_stats[pool_name]["active_connections"] += 1
            
            try:
                yield session
            finally:
                self._pool_stats[pool_name]["active_connections"] -= 1
                
                # Optimize pool if needed
                await self._optimize_pool_if_needed(pool_name)
    
    async def execute_with_retry(
        self,
        session: AsyncSession,
        query: Any,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Any:
        """
        Execute query with automatic retry on connection errors.
        
        Args:
            session: Database session
            query: Query to execute
            max_retries: Maximum retry attempts
            backoff_factor: Exponential backoff factor
        
        Returns:
            Query result
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                with monitor_performance("db_query_with_retry"):
                    result = await session.execute(query)
                    return result
                    
            except (exc.DBAPIError, exc.OperationalError) as e:
                last_error = e
                
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Query failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    
                    # Rollback the session
                    await session.rollback()
                else:
                    logger.error(f"Query failed after {max_retries} attempts: {e}")
                    raise
        
        raise last_error
    
    async def get_pool_statistics(
        self,
        pool_name: str = "default"
    ) -> Dict[str, Any]:
        """Get detailed pool statistics."""
        if pool_name not in self._engines:
            return {"error": f"Pool '{pool_name}' not found"}
        
        engine = self._engines[pool_name]
        pool = engine.pool
        
        stats = {
            **self._pool_stats[pool_name],
            "pool_size": pool.size() if hasattr(pool, 'size') else 0,
            "checked_in_connections": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
            "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
            "total": pool.total() if hasattr(pool, 'total') else 0,
            "uptime": (
                datetime.utcnow() - self._pool_stats[pool_name]["created_at"]
            ).total_seconds()
        }
        
        # Calculate health score
        if stats["total"] > 0:
            stats["health_score"] = min(100, max(0,
                100 - (stats["slow_queries"] / stats["total_connections"] * 100)
                - (stats["errors"] / stats["total_connections"] * 50)
            ))
        else:
            stats["health_score"] = 100
        
        return stats
    
    async def optimize_all_pools(self):
        """Optimize all connection pools based on usage patterns."""
        for pool_name in list(self._engines.keys()):
            await self._optimize_pool(pool_name)
    
    async def close_all_pools(self):
        """Gracefully close all connection pools."""
        for pool_name, engine in self._engines.items():
            logger.info(f"Closing connection pool '{pool_name}'")
            await engine.dispose()
        
        self._engines.clear()
        self._session_makers.clear()
        self._pool_stats.clear()
    
    def _setup_engine_events(self, engine: AsyncEngine, pool_name: str):
        """Set up event listeners for monitoring."""
        
        @event.listens_for(engine.sync_engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Track new connections."""
            self._pool_stats[pool_name]["total_connections"] += 1
            connection_record.info['connect_time'] = time.time()
        
        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Track connection checkout."""
            connection_record.info['checkout_time'] = time.time()
        
        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Track connection checkin and monitor query time."""
            checkout_time = connection_record.info.get('checkout_time', 0)
            if checkout_time:
                duration = time.time() - checkout_time
                if duration > self.slow_query_threshold:
                    self._pool_stats[pool_name]["slow_queries"] += 1
                    logger.warning(
                        f"Slow query detected in pool '{pool_name}': {duration:.2f}s"
                    )
    
    async def _optimize_pool_if_needed(self, pool_name: str):
        """Optimize pool if enough time has passed."""
        current_time = time.time()
        
        if current_time - self._last_optimization < self._optimization_interval:
            return
        
        self._last_optimization = current_time
        await self._optimize_pool(pool_name)
    
    async def _optimize_pool(self, pool_name: str):
        """Optimize a specific connection pool based on usage."""
        stats = await self.get_pool_statistics(pool_name)
        engine = self._engines[pool_name]
        
        # Calculate optimal pool size based on usage
        active_ratio = stats["active_connections"] / max(stats["pool_size"], 1)
        
        if active_ratio > 0.8:
            # High load - consider increasing pool size
            logger.info(
                f"Pool '{pool_name}' under high load ({active_ratio:.1%}), "
                "consider increasing pool size"
            )
        elif active_ratio < 0.2 and stats["pool_size"] > self.min_pool_size:
            # Low load - consider decreasing pool size
            logger.info(
                f"Pool '{pool_name}' under low load ({active_ratio:.1%}), "
                "consider decreasing pool size"
            )
        
        # Update optimization timestamp
        self._pool_stats[pool_name]["last_optimized"] = datetime.utcnow()
    
    async def create_read_replica_pool(
        self,
        replica_url: str,
        pool_name: str = "read_replica"
    ) -> AsyncEngine:
        """
        Create a connection pool specifically for read replicas.
        
        Args:
            replica_url: Database URL for read replica
            pool_name: Name for this pool
        
        Returns:
            Configured AsyncEngine for read replica
        """
        # Store original URL and use replica URL
        original_url = self.database_url
        self.database_url = replica_url
        
        try:
            # Create engine with read-optimized settings
            engine = await self.create_optimized_engine(
                pool_name=pool_name,
                pool_size=self.max_pool_size,  # More connections for reads
                pool_use_lifo=False,  # Use FIFO for better distribution
            )
            
            return engine
        finally:
            # Restore original URL
            self.database_url = original_url
    
    def get_session_for_workload(
        self,
        workload_type: str = "general"
    ) -> async_sessionmaker:
        """
        Get session maker optimized for specific workload type.
        
        Args:
            workload_type: Type of workload (general, analytics, bulk, realtime)
        
        Returns:
            Async session maker
        """
        pool_configs = {
            "general": {"pool_name": "default"},
            "analytics": {"pool_name": "analytics", "read_only": True},
            "bulk": {"pool_name": "bulk", "pool_size": 10},
            "realtime": {"pool_name": "realtime", "pool_size": 20}
        }
        
        config = pool_configs.get(workload_type, pool_configs["general"])
        pool_name = config["pool_name"]
        
        if pool_name not in self._session_makers:
            asyncio.create_task(
                self.create_optimized_engine(pool_name, **config)
            )
            # Return default until specialized pool is ready
            return self._session_makers.get("default")
        
        return self._session_makers[pool_name]


# Global connection pool optimizer
# Initialize with your database URL when the app starts
connection_pool_optimizer = None

def init_connection_pool_optimizer(database_url: str):
    """Initialize the global connection pool optimizer."""
    global connection_pool_optimizer
    connection_pool_optimizer = ConnectionPoolOptimizer(database_url)
    return connection_pool_optimizer