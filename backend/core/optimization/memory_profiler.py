"""
Memory profiling and optimization utilities.
"""

import gc
import tracemalloc
import psutil
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from functools import wraps
import weakref
import sys
from collections import defaultdict

from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryProfiler:
    """Profile and optimize memory usage."""
    
    def __init__(self):
        self.snapshots = []
        self.memory_stats = []
        self.object_tracker = ObjectTracker()
        self.monitoring_enabled = False
        self.alert_threshold_mb = 500  # Alert if memory usage exceeds 500MB
    
    def start_monitoring(self):
        """Start memory monitoring."""
        tracemalloc.start()
        self.monitoring_enabled = True
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop memory monitoring."""
        tracemalloc.stop()
        self.monitoring_enabled = False
        logger.info("Memory monitoring stopped")
    
    def take_snapshot(self, label: str = None) -> Dict[str, Any]:
        """Take memory snapshot."""
        if not self.monitoring_enabled:
            self.start_monitoring()
        
        # Get current memory usage
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Get tracemalloc snapshot
        snapshot = tracemalloc.take_snapshot()
        
        # Calculate top memory consumers
        top_stats = snapshot.statistics('lineno')[:10]
        
        snapshot_data = {
            "timestamp": datetime.utcnow(),
            "label": label or f"snapshot_{len(self.snapshots)}",
            "memory_usage_mb": memory_info.rss / 1024 / 1024,
            "peak_memory_mb": tracemalloc.get_traced_memory()[1] / 1024 / 1024,
            "top_consumers": [
                {
                    "file": stat.traceback.format()[0],
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count
                }
                for stat in top_stats
            ]
        }
        
        self.snapshots.append(snapshot_data)
        
        # Check memory threshold
        if snapshot_data["memory_usage_mb"] > self.alert_threshold_mb:
            logger.warning(
                f"High memory usage detected: {snapshot_data['memory_usage_mb']:.2f}MB",
                extra=snapshot_data
            )
        
        return snapshot_data
    
    def compare_snapshots(self, label1: str, label2: str) -> Dict[str, Any]:
        """Compare two memory snapshots."""
        snapshot1 = next((s for s in self.snapshots if s["label"] == label1), None)
        snapshot2 = next((s for s in self.snapshots if s["label"] == label2), None)
        
        if not snapshot1 or not snapshot2:
            raise ValueError("Snapshot not found")
        
        memory_diff = snapshot2["memory_usage_mb"] - snapshot1["memory_usage_mb"]
        
        return {
            "memory_diff_mb": memory_diff,
            "time_diff": (snapshot2["timestamp"] - snapshot1["timestamp"]).total_seconds(),
            "snapshot1": snapshot1,
            "snapshot2": snapshot2
        }
    
    def find_memory_leaks(self) -> List[Dict[str, Any]]:
        """Detect potential memory leaks."""
        leaks = []
        
        # Analyze object growth
        gc.collect()
        for obj_type, tracker in self.object_tracker.trackers.items():
            growth_rate = tracker.get_growth_rate()
            if growth_rate > 0.1:  # 10% growth rate
                leaks.append({
                    "type": obj_type,
                    "count": len(tracker.objects),
                    "growth_rate": growth_rate,
                    "sample_objects": list(tracker.objects)[:5]
                })
        
        # Analyze uncollectable objects
        uncollectable = gc.garbage
        if uncollectable:
            leaks.append({
                "type": "uncollectable",
                "count": len(uncollectable),
                "objects": uncollectable[:10]
            })
        
        return leaks
    
    def optimize_memory(self) -> Dict[str, Any]:
        """Perform memory optimization."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Force garbage collection
        gc.collect()
        gc.collect()  # Run twice to ensure cleanup
        
        # Clear caches
        for module in sys.modules.values():
            if hasattr(module, '__dict__'):
                for attr_name in dir(module):
                    attr = getattr(module, attr_name, None)
                    if hasattr(attr, 'cache_clear'):
                        attr.cache_clear()
        
        # Get final memory usage
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        optimization_result = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "freed_memory_mb": initial_memory - final_memory,
            "gc_stats": gc.get_stats()
        }
        
        logger.info(
            f"Memory optimization completed: freed {optimization_result['freed_memory_mb']:.2f}MB",
            extra=optimization_result
        )
        
        return optimization_result
    
    async def monitor_memory_async(self, interval: int = 60):
        """Monitor memory usage asynchronously."""
        while self.monitoring_enabled:
            stats = self.collect_memory_stats()
            self.memory_stats.append(stats)
            
            # Keep only last hour of stats
            if len(self.memory_stats) > 60:
                self.memory_stats = self.memory_stats[-60:]
            
            await asyncio.sleep(interval)
    
    def collect_memory_stats(self) -> Dict[str, Any]:
        """Collect current memory statistics."""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "timestamp": datetime.utcnow(),
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_mb": psutil.virtual_memory().available / 1024 / 1024,
            "gc_count": gc.get_count(),
            "gc_stats": gc.get_stats()
        }
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Generate memory usage report."""
        if not self.memory_stats:
            return {"error": "No memory statistics available"}
        
        current_stats = self.memory_stats[-1]
        
        # Calculate trends
        memory_trend = []
        if len(self.memory_stats) > 1:
            for i in range(1, len(self.memory_stats)):
                prev = self.memory_stats[i-1]["rss_mb"]
                curr = self.memory_stats[i]["rss_mb"]
                memory_trend.append(curr - prev)
        
        return {
            "current_memory_mb": current_stats["rss_mb"],
            "memory_percent": current_stats["percent"],
            "available_mb": current_stats["available_mb"],
            "average_growth_mb": sum(memory_trend) / len(memory_trend) if memory_trend else 0,
            "max_growth_mb": max(memory_trend) if memory_trend else 0,
            "gc_stats": current_stats["gc_stats"],
            "potential_leaks": self.find_memory_leaks()
        }


class ObjectTracker:
    """Track object creation and lifecycle."""
    
    def __init__(self):
        self.trackers = defaultdict(ObjectTypeTracker)
    
    def track(self, obj: Any):
        """Track an object."""
        obj_type = type(obj).__name__
        self.trackers[obj_type].track(obj)
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get tracking statistics."""
        return {
            obj_type: tracker.get_stats()
            for obj_type, tracker in self.trackers.items()
        }


class ObjectTypeTracker:
    """Track objects of a specific type."""
    
    def __init__(self):
        self.objects = weakref.WeakSet()
        self.creation_times = []
        self.total_created = 0
    
    def track(self, obj: Any):
        """Track an object."""
        self.objects.add(obj)
        self.creation_times.append(datetime.utcnow())
        self.total_created += 1
        
        # Keep only last hour of creation times
        cutoff = datetime.utcnow().timestamp() - 3600
        self.creation_times = [
            t for t in self.creation_times
            if t.timestamp() > cutoff
        ]
    
    def get_growth_rate(self) -> float:
        """Calculate object growth rate."""
        if len(self.creation_times) < 2:
            return 0.0
        
        time_span = (
            self.creation_times[-1] - self.creation_times[0]
        ).total_seconds()
        
        if time_span == 0:
            return 0.0
        
        return len(self.creation_times) / time_span
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        return {
            "alive_count": len(self.objects),
            "total_created": self.total_created,
            "growth_rate": self.get_growth_rate(),
            "creation_rate_per_minute": len(self.creation_times) / 60
        }


def profile_memory(threshold_mb: float = 10):
    """Decorator to profile function memory usage."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Take snapshot before
            profiler = MemoryProfiler()
            profiler.start_monitoring()
            before = profiler.take_snapshot(f"before_{func.__name__}")
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Take snapshot after
                after = profiler.take_snapshot(f"after_{func.__name__}")
                
                # Check memory usage
                memory_used = after["memory_usage_mb"] - before["memory_usage_mb"]
                
                if memory_used > threshold_mb:
                    logger.warning(
                        f"High memory usage in {func.__name__}: {memory_used:.2f}MB",
                        extra={
                            "function": func.__name__,
                            "memory_used_mb": memory_used,
                            "before": before["memory_usage_mb"],
                            "after": after["memory_usage_mb"]
                        }
                    )
                
                return result
                
            finally:
                profiler.stop_monitoring()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar implementation for sync functions
            profiler = MemoryProfiler()
            profiler.start_monitoring()
            before = profiler.take_snapshot(f"before_{func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                after = profiler.take_snapshot(f"after_{func.__name__}")
                
                memory_used = after["memory_usage_mb"] - before["memory_usage_mb"]
                
                if memory_used > threshold_mb:
                    logger.warning(
                        f"High memory usage in {func.__name__}: {memory_used:.2f}MB"
                    )
                
                return result
                
            finally:
                profiler.stop_monitoring()
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Memory optimization tips
MEMORY_OPTIMIZATION_TIPS = {
    "large_lists": {
        "issue": "Large lists consuming memory",
        "solution": "Use generators or iterators instead of lists",
        "example": "Use (x for x in range(1000000)) instead of [x for x in range(1000000)]"
    },
    "circular_references": {
        "issue": "Circular references preventing garbage collection",
        "solution": "Use weak references or break cycles explicitly",
        "example": "Use weakref.ref() for parent-child relationships"
    },
    "global_caches": {
        "issue": "Unbounded global caches",
        "solution": "Implement LRU cache with size limits",
        "example": "Use functools.lru_cache(maxsize=128)"
    },
    "large_strings": {
        "issue": "Large string concatenation",
        "solution": "Use join() or io.StringIO for string building",
        "example": "''.join(parts) instead of s += part"
    },
    "unused_imports": {
        "issue": "Importing large modules unnecessarily",
        "solution": "Import only what you need",
        "example": "from module import specific_function"
    }
}