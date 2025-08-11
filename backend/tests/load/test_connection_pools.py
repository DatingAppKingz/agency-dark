"""
Connection pool load testing for OAuth implementation.
Tests database and Redis connection pool performance.
"""
import asyncio
import time
import random
from datetime import datetime, timezone
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import psutil
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy import text, pool
import redis.asyncio as redis
import aioredis
from uuid import uuid4


class ConnectionPoolLoadTest:
    """Test connection pool performance under load."""
    
    def __init__(self):
        self.db_engine = None
        self.redis_client = None
        self.metrics = {
            "db_connections": [],
            "redis_connections": [],
            "response_times": [],
            "errors": [],
        }
    
    async def setup_database_pool(self, pool_size: int = 20, max_overflow: int = 10):
        """Set up database connection pool."""
        self.db_engine = create_async_engine(
            "postgresql+asyncpg://test:test@localhost/test_oauth",
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo_pool=True,  # Enable pool logging for debugging
        )
        
        return self.db_engine
    
    async def setup_redis_pool(self, max_connections: int = 50):
        """Set up Redis connection pool."""
        self.redis_client = await redis.from_url(
            "redis://localhost:6379",
            max_connections=max_connections,
            decode_responses=True,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 3,  # TCP_KEEPCNT
            }
        )
        
        return self.redis_client
    
    async def teardown(self):
        """Clean up connections."""
        if self.db_engine:
            await self.db_engine.dispose()
        
        if self.redis_client:
            await self.redis_client.close()
    
    @pytest.mark.asyncio
    async def test_database_pool_saturation(self):
        """Test database connection pool under saturation."""
        pool_size = 20
        max_overflow = 10
        total_pool = pool_size + max_overflow
        
        await self.setup_database_pool(pool_size, max_overflow)
        
        try:
            # Track metrics
            connection_times = []
            pool_exhausted_count = 0
            successful_queries = 0
            failed_queries = 0
            
            async def execute_query(query_id: int):
                """Execute a database query."""
                start_time = time.time()
                
                try:
                    async with self.db_engine.begin() as conn:
                        # Simulate OAuth token query
                        result = await conn.execute(
                            text("""
                                SELECT 
                                    :token_id as token_id,
                                    :user_id as user_id,
                                    NOW() as created_at
                            """),
                            {
                                "token_id": str(uuid4()),
                                "user_id": str(uuid4()),
                            }
                        )
                        
                        # Simulate processing time
                        await asyncio.sleep(random.uniform(0.01, 0.1))
                        
                        connection_time = (time.time() - start_time) * 1000
                        return connection_time, True
                        
                except asyncio.TimeoutError:
                    return None, False
                except Exception as e:
                    print(f"Query {query_id} failed: {e}")
                    return None, False
            
            # Test with increasing concurrent connections
            for concurrent_level in [10, 20, 30, 40, 50]:
                print(f"\nTesting with {concurrent_level} concurrent connections...")
                
                tasks = [
                    execute_query(i) 
                    for i in range(concurrent_level)
                ]
                
                results = await asyncio.gather(*tasks)
                
                # Analyze results
                for conn_time, success in results:
                    if success and conn_time:
                        connection_times.append(conn_time)
                        successful_queries += 1
                    else:
                        failed_queries += 1
                        if concurrent_level > total_pool:
                            pool_exhausted_count += 1
                
                # Get pool statistics
                pool_stats = self.db_engine.pool.status()
                print(f"  Pool Status: {pool_stats}")
                print(f"  Successful: {successful_queries}, Failed: {failed_queries}")
                
                if connection_times:
                    avg_time = sum(connection_times) / len(connection_times)
                    print(f"  Avg Connection Time: {avg_time:.2f}ms")
            
            # Verify pool behavior
            assert pool_exhausted_count > 0, "Pool exhaustion not tested"
            assert successful_queries > failed_queries, "Too many failed queries"
            
            print(f"\nDatabase Pool Test Summary:")
            print(f"  Total Successful Queries: {successful_queries}")
            print(f"  Total Failed Queries: {failed_queries}")
            print(f"  Pool Exhaustion Events: {pool_exhausted_count}")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_redis_pool_performance(self):
        """Test Redis connection pool performance."""
        max_connections = 50
        await self.setup_redis_pool(max_connections)
        
        try:
            operation_times = {
                "set": [],
                "get": [],
                "expire": [],
                "delete": [],
            }
            
            async def redis_operations(op_id: int):
                """Perform Redis operations."""
                results = {}
                
                # Token storage simulation
                token_key = f"oauth:token:{uuid4()}"
                token_data = {
                    "user_id": str(uuid4()),
                    "scope": "read write",
                    "expires_at": time.time() + 3600,
                }
                
                # SET operation
                start = time.time()
                await self.redis_client.hset(
                    token_key,
                    mapping=token_data
                )
                results["set"] = (time.time() - start) * 1000
                
                # GET operation
                start = time.time()
                data = await self.redis_client.hgetall(token_key)
                results["get"] = (time.time() - start) * 1000
                
                # EXPIRE operation
                start = time.time()
                await self.redis_client.expire(token_key, 3600)
                results["expire"] = (time.time() - start) * 1000
                
                # DELETE operation
                start = time.time()
                await self.redis_client.delete(token_key)
                results["delete"] = (time.time() - start) * 1000
                
                return results
            
            # Test with concurrent operations
            for batch_size in [10, 25, 50, 75, 100]:
                print(f"\nTesting Redis with {batch_size} concurrent operations...")
                
                tasks = [redis_operations(i) for i in range(batch_size)]
                results = await asyncio.gather(*tasks)
                
                # Aggregate results
                for result in results:
                    for op, time_ms in result.items():
                        operation_times[op].append(time_ms)
                
                # Get pool info
                pool_info = await self.redis_client.client_info()
                print(f"  Connected Clients: {pool_info.get('connected_clients', 'N/A')}")
                
                # Calculate averages for this batch
                for op in ["set", "get", "expire", "delete"]:
                    if operation_times[op]:
                        avg = sum(operation_times[op][-batch_size:]) / batch_size
                        print(f"  Avg {op.upper()}: {avg:.2f}ms")
            
            # Overall statistics
            print(f"\nRedis Pool Test Summary:")
            for op, times in operation_times.items():
                if times:
                    avg = sum(times) / len(times)
                    p95 = sorted(times)[int(len(times) * 0.95)]
                    print(f"  {op.upper()}: Avg={avg:.2f}ms, P95={p95:.2f}ms")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_connection_pool_recovery(self):
        """Test connection pool recovery after failures."""
        await self.setup_database_pool(pool_size=10, max_overflow=5)
        await self.setup_redis_pool(max_connections=20)
        
        try:
            print("\nTesting connection pool recovery...")
            
            # Simulate connection failures
            async def simulate_db_failure():
                """Simulate database connection failure."""
                try:
                    # Force close some connections
                    await self.db_engine.dispose()
                    await asyncio.sleep(1)
                    # Recreate pool
                    await self.setup_database_pool(pool_size=10, max_overflow=5)
                    return True
                except Exception as e:
                    print(f"DB recovery failed: {e}")
                    return False
            
            async def simulate_redis_failure():
                """Simulate Redis connection failure."""
                try:
                    # Close Redis connection
                    await self.redis_client.close()
                    await asyncio.sleep(1)
                    # Recreate connection
                    await self.setup_redis_pool(max_connections=20)
                    return True
                except Exception as e:
                    print(f"Redis recovery failed: {e}")
                    return False
            
            # Test recovery
            recovery_times = []
            
            for i in range(3):
                print(f"\n  Recovery test iteration {i+1}...")
                
                # Measure recovery time for database
                start = time.time()
                db_recovered = await simulate_db_failure()
                db_recovery_time = (time.time() - start) * 1000
                
                # Measure recovery time for Redis
                start = time.time()
                redis_recovered = await simulate_redis_failure()
                redis_recovery_time = (time.time() - start) * 1000
                
                recovery_times.append({
                    "db": db_recovery_time,
                    "redis": redis_recovery_time,
                })
                
                print(f"    DB Recovery: {db_recovery_time:.2f}ms - {'Success' if db_recovered else 'Failed'}")
                print(f"    Redis Recovery: {redis_recovery_time:.2f}ms - {'Success' if redis_recovered else 'Failed'}")
                
                assert db_recovered, "Database recovery failed"
                assert redis_recovered, "Redis recovery failed"
                
                # Test operations after recovery
                async with self.db_engine.begin() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    assert result.scalar() == 1
                
                await self.redis_client.ping()
            
            # Summary
            avg_db_recovery = sum(r["db"] for r in recovery_times) / len(recovery_times)
            avg_redis_recovery = sum(r["redis"] for r in recovery_times) / len(recovery_times)
            
            print(f"\nRecovery Test Summary:")
            print(f"  Avg DB Recovery: {avg_db_recovery:.2f}ms")
            print(f"  Avg Redis Recovery: {avg_redis_recovery:.2f}ms")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_connection_leak_detection(self):
        """Test for connection leaks in the pool."""
        await self.setup_database_pool(pool_size=5, max_overflow=0)
        
        try:
            print("\nTesting for connection leaks...")
            
            initial_connections = []
            leaked_connections = []
            
            # Get initial connection count
            async with self.db_engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                initial_count = result.scalar()
                initial_connections.append(initial_count)
            
            # Simulate potential leak scenarios
            async def potentially_leaky_operation():
                """Operation that might leak connections."""
                try:
                    # Intentionally not using context manager
                    conn = await self.db_engine.connect()
                    await conn.execute(text("SELECT 1"))
                    # Forgot to close connection (leak)
                    return conn
                except Exception:
                    pass
            
            # Run operations
            for i in range(10):
                conn = await potentially_leaky_operation()
                if conn:
                    leaked_connections.append(conn)
            
            # Check for leaks
            async with self.db_engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                current_count = result.scalar()
            
            # Clean up leaked connections
            for conn in leaked_connections:
                await conn.close()
            
            # Final check
            async with self.db_engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                final_count = result.scalar()
            
            print(f"  Initial connections: {initial_count}")
            print(f"  Peak connections: {current_count}")
            print(f"  Final connections: {final_count}")
            print(f"  Leaked connections detected: {len(leaked_connections)}")
            
            # Verify cleanup
            assert final_count <= initial_count + 1, "Connection leak detected"
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_pool_timeout_behavior(self):
        """Test connection pool timeout behavior."""
        # Small pool to force timeouts
        await self.setup_database_pool(pool_size=2, max_overflow=0)
        
        try:
            print("\nTesting pool timeout behavior...")
            
            timeout_count = 0
            success_count = 0
            
            async def long_running_query(query_id: int):
                """Simulate long-running query."""
                try:
                    async with self.db_engine.begin() as conn:
                        # Hold connection for extended time
                        await conn.execute(text("SELECT pg_sleep(2)"))
                        return True
                except asyncio.TimeoutError:
                    return False
                except Exception as e:
                    print(f"Query {query_id} error: {e}")
                    return False
            
            # Start queries that exceed pool size
            tasks = [long_running_query(i) for i in range(5)]
            
            # Set timeout for gathering
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0
                )
                
                for result in results:
                    if isinstance(result, bool):
                        if result:
                            success_count += 1
                        else:
                            timeout_count += 1
                    else:
                        timeout_count += 1
                        
            except asyncio.TimeoutError:
                timeout_count += len(tasks)
            
            print(f"  Successful queries: {success_count}")
            print(f"  Timed out queries: {timeout_count}")
            
            # Verify some timeouts occurred due to pool exhaustion
            assert timeout_count > 0, "No timeouts detected with small pool"
            
        finally:
            await self.teardown()


class ConcurrentLoadSimulator:
    """Simulate concurrent OAuth load patterns."""
    
    @staticmethod
    async def simulate_burst_traffic(duration: int = 10):
        """Simulate burst traffic pattern."""
        print(f"\nSimulating burst traffic for {duration} seconds...")
        
        metrics = {
            "requests": 0,
            "errors": 0,
            "response_times": [],
        }
        
        async def burst_request():
            """Single burst request."""
            start = time.time()
            try:
                # Simulate OAuth operation
                await asyncio.sleep(random.uniform(0.01, 0.05))
                metrics["requests"] += 1
                elapsed = (time.time() - start) * 1000
                metrics["response_times"].append(elapsed)
                return True
            except Exception:
                metrics["errors"] += 1
                return False
        
        # Generate bursts
        start_time = time.time()
        while time.time() - start_time < duration:
            # Burst of 50-100 requests
            burst_size = random.randint(50, 100)
            tasks = [burst_request() for _ in range(burst_size)]
            await asyncio.gather(*tasks)
            
            # Pause between bursts
            await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Calculate statistics
        avg_response = sum(metrics["response_times"]) / len(metrics["response_times"]) if metrics["response_times"] else 0
        
        print(f"  Total Requests: {metrics['requests']}")
        print(f"  Errors: {metrics['errors']}")
        print(f"  Avg Response: {avg_response:.2f}ms")
        
        return metrics
    
    @staticmethod
    async def simulate_sustained_load(duration: int = 30, rps: int = 100):
        """Simulate sustained load at target RPS."""
        print(f"\nSimulating sustained load at {rps} RPS for {duration} seconds...")
        
        metrics = {
            "requests": 0,
            "errors": 0,
            "response_times": [],
        }
        
        async def sustained_request():
            """Single sustained request."""
            start = time.time()
            try:
                # Simulate OAuth operation
                await asyncio.sleep(random.uniform(0.01, 0.03))
                metrics["requests"] += 1
                elapsed = (time.time() - start) * 1000
                metrics["response_times"].append(elapsed)
                return True
            except Exception:
                metrics["errors"] += 1
                return False
        
        # Generate sustained load
        start_time = time.time()
        request_interval = 1.0 / rps
        
        while time.time() - start_time < duration:
            asyncio.create_task(sustained_request())
            await asyncio.sleep(request_interval)
        
        # Wait for remaining tasks
        await asyncio.sleep(1)
        
        # Calculate statistics
        actual_rps = metrics["requests"] / duration
        avg_response = sum(metrics["response_times"]) / len(metrics["response_times"]) if metrics["response_times"] else 0
        
        print(f"  Target RPS: {rps}, Actual RPS: {actual_rps:.2f}")
        print(f"  Total Requests: {metrics['requests']}")
        print(f"  Errors: {metrics['errors']}")
        print(f"  Avg Response: {avg_response:.2f}ms")
        
        return metrics


if __name__ == "__main__":
    # Run connection pool tests
    async def run_all_tests():
        """Run all connection pool tests."""
        test_suite = ConnectionPoolLoadTest()
        
        print("=" * 60)
        print("OAuth Connection Pool Load Tests")
        print("=" * 60)
        
        # Run tests
        await test_suite.test_database_pool_saturation()
        await test_suite.test_redis_pool_performance()
        await test_suite.test_connection_pool_recovery()
        await test_suite.test_connection_leak_detection()
        await test_suite.test_pool_timeout_behavior()
        
        # Run load simulations
        simulator = ConcurrentLoadSimulator()
        await simulator.simulate_burst_traffic(duration=10)
        await simulator.simulate_sustained_load(duration=20, rps=50)
        
        print("\n" + "=" * 60)
        print("All connection pool tests completed!")
        print("=" * 60)
    
    asyncio.run(run_all_tests())