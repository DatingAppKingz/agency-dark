"""
Enhanced Connection Pool Manager - Advanced pooling with dynamic optimization
"""
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import asyncio
import time
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timedelta
import json

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool, Pool
from sqlalchemy import event, text

from core.config import settings
from core.logging import get_logger
from core.redis import redis_client

logger = get_logger(__name__)


@dataclass
class PoolMetrics:
    """Metrics for a connection pool"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    wait_time_total: float = 0
    wait_count: int = 0
    error_count: int = 0
    slow_query_count: int = 0
    queries_executed: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    

@dataclass
class EnhancedPoolConfig:
    """Enhanced configuration for database connection pools"""
    # Basic pool settings
    pool_size: int = 10
    max_overflow: int = 5
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    echo_pool: bool = False
    pre_ping: bool = True
    pool_class: type = QueuePool
    
    # Performance settings
    statement_timeout: int = 30000  # milliseconds
    lock_timeout: int = 10000  # milliseconds
    idle_in_transaction_timeout: int = 60000  # milliseconds
    
    # Query optimization settings
    work_mem: str = "4MB"
    enable_jit: bool = True
    parallel_workers: int = 2
    effective_cache_size: str = "4GB"
    random_page_cost: float = 1.1  # For SSD
    
    # Monitoring settings
    slow_query_threshold: float = 1.0  # seconds
    track_activities: bool = True
    log_min_duration: int = 1000  # milliseconds
    

class EnhancedConnectionPoolManager:
    """Advanced connection pool manager with dynamic optimization"""
    
    def __init__(self):
        self.pools: Dict[str, AsyncEngine] = {}
        self.sessions: Dict[str, sessionmaker] = {}
        self.pool_configs: Dict[str, EnhancedPoolConfig] = {
            "default": EnhancedPoolConfig(
                pool_size=20, 
                max_overflow=10,
                work_mem="4MB",
                parallel_workers=2
            ),
            "analytics": EnhancedPoolConfig(
                pool_size=10, 
                max_overflow=5, 
                pool_timeout=60,
                work_mem="16MB",
                parallel_workers=4,
                statement_timeout=300000  # 5 minutes
            ),
            "bulk_operations": EnhancedPoolConfig(
                pool_size=5, 
                max_overflow=2,
                work_mem="32MB",
                enable_jit=False,  # Disable JIT for bulk ops
                pre_ping=False
            ),
            "reporting": EnhancedPoolConfig(
                pool_size=8, 
                max_overflow=4, 
                pool_timeout=120,
                work_mem="64MB",
                parallel_workers=6,
                statement_timeout=600000  # 10 minutes
            ),
            "realtime": EnhancedPoolConfig(
                pool_size=15, 
                max_overflow=5, 
                pool_timeout=10,
                statement_timeout=10000,  # 10 seconds
                lock_timeout=5000  # 5 seconds
            ),
            "background": EnhancedPoolConfig(
                pool_size=3, 
                max_overflow=1, 
                pool_timeout=300,
                statement_timeout=3600000,  # 1 hour
                enable_jit=False
            )
        }
        self._initialized = False
        self._metrics: Dict[str, PoolMetrics] = defaultdict(PoolMetrics)
        self._query_cache: Dict[str, Any] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize all connection pools"""
        if self._initialized:
            return
            
        for pool_name, config in self.pool_configs.items():
            self.pools[pool_name] = await self._create_optimized_pool(pool_name, config)
            self.sessions[pool_name] = sessionmaker(
                self.pools[pool_name], 
                class_=AsyncSession, 
                expire_on_commit=False
            )
            
        self._initialized = True
        
        # Start monitoring
        self._monitor_task = asyncio.create_task(self._monitor_and_optimize())
        
        logger.info(f"Initialized {len(self.pools)} optimized connection pools")
        
    async def _create_optimized_pool(
        self, 
        name: str, 
        config: EnhancedPoolConfig
    ) -> AsyncEngine:
        """Create an optimized connection pool"""
        # Build connection arguments
        connect_args = {
            "server_settings": {
                "application_name": f"agencydark_{name}",
                "jit": "on" if config.enable_jit else "off",
                "work_mem": config.work_mem,
                "effective_cache_size": config.effective_cache_size,
                "random_page_cost": str(config.random_page_cost),
                "effective_io_concurrency": "200",
                "max_parallel_workers_per_gather": str(config.parallel_workers),
                "statement_timeout": str(config.statement_timeout),
                "lock_timeout": str(config.lock_timeout),
                "idle_in_transaction_session_timeout": str(config.idle_in_transaction_timeout),
                "log_min_duration_statement": str(config.log_min_duration),
                "track_activities": "on" if config.track_activities else "off"
            },
            "command_timeout": config.statement_timeout / 1000,  # Convert to seconds
            "options": "-c default_statistics_target=100"
        }
        
        # Special optimizations for specific pools
        if name == "bulk_operations":
            connect_args["server_settings"].update({
                "synchronous_commit": "off",
                "wal_buffers": "16MB",
                "checkpoint_completion_target": "0.9",
                "max_wal_size": "4GB"
            })
        elif name == "analytics":
            connect_args["server_settings"].update({
                "enable_hashjoin": "on",
                "enable_mergejoin": "on",
                "enable_material": "on",
                "enable_partitionwise_join": "on",
                "enable_partitionwise_aggregate": "on"
            })
            
        engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            echo_pool=config.echo_pool,
            pool_pre_ping=config.pre_ping,
            poolclass=config.pool_class,
            connect_args=connect_args,
            query_cache_size=1200,  # Enable query caching
            execution_options={
                "isolation_level": "READ COMMITTED",
                "postgresql_readonly": name == "reporting",
                "postgresql_deferrable": name == "reporting"
            }
        )
        
        # Setup monitoring
        self._setup_advanced_monitoring(engine, name, config)
        
        # Warm up the pool
        await self._warmup_pool(engine, config.pool_size // 2)
        
        logger.info(f"Created optimized pool '{name}' with advanced configuration")
        return engine
        
    def _setup_advanced_monitoring(
        self, 
        engine: AsyncEngine, 
        pool_name: str, 
        config: EnhancedPoolConfig
    ):
        """Setup advanced monitoring for the pool"""
        pool = engine.pool
        metrics = self._metrics[pool_name]
        
        @event.listens_for(pool, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Enhanced connection tracking"""
            connection_record.info['pool_name'] = pool_name
            connection_record.info['connected_at'] = time.time()
            connection_record.info['queries_count'] = 0
            metrics.total_connections += 1
            
            # Set connection-level parameters
            with dbapi_conn.cursor() as cursor:
                # Enable timing
                cursor.execute("SET track_io_timing = on")
                # Set application name with connection ID
                cursor.execute(
                    f"SET application_name = 'agencydark_{pool_name}_{id(connection_record)}'"
                )
                
        @event.listens_for(pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Enhanced checkout tracking"""
            checkout_time = time.time()
            connection_record.info['checkout_time'] = checkout_time
            
            # Track wait time
            if 'wait_start' in connection_record.info:
                wait_time = checkout_time - connection_record.info['wait_start']
                metrics.wait_time_total += wait_time
                metrics.wait_count += 1
                
                # Log excessive wait times
                if wait_time > config.pool_timeout * 0.5:
                    logger.warning(
                        f"Long wait time for pool '{pool_name}': {wait_time:.2f}s"
                    )
                    
                del connection_record.info['wait_start']
                
            metrics.active_connections += 1
            metrics.idle_connections = max(0, metrics.idle_connections - 1)
            
        @event.listens_for(pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Enhanced checkin tracking"""
            if 'checkout_time' in connection_record.info:
                usage_time = time.time() - connection_record.info['checkout_time']
                queries_count = connection_record.info.get('queries_count', 0)
                
                # Track slow connections
                if usage_time > config.slow_query_threshold:
                    metrics.slow_query_count += 1
                    
                # Reset query count
                connection_record.info['queries_count'] = 0
                del connection_record.info['checkout_time']
                
            metrics.active_connections = max(0, metrics.active_connections - 1)
            metrics.idle_connections += 1
            
    async def _warmup_pool(self, engine: AsyncEngine, size: int):
        """Warm up connection pool"""
        tasks = []
        for _ in range(min(size, 5)):
            tasks.append(self._create_warmup_connection(engine))
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _create_warmup_connection(self, engine: AsyncEngine):
        """Create a single warmup connection"""
        async with engine.connect() as conn:
            # Warm up the connection with a simple query
            await conn.execute(text("SELECT 1"))
            # Prepare common statements
            await conn.execute(text("PREPARE warmup AS SELECT 1"))
            
    def get_pool(self, pool_name: str = "default") -> AsyncEngine:
        """Get a specific connection pool"""
        if not self._initialized:
            raise RuntimeError("Connection pools not initialized")
        return self.pools.get(pool_name, self.pools["default"])
        
    @asynccontextmanager
    async def get_session(self, pool_name: str = "default", **options):
        """Get an optimized database session"""
        if not self._initialized:
            await self.initialize()
            
        SessionClass = self.sessions.get(pool_name, self.sessions["default"])
        
        async with SessionClass() as session:
            # Apply session-level optimizations
            if pool_name == "analytics":
                await session.execute(text("SET enable_seqscan = off"))
            elif pool_name == "bulk_operations":
                await session.execute(text("SET synchronous_commit = off"))
                
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                self._metrics[pool_name].error_count += 1
                self._metrics[pool_name].last_error = str(e)
                raise
            finally:
                await session.close()
                
    async def analyze_pool_performance(self) -> Dict[str, Any]:
        """Analyze performance across all pools"""
        performance_data = {}
        
        for pool_name, engine in self.pools.items():
            pool = engine.pool
            metrics = self._metrics[pool_name]
            
            # Calculate performance indicators
            avg_wait_time = (
                metrics.wait_time_total / metrics.wait_count 
                if metrics.wait_count > 0 else 0
            )
            
            error_rate = (
                metrics.error_count / metrics.queries_executed 
                if metrics.queries_executed > 0 else 0
            )
            
            slow_query_rate = (
                metrics.slow_query_count / metrics.queries_executed 
                if metrics.queries_executed > 0 else 0
            )
            
            # Get pool utilization
            pool_size = pool.size() if hasattr(pool, 'size') else 0
            checked_out = pool.checkedout() if hasattr(pool, 'checkedout') else 0
            utilization = checked_out / pool_size if pool_size > 0 else 0
            
            performance_data[pool_name] = {
                "utilization": utilization,
                "avg_wait_time": avg_wait_time,
                "error_rate": error_rate,
                "slow_query_rate": slow_query_rate,
                "total_queries": metrics.queries_executed,
                "recommendations": self._generate_optimization_recommendations(
                    pool_name, utilization, avg_wait_time, error_rate, slow_query_rate
                )
            }
            
        return performance_data
        
    def _generate_optimization_recommendations(
        self,
        pool_name: str,
        utilization: float,
        avg_wait_time: float,
        error_rate: float,
        slow_query_rate: float
    ) -> List[str]:
        """Generate optimization recommendations for a pool"""
        recommendations = []
        config = self.pool_configs[pool_name]
        
        # Pool size recommendations
        if utilization > 0.8 and avg_wait_time > 1.0:
            recommendations.append(
                f"Increase pool size from {config.pool_size} to {config.pool_size + 5}"
            )
        elif utilization < 0.2 and config.pool_size > 5:
            recommendations.append(
                f"Decrease pool size from {config.pool_size} to {max(5, config.pool_size - 5)}"
            )
            
        # Performance recommendations
        if slow_query_rate > 0.1:
            recommendations.append("Enable query optimization and add missing indexes")
            if config.work_mem == "4MB":
                recommendations.append("Increase work_mem to 8MB for better sort performance")
                
        # Error handling recommendations
        if error_rate > 0.05:
            recommendations.append("Investigate connection errors and timeouts")
            recommendations.append("Consider increasing statement_timeout")
            
        # Wait time recommendations
        if avg_wait_time > 5.0:
            recommendations.append("Critical: Pool exhaustion detected")
            recommendations.append(f"Increase max_overflow from {config.max_overflow}")
            
        return recommendations
        
    async def optimize_pools_dynamically(self):
        """Dynamically optimize pool configurations based on usage"""
        performance = await self.analyze_pool_performance()
        
        for pool_name, perf_data in performance.items():
            config = self.pool_configs[pool_name]
            utilization = perf_data["utilization"]
            avg_wait_time = perf_data["avg_wait_time"]
            
            # Auto-scale pool size
            if utilization > 0.9 and avg_wait_time > 2.0:
                new_size = min(config.pool_size + 2, 50)
                if new_size != config.pool_size:
                    logger.info(
                        f"Auto-scaling pool '{pool_name}' from {config.pool_size} to {new_size}"
                    )
                    config.pool_size = new_size
                    # Note: Pool recreation would be needed for this to take effect
                    
            # Adjust timeouts based on performance
            if perf_data["slow_query_rate"] > 0.2:
                config.statement_timeout = int(config.statement_timeout * 1.5)
                logger.info(
                    f"Increased statement timeout for '{pool_name}' to {config.statement_timeout}ms"
                )
                
    async def _monitor_and_optimize(self):
        """Background monitoring and optimization task"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Collect performance data
                performance = await self.analyze_pool_performance()
                
                # Store metrics in Redis
                await redis_client.setex(
                    f"pool_performance:{datetime.utcnow().timestamp()}",
                    3600,
                    json.dumps(performance)
                )
                
                # Run optimization
                await self.optimize_pools_dynamically()
                
                # Check for critical issues
                for pool_name, perf_data in performance.items():
                    if perf_data["utilization"] > 0.95:
                        logger.critical(f"Pool '{pool_name}' near exhaustion!")
                    if perf_data["error_rate"] > 0.1:
                        logger.error(f"High error rate in pool '{pool_name}'")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in pool monitoring: {e}")
                
    async def get_pool_recommendations(self) -> Dict[str, List[str]]:
        """Get optimization recommendations for all pools"""
        performance = await self.analyze_pool_performance()
        return {
            pool_name: perf_data["recommendations"]
            for pool_name, perf_data in performance.items()
            if perf_data["recommendations"]
        }
        
    async def execute_maintenance(self, pool_name: str = "all"):
        """Execute maintenance operations on pools"""
        pools_to_maintain = (
            [pool_name] if pool_name != "all" 
            else list(self.pools.keys())
        )
        
        for name in pools_to_maintain:
            if name in self.pools:
                engine = self.pools[name]
                
                # Reset metrics
                self._metrics[name] = PoolMetrics()
                
                # Clear connection pool
                await engine.dispose()
                
                # Recreate pool
                config = self.pool_configs[name]
                self.pools[name] = await self._create_optimized_pool(name, config)
                self.sessions[name] = sessionmaker(
                    self.pools[name], 
                    class_=AsyncSession, 
                    expire_on_commit=False
                )
                
                logger.info(f"Completed maintenance on pool '{name}'")
                
    async def close_all(self):
        """Close all connection pools"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        for name, engine in self.pools.items():
            await engine.dispose()
            logger.info(f"Closed connection pool '{name}'")
            
        self.pools.clear()
        self.sessions.clear()
        self._initialized = False


# Global enhanced connection pool manager
enhanced_pool_manager = EnhancedConnectionPoolManager()