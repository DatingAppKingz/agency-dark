"""
Async processing optimization for Celery and background tasks.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import time
from datetime import datetime, timedelta
from collections import defaultdict
import aioredis

from celery import Celery, Task
from celery.result import AsyncResult
from kombu import Queue, Exchange

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# Optimized Celery configuration
CELERY_CONFIG = {
    "broker_url": settings.REDIS_URL,
    "result_backend": settings.REDIS_URL,
    "task_serializer": "msgpack",
    "result_serializer": "msgpack",
    "accept_content": ["msgpack", "json"],
    "timezone": "UTC",
    "enable_utc": True,
    
    # Performance optimizations
    "worker_prefetch_multiplier": 4,
    "worker_max_tasks_per_child": 1000,
    "worker_disable_rate_limits": True,
    "task_compression": "gzip",
    "result_compression": "gzip",
    
    # Task execution
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "task_ignore_result": False,
    
    # Result backend settings
    "result_expires": 3600,
    "result_persistent": True,
    
    # Connection pool settings
    "broker_pool_limit": 50,
    "broker_connection_timeout": 30,
    "broker_connection_retry": True,
    "broker_connection_max_retries": 3,
    
    # Task routing
    "task_routes": {
        "app.tasks.email.*": {"queue": "email", "priority": 5},
        "app.tasks.analytics.*": {"queue": "analytics", "priority": 3},
        "app.tasks.reports.*": {"queue": "reports", "priority": 1},
        "app.tasks.background.*": {"queue": "default", "priority": 0},
    },
    
    # Queue configuration
    "task_queues": [
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("email", Exchange("email"), routing_key="email", priority=5),
        Queue("analytics", Exchange("analytics"), routing_key="analytics", priority=3),
        Queue("reports", Exchange("reports"), routing_key="reports", priority=1),
    ],
}


class OptimizedCelery(Celery):
    """Optimized Celery application with performance enhancements."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conf.update(CELERY_CONFIG)
        self._task_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "failures": 0,
            "retries": 0
        })
    
    def task(self, *args, **kwargs):
        """Enhanced task decorator with monitoring."""
        # Set default options for optimization
        kwargs.setdefault("bind", True)
        kwargs.setdefault("max_retries", 3)
        kwargs.setdefault("default_retry_delay", 60)
        
        original_decorator = super().task(*args, **kwargs)
        
        def wrapper(func):
            task = original_decorator(func)
            
            # Add performance monitoring
            @wraps(func)
            def monitored_run(self, *args, **kwargs):
                start_time = time.time()
                task_name = self.name
                
                try:
                    result = func(self, *args, **kwargs)
                    
                    # Update statistics
                    execution_time = time.time() - start_time
                    self._task_stats[task_name]["count"] += 1
                    self._task_stats[task_name]["total_time"] += execution_time
                    
                    # Log slow tasks
                    if execution_time > 30:  # 30 seconds
                        logger.warning(
                            f"Slow task detected: {task_name}",
                            extra={
                                "task_name": task_name,
                                "execution_time": execution_time,
                                "args": args,
                                "kwargs": kwargs
                            }
                        )
                    
                    return result
                    
                except Exception as e:
                    self._task_stats[task_name]["failures"] += 1
                    
                    # Retry with exponential backoff
                    if self.request.retries < self.max_retries:
                        self._task_stats[task_name]["retries"] += 1
                        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
                        raise self.retry(exc=e, countdown=retry_delay)
                    else:
                        raise
            
            task.run = monitored_run
            return task
        
        return wrapper


# Create optimized Celery app
celery_app = OptimizedCelery("app")


class TaskBatcher:
    """Batch multiple tasks for efficient processing."""
    
    def __init__(self, batch_size: int = 100, timeout: float = 1.0):
        self.batch_size = batch_size
        self.timeout = timeout
        self.pending_tasks = defaultdict(list)
        self.lock = asyncio.Lock()
        self._batch_task = None
    
    async def add_task(self, task_name: str, *args, **kwargs):
        """Add task to batch."""
        async with self.lock:
            self.pending_tasks[task_name].append((args, kwargs))
            
            # Start batch processing if not running
            if not self._batch_task or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._process_batches())
            
            # Process immediately if batch is full
            if len(self.pending_tasks[task_name]) >= self.batch_size:
                await self._process_batch(task_name)
    
    async def _process_batches(self):
        """Process batches periodically."""
        await asyncio.sleep(self.timeout)
        
        async with self.lock:
            for task_name in list(self.pending_tasks.keys()):
                if self.pending_tasks[task_name]:
                    await self._process_batch(task_name)
    
    async def _process_batch(self, task_name: str):
        """Process a batch of tasks."""
        tasks = self.pending_tasks[task_name]
        if not tasks:
            return
        
        # Clear pending tasks
        self.pending_tasks[task_name] = []
        
        # Get task function
        task_func = celery_app.tasks.get(task_name)
        if not task_func:
            logger.error(f"Task not found: {task_name}")
            return
        
        # Execute batch
        batch_args = [args for args, _ in tasks]
        batch_kwargs = [kwargs for _, kwargs in tasks]
        
        # Use group for parallel execution
        from celery import group
        job = group(
            task_func.s(*args, **kwargs)
            for args, kwargs in zip(batch_args, batch_kwargs)
        )
        
        result = job.apply_async()
        return result


class AsyncTaskExecutor:
    """Execute sync tasks asynchronously."""
    
    def __init__(self, max_workers: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running_tasks = {}
    
    async def run_sync_task(self, func: Callable, *args, **kwargs) -> Any:
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        
        # Create task ID
        task_id = f"{func.__name__}_{time.time()}"
        
        # Track running task
        future = loop.run_in_executor(self.executor, func, *args, **kwargs)
        self.running_tasks[task_id] = future
        
        try:
            result = await future
            return result
        finally:
            # Clean up
            self.running_tasks.pop(task_id, None)
    
    def cancel_all(self):
        """Cancel all running tasks."""
        for future in self.running_tasks.values():
            future.cancel()
        self.running_tasks.clear()
    
    def shutdown(self):
        """Shutdown executor."""
        self.cancel_all()
        self.executor.shutdown(wait=True)


class PriorityTaskQueue:
    """Priority queue for task execution."""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis = None
        self.queues = {
            "critical": "tasks:priority:critical",
            "high": "tasks:priority:high",
            "normal": "tasks:priority:normal",
            "low": "tasks:priority:low"
        }
    
    async def connect(self):
        """Connect to Redis."""
        self.redis = await aioredis.create_redis_pool(self.redis_url)
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
    
    async def enqueue(
        self,
        task_name: str,
        args: Tuple = (),
        kwargs: Dict = None,
        priority: str = "normal"
    ) -> str:
        """Enqueue task with priority."""
        if priority not in self.queues:
            raise ValueError(f"Invalid priority: {priority}")
        
        task_data = {
            "id": f"{task_name}_{time.time()}",
            "name": task_name,
            "args": args,
            "kwargs": kwargs or {},
            "enqueued_at": datetime.utcnow().isoformat(),
            "priority": priority
        }
        
        # Serialize and enqueue
        import json
        await self.redis.lpush(
            self.queues[priority],
            json.dumps(task_data)
        )
        
        return task_data["id"]
    
    async def dequeue(self, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """Dequeue highest priority task."""
        # Check queues in priority order
        for priority in ["critical", "high", "normal", "low"]:
            queue_name = self.queues[priority]
            
            # Try to get task from queue
            data = await self.redis.brpop(queue_name, timeout=timeout)
            
            if data:
                import json
                return json.loads(data[1])
        
        return None
    
    async def get_queue_sizes(self) -> Dict[str, int]:
        """Get size of each priority queue."""
        sizes = {}
        
        for priority, queue_name in self.queues.items():
            size = await self.redis.llen(queue_name)
            sizes[priority] = size
        
        return sizes


# Task optimization decorators
def optimize_task(
    batch_size: Optional[int] = None,
    cache_result: bool = False,
    cache_ttl: int = 3600,
    rate_limit: Optional[str] = None
):
    """Decorator to optimize task execution."""
    def decorator(func):
        @wraps(func)
        @celery_app.task(bind=True)
        def optimized_task(self, *args, **kwargs):
            # Apply rate limiting
            if rate_limit:
                # Use Redis to track rate limit
                import redis
                r = redis.from_url(settings.REDIS_URL)
                key = f"rate_limit:{self.name}"
                
                current = r.incr(key)
                if current == 1:
                    r.expire(key, 60)  # Reset every minute
                
                limit = int(rate_limit.split("/")[0])
                if current > limit:
                    # Retry later
                    raise self.retry(countdown=60)
            
            # Check cache
            if cache_result:
                cache_key = f"task_result:{self.name}:{hash((args, tuple(sorted(kwargs.items()))))}"
                r = redis.from_url(settings.REDIS_URL)
                
                cached = r.get(cache_key)
                if cached:
                    import pickle
                    return pickle.loads(cached)
            
            # Execute task
            result = func(self, *args, **kwargs)
            
            # Cache result
            if cache_result:
                import pickle
                r.setex(cache_key, cache_ttl, pickle.dumps(result))
            
            return result
        
        # Add batching support
        if batch_size:
            optimized_task.batch_size = batch_size
        
        return optimized_task
    
    return decorator


# Async task monitoring
class TaskMonitor:
    """Monitor task execution and performance."""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            "executions": 0,
            "failures": 0,
            "total_time": 0,
            "queue_time": 0
        })
    
    def record_execution(
        self,
        task_name: str,
        execution_time: float,
        queue_time: float,
        success: bool
    ):
        """Record task execution metrics."""
        metrics = self.metrics[task_name]
        metrics["executions"] += 1
        
        if not success:
            metrics["failures"] += 1
        
        metrics["total_time"] += execution_time
        metrics["queue_time"] += queue_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        stats = {}
        
        for task_name, metrics in self.metrics.items():
            if metrics["executions"] > 0:
                stats[task_name] = {
                    "executions": metrics["executions"],
                    "failures": metrics["failures"],
                    "success_rate": (
                        (metrics["executions"] - metrics["failures"]) /
                        metrics["executions"] * 100
                    ),
                    "avg_execution_time": metrics["total_time"] / metrics["executions"],
                    "avg_queue_time": metrics["queue_time"] / metrics["executions"]
                }
        
        return stats