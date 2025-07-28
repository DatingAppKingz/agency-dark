"""
Performance benchmarking and monitoring utilities
"""
import time
import asyncio
import psutil
import gc
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager
from functools import wraps
import statistics

from core.config import get_settings
from core.logging import get_logger
from core.metrics import metrics_collector

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark test"""
    name: str
    duration: float
    memory_used: float
    cpu_percent: float
    iterations: int
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceBenchmark:
    """Performance benchmarking utility"""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.process = psutil.Process()
    
    @asynccontextmanager
    async def measure(self, name: str, iterations: int = 1):
        """Context manager for measuring performance"""
        # Force garbage collection before measurement
        gc.collect()
        
        # Get initial metrics
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = self.process.cpu_percent(interval=0.1)
        
        times = []
        
        try:
            for i in range(iterations):
                iter_start = time.perf_counter()
                yield i
                iter_end = time.perf_counter()
                times.append(iter_end - iter_start)
            
            # Get final metrics
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            end_cpu = self.process.cpu_percent(interval=0.1)
            
            # Calculate statistics
            total_time = sum(times)
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            
            # Create result
            result = BenchmarkResult(
                name=name,
                duration=total_time,
                memory_used=end_memory - start_memory,
                cpu_percent=(start_cpu + end_cpu) / 2,
                iterations=iterations,
                avg_time=avg_time,
                min_time=min_time,
                max_time=max_time,
                std_dev=std_dev
            )
            
            self.results.append(result)
            
            # Log result
            logger.info(
                f"Benchmark '{name}': "
                f"avg={avg_time*1000:.2f}ms, "
                f"min={min_time*1000:.2f}ms, "
                f"max={max_time*1000:.2f}ms, "
                f"memory={result.memory_used:.2f}MB"
            )
            
        except Exception as e:
            logger.error(f"Benchmark '{name}' failed: {e}")
            raise
    
    def compare(self, baseline: str, comparison: str) -> Dict[str, Any]:
        """Compare two benchmark results"""
        baseline_result = next((r for r in self.results if r.name == baseline), None)
        comparison_result = next((r for r in self.results if r.name == comparison), None)
        
        if not baseline_result or not comparison_result:
            raise ValueError("Benchmark results not found")
        
        return {
            "baseline": baseline,
            "comparison": comparison,
            "time_diff": comparison_result.avg_time - baseline_result.avg_time,
            "time_ratio": comparison_result.avg_time / baseline_result.avg_time,
            "memory_diff": comparison_result.memory_used - baseline_result.memory_used,
            "cpu_diff": comparison_result.cpu_percent - baseline_result.cpu_percent
        }
    
    def get_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all benchmark results"""
        return [
            {
                "name": r.name,
                "avg_time_ms": r.avg_time * 1000,
                "min_time_ms": r.min_time * 1000,
                "max_time_ms": r.max_time * 1000,
                "memory_mb": r.memory_used,
                "cpu_percent": r.cpu_percent,
                "iterations": r.iterations
            }
            for r in self.results
        ]


class PerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.thresholds: Dict[str, float] = {
            "response_time": 1.0,  # 1 second
            "memory_usage": 80.0,  # 80%
            "cpu_usage": 80.0,     # 80%
            "error_rate": 5.0      # 5%
        }
    
    async def start_monitoring(self, interval: int = 60):
        """Start continuous performance monitoring"""
        while True:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent
                
                # Store metrics
                self._record_metric("cpu_usage", cpu_percent)
                self._record_metric("memory_usage", memory_percent)
                self._record_metric("disk_usage", disk_usage)
                
                # Check thresholds
                self._check_thresholds()
                
                # Send to metrics collector
                metrics_collector.gauge("system.cpu_usage", cpu_percent)
                metrics_collector.gauge("system.memory_usage", memory_percent)
                metrics_collector.gauge("system.disk_usage", disk_usage)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def _record_metric(self, name: str, value: float):
        """Record a metric value"""
        if name not in self.metrics:
            self.metrics[name] = []
        
        # Keep last 100 values
        self.metrics[name].append(value)
        if len(self.metrics[name]) > 100:
            self.metrics[name].pop(0)
    
    def _check_thresholds(self):
        """Check if any metrics exceed thresholds"""
        for metric_name, threshold in self.thresholds.items():
            if metric_name in self.metrics and self.metrics[metric_name]:
                current_value = self.metrics[metric_name][-1]
                
                if current_value > threshold:
                    logger.warning(
                        f"Performance threshold exceeded: "
                        f"{metric_name}={current_value:.2f} > {threshold}"
                    )
                    
                    # Send alert
                    metrics_collector.increment(
                        "performance.threshold_exceeded",
                        tags={"metric": metric_name}
                    )
    
    def get_metrics_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary statistics for all metrics"""
        summary = {}
        
        for name, values in self.metrics.items():
            if values:
                summary[name] = {
                    "current": values[-1],
                    "avg": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0
                }
        
        return summary


# Decorators for performance measurement
def benchmark(name: Optional[str] = None, iterations: int = 1):
    """Decorator for benchmarking functions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            benchmark_name = name or f"{func.__module__}.{func.__name__}"
            benchmark = PerformanceBenchmark()
            
            async with benchmark.measure(benchmark_name, iterations):
                if iterations == 1:
                    return await func(*args, **kwargs)
                else:
                    results = []
                    for _ in range(iterations):
                        result = await func(*args, **kwargs)
                        results.append(result)
                    return results[-1]  # Return last result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            benchmark_name = name or f"{func.__module__}.{func.__name__}"
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                
                logger.info(f"Benchmark '{benchmark_name}': {duration*1000:.2f}ms")
                metrics_collector.timing(f"benchmark.{benchmark_name}", duration * 1000)
                
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(f"Benchmark '{benchmark_name}' failed after {duration*1000:.2f}ms: {e}")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def profile_memory(func: Callable) -> Callable:
    """Decorator for profiling memory usage"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        gc.collect()
        
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        result = await func(*args, **kwargs)
        
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = end_memory - start_memory
        
        logger.info(
            f"Memory profile '{func.__name__}': "
            f"used={memory_used:.2f}MB, "
            f"total={end_memory:.2f}MB"
        )
        
        metrics_collector.gauge(f"memory.{func.__name__}", memory_used)
        
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        gc.collect()
        
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        result = func(*args, **kwargs)
        
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = end_memory - start_memory
        
        logger.info(
            f"Memory profile '{func.__name__}': "
            f"used={memory_used:.2f}MB, "
            f"total={end_memory:.2f}MB"
        )
        
        return result
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# Load testing utilities
class LoadTester:
    """Simple load testing utility"""
    
    @staticmethod
    async def run_concurrent_requests(
        func: Callable,
        num_requests: int,
        concurrency: int = 10,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Run concurrent requests and measure performance"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_func():
            async with semaphore:
                start = time.perf_counter()
                try:
                    await func(*args, **kwargs)
                    return time.perf_counter() - start, True
                except Exception as e:
                    return time.perf_counter() - start, False
        
        # Run all requests
        start_time = time.perf_counter()
        results = await asyncio.gather(
            *[limited_func() for _ in range(num_requests)],
            return_exceptions=True
        )
        total_time = time.perf_counter() - start_time
        
        # Analyze results
        times = [r[0] for r in results if isinstance(r, tuple)]
        successes = [r[1] for r in results if isinstance(r, tuple) and r[1]]
        failures = [r for r in results if isinstance(r, Exception) or (isinstance(r, tuple) and not r[1])]
        
        return {
            "total_requests": num_requests,
            "successful_requests": len(successes),
            "failed_requests": len(failures),
            "total_time": total_time,
            "requests_per_second": num_requests / total_time,
            "avg_response_time": statistics.mean(times) if times else 0,
            "min_response_time": min(times) if times else 0,
            "max_response_time": max(times) if times else 0,
            "p95_response_time": statistics.quantiles(times, n=20)[18] if len(times) > 1 else 0,
            "p99_response_time": statistics.quantiles(times, n=100)[98] if len(times) > 1 else 0
        }


# Global instances
performance_monitor = PerformanceMonitor()
benchmark_suite = PerformanceBenchmark()