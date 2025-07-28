"""
Log aggregation and centralized logging
"""
import json
import asyncio
import gzip
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import re
import hashlib

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
import structlog

from core.config import settings
from core.redis import redis_client
from core.monitoring.tracing import get_current_trace_id, get_current_span_id


class LogLevel(Enum):
    """Log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogProcessor:
    """Base class for log processors"""
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Process a log entry"""
        raise NotImplementedError


class TraceEnricher(LogProcessor):
    """Enrich logs with trace information"""
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Add trace context to logs"""
        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
        
        if trace_id:
            log_entry['trace_id'] = trace_id
        if span_id:
            log_entry['span_id'] = span_id
        
        return log_entry


class ErrorParser(LogProcessor):
    """Parse and extract error information"""
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract error details from log messages"""
        if log_entry.get('level') in ['error', 'critical']:
            message = log_entry.get('message', '')
            
            # Extract stack trace
            if 'traceback' in log_entry:
                log_entry['error_details'] = {
                    'has_traceback': True,
                    'traceback_lines': len(log_entry['traceback'].split('\n'))
                }
            
            # Extract error type
            error_match = re.search(r'(\w+Error|\w+Exception):', message)
            if error_match:
                log_entry['error_type'] = error_match.group(1)
        
        return log_entry


class PatternDetector(LogProcessor):
    """Detect patterns and anomalies in logs"""
    
    def __init__(self):
        self.patterns = {
            'sql_injection': re.compile(r"(union.*select|select.*from.*where|';\s*(drop|delete|update))", re.I),
            'auth_failure': re.compile(r"(authentication failed|invalid credentials|unauthorized)", re.I),
            'rate_limit': re.compile(r"(rate limit|too many requests|throttled)", re.I),
            'out_of_memory': re.compile(r"(out of memory|memory exhausted|oom)", re.I),
            'connection_error': re.compile(r"(connection refused|timeout|unreachable)", re.I)
        }
    
    async def process(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Detect patterns in log messages"""
        message = log_entry.get('message', '')
        detected_patterns = []
        
        for pattern_name, pattern_regex in self.patterns.items():
            if pattern_regex.search(message):
                detected_patterns.append(pattern_name)
        
        if detected_patterns:
            log_entry['detected_patterns'] = detected_patterns
        
        return log_entry


class LogAggregator:
    """Central log aggregation service"""
    
    def __init__(self):
        self.buffer = deque(maxlen=10000)
        self.processors: List[LogProcessor] = []
        self.elasticsearch = None
        self.batch_size = 100
        self.flush_interval = 5  # seconds
        self._flush_task = None
        self._stats = defaultdict(int)
    
    async def initialize(self):
        """Initialize the log aggregator"""
        # Initialize Elasticsearch if configured
        if hasattr(settings, 'ELASTICSEARCH_URL'):
            self.elasticsearch = AsyncElasticsearch(
                [settings.ELASTICSEARCH_URL],
                basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)
                if hasattr(settings, 'ELASTICSEARCH_USER') else None
            )
        
        # Add default processors
        self.add_processor(TraceEnricher())
        self.add_processor(ErrorParser())
        self.add_processor(PatternDetector())
        
        # Start flush task
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def shutdown(self):
        """Shutdown the aggregator"""
        if self._flush_task:
            self._flush_task.cancel()
            await asyncio.gather(self._flush_task, return_exceptions=True)
        
        # Final flush
        await self._flush_buffer()
        
        if self.elasticsearch:
            await self.elasticsearch.close()
    
    def add_processor(self, processor: LogProcessor):
        """Add a log processor"""
        self.processors.append(processor)
    
    async def log(self, level: str, message: str, **kwargs):
        """Add a log entry"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message,
            'service': getattr(settings, 'SERVICE_NAME', 'agency-backend'),
            'environment': getattr(settings, 'ENVIRONMENT', 'production'),
            **kwargs
        }
        
        # Process log entry
        for processor in self.processors:
            log_entry = await processor.process(log_entry)
        
        # Add to buffer
        self.buffer.append(log_entry)
        self._stats['total_logs'] += 1
        self._stats[f'level_{level}'] += 1
        
        # Flush if buffer is full
        if len(self.buffer) >= self.batch_size:
            await self._flush_buffer()
    
    async def _flush_loop(self):
        """Periodically flush the buffer"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"Error in flush loop: {exc}")
    
    async def _flush_buffer(self):
        """Flush buffered logs"""
        if not self.buffer:
            return
        
        logs_to_flush = []
        while self.buffer and len(logs_to_flush) < self.batch_size:
            logs_to_flush.append(self.buffer.popleft())
        
        if logs_to_flush:
            # Store in Elasticsearch
            if self.elasticsearch:
                await self._store_in_elasticsearch(logs_to_flush)
            
            # Store in Redis for quick access
            await self._store_in_redis(logs_to_flush)
            
            self._stats['flushed_logs'] += len(logs_to_flush)
    
    async def _store_in_elasticsearch(self, logs: List[Dict[str, Any]]):
        """Store logs in Elasticsearch"""
        try:
            # Prepare bulk operations
            operations = []
            for log in logs:
                operations.append({
                    "_index": f"logs-{datetime.utcnow().strftime('%Y.%m.%d')}",
                    "_source": log
                })
            
            # Bulk insert
            await async_bulk(self.elasticsearch, operations)
            
        except Exception as exc:
            print(f"Error storing logs in Elasticsearch: {exc}")
    
    async def _store_in_redis(self, logs: List[Dict[str, Any]]):
        """Store recent logs in Redis"""
        try:
            # Store by level
            logs_by_level = defaultdict(list)
            for log in logs:
                level = log.get('level', 'info')
                logs_by_level[level].append(json.dumps(log))
            
            # Store in Redis lists
            for level, level_logs in logs_by_level.items():
                key = f"logs:{level}:recent"
                await redis_client.lpush(key, *level_logs)
                await redis_client.ltrim(key, 0, 999)  # Keep last 1000
                await redis_client.expire(key, 86400)  # 24 hours
            
            # Store errors separately for quick access
            error_logs = [log for log in logs if log.get('level') in ['error', 'critical']]
            if error_logs:
                error_key = "logs:errors:recent"
                error_entries = [json.dumps(log) for log in error_logs]
                await redis_client.lpush(error_key, *error_entries)
                await redis_client.ltrim(error_key, 0, 499)  # Keep last 500
            
        except Exception as exc:
            print(f"Error storing logs in Redis: {exc}")
    
    async def search_logs(
        self,
        query: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        trace_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search logs with filters"""
        if self.elasticsearch:
            return await self._search_elasticsearch(
                query, level, start_time, end_time, trace_id, limit
            )
        else:
            return await self._search_redis(
                level, limit
            )
    
    async def _search_elasticsearch(
        self,
        query: Optional[str],
        level: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        trace_id: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search logs in Elasticsearch"""
        # Build query
        must_clauses = []
        
        if query:
            must_clauses.append({"match": {"message": query}})
        
        if level:
            must_clauses.append({"term": {"level": level}})
        
        if trace_id:
            must_clauses.append({"term": {"trace_id": trace_id}})
        
        if start_time or end_time:
            time_range = {"range": {"timestamp": {}}}
            if start_time:
                time_range["range"]["timestamp"]["gte"] = start_time.isoformat()
            if end_time:
                time_range["range"]["timestamp"]["lte"] = end_time.isoformat()
            must_clauses.append(time_range)
        
        # Execute search
        es_query = {
            "query": {
                "bool": {"must": must_clauses} if must_clauses else {"match_all": {}}
            },
            "sort": [{"timestamp": "desc"}],
            "size": limit
        }
        
        result = await self.elasticsearch.search(index="logs-*", body=es_query)
        
        return [hit["_source"] for hit in result["hits"]["hits"]]
    
    async def _search_redis(
        self,
        level: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search logs in Redis (limited functionality)"""
        if level:
            key = f"logs:{level}:recent"
        else:
            key = "logs:info:recent"  # Default to info
        
        logs = await redis_client.lrange(key, 0, limit - 1)
        return [json.loads(log) for log in logs]
    
    async def get_log_stats(self, time_range: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
        """Get log statistics"""
        stats = {
            'time_range': time_range.total_seconds(),
            'levels': {},
            'patterns': defaultdict(int),
            'top_errors': [],
            'error_rate': 0
        }
        
        # Get recent logs
        end_time = datetime.utcnow()
        start_time = end_time - time_range
        
        logs = await self.search_logs(
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        
        # Calculate statistics
        total_logs = len(logs)
        error_logs = 0
        error_types = defaultdict(int)
        
        for log in logs:
            level = log.get('level', 'info')
            stats['levels'][level] = stats['levels'].get(level, 0) + 1
            
            if level in ['error', 'critical']:
                error_logs += 1
                if 'error_type' in log:
                    error_types[log['error_type']] += 1
            
            # Count patterns
            for pattern in log.get('detected_patterns', []):
                stats['patterns'][pattern] += 1
        
        # Calculate error rate
        if total_logs > 0:
            stats['error_rate'] = (error_logs / total_logs) * 100
        
        # Top errors
        stats['top_errors'] = sorted(
            error_types.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Add buffer stats
        stats['buffer_size'] = len(self.buffer)
        stats['total_processed'] = self._stats['total_logs']
        stats['total_flushed'] = self._stats['flushed_logs']
        
        return stats


# Structured logging setup
def setup_structured_logging():
    """Setup structured logging with processors"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            AsyncLogProcessor(),  # Custom async processor
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


class AsyncLogProcessor:
    """Custom async log processor for structlog"""
    
    def __call__(self, logger, method_name, event_dict):
        """Process log event asynchronously"""
        # Add trace context
        trace_id = get_current_trace_id()
        if trace_id:
            event_dict['trace_id'] = trace_id
        
        span_id = get_current_span_id()
        if span_id:
            event_dict['span_id'] = span_id
        
        # Add service context
        event_dict['service'] = getattr(settings, 'SERVICE_NAME', 'agency-backend')
        event_dict['environment'] = getattr(settings, 'ENVIRONMENT', 'production')
        
        # Send to aggregator (non-blocking)
        if hasattr(logger, '_aggregator'):
            asyncio.create_task(
                logger._aggregator.log(
                    level=method_name,
                    **event_dict
                )
            )
        
        return event_dict


# Log streaming for real-time monitoring
class LogStreamer:
    """Stream logs in real-time"""
    
    def __init__(self, aggregator: LogAggregator):
        self.aggregator = aggregator
        self.subscribers: Dict[str, asyncio.Queue] = {}
    
    async def subscribe(self, client_id: str, filters: Optional[Dict[str, Any]] = None) -> asyncio.Queue:
        """Subscribe to log stream"""
        queue = asyncio.Queue(maxsize=100)
        self.subscribers[client_id] = queue
        return queue
    
    async def unsubscribe(self, client_id: str):
        """Unsubscribe from log stream"""
        if client_id in self.subscribers:
            del self.subscribers[client_id]
    
    async def stream_logs(self, client_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream logs to a client"""
        queue = self.subscribers.get(client_id)
        if not queue:
            return
        
        while client_id in self.subscribers:
            try:
                log = await asyncio.wait_for(queue.get(), timeout=30)
                yield log
            except asyncio.TimeoutError:
                # Send heartbeat
                yield {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}


# Global instances
log_aggregator = LogAggregator()
log_streamer = LogStreamer(log_aggregator)


# FastAPI integration
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from typing import Optional


def setup_log_aggregation(app: FastAPI):
    """Setup log aggregation for FastAPI"""
    
    @app.on_event("startup")
    async def startup_aggregator():
        await log_aggregator.initialize()
        setup_structured_logging()
    
    @app.on_event("shutdown")
    async def shutdown_aggregator():
        await log_aggregator.shutdown()
    
    # API endpoints
    @app.get("/api/v1/logs")
    async def search_logs(
        query: Optional[str] = None,
        level: Optional[str] = None,
        trace_id: Optional[str] = None,
        hours: int = Query(1, ge=1, le=24),
        limit: int = Query(100, ge=1, le=1000)
    ):
        """Search logs"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        logs = await log_aggregator.search_logs(
            query=query,
            level=level,
            start_time=start_time,
            end_time=end_time,
            trace_id=trace_id,
            limit=limit
        )
        
        return {
            "logs": logs,
            "count": len(logs),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }
    
    @app.get("/api/v1/logs/stats")
    async def get_log_stats(hours: int = Query(1, ge=1, le=24)):
        """Get log statistics"""
        return await log_aggregator.get_log_stats(
            time_range=timedelta(hours=hours)
        )
    
    @app.websocket("/ws/logs")
    async def log_websocket(websocket: WebSocket):
        """WebSocket endpoint for real-time log streaming"""
        await websocket.accept()
        client_id = f"ws_{id(websocket)}"
        
        try:
            # Subscribe to log stream
            await log_streamer.subscribe(client_id)
            
            # Stream logs
            async for log in log_streamer.stream_logs(client_id):
                await websocket.send_json(log)
        
        except WebSocketDisconnect:
            pass
        finally:
            await log_streamer.unsubscribe(client_id)
