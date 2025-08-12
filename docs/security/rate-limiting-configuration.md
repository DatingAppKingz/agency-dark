# OAuth Rate Limiting Configuration Guide

## Overview
Rate limiting is crucial for protecting OAuth endpoints from abuse, preventing brute force attacks, and ensuring fair resource usage. This guide provides comprehensive rate limiting strategies and implementations for the Agency Dark OAuth infrastructure.

## Table of Contents
- [Rate Limiting Strategies](#rate-limiting-strategies)
- [Endpoint-Specific Limits](#endpoint-specific-limits)
- [Implementation Patterns](#implementation-patterns)
- [Redis-Based Rate Limiting](#redis-based-rate-limiting)
- [Distributed Rate Limiting](#distributed-rate-limiting)
- [Adaptive Rate Limiting](#adaptive-rate-limiting)
- [Client-Specific Configuration](#client-specific-configuration)
- [Error Handling and Responses](#error-handling-and-responses)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Best Practices](#best-practices)

---

## Rate Limiting Strategies

### Algorithm Comparison

| Algorithm | Description | Pros | Cons | Best For |
|-----------|-------------|------|------|----------|
| **Token Bucket** | Tokens refill at fixed rate | Allows bursts, Simple | Memory overhead | API endpoints |
| **Sliding Window Log** | Tracks exact request times | Most accurate | High memory usage | Critical endpoints |
| **Sliding Window Counter** | Hybrid approach | Good accuracy, Efficient | More complex | High-traffic APIs |
| **Fixed Window** | Reset at intervals | Simple, Low memory | Can allow 2x rate at boundaries | Basic protection |
| **Leaky Bucket** | Fixed output rate | Smooth rate | No bursts allowed | Streaming APIs |

### Strategy Selection

```python
# backend/security/rate_limiting/strategies.py
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

class RateLimitStrategy(Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW_LOG = "sliding_window_log"
    SLIDING_WINDOW_COUNTER = "sliding_window_counter"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"

@dataclass
class RateLimitConfig:
    strategy: RateLimitStrategy
    limit: int  # Number of requests
    window: int  # Time window in seconds
    burst_allowance: Optional[int] = None  # For token bucket
    cost_per_request: int = 1  # For weighted limits

class RateLimitStrategySelector:
    """
    Select appropriate rate limiting strategy based on endpoint characteristics
    """
    
    @staticmethod
    def select_strategy(
        endpoint_type: str,
        expected_traffic: str,
        accuracy_requirement: str
    ) -> RateLimitConfig:
        """
        Select rate limiting strategy based on requirements
        """
        
        strategies = {
            # High accuracy, low traffic
            ("auth", "low", "high"): RateLimitConfig(
                strategy=RateLimitStrategy.SLIDING_WINDOW_LOG,
                limit=10,
                window=60
            ),
            
            # Medium accuracy, high traffic
            ("token", "high", "medium"): RateLimitConfig(
                strategy=RateLimitStrategy.SLIDING_WINDOW_COUNTER,
                limit=100,
                window=60
            ),
            
            # Burst allowance needed
            ("api", "medium", "medium"): RateLimitConfig(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                limit=60,
                window=60,
                burst_allowance=10
            ),
            
            # Simple, low overhead
            ("public", "high", "low"): RateLimitConfig(
                strategy=RateLimitStrategy.FIXED_WINDOW,
                limit=1000,
                window=3600
            )
        }
        
        key = (endpoint_type, expected_traffic, accuracy_requirement)
        return strategies.get(key, RateLimitConfig(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            limit=100,
            window=60
        ))
```

---

## Endpoint-Specific Limits

### OAuth Endpoint Configuration

```python
# backend/security/rate_limiting/endpoint_limits.py
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class EndpointRateLimit:
    path: str
    method: str
    authenticated_limit: int
    unauthenticated_limit: int
    window_seconds: int
    burst_allowance: Optional[int] = None
    cost_function: Optional[str] = None
    bypass_roles: List[str] = field(default_factory=list)
    
class OAuthEndpointLimits:
    """
    Rate limit configuration for OAuth endpoints
    """
    
    ENDPOINT_LIMITS = [
        # Authorization endpoint - strict limits to prevent abuse
        EndpointRateLimit(
            path="/oauth/authorize",
            method="GET",
            authenticated_limit=20,
            unauthenticated_limit=5,
            window_seconds=60,
            burst_allowance=3
        ),
        
        # Token endpoint - moderate limits for normal usage
        EndpointRateLimit(
            path="/oauth/token",
            method="POST",
            authenticated_limit=60,
            unauthenticated_limit=20,
            window_seconds=60,
            cost_function="token_cost"  # Different costs for different grant types
        ),
        
        # Introspection - higher limits for resource servers
        EndpointRateLimit(
            path="/oauth/introspect",
            method="POST",
            authenticated_limit=300,
            unauthenticated_limit=0,  # Requires authentication
            window_seconds=60,
            bypass_roles=["resource_server"]
        ),
        
        # Revocation - moderate limits
        EndpointRateLimit(
            path="/oauth/revoke",
            method="POST",
            authenticated_limit=30,
            unauthenticated_limit=10,
            window_seconds=60
        ),
        
        # User info - standard API limits
        EndpointRateLimit(
            path="/oauth/userinfo",
            method="GET",
            authenticated_limit=120,
            unauthenticated_limit=0,
            window_seconds=60
        ),
        
        # Client registration - strict limits
        EndpointRateLimit(
            path="/oauth/register",
            method="POST",
            authenticated_limit=5,
            unauthenticated_limit=1,
            window_seconds=3600  # Per hour
        ),
        
        # JWKS endpoint - cacheable, higher limits
        EndpointRateLimit(
            path="/.well-known/jwks.json",
            method="GET",
            authenticated_limit=1000,
            unauthenticated_limit=500,
            window_seconds=60
        )
    ]
    
    @classmethod
    def get_limit_for_endpoint(
        cls,
        path: str,
        method: str,
        is_authenticated: bool
    ) -> Optional[EndpointRateLimit]:
        """
        Get rate limit configuration for endpoint
        """
        for limit in cls.ENDPOINT_LIMITS:
            if limit.path == path and limit.method == method:
                return limit
        return None
    
    @staticmethod
    def token_cost(grant_type: str) -> int:
        """
        Calculate cost for token endpoint based on grant type
        """
        costs = {
            "authorization_code": 1,
            "refresh_token": 1,
            "client_credentials": 2,  # Higher cost for service accounts
            "password": 5,  # Discouraged, higher cost
            "device_code": 1
        }
        return costs.get(grant_type, 1)
```

---

## Implementation Patterns

### Base Rate Limiter

```python
# backend/security/rate_limiting/base.py
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
import time
import hashlib

class RateLimiter(ABC):
    """
    Abstract base class for rate limiters
    """
    
    def __init__(self, storage):
        self.storage = storage
    
    @abstractmethod
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed
        
        Returns:
            Tuple of (allowed, metadata)
        """
        pass
    
    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limit for key"""
        pass
    
    def generate_key(
        self,
        identifier: str,
        endpoint: str,
        method: str
    ) -> str:
        """
        Generate rate limit key
        """
        components = [
            "ratelimit",
            identifier,
            endpoint.replace("/", ":"),
            method.lower()
        ]
        return ":".join(components)
    
    def get_headers(
        self,
        limit: int,
        remaining: int,
        reset_time: int
    ) -> Dict[str, str]:
        """
        Generate rate limit headers
        """
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Reset-After": str(max(0, reset_time - int(time.time())))
        }

class TokenBucketRateLimiter(RateLimiter):
    """
    Token bucket rate limiting implementation
    """
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Token bucket algorithm
        """
        now = time.time()
        
        # Get current bucket state
        bucket = await self.storage.get_bucket(key)
        
        if not bucket:
            # Initialize bucket
            bucket = {
                "tokens": limit,
                "last_refill": now
            }
        
        # Calculate tokens to add
        time_passed = now - bucket["last_refill"]
        refill_rate = limit / window
        tokens_to_add = time_passed * refill_rate
        
        # Update bucket
        bucket["tokens"] = min(limit, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now
        
        # Check if request is allowed
        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            allowed = True
        else:
            allowed = False
        
        # Save bucket state
        await self.storage.set_bucket(key, bucket, ttl=window * 2)
        
        # Calculate reset time
        if bucket["tokens"] < limit:
            reset_time = int(now + (limit - bucket["tokens"]) / refill_rate)
        else:
            reset_time = 0
        
        metadata = {
            "tokens_remaining": int(bucket["tokens"]),
            "reset_time": reset_time
        }
        
        return allowed, metadata
    
    async def reset(self, key: str) -> None:
        await self.storage.delete_bucket(key)

class SlidingWindowLogRateLimiter(RateLimiter):
    """
    Sliding window log rate limiting (most accurate)
    """
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Sliding window log algorithm
        """
        now = time.time()
        window_start = now - window
        
        # Get request log
        requests = await self.storage.get_requests(key, window_start)
        
        # Calculate total cost in window
        total_cost = sum(r.get("cost", 1) for r in requests)
        
        # Check if allowed
        if total_cost + cost <= limit:
            # Add request to log
            await self.storage.add_request(key, {
                "timestamp": now,
                "cost": cost
            })
            allowed = True
            remaining = limit - total_cost - cost
        else:
            allowed = False
            remaining = limit - total_cost
        
        # Calculate reset time (when oldest request expires)
        if requests:
            oldest = min(r["timestamp"] for r in requests)
            reset_time = int(oldest + window)
        else:
            reset_time = 0
        
        metadata = {
            "requests_in_window": len(requests),
            "remaining": max(0, remaining),
            "reset_time": reset_time
        }
        
        return allowed, metadata
    
    async def reset(self, key: str) -> None:
        await self.storage.clear_requests(key)

class SlidingWindowCounterRateLimiter(RateLimiter):
    """
    Sliding window counter (hybrid approach)
    """
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Sliding window counter algorithm
        """
        now = time.time()
        current_window = int(now // window)
        previous_window = current_window - 1
        
        # Get counters for current and previous windows
        current_count = await self.storage.get_counter(
            f"{key}:{current_window}"
        ) or 0
        previous_count = await self.storage.get_counter(
            f"{key}:{previous_window}"
        ) or 0
        
        # Calculate weighted count
        window_position = (now % window) / window
        weighted_count = (
            previous_count * (1 - window_position) +
            current_count
        )
        
        # Check if allowed
        if weighted_count + cost <= limit:
            # Increment current window counter
            await self.storage.increment_counter(
                f"{key}:{current_window}",
                cost,
                ttl=window * 2
            )
            allowed = True
            remaining = limit - weighted_count - cost
        else:
            allowed = False
            remaining = limit - weighted_count
        
        # Calculate reset time
        reset_time = (current_window + 1) * window
        
        metadata = {
            "weighted_count": weighted_count,
            "remaining": max(0, int(remaining)),
            "reset_time": int(reset_time)
        }
        
        return allowed, metadata
    
    async def reset(self, key: str) -> None:
        now = time.time()
        window_duration = 60  # Default, should be configurable
        current_window = int(now // window_duration)
        previous_window = current_window - 1
        
        await self.storage.delete_counter(f"{key}:{current_window}")
        await self.storage.delete_counter(f"{key}:{previous_window}")
```

---

## Redis-Based Rate Limiting

### Redis Storage Implementation

```python
# backend/security/rate_limiting/redis_storage.py
import redis.asyncio as redis
import json
from typing import Optional, Dict, List, Any
import time

class RedisRateLimitStorage:
    """
    Redis storage backend for rate limiting
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    # Token Bucket Storage
    async def get_bucket(self, key: str) -> Optional[Dict]:
        """Get token bucket state"""
        data = await self.redis.get(f"bucket:{key}")
        if data:
            return json.loads(data)
        return None
    
    async def set_bucket(self, key: str, bucket: Dict, ttl: int) -> None:
        """Set token bucket state"""
        await self.redis.setex(
            f"bucket:{key}",
            ttl,
            json.dumps(bucket)
        )
    
    async def delete_bucket(self, key: str) -> None:
        """Delete token bucket"""
        await self.redis.delete(f"bucket:{key}")
    
    # Sliding Window Log Storage
    async def get_requests(self, key: str, since: float) -> List[Dict]:
        """Get requests since timestamp"""
        # Use Redis sorted set
        requests = await self.redis.zrangebyscore(
            f"requests:{key}",
            since,
            "+inf",
            withscores=True
        )
        
        result = []
        for value, score in requests:
            data = json.loads(value)
            data["timestamp"] = score
            result.append(data)
        
        return result
    
    async def add_request(self, key: str, request: Dict) -> None:
        """Add request to log"""
        timestamp = request.pop("timestamp")
        
        # Add to sorted set
        await self.redis.zadd(
            f"requests:{key}",
            {json.dumps(request): timestamp}
        )
        
        # Set expiration
        await self.redis.expire(f"requests:{key}", 7200)  # 2 hours
        
        # Remove old entries
        cutoff = time.time() - 7200
        await self.redis.zremrangebyscore(
            f"requests:{key}",
            "-inf",
            cutoff
        )
    
    async def clear_requests(self, key: str) -> None:
        """Clear request log"""
        await self.redis.delete(f"requests:{key}")
    
    # Sliding Window Counter Storage
    async def get_counter(self, key: str) -> Optional[int]:
        """Get counter value"""
        value = await self.redis.get(f"counter:{key}")
        if value:
            return int(value)
        return None
    
    async def increment_counter(
        self,
        key: str,
        amount: int,
        ttl: int
    ) -> int:
        """Increment counter atomically"""
        pipe = self.redis.pipeline()
        pipe.incrby(f"counter:{key}", amount)
        pipe.expire(f"counter:{key}", ttl)
        results = await pipe.execute()
        return results[0]
    
    async def delete_counter(self, key: str) -> None:
        """Delete counter"""
        await self.redis.delete(f"counter:{key}")
    
    # Lua Scripts for Atomic Operations
    async def load_lua_scripts(self):
        """Load Lua scripts for atomic rate limiting"""
        
        # Token bucket script
        self.token_bucket_script = await self.redis.script_load("""
            local key = KEYS[1]
            local limit = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local cost = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])
            
            local bucket = redis.call('GET', key)
            if bucket then
                bucket = cjson.decode(bucket)
            else
                bucket = {tokens = limit, last_refill = now}
            end
            
            -- Refill tokens
            local time_passed = now - bucket.last_refill
            local refill_rate = limit / window
            local tokens_to_add = time_passed * refill_rate
            bucket.tokens = math.min(limit, bucket.tokens + tokens_to_add)
            bucket.last_refill = now
            
            -- Check if allowed
            if bucket.tokens >= cost then
                bucket.tokens = bucket.tokens - cost
                redis.call('SETEX', key, window * 2, cjson.encode(bucket))
                return {1, bucket.tokens}
            else
                redis.call('SETEX', key, window * 2, cjson.encode(bucket))
                return {0, bucket.tokens}
            end
        """)
        
        # Sliding window counter script
        self.sliding_window_script = await self.redis.script_load("""
            local key = KEYS[1]
            local limit = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local cost = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])
            
            local current_window = math.floor(now / window)
            local previous_window = current_window - 1
            
            local current_key = key .. ':' .. current_window
            local previous_key = key .. ':' .. previous_window
            
            local current_count = redis.call('GET', current_key) or 0
            local previous_count = redis.call('GET', previous_key) or 0
            
            current_count = tonumber(current_count)
            previous_count = tonumber(previous_count)
            
            -- Calculate weighted count
            local window_position = (now % window) / window
            local weighted_count = previous_count * (1 - window_position) + current_count
            
            if weighted_count + cost <= limit then
                redis.call('INCRBY', current_key, cost)
                redis.call('EXPIRE', current_key, window * 2)
                return {1, limit - weighted_count - cost}
            else
                return {0, limit - weighted_count}
            end
        """)
    
    async def token_bucket_atomic(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, float]:
        """Atomic token bucket check using Lua script"""
        result = await self.redis.evalsha(
            self.token_bucket_script,
            1,
            key,
            limit,
            window,
            cost,
            time.time()
        )
        return bool(result[0]), result[1]
```

---

## Distributed Rate Limiting

### Multi-Node Coordination

```python
# backend/security/rate_limiting/distributed.py
from typing import List, Dict, Any, Optional
import asyncio
import aiohttp
from dataclasses import dataclass

@dataclass
class NodeInfo:
    node_id: str
    url: str
    weight: float = 1.0
    healthy: bool = True

class DistributedRateLimiter:
    """
    Distributed rate limiting across multiple nodes
    """
    
    def __init__(
        self,
        nodes: List[NodeInfo],
        redis_cluster,
        consistency_level: str = "eventual"
    ):
        self.nodes = nodes
        self.redis = redis_cluster
        self.consistency_level = consistency_level
        self.local_cache = {}
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Check rate limit across distributed system
        """
        
        if self.consistency_level == "strong":
            return await self.strong_consistency_check(key, limit, window, cost)
        elif self.consistency_level == "eventual":
            return await self.eventual_consistency_check(key, limit, window, cost)
        else:
            return await self.best_effort_check(key, limit, window, cost)
    
    async def strong_consistency_check(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int
    ) -> Tuple[bool, Dict]:
        """
        Strong consistency using distributed lock
        """
        lock_key = f"ratelimit:lock:{key}"
        
        # Acquire distributed lock
        lock = await self.acquire_lock(lock_key, timeout=5)
        if not lock:
            # Couldn't acquire lock, fail closed
            return False, {"error": "lock_timeout"}
        
        try:
            # Perform rate limit check
            result = await self.centralized_check(key, limit, window, cost)
            return result
        finally:
            await self.release_lock(lock_key)
    
    async def eventual_consistency_check(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int
    ) -> Tuple[bool, Dict]:
        """
        Eventual consistency with local quota
        """
        # Calculate local quota
        local_quota = limit // len(self.nodes)
        
        # Check local quota first
        local_result = await self.local_check(key, local_quota, window, cost)
        
        if local_result[0]:
            # Local quota available
            return local_result
        
        # Try to borrow from other nodes
        borrowed = await self.try_borrow_quota(key, cost)
        if borrowed:
            return True, {"borrowed": True}
        
        return False, {"exhausted": True}
    
    async def best_effort_check(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int
    ) -> Tuple[bool, Dict]:
        """
        Best effort with async replication
        """
        # Check against local view
        local_count = await self.get_local_count(key)
        
        if local_count + cost <= limit:
            # Update local count
            await self.increment_local_count(key, cost)
            
            # Async replicate to other nodes
            asyncio.create_task(
                self.replicate_to_nodes(key, cost)
            )
            
            return True, {"count": local_count + cost}
        
        return False, {"count": local_count}
    
    async def acquire_lock(
        self,
        lock_key: str,
        timeout: int
    ) -> Optional[str]:
        """
        Acquire distributed lock using Redis
        """
        lock_id = f"{self.node_id}:{time.time()}"
        
        acquired = await self.redis.set(
            lock_key,
            lock_id,
            nx=True,
            ex=timeout
        )
        
        if acquired:
            return lock_id
        return None
    
    async def release_lock(self, lock_key: str) -> None:
        """
        Release distributed lock
        """
        await self.redis.delete(lock_key)
    
    async def try_borrow_quota(self, key: str, cost: int) -> bool:
        """
        Try to borrow quota from other nodes
        """
        for node in self.nodes:
            if not node.healthy or node.node_id == self.node_id:
                continue
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{node.url}/internal/rate-limit/borrow",
                        json={"key": key, "cost": cost},
                        timeout=aiohttp.ClientTimeout(total=1)
                    ) as response:
                        if response.status == 200:
                            return True
            except:
                # Mark node as unhealthy
                node.healthy = False
        
        return False
    
    async def replicate_to_nodes(self, key: str, cost: int) -> None:
        """
        Replicate rate limit update to other nodes
        """
        tasks = []
        for node in self.nodes:
            if node.node_id != self.node_id and node.healthy:
                tasks.append(
                    self.replicate_to_node(node, key, cost)
                )
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def replicate_to_node(
        self,
        node: NodeInfo,
        key: str,
        cost: int
    ) -> None:
        """
        Replicate to single node
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{node.url}/internal/rate-limit/sync",
                    json={"key": key, "cost": cost},
                    timeout=aiohttp.ClientTimeout(total=1)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to sync with node {node.node_id}")
        except Exception as e:
            logger.error(f"Error syncing with node {node.node_id}: {e}")
```

---

## Adaptive Rate Limiting

### Dynamic Rate Adjustment

```python
# backend/security/rate_limiting/adaptive.py
from typing import Dict, Any, Optional, List
import statistics
import time
from collections import deque
from dataclasses import dataclass, field

@dataclass
class SystemMetrics:
    cpu_usage: float
    memory_usage: float
    response_time_p95: float
    error_rate: float
    timestamp: float = field(default_factory=time.time)

class AdaptiveRateLimiter:
    """
    Adaptive rate limiting based on system health
    """
    
    def __init__(
        self,
        base_limiter: RateLimiter,
        metrics_provider
    ):
        self.base_limiter = base_limiter
        self.metrics_provider = metrics_provider
        
        # Configuration
        self.adjustment_interval = 60  # seconds
        self.history_size = 10
        
        # Thresholds
        self.thresholds = {
            "cpu_critical": 80,
            "cpu_warning": 60,
            "memory_critical": 85,
            "memory_warning": 70,
            "response_time_critical": 1000,  # ms
            "response_time_warning": 500,
            "error_rate_critical": 0.05,
            "error_rate_warning": 0.01
        }
        
        # State
        self.metrics_history = deque(maxlen=self.history_size)
        self.current_multiplier = 1.0
        self.last_adjustment = time.time()
    
    async def check_and_adapt(
        self,
        key: str,
        base_limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Check rate limit with adaptive adjustment
        """
        # Update multiplier if needed
        await self.maybe_adjust_limits()
        
        # Apply multiplier to limit
        adjusted_limit = int(base_limit * self.current_multiplier)
        
        # Perform rate limit check
        allowed, metadata = await self.base_limiter.is_allowed(
            key,
            adjusted_limit,
            window,
            cost
        )
        
        # Add adjustment info to metadata
        metadata["base_limit"] = base_limit
        metadata["adjusted_limit"] = adjusted_limit
        metadata["multiplier"] = self.current_multiplier
        
        return allowed, metadata
    
    async def maybe_adjust_limits(self) -> None:
        """
        Adjust limits based on system metrics
        """
        now = time.time()
        
        if now - self.last_adjustment < self.adjustment_interval:
            return
        
        # Get current metrics
        metrics = await self.metrics_provider.get_metrics()
        self.metrics_history.append(metrics)
        
        # Calculate new multiplier
        new_multiplier = self.calculate_multiplier(metrics)
        
        if new_multiplier != self.current_multiplier:
            logger.info(
                f"Adjusting rate limit multiplier: "
                f"{self.current_multiplier} -> {new_multiplier}"
            )
            self.current_multiplier = new_multiplier
        
        self.last_adjustment = now
    
    def calculate_multiplier(self, metrics: SystemMetrics) -> float:
        """
        Calculate rate limit multiplier based on system health
        """
        multiplier = 1.0
        
        # CPU-based adjustment
        if metrics.cpu_usage > self.thresholds["cpu_critical"]:
            multiplier *= 0.5
        elif metrics.cpu_usage > self.thresholds["cpu_warning"]:
            multiplier *= 0.75
        
        # Memory-based adjustment
        if metrics.memory_usage > self.thresholds["memory_critical"]:
            multiplier *= 0.5
        elif metrics.memory_usage > self.thresholds["memory_warning"]:
            multiplier *= 0.75
        
        # Response time adjustment
        if metrics.response_time_p95 > self.thresholds["response_time_critical"]:
            multiplier *= 0.6
        elif metrics.response_time_p95 > self.thresholds["response_time_warning"]:
            multiplier *= 0.8
        
        # Error rate adjustment
        if metrics.error_rate > self.thresholds["error_rate_critical"]:
            multiplier *= 0.5
        elif metrics.error_rate > self.thresholds["error_rate_warning"]:
            multiplier *= 0.75
        
        # Consider historical trend
        if len(self.metrics_history) >= 3:
            trend_multiplier = self.calculate_trend_multiplier()
            multiplier *= trend_multiplier
        
        # Clamp multiplier
        return max(0.1, min(1.5, multiplier))
    
    def calculate_trend_multiplier(self) -> float:
        """
        Calculate multiplier based on metrics trend
        """
        if len(self.metrics_history) < 3:
            return 1.0
        
        # Get recent CPU usage
        recent_cpu = [m.cpu_usage for m in self.metrics_history]
        
        # Calculate trend (positive = increasing)
        trend = statistics.mean(recent_cpu[-3:]) - statistics.mean(recent_cpu[:-3])
        
        if trend > 10:  # Rapid increase
            return 0.8
        elif trend > 5:  # Moderate increase
            return 0.9
        elif trend < -5:  # Decreasing
            return 1.1
        
        return 1.0

class PredictiveRateLimiter:
    """
    Predictive rate limiting using ML models
    """
    
    def __init__(self, model_path: str):
        self.model = self.load_model(model_path)
        self.feature_buffer = deque(maxlen=100)
    
    async def predict_load(self, time_window: int = 300) -> float:
        """
        Predict system load for next time window
        """
        features = self.extract_features()
        prediction = self.model.predict(features)
        
        return prediction[0]
    
    def extract_features(self) -> np.array:
        """
        Extract features for prediction
        """
        features = []
        
        # Time-based features
        now = datetime.now()
        features.extend([
            now.hour,
            now.weekday(),
            now.day,
            now.month
        ])
        
        # Historical patterns
        if self.feature_buffer:
            recent = list(self.feature_buffer)[-10:]
            features.extend([
                statistics.mean(recent),
                statistics.stdev(recent) if len(recent) > 1 else 0,
                max(recent),
                min(recent)
            ])
        else:
            features.extend([0, 0, 0, 0])
        
        return np.array(features).reshape(1, -1)
```

---

## Client-Specific Configuration

### Per-Client Rate Limits

```python
# backend/security/rate_limiting/client_config.py
from typing import Dict, Optional, List
from dataclasses import dataclass
import yaml

@dataclass
class ClientRateLimitConfig:
    client_id: str
    limits: Dict[str, int]  # endpoint -> limit
    window: int = 60
    burst_allowance: Optional[int] = None
    tier: str = "standard"
    custom_rules: List[Dict] = None

class ClientRateLimitManager:
    """
    Manage per-client rate limit configurations
    """
    
    def __init__(self, config_path: str):
        self.configs = self.load_configs(config_path)
        self.tiers = self.define_tiers()
    
    def load_configs(self, config_path: str) -> Dict[str, ClientRateLimitConfig]:
        """
        Load client configurations from file
        """
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        configs = {}
        for client_data in data.get('clients', []):
            config = ClientRateLimitConfig(**client_data)
            configs[config.client_id] = config
        
        return configs
    
    def define_tiers(self) -> Dict[str, Dict]:
        """
        Define rate limit tiers
        """
        return {
            "free": {
                "token": 10,
                "introspect": 50,
                "userinfo": 20,
                "window": 60
            },
            "standard": {
                "token": 60,
                "introspect": 200,
                "userinfo": 100,
                "window": 60
            },
            "premium": {
                "token": 200,
                "introspect": 1000,
                "userinfo": 500,
                "window": 60
            },
            "enterprise": {
                "token": 1000,
                "introspect": 5000,
                "userinfo": 2000,
                "window": 60
            }
        }
    
    def get_client_limit(
        self,
        client_id: str,
        endpoint: str
    ) -> Optional[Dict]:
        """
        Get rate limit for client and endpoint
        """
        # Check custom config
        if client_id in self.configs:
            config = self.configs[client_id]
            
            # Check endpoint-specific limit
            if endpoint in config.limits:
                return {
                    "limit": config.limits[endpoint],
                    "window": config.window,
                    "burst": config.burst_allowance
                }
            
            # Fall back to tier
            tier = config.tier
        else:
            # Default tier
            tier = "standard"
        
        # Get tier limits
        if tier in self.tiers:
            tier_config = self.tiers[tier]
            endpoint_key = endpoint.split("/")[-1]  # Simplify endpoint
            
            if endpoint_key in tier_config:
                return {
                    "limit": tier_config[endpoint_key],
                    "window": tier_config.get("window", 60),
                    "burst": None
                }
        
        return None
    
    def apply_custom_rules(
        self,
        client_id: str,
        context: Dict
    ) -> Optional[Dict]:
        """
        Apply custom rate limiting rules
        """
        if client_id not in self.configs:
            return None
        
        config = self.configs[client_id]
        if not config.custom_rules:
            return None
        
        for rule in config.custom_rules:
            if self.evaluate_rule(rule, context):
                return {
                    "limit": rule.get("limit"),
                    "window": rule.get("window", 60),
                    "action": rule.get("action", "limit")
                }
        
        return None
    
    def evaluate_rule(self, rule: Dict, context: Dict) -> bool:
        """
        Evaluate custom rule condition
        """
        condition = rule.get("condition", {})
        
        for key, value in condition.items():
            if key not in context:
                return False
            
            if isinstance(value, dict):
                # Complex condition
                operator = value.get("operator", "eq")
                operand = value.get("value")
                
                if operator == "eq" and context[key] != operand:
                    return False
                elif operator == "gt" and context[key] <= operand:
                    return False
                elif operator == "lt" and context[key] >= operand:
                    return False
                elif operator == "in" and context[key] not in operand:
                    return False
            else:
                # Simple equality
                if context[key] != value:
                    return False
        
        return True
```

### Client Configuration File

```yaml
# config/rate_limits.yaml
clients:
  - client_id: "premium-client-001"
    tier: "premium"
    limits:
      "/oauth/token": 500
      "/oauth/introspect": 2000
      "/oauth/userinfo": 1000
    window: 60
    burst_allowance: 50
    custom_rules:
      - condition:
          ip_country: "US"
          time_of_day:
            operator: "gt"
            value: 22
        limit: 100
        window: 60
        action: "limit"
  
  - client_id: "enterprise-client-001"
    tier: "enterprise"
    limits:
      "/oauth/token": 2000
      "/oauth/introspect": 10000
    window: 60
  
  - client_id: "restricted-client-001"
    tier: "free"
    limits:
      "/oauth/token": 5
    window: 60
    custom_rules:
      - condition:
          suspicious_activity: true
        limit: 1
        window: 300
        action: "block"

tiers:
  free:
    daily_limit: 1000
    burst_limit: 10
  standard:
    daily_limit: 10000
    burst_limit: 100
  premium:
    daily_limit: 100000
    burst_limit: 500
  enterprise:
    daily_limit: 1000000
    burst_limit: 2000
```

---

## Error Handling and Responses

### Rate Limit Response Handler

```python
# backend/security/rate_limiting/responses.py
from fastapi import HTTPException, Response, Request
from fastapi.responses import JSONResponse
from typing import Dict, Optional
import time

class RateLimitResponse:
    """
    Standard rate limit response handler
    """
    
    @staticmethod
    def create_rate_limit_response(
        request: Request,
        metadata: Dict,
        retry_after: Optional[int] = None
    ) -> Response:
        """
        Create rate limit exceeded response
        """
        # Calculate retry after
        if not retry_after and "reset_time" in metadata:
            retry_after = max(1, metadata["reset_time"] - int(time.time()))
        
        # Build response body
        response_body = {
            "error": "rate_limit_exceeded",
            "error_description": "API rate limit exceeded",
            "retry_after": retry_after
        }
        
        # Add details based on verbosity setting
        if request.app.state.rate_limit_verbose:
            response_body.update({
                "limit": metadata.get("limit"),
                "remaining": metadata.get("remaining", 0),
                "reset": metadata.get("reset_time")
            })
        
        # Create response
        response = JSONResponse(
            status_code=429,
            content=response_body
        )
        
        # Add headers
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(metadata.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(max(0, metadata.get("remaining", 0)))
        response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", 0))
        
        # Add custom headers for debugging
        if request.app.state.debug:
            response.headers["X-RateLimit-Key"] = metadata.get("key", "")
            response.headers["X-RateLimit-Strategy"] = metadata.get("strategy", "")
        
        return response
    
    @staticmethod
    def create_service_unavailable_response(
        reason: str = "Service temporarily unavailable"
    ) -> Response:
        """
        Create service unavailable response for circuit breaker
        """
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_unavailable",
                "error_description": reason
            },
            headers={
                "Retry-After": "60"
            }
        )

class RateLimitMiddleware:
    """
    Rate limiting middleware for FastAPI
    """
    
    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        config_manager: ClientRateLimitManager
    ):
        self.app = app
        self.rate_limiter = rate_limiter
        self.config_manager = config_manager
    
    async def __call__(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Identify client
        client_id = self.identify_client(request)
        
        # Get rate limit configuration
        limit_config = self.config_manager.get_client_limit(
            client_id,
            request.url.path
        )
        
        if not limit_config:
            # No specific limit, use defaults
            limit_config = {
                "limit": 100,
                "window": 60
            }
        
        # Generate rate limit key
        key = self.rate_limiter.generate_key(
            client_id,
            request.url.path,
            request.method
        )
        
        # Check rate limit
        allowed, metadata = await self.rate_limiter.is_allowed(
            key,
            limit_config["limit"],
            limit_config["window"]
        )
        
        if not allowed:
            return RateLimitResponse.create_rate_limit_response(
                request,
                metadata
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        for header, value in self.rate_limiter.get_headers(
            limit_config["limit"],
            metadata.get("remaining", 0),
            metadata.get("reset_time", 0)
        ).items():
            response.headers[header] = value
        
        return response
    
    def identify_client(self, request: Request) -> str:
        """
        Identify client from request
        """
        # Try OAuth client ID
        if hasattr(request.state, "client_id"):
            return request.state.client_id
        
        # Try API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key[:8]}"
        
        # Try user ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Fall back to IP
        return f"ip:{request.client.host}"
```

---

## Monitoring and Alerting

### Rate Limit Metrics

```python
# backend/security/rate_limiting/monitoring.py
from prometheus_client import Counter, Histogram, Gauge
from typing import Dict, List
import time

class RateLimitMetrics:
    """
    Metrics collection for rate limiting
    """
    
    def __init__(self):
        # Counters
        self.requests_total = Counter(
            'rate_limit_requests_total',
            'Total rate limit checks',
            ['endpoint', 'client_type', 'result']
        )
        
        self.requests_blocked = Counter(
            'rate_limit_requests_blocked_total',
            'Total requests blocked by rate limiting',
            ['endpoint', 'client_type', 'reason']
        )
        
        # Histograms
        self.check_duration = Histogram(
            'rate_limit_check_duration_seconds',
            'Time to check rate limit',
            ['strategy']
        )
        
        self.tokens_remaining = Histogram(
            'rate_limit_tokens_remaining',
            'Tokens remaining after request',
            ['endpoint', 'client_type'],
            buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500, 1000]
        )
        
        # Gauges
        self.active_limiters = Gauge(
            'rate_limit_active_limiters',
            'Number of active rate limiters'
        )
        
        self.multiplier = Gauge(
            'rate_limit_adaptive_multiplier',
            'Current adaptive rate limit multiplier'
        )
    
    def record_check(
        self,
        endpoint: str,
        client_type: str,
        allowed: bool,
        duration: float,
        remaining: int
    ):
        """
        Record rate limit check
        """
        result = "allowed" if allowed else "blocked"
        
        self.requests_total.labels(
            endpoint=endpoint,
            client_type=client_type,
            result=result
        ).inc()
        
        if not allowed:
            self.requests_blocked.labels(
                endpoint=endpoint,
                client_type=client_type,
                reason="rate_limit"
            ).inc()
        
        self.check_duration.labels(
            strategy="default"
        ).observe(duration)
        
        self.tokens_remaining.labels(
            endpoint=endpoint,
            client_type=client_type
        ).observe(remaining)

class RateLimitAlerting:
    """
    Alerting for rate limit events
    """
    
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.thresholds = {
            "block_rate_warning": 0.1,  # 10% blocked
            "block_rate_critical": 0.25,  # 25% blocked
            "client_block_threshold": 100,  # Blocks per client
            "endpoint_block_threshold": 1000  # Blocks per endpoint
        }
    
    async def check_alerts(self, metrics: Dict):
        """
        Check metrics and send alerts
        """
        # Check overall block rate
        total_requests = metrics.get("total_requests", 0)
        blocked_requests = metrics.get("blocked_requests", 0)
        
        if total_requests > 0:
            block_rate = blocked_requests / total_requests
            
            if block_rate > self.thresholds["block_rate_critical"]:
                await self.send_alert(
                    severity="critical",
                    title="High rate limit block rate",
                    description=f"Block rate: {block_rate:.2%}"
                )
            elif block_rate > self.thresholds["block_rate_warning"]:
                await self.send_alert(
                    severity="warning",
                    title="Elevated rate limit blocks",
                    description=f"Block rate: {block_rate:.2%}"
                )
        
        # Check per-client blocks
        for client_id, blocks in metrics.get("client_blocks", {}).items():
            if blocks > self.thresholds["client_block_threshold"]:
                await self.send_alert(
                    severity="warning",
                    title=f"High block rate for client {client_id}",
                    description=f"Blocked {blocks} requests"
                )
    
    async def send_alert(
        self,
        severity: str,
        title: str,
        description: str
    ):
        """
        Send alert through configured channels
        """
        await self.alert_manager.send_alert({
            "severity": severity,
            "title": title,
            "description": description,
            "source": "rate_limiting",
            "timestamp": time.time()
        })
```

---

## Best Practices

### Configuration Best Practices

```yaml
# Best practice rate limit configuration
rate_limiting:
  # Use different strategies for different endpoints
  strategies:
    auth_endpoints:
      type: sliding_window_log
      reason: High accuracy needed for security
    
    api_endpoints:
      type: token_bucket
      reason: Allow bursts for better UX
    
    public_endpoints:
      type: fixed_window
      reason: Simple and efficient
  
  # Layer rate limits
  layers:
    - name: global
      limit: 10000
      window: 60
      scope: all
    
    - name: per_client
      limit: 1000
      window: 60
      scope: client
    
    - name: per_user
      limit: 100
      window: 60
      scope: user
    
    - name: per_ip
      limit: 50
      window: 60
      scope: ip
  
  # Progressive penalties
  penalties:
    first_violation:
      block_duration: 60
      multiplier: 0.5
    
    second_violation:
      block_duration: 300
      multiplier: 0.25
    
    third_violation:
      block_duration: 3600
      multiplier: 0.1
  
  # Whitelisting
  whitelist:
    - type: ip_range
      value: 10.0.0.0/8
      reason: Internal network
    
    - type: client_id
      value: monitoring-client
      reason: Monitoring service
  
  # Monitoring
  monitoring:
    metrics_enabled: true
    detailed_logging: true
    alert_thresholds:
      block_rate: 0.1
      error_rate: 0.05
```

### Implementation Checklist

```markdown
## Rate Limiting Implementation Checklist

### Planning
- [ ] Identify endpoints requiring rate limiting
- [ ] Determine appropriate limits for each endpoint
- [ ] Choose rate limiting strategy per endpoint
- [ ] Plan for distributed system requirements
- [ ] Define client tiers and limits

### Implementation
- [ ] Implement base rate limiting algorithm
- [ ] Add Redis storage backend
- [ ] Configure per-endpoint limits
- [ ] Implement client identification
- [ ] Add rate limit headers to responses
- [ ] Implement graceful degradation

### Security
- [ ] Protect against race conditions
- [ ] Implement atomic operations
- [ ] Add bypass for critical services
- [ ] Implement progressive penalties
- [ ] Add IP-based fallback limiting

### Monitoring
- [ ] Add metrics collection
- [ ] Configure alerting thresholds
- [ ] Implement dashboards
- [ ] Add detailed logging
- [ ] Set up trend analysis

### Testing
- [ ] Load test rate limits
- [ ] Test distributed coordination
- [ ] Verify atomic operations
- [ ] Test edge cases
- [ ] Validate monitoring

### Documentation
- [ ] Document rate limits per endpoint
- [ ] Create client onboarding guide
- [ ] Document monitoring procedures
- [ ] Create troubleshooting guide
- [ ] Update API documentation
```

---

## Troubleshooting

### Common Issues

1. **Rate Limit Not Applied**
   - Check client identification
   - Verify endpoint matching
   - Check Redis connectivity

2. **Inconsistent Limits**
   - Check for race conditions
   - Verify atomic operations
   - Check distributed sync

3. **Performance Issues**
   - Optimize Redis operations
   - Use Lua scripts
   - Implement caching

4. **False Positives**
   - Review client identification
   - Check for shared IPs/proxies
   - Adjust limits based on usage

---

## Resources

- [IETF Rate Limiting Headers Draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
- [Redis Rate Limiting Patterns](https://redis.io/docs/reference/patterns/rate-limiting/)
- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [API Rate Limiting Best Practices](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)