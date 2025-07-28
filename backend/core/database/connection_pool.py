"""
Advanced database connection pooling configuration
"""
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
import asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy import event, pool
import asyncpg

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class DatabasePoolConfig:
    """Configuration for database connection pooling"""
    
    def __init__(
        self,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo_pool: bool = False,
        statsd_client: Optional[Any] = None
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.echo_pool = echo_pool
        self.statsd_client = statsd_client
        
        # Connection retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0
        self.retry_backoff = 2.0
        
        # Performance monitoring
        self.slow_query_threshold = 1.0  # seconds
        self.track_pool_metrics = True


class OptimizedDatabasePool:
    """Optimized database connection pool with monitoring"""
    
    def __init__(self, config: Optional[DatabasePoolConfig] = None):
        self.config = config or DatabasePoolConfig()
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        
        # Pool statistics
        self._stats = {
            "connections_created": 0,
            "connections_closed": 0,
            "connections_recycled": 0,
            "connection_errors": 0,
            "slow_queries": 0
        }
    
    async def initialize(self, database_url: str):
        """Initialize the connection pool"""
        # Configure asyncpg for better performance
        asyncpg_config = {
            "server_settings": {
                "application_name": f"agencydark_{settings.ENVIRONMENT}",
                "jit": "off"  # Disable JIT for more predictable performance
            },
            "command_timeout": 60,
            "max_cached_statement_lifetime": 300,
            "max_cacheable_statement_size": 1024 * 15
        }
        
        # Create engine with optimized pool
        self._engine = create_async_engine(
            database_url,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            echo_pool=self.config.echo_pool,
            poolclass=QueuePool,
            connect_args=asyncpg_config
        )
        
        # Set up event listeners
        self._setup_event_listeners()
        
        # Create session factory
        self._sessionmaker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Warm up the pool
        await self._warmup_pool()
        
        logger.info(
            f"Database pool initialized with size={self.config.pool_size}, "
            f"max_overflow={self.config.max_overflow}"
        )
    
    def _setup_event_listeners(self):
        """Set up SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(self._engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Track connection creation"""
            self._stats["connections_created"] += 1
            
            # Set connection parameters for optimization
            with dbapi_conn.cursor() as cursor:
                # Set statement timeout
                cursor.execute("SET statement_timeout = '30s'")
                # Set lock timeout
                cursor.execute("SET lock_timeout = '10s'")
                # Enable auto explain for slow queries
                cursor.execute("SET auto_explain.log_min_duration = '1s'")
        
        @event.listens_for(self._engine.sync_engine, "close")
        def receive_close(dbapi_conn, connection_record):
            """Track connection closure"""
            self._stats["connections_closed"] += 1
        
        @event.listens_for(self._engine.sync_engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout from pool"""
            # Record checkout time
            connection_record.info["checkout_time"] = asyncio.get_event_loop().time()
        
        @event.listens_for(self._engine.sync_engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Track connection checkin to pool"""
            # Calculate connection usage time
            checkout_time = connection_record.info.get("checkout_time")
            if checkout_time:
                usage_time = asyncio.get_event_loop().time() - checkout_time
                
                # Track slow queries
                if usage_time > self.config.slow_query_threshold:
                    self._stats["slow_queries"] += 1
                    logger.warning(f"Slow query detected: {usage_time:.2f}s")
                
                # Send metrics if configured
                if self.config.statsd_client:
                    self.config.statsd_client.timing(
                        "db.connection.usage_time",
                        usage_time * 1000
                    )
    
    async def _warmup_pool(self):
        """Pre-create connections to warm up the pool"""
        logger.info("Warming up connection pool...")
        
        tasks = []
        for _ in range(min(self.config.pool_size, 5)):
            tasks.append(self._create_warmup_connection())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Connection pool warmed up")
    
    async def _create_warmup_connection(self):
        """Create a single warmup connection"""
        async with self._engine.connect() as conn:
            await conn.execute("SELECT 1")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get a database session with retry logic"""
        retries = 0
        delay = self.config.retry_delay
        
        while retries < self.config.max_retries:
            try:
                async with self._sessionmaker() as session:
                    yield session
                    await session.commit()
                return
            
            except asyncpg.PostgresError as e:
                await session.rollback()
                retries += 1
                
                if retries >= self.config.max_retries:
                    self._stats["connection_errors"] += 1
                    logger.error(f"Database error after {retries} retries: {e}")
                    raise
                
                logger.warning(
                    f"Database error (retry {retries}/{self.config.max_retries}): {e}"
                )
                await asyncio.sleep(delay)
                delay *= self.config.retry_backoff
            
            except Exception as e:
                await session.rollback()
                self._stats["connection_errors"] += 1
                logger.error(f"Unexpected database error: {e}")
                raise
    
    async def execute_with_retry(
        self,
        func,
        *args,
        **kwargs
    ):
        """Execute a database operation with automatic retry"""
        retries = 0
        delay = self.config.retry_delay
        
        while retries < self.config.max_retries:
            try:
                async with self.get_session() as session:
                    return await func(session, *args, **kwargs)
            
            except asyncpg.PostgresError as e:
                retries += 1
                
                if retries >= self.config.max_retries:
                    raise
                
                await asyncio.sleep(delay)
                delay *= self.config.retry_backoff
    
    async def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status and statistics"""
        pool = self._engine.pool
        
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.total(),
            "statistics": self._stats.copy()
        }
    
    async def health_check(self) -> bool:
        """Perform health check on the connection pool"""
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Close the connection pool"""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database pool closed")
    
    def get_engine(self) -> AsyncEngine:
        """Get the underlying engine"""
        return self._engine
    
    def get_sessionmaker(self) -> async_sessionmaker:
        """Get the session factory"""
        return self._sessionmaker


class ConnectionPoolManager:
    """Manage multiple connection pools for different workloads"""
    
    def __init__(self):
        self.pools: Dict[str, OptimizedDatabasePool] = {}
        
        # Define pool configurations for different workloads
        self.pool_configs = {
            "default": DatabasePoolConfig(
                pool_size=20,
                max_overflow=10
            ),
            "analytics": DatabasePoolConfig(
                pool_size=10,
                max_overflow=5,
                pool_timeout=60  # Longer timeout for analytics queries
            ),
            "bulk_operations": DatabasePoolConfig(
                pool_size=5,
                max_overflow=2,
                pool_pre_ping=False  # Disable for bulk operations
            )
        }
    
    async def initialize_pools(self, database_url: str):
        """Initialize all connection pools"""
        for name, config in self.pool_configs.items():
            pool = OptimizedDatabasePool(config)
            await pool.initialize(database_url)
            self.pools[name] = pool
        
        logger.info(f"Initialized {len(self.pools)} connection pools")
    
    def get_pool(self, workload_type: str = "default") -> OptimizedDatabasePool:
        """Get connection pool for specific workload"""
        return self.pools.get(workload_type, self.pools["default"])
    
    async def close_all(self):
        """Close all connection pools"""
        for name, pool in self.pools.items():
            await pool.close()
        
        self.pools.clear()


# Global pool manager instance
pool_manager = ConnectionPoolManager()


# Utility functions
async def get_db_session(workload_type: str = "default") -> AsyncSession:
    """Get a database session for specific workload type"""
    pool = pool_manager.get_pool(workload_type)
    async with pool.get_session() as session:
        yield session


async def init_db_pools(database_url: str = None):
    """Initialize database connection pools"""
    url = database_url or settings.DATABASE_URL
    await pool_manager.initialize_pools(url)


async def close_db_pools():
    """Close all database connection pools"""
    await pool_manager.close_all()