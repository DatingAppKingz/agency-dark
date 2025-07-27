"""
System metrics collector for CPU, memory, disk, and network.
"""
import asyncio
import psutil
import platform
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from core.monitoring.models import Metric, MetricType
from core.database import get_db
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Collects system-level metrics."""
    
    def __init__(self):
        self.hostname = platform.node()
        self.collection_interval = 60  # seconds
        self.is_running = False
        
    async def start(self):
        """Start the metrics collection loop."""
        self.is_running = True
        logger.info("Starting system metrics collector")
        
        while self.is_running:
            try:
                async for db in get_db():
                    await self.collect_all_metrics(db)
                    break
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
            
            await asyncio.sleep(self.collection_interval)
    
    async def stop(self):
        """Stop the metrics collection."""
        self.is_running = False
        logger.info("Stopping system metrics collector")
    
    async def collect_all_metrics(self, db: AsyncSession):
        """Collect all system metrics."""
        timestamp = datetime.utcnow()
        metrics = []
        
        # CPU metrics
        cpu_metrics = self._collect_cpu_metrics(timestamp)
        metrics.extend(cpu_metrics)
        
        # Memory metrics
        memory_metrics = self._collect_memory_metrics(timestamp)
        metrics.extend(memory_metrics)
        
        # Disk metrics
        disk_metrics = self._collect_disk_metrics(timestamp)
        metrics.extend(disk_metrics)
        
        # Network metrics
        network_metrics = self._collect_network_metrics(timestamp)
        metrics.extend(network_metrics)
        
        # Process-specific metrics
        process_metrics = self._collect_process_metrics(timestamp)
        metrics.extend(process_metrics)
        
        # Save all metrics
        db.add_all(metrics)
        await db.commit()
        
        logger.debug(f"Collected {len(metrics)} system metrics")
    
    def _collect_cpu_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect CPU-related metrics."""
        metrics = []
        
        # Overall CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(Metric(
            metric_type=MetricType.SYSTEM_CPU,
            metric_name="cpu_usage_percent",
            value=cpu_percent,
            unit="percent",
            tags={"type": "overall"},
            hostname=self.hostname,
            service_name="system",
            timestamp=timestamp
        ))
        
        # Per-CPU usage
        cpu_percent_per_core = psutil.cpu_percent(interval=1, percpu=True)
        for i, percent in enumerate(cpu_percent_per_core):
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_CPU,
                metric_name="cpu_core_usage_percent",
                value=percent,
                unit="percent",
                tags={"core": str(i)},
                hostname=self.hostname,
                service_name="system",
                timestamp=timestamp
            ))
        
        # CPU frequency
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_CPU,
                metric_name="cpu_frequency_mhz",
                value=cpu_freq.current,
                unit="mhz",
                tags={"min": str(cpu_freq.min), "max": str(cpu_freq.max)},
                hostname=self.hostname,
                service_name="system",
                timestamp=timestamp
            ))
        
        # Load average (Unix only)
        if hasattr(psutil, "getloadavg"):
            load1, load5, load15 = psutil.getloadavg()
            for interval, value in [("1min", load1), ("5min", load5), ("15min", load15)]:
                metrics.append(Metric(
                    metric_type=MetricType.SYSTEM_CPU,
                    metric_name="load_average",
                    value=value,
                    unit="load",
                    tags={"interval": interval},
                    hostname=self.hostname,
                    service_name="system",
                    timestamp=timestamp
                ))
        
        return metrics
    
    def _collect_memory_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect memory-related metrics."""
        metrics = []
        
        # Virtual memory
        vm = psutil.virtual_memory()
        memory_metrics = {
            "memory_total_bytes": vm.total,
            "memory_available_bytes": vm.available,
            "memory_used_bytes": vm.used,
            "memory_free_bytes": vm.free,
            "memory_usage_percent": vm.percent
        }
        
        for name, value in memory_metrics.items():
            unit = "bytes" if "bytes" in name else "percent"
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_MEMORY,
                metric_name=name,
                value=float(value),
                unit=unit,
                hostname=self.hostname,
                service_name="system",
                timestamp=timestamp
            ))
        
        # Swap memory
        swap = psutil.swap_memory()
        swap_metrics = {
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_free_bytes": swap.free,
            "swap_usage_percent": swap.percent
        }
        
        for name, value in swap_metrics.items():
            unit = "bytes" if "bytes" in name else "percent"
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_MEMORY,
                metric_name=name,
                value=float(value),
                unit=unit,
                hostname=self.hostname,
                service_name="system",
                timestamp=timestamp
            ))
        
        return metrics
    
    def _collect_disk_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect disk-related metrics."""
        metrics = []
        
        # Disk usage per partition
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                disk_metrics = {
                    "disk_total_bytes": usage.total,
                    "disk_used_bytes": usage.used,
                    "disk_free_bytes": usage.free,
                    "disk_usage_percent": usage.percent
                }
                
                for name, value in disk_metrics.items():
                    unit = "bytes" if "bytes" in name else "percent"
                    metrics.append(Metric(
                        metric_type=MetricType.SYSTEM_DISK,
                        metric_name=name,
                        value=float(value),
                        unit=unit,
                        tags={
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype
                        },
                        hostname=self.hostname,
                        service_name="system",
                        timestamp=timestamp
                    ))
            except PermissionError:
                # Some partitions may not be accessible
                continue
        
        # Disk I/O statistics
        disk_io = psutil.disk_io_counters()
        if disk_io:
            io_metrics = {
                "disk_read_bytes_total": disk_io.read_bytes,
                "disk_write_bytes_total": disk_io.write_bytes,
                "disk_read_count": disk_io.read_count,
                "disk_write_count": disk_io.write_count
            }
            
            for name, value in io_metrics.items():
                unit = "bytes" if "bytes" in name else "count"
                metrics.append(Metric(
                    metric_type=MetricType.SYSTEM_DISK,
                    metric_name=name,
                    value=float(value),
                    unit=unit,
                    hostname=self.hostname,
                    service_name="system",
                    timestamp=timestamp
                ))
        
        return metrics
    
    def _collect_network_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect network-related metrics."""
        metrics = []
        
        # Network I/O statistics
        net_io = psutil.net_io_counters()
        if net_io:
            network_metrics = {
                "network_bytes_sent_total": net_io.bytes_sent,
                "network_bytes_recv_total": net_io.bytes_recv,
                "network_packets_sent_total": net_io.packets_sent,
                "network_packets_recv_total": net_io.packets_recv,
                "network_errors_in": net_io.errin,
                "network_errors_out": net_io.errout,
                "network_drop_in": net_io.dropin,
                "network_drop_out": net_io.dropout
            }
            
            for name, value in network_metrics.items():
                unit = "bytes" if "bytes" in name else "count"
                metrics.append(Metric(
                    metric_type=MetricType.SYSTEM_NETWORK,
                    metric_name=name,
                    value=float(value),
                    unit=unit,
                    hostname=self.hostname,
                    service_name="system",
                    timestamp=timestamp
                ))
        
        # Network connections
        connections = len(psutil.net_connections())
        metrics.append(Metric(
            metric_type=MetricType.SYSTEM_NETWORK,
            metric_name="network_connections_total",
            value=float(connections),
            unit="count",
            hostname=self.hostname,
            service_name="system",
            timestamp=timestamp
        ))
        
        return metrics
    
    def _collect_process_metrics(self, timestamp: datetime) -> List[Metric]:
        """Collect metrics for the current process."""
        metrics = []
        
        try:
            process = psutil.Process()
            
            # CPU usage for this process
            cpu_percent = process.cpu_percent(interval=1)
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_CPU,
                metric_name="process_cpu_percent",
                value=cpu_percent,
                unit="percent",
                tags={"process": "api_server"},
                hostname=self.hostname,
                service_name="api",
                timestamp=timestamp
            ))
            
            # Memory usage for this process
            memory_info = process.memory_info()
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_MEMORY,
                metric_name="process_memory_rss_bytes",
                value=float(memory_info.rss),
                unit="bytes",
                tags={"process": "api_server"},
                hostname=self.hostname,
                service_name="api",
                timestamp=timestamp
            ))
            
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_MEMORY,
                metric_name="process_memory_vms_bytes",
                value=float(memory_info.vms),
                unit="bytes",
                tags={"process": "api_server"},
                hostname=self.hostname,
                service_name="api",
                timestamp=timestamp
            ))
            
            # Thread count
            metrics.append(Metric(
                metric_type=MetricType.SYSTEM_CPU,
                metric_name="process_thread_count",
                value=float(process.num_threads()),
                unit="count",
                tags={"process": "api_server"},
                hostname=self.hostname,
                service_name="api",
                timestamp=timestamp
            ))
            
            # File descriptors (Unix only)
            if hasattr(process, "num_fds"):
                metrics.append(Metric(
                    metric_type=MetricType.SYSTEM_CPU,
                    metric_name="process_fd_count",
                    value=float(process.num_fds()),
                    unit="count",
                    tags={"process": "api_server"},
                    hostname=self.hostname,
                    service_name="api",
                    timestamp=timestamp
                ))
            
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
        
        return metrics


# Global instance
system_collector = SystemMetricsCollector()