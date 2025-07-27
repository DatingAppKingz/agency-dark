# Redis Caching System Documentation

## Overview

The Redis caching system provides high-performance data caching with multiple strategies, automatic serialization, monitoring, and management capabilities. It's designed to significantly improve application performance by reducing database queries and expensive computations.

## Architecture

### Core Components

1. **CacheService** - Main caching interface with get/set/delete operations
2. **CacheKey** - Standardized key generation with automatic namespacing
3. **CacheSerializer** - Handles serialization for different data types
4. **CacheMonitor** - Real-time monitoring and health checks
5. **CacheManager** - Administrative operations and maintenance

### Module-Specific Caches

- **ModelCache** - User and model profile caching
- **FinancialCache** - Transaction summaries and balances
- **AnalyticsCache** - Metrics and analytics data
- **FanCache** - Fan/subscriber information

## Features

### 1. Automatic Serialization

Supports multiple data types:
- Strings, integers, floats
- Dictionaries and lists
- Pydantic models
- Complex objects (via pickle)

```python
# Pydantic model
model = UserProfile(id="123", name="John")
await cache.set("user:123", model)
retrieved = await cache.get("user:123", UserProfile)

# Dictionary
data = {"revenue": 1000, "transactions": 50}
await cache.set("stats:today", data)
```

### 2. TTL Management

Flexible TTL options:
```python
from datetime import timedelta

# Set with seconds
await cache.set("key", "value", ttl=300)  # 5 minutes

# Set with timedelta
await cache.set("key", "value", ttl=timedelta(hours=1))

# Different TTLs for different data types
METRICS_TTL = timedelta(minutes=5)    # Real-time metrics
PROFILE_TTL = timedelta(minutes=30)   # User profiles
REPORT_TTL = timedelta(hours=6)      # Generated reports
```

### 3. Batch Operations

Efficient multi-key operations:
```python
# Get multiple values
keys = ["user:1", "user:2", "user:3"]
results = await cache.get_many(keys)

# Set multiple values
data = {
    "metric:revenue": 1000,
    "metric:users": 50,
    "metric:transactions": 200
}
await cache.set_many(data, ttl=300)
```

### 4. Cache Decorators

Simplify caching with decorators:

```python
from core.cache import cached, cache_invalidate

@cached(prefix="analytics:revenue", ttl=timedelta(minutes=15))
async def calculate_revenue(model_id: str, date: datetime) -> Decimal:
    # Expensive calculation
    return revenue

@cache_invalidate(prefix="analytics:revenue", 
                  key_func=lambda model_id, **kwargs: f"*{model_id}*")
async def update_transaction(model_id: str, amount: Decimal):
    # Update logic that invalidates cache
    pass
```

### 5. Pattern-Based Operations

Work with key patterns:
```python
# Delete by pattern
await cache.delete_pattern("user:temp:*")

# Analyze key patterns
patterns = await monitor.get_key_patterns()
# Returns: {"user:profile": 150, "analytics:metric": 340, ...}
```

## Cache Strategies

### 1. Cache-Aside Pattern
Most common pattern - check cache, compute if missing:
```python
@cache_aside(prefix="expensive", ttl=3600)
async def expensive_operation(param: str) -> dict:
    # Only called if not in cache
    return await compute_expensive_data(param)
```

### 2. Write-Through Cache
Update cache when data changes:
```python
async def update_user_profile(user_id: str, data: dict):
    # Update database
    await db.update_user(user_id, data)
    
    # Update cache
    await ModelCache.set_user_profile(user_id, data)
```

### 3. Cache Invalidation
Remove stale data on updates:
```python
async def delete_user(user_id: str):
    # Delete from database
    await db.delete_user(user_id)
    
    # Invalidate all user caches
    await ModelCache.invalidate_user_cache(user_id)
```

## Module-Specific Usage

### Financial Module

```python
from modules.financial.cache.financial_cache import FinancialCache

# Cache balance
await FinancialCache.set_balance("model", model_id, Decimal("1500.00"))
balance = await FinancialCache.get_balance("model", model_id)

# Cache commission rates
await FinancialCache.cache_commission_rate(model_id, "subscription", Decimal("0.20"))

# Prevent duplicate payouts with locks
if await PayoutCache.acquire_payout_lock(model_id, amount):
    # Process payout
    await process_payout(model_id, amount)
    await PayoutCache.release_payout_lock(model_id, amount)
```

### Analytics Module

```python
from modules.analytics.cache.analytics_cache import AnalyticsCache

# Cache daily metrics
metrics = {"revenue": 500, "subscribers": 10}
await AnalyticsCache.set_model_metrics(model_id, date, metrics)

# Get revenue summary
summary = await AnalyticsCache.get_revenue_summary(model_id, "today")

# Invalidate all analytics cache for a model
await AnalyticsCache.invalidate_model_cache(model_id)
```

### Model/User Cache

```python
from core.cache import ModelCache, FanCache

# Cache model profile
await ModelCache.set_model_profile(model_id, profile_data)

# Batch get models
model_ids = ["id1", "id2", "id3"]
profiles = await ModelCache.batch_get_models(model_ids)

# Cache user permissions
permissions = {"view_analytics", "edit_profile", "manage_fans"}
await ModelCache.set_user_permissions(user_id, permissions)
```

## Monitoring

### Real-time Metrics

The cache monitor tracks:
- Hit/miss rates
- Memory usage
- Key count
- Error rates
- Operation latency

```python
# Start monitoring
await monitor.start(interval=60)

# Get current stats
stats = cache.get_stats()
# {
#   'hits': 15234,
#   'misses': 2341,
#   'hit_rate': 86.7,
#   'total_requests': 17575
# }

# Health check
health = await monitor.get_health_status()
# {
#   'status': 'healthy',
#   'redis_connected': True,
#   'metrics': {...}
# }
```

### Memory Analysis

Analyze memory usage by pattern:
```python
analysis = await monitor.get_memory_analysis()
# {
#   'user:profile': {
#     'count': 1500,
#     'avg_size_bytes': 2048,
#     'estimated_total_mb': 2.9
#   },
#   'analytics:metric': {
#     'count': 5000,
#     'avg_size_bytes': 512,
#     'estimated_total_mb': 2.4
#   }
# }
```

## Best Practices

### 1. Key Naming Conventions

Use consistent, hierarchical key names:
```
{prefix}:{module}:{entity}:{id}:{attribute}

Examples:
- user:profile:123
- model:analytics:456:daily:2024-01-01
- financial:balance:model:789
```

### 2. TTL Guidelines

- **Real-time data**: 1-5 minutes
- **User sessions**: 15-30 minutes  
- **Computed summaries**: 5-15 minutes
- **Static data**: 1-6 hours
- **Reports**: 6-24 hours

### 3. Cache Warming

Pre-populate frequently accessed data:
```python
async def warm_model_cache(model_id: str):
    # Fetch from database
    profile = await db.get_model_profile(model_id)
    metrics = await db.get_model_metrics(model_id)
    
    # Warm cache
    await ModelCache.set_model_profile(model_id, profile)
    await AnalyticsCache.set_model_metrics(model_id, datetime.now(), metrics)
```

### 4. Error Handling

Always handle cache failures gracefully:
```python
async def get_user_data(user_id: str):
    # Try cache first
    cached = await ModelCache.get_user_profile(user_id)
    if cached:
        return cached
    
    # Fallback to database
    user = await db.get_user(user_id)
    
    # Try to cache (don't fail if cache is down)
    try:
        await ModelCache.set_user_profile(user_id, user)
    except Exception as e:
        logger.warning(f"Failed to cache user {user_id}: {e}")
    
    return user
```

### 5. Cache Stampede Prevention

Use locks for expensive computations:
```python
async def get_expensive_report(report_id: str):
    lock_key = f"lock:report:{report_id}"
    
    # Try to acquire lock
    if await cache.redis.set(lock_key, "1", nx=True, ex=30):
        try:
            # Generate report
            report = await generate_report(report_id)
            await cache.set(f"report:{report_id}", report, ttl=3600)
            return report
        finally:
            await cache.delete(lock_key)
    else:
        # Wait for other process to complete
        for _ in range(30):
            cached = await cache.get(f"report:{report_id}")
            if cached:
                return cached
            await asyncio.sleep(1)
```

## Configuration

### Environment Variables

```env
# Redis connection
REDIS_URL=redis://localhost:6379/0

# Cache settings
CACHE_PREFIX=agencydark
CACHE_DEFAULT_TTL=300
CACHE_MAX_CONNECTIONS=50
```

### Cache Configuration

```python
# core/config.py
class CacheConfig:
    # TTL settings
    DEFAULT_TTL = 300  # 5 minutes
    SHORT_TTL = 60     # 1 minute
    LONG_TTL = 3600    # 1 hour
    
    # Performance settings
    BATCH_SIZE = 100
    SCAN_COUNT = 1000
    
    # Memory limits
    MAX_MEMORY = "2gb"
    EVICTION_POLICY = "allkeys-lru"
```

## Performance Tips

### 1. Use Batch Operations
```python
# Bad - Multiple round trips
for user_id in user_ids:
    profile = await cache.get(f"user:{user_id}")

# Good - Single round trip
profiles = await cache.get_many([f"user:{id}" for id in user_ids])
```

### 2. Avoid Large Values
Keep cached values under 1MB. For larger data:
- Split into chunks
- Store references to external storage
- Compress data

### 3. Monitor Hit Rates
Aim for >80% hit rate. If lower:
- Increase TTLs
- Review key patterns
- Consider cache warming

### 4. Use Appropriate Data Structures
Redis supports specialized data structures:
- Sorted sets for leaderboards
- Lists for queues
- Hashes for objects
- Sets for unique collections

## Troubleshooting

### Common Issues

1. **Low Hit Rate**
   - Check TTL values
   - Review cache key generation
   - Monitor invalidation patterns

2. **High Memory Usage**
   - Analyze key patterns
   - Review TTL settings
   - Enable eviction policies

3. **Connection Errors**
   - Check Redis server status
   - Review connection pool settings
   - Monitor network latency

### Debug Commands

```python
# Check specific key
value = await cache.get("problematic:key")
ttl = await cache.redis.ttl("problematic:key")

# Analyze memory
memory = await cache.redis.memory_usage("large:key")

# Monitor commands
await cache.redis.monitor()  # See all commands in real-time
```

## Maintenance

### Regular Tasks

1. **Monitor metrics** - Review hit rates and memory usage
2. **Clean old keys** - Remove expired data
3. **Optimize patterns** - Refactor inefficient key structures
4. **Update TTLs** - Adjust based on usage patterns
5. **Backup critical data** - Export important cache data

### Cache Cleanup

```python
# Remove old analytics data
await manager.evict_old_keys("analytics:*", max_age=timedelta(days=7))

# Clear specific patterns
await manager.clear_pattern("temp:*")

# Optimize memory
result = await manager.optimize_memory()
print(f"Freed {result['saved_mb']}MB")
```