"""
Automatic failover mechanisms for high availability
"""
import asyncio
import random
from typing import List, Callable, Any, Optional, Dict, TypeVar, Generic
from datetime import datetime, timedelta
from enum import Enum
import hashlib

from core.logging import logger
from core.redis import redis_client
from .circuit_breaker import CircuitBreakerError

T = TypeVar('T')


class FailoverStrategy(Enum):
    """Failover strategies"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    WEIGHTED = "weighted"
    PRIORITY = "priority"
    LEAST_CONNECTIONS = "least_connections"
    CONSISTENT_HASH = "consistent_hash"


class Endpoint:
    """Represents a service endpoint"""
    
    def __init__(
        self,
        name: str,
        url: str,
        priority: int = 0,
        weight: int = 1,
        health_check: Optional[Callable] = None
    ):
        self.name = name
        self.url = url
        self.priority = priority
        self.weight = weight
        self.health_check = health_check
        self.is_healthy = True
        self.last_health_check = None
        self.consecutive_failures = 0
        self.active_connections = 0
    
    async def check_health(self) -> bool:
        """Check if endpoint is healthy"""
        if not self.health_check:
            return True
        
        try:
            result = await self.health_check(self.url)
            self.is_healthy = result
            self.last_health_check = datetime.utcnow()
            
            if result:
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
            
            return result
        except Exception as exc:
            logger.error(f"Health check failed for {self.name}: {exc}")
            self.is_healthy = False
            self.consecutive_failures += 1
            return False


class FailoverManager(Generic[T]):
    """
    Manages failover between multiple endpoints
    """
    
    def __init__(
        self,
        service_name: str,
        endpoints: List[Endpoint],
        strategy: FailoverStrategy = FailoverStrategy.PRIORITY,
        health_check_interval: int = 60,
        max_consecutive_failures: int = 3
    ):
        self.service_name = service_name
        self.endpoints = endpoints
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.max_consecutive_failures = max_consecutive_failures
        
        self._current_index = 0
        self._health_check_task = None
        self._consistent_hash_ring = None
        
        if strategy == FailoverStrategy.CONSISTENT_HASH:
            self._build_hash_ring()
    
    async def start(self):
        """Start health checking"""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Failover manager started for {self.service_name}")
    
    async def stop(self):
        """Stop health checking"""
        if self._health_check_task:
            self._health_check_task.cancel()
            await asyncio.gather(self._health_check_task, return_exceptions=True)
    
    async def _health_check_loop(self):
        """Continuously check endpoint health"""
        while True:
            try:
                await self._check_all_endpoints()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Health check loop error: {exc}")
                await asyncio.sleep(10)
    
    async def _check_all_endpoints(self):
        """Check health of all endpoints"""
        tasks = []
        for endpoint in self.endpoints:
            # Skip if recently checked
            if endpoint.last_health_check:
                time_since_check = datetime.utcnow() - endpoint.last_health_check
                if time_since_check < timedelta(seconds=self.health_check_interval / 2):
                    continue
            
            tasks.append(endpoint.check_health())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Mark endpoints as unhealthy if too many consecutive failures
        for endpoint in self.endpoints:
            if endpoint.consecutive_failures >= self.max_consecutive_failures:
                endpoint.is_healthy = False
                logger.warning(
                    f"Endpoint {endpoint.name} marked unhealthy after "
                    f"{endpoint.consecutive_failures} consecutive failures"
                )
    
    def get_endpoint(self, key: Optional[str] = None) -> Optional[Endpoint]:
        """Get next available endpoint based on strategy"""
        healthy_endpoints = [ep for ep in self.endpoints if ep.is_healthy]
        
        if not healthy_endpoints:
            logger.error(f"No healthy endpoints available for {self.service_name}")
            return None
        
        if self.strategy == FailoverStrategy.ROUND_ROBIN:
            return self._round_robin_select(healthy_endpoints)
        
        elif self.strategy == FailoverStrategy.RANDOM:
            return random.choice(healthy_endpoints)
        
        elif self.strategy == FailoverStrategy.WEIGHTED:
            return self._weighted_select(healthy_endpoints)
        
        elif self.strategy == FailoverStrategy.PRIORITY:
            return self._priority_select(healthy_endpoints)
        
        elif self.strategy == FailoverStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(healthy_endpoints)
        
        elif self.strategy == FailoverStrategy.CONSISTENT_HASH:
            if not key:
                raise ValueError("Key required for consistent hash strategy")
            return self._consistent_hash_select(healthy_endpoints, key)
        
        return healthy_endpoints[0]
    
    def _round_robin_select(self, endpoints: List[Endpoint]) -> Endpoint:
        """Select endpoint using round-robin"""
        endpoint = endpoints[self._current_index % len(endpoints)]
        self._current_index += 1
        return endpoint
    
    def _weighted_select(self, endpoints: List[Endpoint]) -> Endpoint:
        """Select endpoint based on weights"""
        total_weight = sum(ep.weight for ep in endpoints)
        random_weight = random.uniform(0, total_weight)
        
        current_weight = 0
        for endpoint in endpoints:
            current_weight += endpoint.weight
            if current_weight >= random_weight:
                return endpoint
        
        return endpoints[-1]
    
    def _priority_select(self, endpoints: List[Endpoint]) -> Endpoint:
        """Select endpoint with highest priority"""
        # Sort by priority (higher is better)
        sorted_endpoints = sorted(endpoints, key=lambda ep: ep.priority, reverse=True)
        
        # Get all endpoints with highest priority
        highest_priority = sorted_endpoints[0].priority
        top_endpoints = [
            ep for ep in sorted_endpoints
            if ep.priority == highest_priority
        ]
        
        # Round-robin among top priority endpoints
        return self._round_robin_select(top_endpoints)
    
    def _least_connections_select(self, endpoints: List[Endpoint]) -> Endpoint:
        """Select endpoint with least active connections"""
        return min(endpoints, key=lambda ep: ep.active_connections)
    
    def _consistent_hash_select(self, endpoints: List[Endpoint], key: str) -> Endpoint:
        """Select endpoint using consistent hashing"""
        if not self._consistent_hash_ring:
            self._build_hash_ring()
        
        # Hash the key
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)
        
        # Find the endpoint
        for node_hash, endpoint in sorted(self._consistent_hash_ring.items()):
            if key_hash <= node_hash:
                if endpoint in endpoints:
                    return endpoint
        
        # Wrap around to first endpoint
        for _, endpoint in sorted(self._consistent_hash_ring.items()):
            if endpoint in endpoints:
                return endpoint
        
        return endpoints[0]
    
    def _build_hash_ring(self):
        """Build consistent hash ring"""
        self._consistent_hash_ring = {}
        
        # Create multiple virtual nodes for each endpoint
        for endpoint in self.endpoints:
            for i in range(150):  # 150 virtual nodes per endpoint
                virtual_key = f"{endpoint.name}:{i}"
                node_hash = int(hashlib.md5(virtual_key.encode()).hexdigest(), 16)
                self._consistent_hash_ring[node_hash] = endpoint
    
    async def execute_with_failover(
        self,
        func: Callable[..., T],
        *args,
        key: Optional[str] = None,
        max_retries: int = 3,
        **kwargs
    ) -> T:
        """
        Execute function with automatic failover
        """
        exceptions = []
        
        for attempt in range(max_retries):
            endpoint = self.get_endpoint(key)
            if not endpoint:
                raise Exception(f"No healthy endpoints available for {self.service_name}")
            
            try:
                # Track active connections
                endpoint.active_connections += 1
                
                # Execute function with endpoint URL
                result = await func(endpoint.url, *args, **kwargs)
                
                # Mark as successful
                endpoint.consecutive_failures = 0
                return result
                
            except Exception as exc:
                exceptions.append((endpoint.name, exc))
                endpoint.consecutive_failures += 1
                
                # Check if we should mark endpoint as unhealthy
                if endpoint.consecutive_failures >= self.max_consecutive_failures:
                    endpoint.is_healthy = False
                    logger.warning(
                        f"Endpoint {endpoint.name} marked unhealthy after failure"
                    )
                
                # Try next endpoint
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failover from {endpoint.name} to next endpoint "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))  # Brief delay
                
            finally:
                endpoint.active_connections -= 1
        
        # All retries failed
        error_details = "\n".join([
            f"  - {name}: {exc}" for name, exc in exceptions
        ])
        raise Exception(
            f"All failover attempts failed for {self.service_name}:\n{error_details}"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get failover manager status"""
        return {
            'service': self.service_name,
            'strategy': self.strategy.value,
            'endpoints': [
                {
                    'name': ep.name,
                    'url': ep.url,
                    'is_healthy': ep.is_healthy,
                    'priority': ep.priority,
                    'weight': ep.weight,
                    'consecutive_failures': ep.consecutive_failures,
                    'active_connections': ep.active_connections,
                    'last_health_check': ep.last_health_check.isoformat() if ep.last_health_check else None
                }
                for ep in self.endpoints
            ],
            'healthy_count': sum(1 for ep in self.endpoints if ep.is_healthy),
            'total_count': len(self.endpoints)
        }


# Predefined failover configurations
class FailoverConfigurations:
    """Common failover configurations"""
    
    @staticmethod
    def create_onlyfans_failover() -> FailoverManager:
        """Create failover for OnlyFans API"""
        async def health_check(url: str) -> bool:
            """Check OnlyFans API health"""
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}/health",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        return response.status == 200
            except:
                return False
        
        endpoints = [
            Endpoint(
                name="primary",
                url="https://onlyfans.com/api/v2",
                priority=10,
                health_check=health_check
            ),
            Endpoint(
                name="secondary",
                url="https://onlyfans-backup.com/api/v2",
                priority=5,
                health_check=health_check
            )
        ]
        
        return FailoverManager(
            service_name="onlyfans_api",
            endpoints=endpoints,
            strategy=FailoverStrategy.PRIORITY,
            health_check_interval=60
        )
    
    @staticmethod
    def create_database_failover(connections: List[str]) -> FailoverManager:
        """Create failover for database connections"""
        async def health_check(connection_string: str) -> bool:
            """Check database health"""
            from sqlalchemy.ext.asyncio import create_async_engine
            try:
                engine = create_async_engine(connection_string)
                async with engine.connect() as conn:
                    await conn.execute("SELECT 1")
                await engine.dispose()
                return True
            except:
                return False
        
        endpoints = [
            Endpoint(
                name=f"db_{i}",
                url=conn,
                priority=10 if i == 0 else 5,  # Primary gets higher priority
                health_check=health_check
            )
            for i, conn in enumerate(connections)
        ]
        
        return FailoverManager(
            service_name="database",
            endpoints=endpoints,
            strategy=FailoverStrategy.PRIORITY,
            health_check_interval=30
        )
    
    @staticmethod
    def create_cache_failover(redis_urls: List[str]) -> FailoverManager:
        """Create failover for Redis cache"""
        async def health_check(url: str) -> bool:
            """Check Redis health"""
            import aioredis
            try:
                redis = await aioredis.from_url(url)
                await redis.ping()
                await redis.close()
                return True
            except:
                return False
        
        endpoints = [
            Endpoint(
                name=f"redis_{i}",
                url=url,
                weight=100 if i == 0 else 50,  # Primary gets more traffic
                health_check=health_check
            )
            for i, url in enumerate(redis_urls)
        ]
        
        return FailoverManager(
            service_name="redis_cache",
            endpoints=endpoints,
            strategy=FailoverStrategy.WEIGHTED,
            health_check_interval=20
        )