"""
API Performance Optimization Module

Provides comprehensive performance optimizations for API endpoints including:
- Response compression
- Query result caching
- Connection pooling optimization
- Async I/O optimization
- Response streaming for large datasets
"""
import asyncio
import gzip
import json
from typing import Any, Dict, List, Optional, Callable, TypeVar, Union
from datetime import datetime, timedelta
from functools import wraps
import hashlib

from fastapi import Response, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
import orjson

from core.redis import redis_client
from core.logger import get_logger
from core.monitoring import monitor_performance

logger = get_logger(__name__)

T = TypeVar("T")


class APIPerformanceOptimizer:
    """Comprehensive API performance optimization toolkit."""
    
    def __init__(self):
        self.cache_ttl_default = 300  # 5 minutes
        self.compression_threshold = 1024  # 1KB
        self.batch_size = 100
        self.max_concurrent_requests = 50
        
    def cache_response(
        self,
        ttl: Optional[int] = None,
        key_prefix: str = "api_cache",
        vary_on: Optional[List[str]] = None
    ):
        """
        Decorator to cache API responses in Redis.
        
        Args:
            ttl: Cache time-to-live in seconds
            key_prefix: Prefix for cache keys
            vary_on: List of request attributes to vary cache on
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Generate cache key
                cache_key = self._generate_cache_key(
                    request,
                    key_prefix,
                    vary_on,
                    args,
                    kwargs
                )
                
                # Try to get from cache
                cached_response = await self._get_cached_response(cache_key)
                if cached_response is not None:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return Response(
                        content=cached_response,
                        media_type="application/json",
                        headers={"X-Cache": "HIT"}
                    )
                
                # Execute function
                result = await func(request, *args, **kwargs)
                
                # Cache the response
                if isinstance(result, dict) or isinstance(result, list):
                    await self._cache_response(
                        cache_key,
                        result,
                        ttl or self.cache_ttl_default
                    )
                    
                    # Add cache headers
                    if isinstance(result, Response):
                        result.headers["X-Cache"] = "MISS"
                    else:
                        return Response(
                            content=orjson.dumps(result),
                            media_type="application/json",
                            headers={
                                "X-Cache": "MISS",
                                "Cache-Control": f"max-age={ttl or self.cache_ttl_default}"
                            }
                        )
                
                return result
            
            return wrapper
        return decorator
    
    def compress_response(self, func: Callable) -> Callable:
        """
        Decorator to compress large responses with gzip.
        """
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check if client accepts gzip
            accept_encoding = request.headers.get("accept-encoding", "")
            
            # Execute function
            result = await func(request, *args, **kwargs)
            
            # Convert to JSON if needed
            if isinstance(result, (dict, list)):
                content = orjson.dumps(result)
            elif isinstance(result, Response):
                return result  # Already a response
            else:
                content = str(result).encode()
            
            # Check if compression is beneficial
            if "gzip" in accept_encoding and len(content) > self.compression_threshold:
                compressed = gzip.compress(content)
                
                # Only use compression if it reduces size
                if len(compressed) < len(content):
                    return Response(
                        content=compressed,
                        media_type="application/json",
                        headers={
                            "Content-Encoding": "gzip",
                            "Vary": "Accept-Encoding"
                        }
                    )
            
            return Response(
                content=content,
                media_type="application/json"
            )
        
        return wrapper
    
    async def stream_large_dataset(
        self,
        query_func: Callable,
        batch_size: Optional[int] = None,
        transform_func: Optional[Callable] = None
    ) -> StreamingResponse:
        """
        Stream large datasets to avoid memory issues.
        
        Args:
            query_func: Async function that yields data batches
            batch_size: Size of each batch
            transform_func: Optional transformation function for each item
        """
        batch_size = batch_size or self.batch_size
        
        async def generate():
            # Start JSON array
            yield b'{"items":['
            first = True
            
            async for batch in query_func(batch_size):
                for item in batch:
                    if not first:
                        yield b','
                    else:
                        first = False
                    
                    # Transform item if needed
                    if transform_func:
                        item = await transform_func(item)
                    
                    # Serialize item
                    yield orjson.dumps(item)
            
            # Close JSON array
            yield b'],"streaming":true}'
        
        return StreamingResponse(
            generate(),
            media_type="application/json",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Transfer-Encoding": "chunked"
            }
        )
    
    def batch_requests(self, func: Callable) -> Callable:
        """
        Decorator to batch multiple requests for efficiency.
        """
        batch_queue = {}
        batch_lock = asyncio.Lock()
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate batch key
            batch_key = self._generate_batch_key(args, kwargs)
            
            async with batch_lock:
                if batch_key not in batch_queue:
                    batch_queue[batch_key] = {
                        "requests": [],
                        "event": asyncio.Event()
                    }
                
                batch_info = batch_queue[batch_key]
                batch_info["requests"].append((args, kwargs))
                
                # If this is the first request, process the batch
                if len(batch_info["requests"]) == 1:
                    asyncio.create_task(self._process_batch(
                        func,
                        batch_key,
                        batch_queue,
                        batch_lock
                    ))
            
            # Wait for batch processing
            await batch_info["event"].wait()
            
            # Return result
            return batch_info.get("result")
        
        return wrapper
    
    async def parallel_fetch(
        self,
        tasks: List[Callable],
        max_concurrent: Optional[int] = None
    ) -> List[Any]:
        """
        Execute multiple async tasks in parallel with concurrency control.
        
        Args:
            tasks: List of async callables
            max_concurrent: Maximum concurrent tasks
        
        Returns:
            List of results in the same order as tasks
        """
        max_concurrent = max_concurrent or self.max_concurrent_requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await task()
        
        return await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
    
    def optimize_pagination(
        self,
        default_size: int = 20,
        max_size: int = 100
    ):
        """
        Decorator to optimize pagination parameters.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(
                request: Request,
                page: int = 1,
                size: int = default_size,
                *args,
                **kwargs
            ):
                # Validate and optimize pagination
                page = max(1, page)
                size = min(max(1, size), max_size)
                
                # Add pagination metadata to response
                result = await func(request, page, size, *args, **kwargs)
                
                if isinstance(result, dict):
                    result["pagination"] = {
                        "page": page,
                        "size": size,
                        "has_more": len(result.get("items", [])) == size
                    }
                
                return result
            
            return wrapper
        return decorator
    
    @staticmethod
    def add_performance_headers(response: Response) -> Response:
        """
        Add performance-related headers to response.
        """
        response.headers["X-Response-Time"] = str(
            datetime.utcnow().timestamp()
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
    
    async def warmup_cache(
        self,
        endpoints: List[Dict[str, Any]],
        background_tasks: BackgroundTasks
    ):
        """
        Warmup cache for critical endpoints.
        
        Args:
            endpoints: List of endpoint configurations
            background_tasks: FastAPI background tasks
        """
        async def warmup_endpoint(endpoint: Dict[str, Any]):
            try:
                # Generate cache key
                cache_key = f"warmup:{endpoint['path']}"
                
                # Execute endpoint function
                result = await endpoint["func"](**endpoint.get("params", {}))
                
                # Cache result
                await redis_client.setex(
                    cache_key,
                    endpoint.get("ttl", 3600),
                    orjson.dumps(result)
                )
                
                logger.info(f"Warmed up cache for {endpoint['path']}")
            except Exception as e:
                logger.error(f"Failed to warmup {endpoint['path']}: {e}")
        
        # Schedule warmup tasks
        for endpoint in endpoints:
            background_tasks.add_task(warmup_endpoint, endpoint)
    
    def _generate_cache_key(
        self,
        request: Request,
        prefix: str,
        vary_on: Optional[List[str]],
        args: tuple,
        kwargs: dict
    ) -> str:
        """Generate cache key based on request and parameters."""
        key_parts = [prefix, request.url.path]
        
        # Add query parameters
        if request.query_params:
            key_parts.append(str(dict(request.query_params)))
        
        # Add vary-on attributes
        if vary_on:
            for attr in vary_on:
                if attr == "user":
                    # Add user ID if authenticated
                    if hasattr(request.state, "user_id"):
                        key_parts.append(f"user:{request.state.user_id}")
                elif attr == "headers":
                    # Add specific headers
                    key_parts.append(f"headers:{request.headers}")
        
        # Add function arguments
        if args:
            key_parts.append(f"args:{args}")
        if kwargs:
            key_parts.append(f"kwargs:{kwargs}")
        
        # Generate hash
        key_str = ":".join(str(part) for part in key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _get_cached_response(self, cache_key: str) -> Optional[bytes]:
        """Get cached response from Redis."""
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    async def _cache_response(
        self,
        cache_key: str,
        data: Union[dict, list],
        ttl: int
    ):
        """Cache response in Redis."""
        try:
            serialized = orjson.dumps(data)
            await redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def _generate_batch_key(self, args: tuple, kwargs: dict) -> str:
        """Generate key for request batching."""
        key_parts = [str(args), str(sorted(kwargs.items()))]
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _process_batch(
        self,
        func: Callable,
        batch_key: str,
        batch_queue: dict,
        batch_lock: asyncio.Lock
    ):
        """Process a batch of requests."""
        await asyncio.sleep(0.01)  # Small delay to collect more requests
        
        async with batch_lock:
            batch_info = batch_queue.get(batch_key)
            if not batch_info:
                return
            
            try:
                # Process all requests in batch
                results = await func(batch_info["requests"])
                batch_info["result"] = results
            except Exception as e:
                batch_info["error"] = e
            finally:
                # Signal completion
                batch_info["event"].set()
                
                # Clean up after delay
                await asyncio.sleep(1)
                batch_queue.pop(batch_key, None)


# Global optimizer instance
api_performance_optimizer = APIPerformanceOptimizer()