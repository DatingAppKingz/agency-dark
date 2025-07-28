"""
Performance profiling and analysis
"""
import cProfile
import pstats
import io
import time
import asyncio
import tracemalloc
import linecache
import functools
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from contextlib import contextmanager
import threading
import psutil
import gc

import py_spy
import memory_profiler
import line_profiler
from pyflame import Flame

from core.redis import redis_client
from core.logging import logger
from core.monitoring.metrics import Histogram, Gauge, registry


# Profiling metrics
profile_duration = Histogram(
    'profile_duration_seconds',
    'Time spent in profiled functions',
    ['function_name', 'module'],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
    registry=registry
)

memory_usage = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes',
    ['type'],  # heap, rss, vms
    registry=registry
)

gc_collections = Gauge(
    'gc_collections_total',
    'Total garbage collections',
    ['generation'],
    registry=registry
)


class ProfileType:
    """Types of profiling"""
    CPU = "cpu"
    MEMORY = "memory"
    LINE = "line"
    ASYNC = "async"
    FLAME = "flame"


class ProfileResult:
    """Container for profiling results"""
    
    def __init__(self, profile_type: str, function_name: str):
        self.profile_type = profile_type
        self.function_name = function_name
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.duration = None
        self.stats = {}
        self.raw_data = None
    
    def finish(self):
        """Mark profiling as finished"""
        self.end_time = datetime.utcnow()
        self.duration = (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'profile_type': self.profile_type,
            'function_name': self.function_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'stats': self.stats
        }


class CPUProfiler:
    """CPU profiling using cProfile"""
    
    @staticmethod
    @contextmanager
    def profile():
        """Context manager for CPU profiling"""
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            yield profiler
        finally:
            profiler.disable()
    
    @staticmethod
    def get_stats(profiler: cProfile.Profile, limit: int = 20) -> Dict[str, Any]:
        """Extract statistics from profiler"""
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(limit)
        
        # Parse stats
        stats = {
            'top_functions': [],
            'total_calls': ps.total_calls,
            'primitive_calls': ps.prim_calls,
            'total_time': ps.total_tt
        }
        
        # Extract top functions
        for func, (cc, nc, tt, ct, callers) in list(ps.stats.items())[:limit]:
            stats['top_functions'].append({
                'function': f"{func[0]}:{func[1]}:{func[2]}",
                'calls': nc,
                'total_time': tt,
                'cumulative_time': ct,
                'time_per_call': tt / nc if nc > 0 else 0
            })
        
        stats['full_output'] = s.getvalue()
        return stats


class MemoryProfiler:
    """Memory profiling"""
    
    @staticmethod
    def start_tracing():
        """Start memory tracing"""
        tracemalloc.start()
    
    @staticmethod
    def stop_tracing():
        """Stop memory tracing"""
        tracemalloc.stop()
    
    @staticmethod
    def get_memory_stats() -> Dict[str, Any]:
        """Get current memory statistics"""
        if not tracemalloc.is_tracing():
            return {'error': 'Memory tracing not started'}
        
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        stats = {
            'current_size': snapshot.traceback_limit,
            'peak_size': tracemalloc.get_traced_memory()[1],
            'top_allocations': []
        }
        
        for stat in top_stats[:10]:
            frame = stat.traceback[0]
            stats['top_allocations'].append({
                'file': frame.filename,
                'line': frame.lineno,
                'size': stat.size,
                'count': stat.count,
                'average': stat.size // stat.count if stat.count > 0 else 0
            })
        
        return stats
    
    @staticmethod
    def get_object_stats() -> Dict[str, Any]:
        """Get object allocation statistics"""
        gc.collect()
        
        stats = {
            'gc_stats': gc.get_stats(),
            'object_counts': {},
            'garbage_count': len(gc.garbage)
        }
        
        # Count objects by type
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            stats['object_counts'][obj_type] = stats['object_counts'].get(obj_type, 0) + 1
        
        # Sort by count
        stats['top_objects'] = sorted(
            stats['object_counts'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        return stats


class AsyncProfiler:
    """Profiling for async functions"""
    
    @staticmethod
    async def profile_async_function(func: Callable, *args, **kwargs) -> Tuple[Any, ProfileResult]:
        """Profile an async function"""
        result = ProfileResult(ProfileType.ASYNC, func.__name__)
        
        # Start profiling
        start_time = time.perf_counter()
        task_info = {
            'created_tasks': set(),
            'completed_tasks': set(),
            'failed_tasks': set()
        }
        
        # Track task creation
        original_create_task = asyncio.create_task
        
        def tracked_create_task(coro):
            task = original_create_task(coro)
            task_info['created_tasks'].add(task)
            return task
        
        asyncio.create_task = tracked_create_task
        
        try:
            # Execute function
            func_result = await func(*args, **kwargs)
            
            # Collect stats
            end_time = time.perf_counter()
            result.duration = end_time - start_time
            
            # Analyze tasks
            for task in task_info['created_tasks']:
                if task.done():
                    if task.exception():
                        task_info['failed_tasks'].add(task)
                    else:
                        task_info['completed_tasks'].add(task)
            
            result.stats = {
                'duration': result.duration,
                'created_tasks': len(task_info['created_tasks']),
                'completed_tasks': len(task_info['completed_tasks']),
                'failed_tasks': len(task_info['failed_tasks']),
                'pending_tasks': len(task_info['created_tasks']) - len(task_info['completed_tasks']) - len(task_info['failed_tasks'])
            }
            
            return func_result, result
            
        finally:
            asyncio.create_task = original_create_task
            result.finish()


class LineProfiler:
    """Line-by-line profiling"""
    
    @staticmethod
    def profile_function(func: Callable) -> Callable:
        """Decorator for line profiling"""
        profiler = line_profiler.LineProfiler()
        profiler.add_function(func)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return profiler.runcall(func, *args, **kwargs)
        
        wrapper.profiler = profiler
        return wrapper
    
    @staticmethod
    def get_stats(profiler: line_profiler.LineProfiler) -> Dict[str, Any]:
        """Get line profiling statistics"""
        s = io.StringIO()
        profiler.print_stats(stream=s)
        
        return {
            'line_stats': s.getvalue(),
            'functions': list(profiler.functions.keys())
        }


class Profiler:
    """Main profiling service"""
    
    def __init__(self):
        self.active_profiles = {}
        self.results = {}
        self._monitoring_task = None
    
    async def start_monitoring(self):
        """Start system monitoring"""
        self._monitoring_task = asyncio.create_task(self._monitor_system())
        MemoryProfiler.start_tracing()
        logger.info("Profiling monitoring started")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            await asyncio.gather(self._monitoring_task, return_exceptions=True)
        MemoryProfiler.stop_tracing()
    
    async def _monitor_system(self):
        """Monitor system resources"""
        while True:
            try:
                # Memory metrics
                process = psutil.Process()
                memory_info = process.memory_info()
                
                memory_usage.labels(type='rss').set(memory_info.rss)
                memory_usage.labels(type='vms').set(memory_info.vms)
                
                # GC metrics
                for i, count in enumerate(gc.get_count()):
                    gc_collections.labels(generation=str(i)).set(count)
                
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in system monitoring: {exc}")
    
    @contextmanager
    def profile_cpu(self, name: str):
        """Profile CPU usage"""
        result = ProfileResult(ProfileType.CPU, name)
        
        with CPUProfiler.profile() as profiler:
            try:
                yield result
            finally:
                result.finish()
                result.stats = CPUProfiler.get_stats(profiler)
                self._store_result(result)
                
                # Update metrics
                profile_duration.labels(
                    function_name=name,
                    module=__name__
                ).observe(result.duration)
    
    def profile_memory(self, name: str):
        """Get memory profile"""
        result = ProfileResult(ProfileType.MEMORY, name)
        
        result.stats = {
            'memory_stats': MemoryProfiler.get_memory_stats(),
            'object_stats': MemoryProfiler.get_object_stats()
        }
        
        result.finish()
        self._store_result(result)
        return result
    
    async def profile_async(self, func: Callable, *args, **kwargs):
        """Profile async function"""
        func_result, profile_result = await AsyncProfiler.profile_async_function(
            func, *args, **kwargs
        )
        
        self._store_result(profile_result)
        
        # Update metrics
        profile_duration.labels(
            function_name=func.__name__,
            module=func.__module__
        ).observe(profile_result.duration)
        
        return func_result
    
    def _store_result(self, result: ProfileResult):
        """Store profiling result"""
        key = f"{result.profile_type}:{result.function_name}:{result.start_time.timestamp()}"
        self.results[key] = result
        
        # Store in Redis
        asyncio.create_task(self._store_in_redis(key, result))
    
    async def _store_in_redis(self, key: str, result: ProfileResult):
        """Store result in Redis"""
        redis_key = f"profiling:{key}"
        await redis_client.setex(
            redis_key,
            86400,  # 24 hours
            json.dumps(result.to_dict())
        )
    
    async def get_profile_results(
        self,
        profile_type: Optional[str] = None,
        function_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ProfileResult]:
        """Get stored profile results"""
        # Search in Redis
        pattern = "profiling:*"
        if profile_type:
            pattern = f"profiling:{profile_type}:*"
        
        keys = await redis_client.keys(pattern)
        results = []
        
        for key in keys[:limit]:
            data = await redis_client.get(key)
            if data:
                result_dict = json.loads(data)
                if function_name and result_dict['function_name'] != function_name:
                    continue
                results.append(result_dict)
        
        # Sort by start time
        results.sort(key=lambda x: x['start_time'], reverse=True)
        return results


# Decorators for easy profiling
def profile_cpu(name: Optional[str] = None):
    """Decorator for CPU profiling"""
    def decorator(func):
        profile_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with profiler.profile_cpu(profile_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def profile_async(name: Optional[str] = None):
    """Decorator for async profiling"""
    def decorator(func):
        profile_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await profiler.profile_async(func, *args, **kwargs)
        
        return wrapper
    return decorator


def profile_memory(func):
    """Decorator for memory profiling"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Take snapshot before
        profiler.profile_memory(f"{func.__name__}_before")
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Take snapshot after
        profiler.profile_memory(f"{func.__name__}_after")
        
        return result
    
    return wrapper


# Flame graph generation
class FlameGraphGenerator:
    """Generate flame graphs for visualization"""
    
    @staticmethod
    async def generate_flame_graph(duration: int = 30) -> str:
        """Generate a flame graph"""
        flame = Flame()
        
        # Start profiling
        flame.start()
        
        # Wait for duration
        await asyncio.sleep(duration)
        
        # Stop and get data
        data = flame.stop()
        
        # Generate SVG
        svg = flame.generate_svg(data)
        
        # Store SVG
        filename = f"flame_graph_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.svg"
        await redis_client.setex(
            f"profiling:flame:{filename}",
            86400,  # 24 hours
            svg
        )
        
        return filename


# Global profiler instance
profiler = Profiler()


# FastAPI integration
from fastapi import FastAPI, HTTPException
import json


def setup_profiling(app: FastAPI):
    """Setup profiling for FastAPI"""
    
    @app.on_event("startup")
    async def startup_profiling():
        await profiler.start_monitoring()
    
    @app.on_event("shutdown")
    async def shutdown_profiling():
        await profiler.stop_monitoring()
    
    # Profiling endpoints
    @app.get("/api/v1/profile/cpu/{function_name}")
    async def profile_endpoint(function_name: str, duration: int = 10):
        """Profile a specific function"""
        # This is a simplified example
        # In practice, you'd profile actual functions
        with profiler.profile_cpu(function_name):
            await asyncio.sleep(duration)
        
        return {"message": f"Profiled {function_name} for {duration} seconds"}
    
    @app.get("/api/v1/profile/memory")
    async def get_memory_profile():
        """Get current memory profile"""
        result = profiler.profile_memory("memory_snapshot")
        return result.stats
    
    @app.get("/api/v1/profile/results")
    async def get_profile_results(
        profile_type: Optional[str] = None,
        function_name: Optional[str] = None,
        limit: int = 50
    ):
        """Get profiling results"""
        results = await profiler.get_profile_results(
            profile_type=profile_type,
            function_name=function_name,
            limit=limit
        )
        return {"results": results, "count": len(results)}
    
    @app.post("/api/v1/profile/flame")
    async def generate_flame_graph(duration: int = 30):
        """Generate a flame graph"""
        if duration > 300:  # Max 5 minutes
            raise HTTPException(400, "Duration too long (max 300 seconds)")
        
        filename = await FlameGraphGenerator.generate_flame_graph(duration)
        return {"filename": filename, "duration": duration}
    
    @app.get("/api/v1/profile/flame/{filename}")
    async def get_flame_graph(filename: str):
        """Get generated flame graph"""
        svg = await redis_client.get(f"profiling:flame:{filename}")
        if not svg:
            raise HTTPException(404, "Flame graph not found")
        
        return Response(content=svg, media_type="image/svg+xml")


# Example usage
"""
# CPU profiling
@profile_cpu()
def expensive_function():
    # Some expensive computation
    pass

# Async profiling
@profile_async()
async def async_function():
    await asyncio.sleep(1)
    # Async operations

# Memory profiling
@profile_memory
def memory_intensive_function():
    data = [i for i in range(1000000)]
    return data

# Manual profiling
with profiler.profile_cpu("custom_operation"):
    # Code to profile
    pass
"""
