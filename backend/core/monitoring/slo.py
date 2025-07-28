"""
Service Level Objectives (SLO) and Service Level Indicators (SLI) monitoring
"""
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from prometheus_client import Gauge, Counter, Histogram

from core.redis import redis_client
from core.logging import logger
from core.monitoring.metrics import registry, MetricCalculator


class SLIType(Enum):
    """Types of Service Level Indicators"""
    AVAILABILITY = "availability"  # Up/down
    LATENCY = "latency"  # Response time
    ERROR_RATE = "error_rate"  # Error percentage
    THROUGHPUT = "throughput"  # Requests per second
    QUALITY = "quality"  # Custom quality metric
    CORRECTNESS = "correctness"  # Data accuracy


class TimeWindow(Enum):
    """SLO measurement time windows"""
    ROLLING_1H = "1h"
    ROLLING_24H = "24h"
    ROLLING_7D = "7d"
    ROLLING_30D = "30d"
    CALENDAR_DAY = "calendar_day"
    CALENDAR_WEEK = "calendar_week"
    CALENDAR_MONTH = "calendar_month"


@dataclass
class SLI:
    """Service Level Indicator definition"""
    name: str
    type: SLIType
    description: str
    query: str  # Prometheus query
    unit: str = "percent"
    aggregation: str = "avg"  # avg, min, max, percentile
    percentile: Optional[float] = None  # For percentile aggregation
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLO:
    """Service Level Objective definition"""
    name: str
    description: str
    sli: SLI
    target: float  # Target value (e.g., 99.9)
    warning_target: Optional[float] = None  # Warning threshold
    time_windows: List[TimeWindow] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.time_windows:
            self.time_windows = [TimeWindow.ROLLING_24H, TimeWindow.ROLLING_7D]
        if self.warning_target is None:
            # Default warning at 50% of remaining error budget
            self.warning_target = self.target - (100 - self.target) * 0.5


@dataclass
class ErrorBudget:
    """Error budget calculation"""
    slo_name: str
    time_window: TimeWindow
    target: float
    current_value: float
    total_budget: float  # Total error budget (100 - target)
    consumed_budget: float  # How much budget used
    remaining_budget: float  # How much budget left
    burn_rate: float  # Rate of budget consumption
    time_until_exhausted: Optional[float] = None  # Hours until budget exhausted
    
    @property
    def is_exhausted(self) -> bool:
        return self.remaining_budget <= 0
    
    @property
    def is_warning(self) -> bool:
        return self.remaining_budget < (self.total_budget * 0.5)
    
    @property
    def is_critical(self) -> bool:
        return self.remaining_budget < (self.total_budget * 0.1)


# Prometheus metrics for SLO monitoring
slo_compliance = Gauge(
    'slo_compliance',
    'SLO compliance percentage',
    ['slo_name', 'time_window'],
    registry=registry
)

slo_error_budget_remaining = Gauge(
    'slo_error_budget_remaining',
    'Remaining error budget percentage',
    ['slo_name', 'time_window'],
    registry=registry
)

slo_burn_rate = Gauge(
    'slo_burn_rate',
    'Error budget burn rate',
    ['slo_name', 'time_window'],
    registry=registry
)

slo_violations = Counter(
    'slo_violations_total',
    'Total SLO violations',
    ['slo_name', 'severity'],
    registry=registry
)


class SLOManager:
    """Manages SLO definitions and monitoring"""
    
    def __init__(self):
        self.slos: Dict[str, SLO] = {}
        self._monitoring_task = None
        self._evaluation_interval = 60  # seconds
    
    def register_slo(self, slo: SLO):
        """Register an SLO"""
        self.slos[slo.name] = slo
        logger.info(f"Registered SLO: {slo.name}")
    
    def register_slos(self, slos: List[SLO]):
        """Register multiple SLOs"""
        for slo in slos:
            self.register_slo(slo)
    
    async def start_monitoring(self):
        """Start SLO monitoring"""
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("SLO monitoring started")
    
    async def stop_monitoring(self):
        """Stop SLO monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            await asyncio.gather(self._monitoring_task, return_exceptions=True)
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._evaluate_all_slos()
                await asyncio.sleep(self._evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in SLO monitoring: {exc}")
                await asyncio.sleep(self._evaluation_interval)
    
    async def _evaluate_all_slos(self):
        """Evaluate all registered SLOs"""
        for slo in self.slos.values():
            try:
                await self._evaluate_slo(slo)
            except Exception as exc:
                logger.error(f"Error evaluating SLO {slo.name}: {exc}")
    
    async def _evaluate_slo(self, slo: SLO):
        """Evaluate a single SLO"""
        for time_window in slo.time_windows:
            try:
                # Calculate SLI value
                sli_value = await self._calculate_sli(slo.sli, time_window)
                
                # Calculate error budget
                error_budget = self._calculate_error_budget(slo, sli_value, time_window)
                
                # Update metrics
                slo_compliance.labels(
                    slo_name=slo.name,
                    time_window=time_window.value
                ).set(sli_value)
                
                slo_error_budget_remaining.labels(
                    slo_name=slo.name,
                    time_window=time_window.value
                ).set(error_budget.remaining_budget)
                
                slo_burn_rate.labels(
                    slo_name=slo.name,
                    time_window=time_window.value
                ).set(error_budget.burn_rate)
                
                # Store evaluation result
                await self._store_evaluation(
                    slo, time_window, sli_value, error_budget
                )
                
                # Check for violations
                await self._check_violations(slo, error_budget)
                
            except Exception as exc:
                logger.error(
                    f"Error evaluating SLO {slo.name} for {time_window.value}: {exc}"
                )
    
    async def _calculate_sli(self, sli: SLI, time_window: TimeWindow) -> float:
        """Calculate SLI value from metrics"""
        # This is a simplified example - in production, you'd query Prometheus
        # or your metrics backend
        
        # For demonstration, calculate based on stored metrics
        if sli.type == SLIType.AVAILABILITY:
            return await self._calculate_availability(time_window)
        elif sli.type == SLIType.LATENCY:
            return await self._calculate_latency_sli(sli, time_window)
        elif sli.type == SLIType.ERROR_RATE:
            return await self._calculate_error_rate_sli(time_window)
        elif sli.type == SLIType.THROUGHPUT:
            return await self._calculate_throughput_sli(time_window)
        else:
            # Custom SLI - would execute the Prometheus query
            return 99.5  # Placeholder
    
    async def _calculate_availability(self, time_window: TimeWindow) -> float:
        """Calculate availability SLI"""
        # Get uptime data from Redis
        window_seconds = self._get_window_seconds(time_window)
        start_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        # Simplified calculation
        total_checks = window_seconds // 60  # Assume checks every minute
        failed_checks = await redis_client.get(
            f"monitoring:failed_checks:{time_window.value}"
        )
        failed_checks = int(failed_checks) if failed_checks else 0
        
        if total_checks == 0:
            return 100.0
        
        return ((total_checks - failed_checks) / total_checks) * 100
    
    async def _calculate_latency_sli(self, sli: SLI, time_window: TimeWindow) -> float:
        """Calculate latency SLI (percentage of requests under threshold)"""
        # This would query metrics for requests under threshold
        # For example: percentage of requests under 500ms
        threshold_ms = sli.metadata.get('threshold_ms', 500)
        
        # Placeholder calculation
        total_requests = 10000
        fast_requests = 9950
        
        if total_requests == 0:
            return 100.0
        
        return (fast_requests / total_requests) * 100
    
    async def _calculate_error_rate_sli(self, time_window: TimeWindow) -> float:
        """Calculate error rate SLI (percentage of successful requests)"""
        # Get error rate data
        window_key = f"metrics:errors:{time_window.value}"
        error_data = await redis_client.get(window_key)
        
        if error_data:
            data = json.loads(error_data)
            total = data.get('total_requests', 0)
            errors = data.get('error_requests', 0)
            
            if total == 0:
                return 100.0
            
            return ((total - errors) / total) * 100
        
        return 99.9  # Default if no data
    
    async def _calculate_throughput_sli(self, time_window: TimeWindow) -> float:
        """Calculate throughput SLI"""
        # This would check if throughput meets minimum requirements
        # For example: system handles at least X requests per second
        return 99.8  # Placeholder
    
    def _calculate_error_budget(self, slo: SLO, current_value: float, 
                               time_window: TimeWindow) -> ErrorBudget:
        """Calculate error budget"""
        total_budget = 100 - slo.target
        
        if current_value >= slo.target:
            # Meeting SLO
            consumed_budget = 0
            remaining_budget = total_budget
            burn_rate = 0
        else:
            # Not meeting SLO
            consumed_budget = slo.target - current_value
            remaining_budget = total_budget - consumed_budget
            
            # Calculate burn rate (budget consumed per hour)
            window_hours = self._get_window_seconds(time_window) / 3600
            burn_rate = consumed_budget / window_hours if window_hours > 0 else 0
        
        # Calculate time until exhausted
        time_until_exhausted = None
        if burn_rate > 0 and remaining_budget > 0:
            time_until_exhausted = remaining_budget / burn_rate
        
        return ErrorBudget(
            slo_name=slo.name,
            time_window=time_window,
            target=slo.target,
            current_value=current_value,
            total_budget=total_budget,
            consumed_budget=consumed_budget,
            remaining_budget=remaining_budget,
            burn_rate=burn_rate,
            time_until_exhausted=time_until_exhausted
        )
    
    async def _store_evaluation(self, slo: SLO, time_window: TimeWindow,
                               sli_value: float, error_budget: ErrorBudget):
        """Store SLO evaluation result"""
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'slo_name': slo.name,
            'time_window': time_window.value,
            'sli_value': sli_value,
            'target': slo.target,
            'meeting_slo': sli_value >= slo.target,
            'error_budget': {
                'total': error_budget.total_budget,
                'consumed': error_budget.consumed_budget,
                'remaining': error_budget.remaining_budget,
                'burn_rate': error_budget.burn_rate,
                'time_until_exhausted': error_budget.time_until_exhausted
            }
        }
        
        # Store in Redis with expiration
        key = f"slo:evaluation:{slo.name}:{time_window.value}"
        await redis_client.setex(
            key,
            86400 * 30,  # 30 days
            json.dumps(result)
        )
        
        # Add to time series
        ts_key = f"slo:timeseries:{slo.name}:{time_window.value}"
        await redis_client.lpush(ts_key, json.dumps(result))
        await redis_client.ltrim(ts_key, 0, 1000)  # Keep last 1000 evaluations
    
    async def _check_violations(self, slo: SLO, error_budget: ErrorBudget):
        """Check for SLO violations and trigger alerts"""
        if error_budget.is_exhausted:
            # SLO violated
            slo_violations.labels(
                slo_name=slo.name,
                severity='critical'
            ).inc()
            
            await self._send_alert(
                slo=slo,
                severity='critical',
                message=f"SLO {slo.name} violated! Error budget exhausted."
            )
        
        elif error_budget.is_critical:
            # Critical warning
            slo_violations.labels(
                slo_name=slo.name,
                severity='warning'
            ).inc()
            
            await self._send_alert(
                slo=slo,
                severity='warning',
                message=f"SLO {slo.name} critical: Only {error_budget.remaining_budget:.1f}% error budget remaining."
            )
        
        elif error_budget.current_value < slo.warning_target:
            # Warning threshold
            await self._send_alert(
                slo=slo,
                severity='info',
                message=f"SLO {slo.name} warning: Performance at {error_budget.current_value:.2f}% (target: {slo.target}%)"
            )
    
    async def _send_alert(self, slo: SLO, severity: str, message: str):
        """Send SLO violation alert"""
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'slo_name': slo.name,
            'severity': severity,
            'message': message,
            'target': slo.target,
            'tags': slo.tags
        }
        
        # Store alert
        await redis_client.lpush(
            f"slo:alerts:{severity}",
            json.dumps(alert)
        )
        await redis_client.ltrim(f"slo:alerts:{severity}", 0, 99)
        
        logger.warning(f"SLO Alert [{severity}]: {message}")
    
    def _get_window_seconds(self, time_window: TimeWindow) -> int:
        """Get time window duration in seconds"""
        if time_window == TimeWindow.ROLLING_1H:
            return 3600
        elif time_window == TimeWindow.ROLLING_24H:
            return 86400
        elif time_window == TimeWindow.ROLLING_7D:
            return 604800
        elif time_window == TimeWindow.ROLLING_30D:
            return 2592000
        else:
            # Calendar-based windows would need date calculation
            return 86400  # Default to 1 day
    
    async def get_slo_status(self, slo_name: str) -> Dict[str, Any]:
        """Get current status of an SLO"""
        slo = self.slos.get(slo_name)
        if not slo:
            return {"error": "SLO not found"}
        
        status = {
            "slo": {
                "name": slo.name,
                "description": slo.description,
                "target": slo.target,
                "warning_target": slo.warning_target
            },
            "evaluations": {}
        }
        
        for time_window in slo.time_windows:
            key = f"slo:evaluation:{slo.name}:{time_window.value}"
            evaluation = await redis_client.get(key)
            
            if evaluation:
                status["evaluations"][time_window.value] = json.loads(evaluation)
        
        return status
    
    async def get_error_budget_report(self) -> Dict[str, Any]:
        """Get error budget report for all SLOs"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "slos": []
        }
        
        for slo in self.slos.values():
            slo_report = {
                "name": slo.name,
                "target": slo.target,
                "windows": {}
            }
            
            for time_window in slo.time_windows:
                key = f"slo:evaluation:{slo.name}:{time_window.value}"
                evaluation = await redis_client.get(key)
                
                if evaluation:
                    data = json.loads(evaluation)
                    slo_report["windows"][time_window.value] = {
                        "current_value": data["sli_value"],
                        "meeting_slo": data["meeting_slo"],
                        "error_budget": data["error_budget"]
                    }
            
            report["slos"].append(slo_report)
        
        return report


# Global SLO manager
slo_manager = SLOManager()


# Default SLO definitions
def create_default_slos() -> List[SLO]:
    """Create default SLO definitions"""
    return [
        # API Availability SLO
        SLO(
            name="api_availability",
            description="API endpoints should be available 99.9% of the time",
            sli=SLI(
                name="api_availability_sli",
                type=SLIType.AVAILABILITY,
                description="Percentage of successful health checks",
                query='up{job="api"} == 1'
            ),
            target=99.9,
            warning_target=99.5,
            time_windows=[TimeWindow.ROLLING_24H, TimeWindow.ROLLING_7D, TimeWindow.ROLLING_30D],
            tags=["api", "availability", "critical"]
        ),
        
        # API Latency SLO
        SLO(
            name="api_latency",
            description="95% of API requests should complete within 500ms",
            sli=SLI(
                name="api_latency_sli",
                type=SLIType.LATENCY,
                description="Percentage of requests under 500ms",
                query='sum(rate(http_request_duration_seconds_bucket{le="0.5"}[5m])) / sum(rate(http_request_duration_seconds_count[5m])) * 100',
                metadata={"threshold_ms": 500}
            ),
            target=95.0,
            warning_target=90.0,
            time_windows=[TimeWindow.ROLLING_1H, TimeWindow.ROLLING_24H],
            tags=["api", "performance"]
        ),
        
        # Error Rate SLO
        SLO(
            name="api_error_rate",
            description="API error rate should be below 0.1%",
            sli=SLI(
                name="api_error_rate_sli",
                type=SLIType.ERROR_RATE,
                description="Percentage of successful requests",
                query='(1 - sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100'
            ),
            target=99.9,
            warning_target=99.5,
            time_windows=[TimeWindow.ROLLING_1H, TimeWindow.ROLLING_24H, TimeWindow.ROLLING_7D],
            tags=["api", "reliability"]
        ),
        
        # Database Query Performance SLO
        SLO(
            name="database_performance",
            description="99% of database queries should complete within 100ms",
            sli=SLI(
                name="db_query_latency_sli",
                type=SLIType.LATENCY,
                description="Percentage of queries under 100ms",
                query='sum(rate(database_query_duration_seconds_bucket{le="0.1"}[5m])) / sum(rate(database_query_duration_seconds_count[5m])) * 100',
                metadata={"threshold_ms": 100}
            ),
            target=99.0,
            warning_target=95.0,
            time_windows=[TimeWindow.ROLLING_1H, TimeWindow.ROLLING_24H],
            tags=["database", "performance"]
        ),
        
        # Task Processing SLO
        SLO(
            name="task_processing",
            description="99.5% of background tasks should complete successfully",
            sli=SLI(
                name="task_success_rate_sli",
                type=SLIType.ERROR_RATE,
                description="Percentage of successful task executions",
                query='sum(rate(celery_tasks_total{status="success"}[5m])) / sum(rate(celery_tasks_total[5m])) * 100'
            ),
            target=99.5,
            warning_target=99.0,
            time_windows=[TimeWindow.ROLLING_24H, TimeWindow.ROLLING_7D],
            tags=["celery", "reliability"]
        )
    ]


# API endpoints for SLO monitoring
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/slo", tags=["slo"])


@router.get("/status")
async def get_all_slo_status():
    """Get status of all SLOs"""
    statuses = {}
    for slo_name in slo_manager.slos:
        statuses[slo_name] = await slo_manager.get_slo_status(slo_name)
    return statuses


@router.get("/status/{slo_name}")
async def get_slo_status(slo_name: str):
    """Get status of a specific SLO"""
    status = await slo_manager.get_slo_status(slo_name)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/error-budget")
async def get_error_budget_report():
    """Get error budget report for all SLOs"""
    return await slo_manager.get_error_budget_report()


@router.get("/alerts")
async def get_slo_alerts(severity: Optional[str] = None, limit: int = 50):
    """Get recent SLO alerts"""
    if severity:
        key = f"slo:alerts:{severity}"
        alerts = await redis_client.lrange(key, 0, limit - 1)
    else:
        # Get alerts from all severities
        alerts = []
        for sev in ['critical', 'warning', 'info']:
            key = f"slo:alerts:{sev}"
            sev_alerts = await redis_client.lrange(key, 0, limit // 3)
            alerts.extend(sev_alerts)
    
    return [
        json.loads(alert) for alert in alerts
    ]


# Initialize default SLOs
def setup_slos():
    """Setup default SLOs"""
    default_slos = create_default_slos()
    slo_manager.register_slos(default_slos)
    logger.info(f"Registered {len(default_slos)} default SLOs")
