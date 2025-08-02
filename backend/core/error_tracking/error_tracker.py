"""
Comprehensive error tracking and reporting system
"""
import json
import traceback
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import asyncio

from sqlalchemy import select, and_, func, desc
from fastapi import Request

from core.tasks.db_context import get_db_context
from core.redis import redis_client
from core.logging import logger
from core.config import settings


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for grouping"""
    API = "api"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorContext:
    """Context information for an error"""
    
    def __init__(
        self,
        error: Exception,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.error = error
        self.error_type = type(error).__name__
        self.error_message = str(error)
        self.traceback = traceback.format_exc()
        self.timestamp = datetime.utcnow()
        
        # Request context
        if request:
            self.request_context = {
                'method': request.method,
                'url': str(request.url),
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'headers': dict(request.headers),
                'client_host': request.client.host if request.client else None
            }
        else:
            self.request_context = None
        
        self.user_id = user_id
        self.operation = operation
        self.metadata = metadata or {}
        
        # Generate fingerprint for grouping similar errors
        self.fingerprint = self._generate_fingerprint()
    
    def _generate_fingerprint(self) -> str:
        """Generate a fingerprint for error grouping"""
        # Use error type and key parts of the stack trace
        key_parts = [
            self.error_type,
            self.operation or 'unknown'
        ]
        
        # Extract key lines from traceback (file names and line numbers)
        tb_lines = self.traceback.split('\n')
        for line in tb_lines:
            if 'File "' in line and 'line' in line:
                # Extract file path and line number
                parts = line.strip().split('"')
                if len(parts) >= 2:
                    file_path = parts[1].split('/')[-1]  # Just filename
                    key_parts.append(file_path)
        
        fingerprint_string = '|'.join(key_parts[:5])  # Limit to 5 parts
        return hashlib.md5(fingerprint_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'error_type': self.error_type,
            'error_message': self.error_message,
            'traceback': self.traceback,
            'timestamp': self.timestamp.isoformat(),
            'fingerprint': self.fingerprint,
            'request_context': self.request_context,
            'user_id': self.user_id,
            'operation': self.operation,
            'metadata': self.metadata
        }


class ErrorTracker:
    """Main error tracking service"""
    
    def __init__(self):
        self.enabled = getattr(settings, 'ERROR_TRACKING_ENABLED', True)
        self.sample_rate = getattr(settings, 'ERROR_SAMPLE_RATE', 1.0)  # 100% by default
        self.retention_days = 30
        self._error_buffer = []
        self._buffer_size = 100
        self._flush_interval = 10  # seconds
        self._flush_task = None
    
    async def start(self):
        """Start the error tracker"""
        if self.enabled:
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("Error tracker started")
    
    async def stop(self):
        """Stop the error tracker"""
        if self._flush_task:
            self._flush_task.cancel()
            await asyncio.gather(self._flush_task, return_exceptions=True)
            # Flush remaining errors
            await self._flush_buffer()
    
    async def track_error(
        self,
        error: Exception,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> Optional[str]:
        """
        Track an error occurrence
        
        Returns:
            Error ID if tracked, None if sampled out or disabled
        """
        if not self.enabled:
            return None
        
        # Apply sampling
        import random
        if random.random() > self.sample_rate:
            return None
        
        # Create error context
        context = ErrorContext(
            error=error,
            request=request,
            user_id=user_id,
            operation=operation,
            metadata=metadata
        )
        
        # Determine severity if not provided
        if not severity:
            severity = self._determine_severity(context)
        
        # Determine category
        category = self._categorize_error(context)
        
        # Create error record
        error_id = f"err_{context.timestamp.timestamp()}_{context.fingerprint[:8]}"
        error_record = {
            'id': error_id,
            'context': context.to_dict(),
            'severity': severity.value,
            'category': category.value
        }
        
        # Add to buffer
        self._error_buffer.append(error_record)
        
        # Flush if buffer is full
        if len(self._error_buffer) >= self._buffer_size:
            await self._flush_buffer()
        
        # Track metrics
        await self._update_metrics(context, severity, category)
        
        # Send alerts for critical errors
        if severity == ErrorSeverity.CRITICAL:
            await self._send_alert(context, error_id)
        
        return error_id
    
    async def get_error_report(
        self,
        time_range: timedelta = timedelta(hours=24),
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> Dict[str, Any]:
        """
        Get error report for the specified time range
        """
        start_time = datetime.utcnow() - time_range
        
        # Get error groups
        groups_key = f"error_tracking:groups:{start_time.strftime('%Y%m%d')}"
        raw_groups = await redis_client.hgetall(groups_key)
        
        error_groups = []
        total_errors = 0
        
        for fingerprint, data in raw_groups.items():
            group_data = json.loads(data)
            
            # Apply filters
            if category and group_data['category'] != category.value:
                continue
            if severity and group_data['severity'] != severity.value:
                continue
            
            error_groups.append({
                'fingerprint': fingerprint,
                'count': group_data['count'],
                'first_seen': group_data['first_seen'],
                'last_seen': group_data['last_seen'],
                'error_type': group_data['error_type'],
                'error_message': group_data['error_message'],
                'category': group_data['category'],
                'severity': group_data['severity'],
                'affected_users': group_data.get('affected_users', [])
            })
            
            total_errors += group_data['count']
        
        # Sort by count (most frequent first)
        error_groups.sort(key=lambda x: x['count'], reverse=True)
        
        # Get metrics
        metrics = await self._get_metrics(start_time)
        
        return {
            'time_range': {
                'start': start_time.isoformat(),
                'end': datetime.utcnow().isoformat()
            },
            'summary': {
                'total_errors': total_errors,
                'unique_errors': len(error_groups),
                'error_rate': metrics.get('error_rate', 0),
                'affected_users': len(set(
                    user for group in error_groups 
                    for user in group.get('affected_users', [])
                ))
            },
            'by_severity': metrics.get('by_severity', {}),
            'by_category': metrics.get('by_category', {}),
            'top_errors': error_groups[:10],  # Top 10 most frequent
            'recent_critical': await self._get_recent_critical_errors()
        }
    
    async def get_error_details(self, error_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific error
        """
        # Try to get from recent errors
        details_key = f"error_tracking:details:{error_id}"
        details_data = await redis_client.get(details_key)
        
        if details_data:
            return json.loads(details_data)
        
        return None
    
    async def get_error_trend(
        self,
        fingerprint: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get trend data for a specific error
        """
        trend_data = []
        
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=i)
            date_key = date.strftime('%Y%m%d')
            
            # Get count for this day
            count_key = f"error_tracking:daily:{date_key}:{fingerprint}"
            count = await redis_client.get(count_key)
            
            trend_data.append({
                'date': date.date().isoformat(),
                'count': int(count) if count else 0
            })
        
        trend_data.reverse()  # Oldest first
        
        return {
            'fingerprint': fingerprint,
            'period': f"{days} days",
            'trend': trend_data,
            'total': sum(d['count'] for d in trend_data)
        }
    
    def _determine_severity(self, context: ErrorContext) -> ErrorSeverity:
        """Determine error severity based on context"""
        error_type = context.error_type.lower()
        error_msg = context.error_message.lower()
        
        # Critical errors
        critical_keywords = ['database', 'connection lost', 'out of memory', 'disk full']
        if any(keyword in error_msg for keyword in critical_keywords):
            return ErrorSeverity.CRITICAL
        
        # High severity
        high_keywords = ['authentication', 'authorization', 'payment', 'security']
        if any(keyword in error_msg for keyword in high_keywords):
            return ErrorSeverity.HIGH
        
        # Medium severity
        medium_keywords = ['timeout', 'validation', 'bad request']
        if any(keyword in error_msg for keyword in medium_keywords):
            return ErrorSeverity.MEDIUM
        
        # Default to low
        return ErrorSeverity.LOW
    
    def _categorize_error(self, context: ErrorContext) -> ErrorCategory:
        """Categorize error based on context"""
        error_type = context.error_type.lower()
        error_msg = context.error_message.lower()
        
        # Check for specific patterns
        if 'database' in error_msg or 'sql' in error_msg:
            return ErrorCategory.DATABASE
        
        if any(keyword in error_msg for keyword in ['api', 'endpoint', 'route']):
            return ErrorCategory.API
        
        if any(keyword in error_msg for keyword in ['external', 'third-party', 'integration']):
            return ErrorCategory.EXTERNAL_SERVICE
        
        if 'validation' in error_msg or 'invalid' in error_msg:
            return ErrorCategory.VALIDATION
        
        if any(keyword in error_msg for keyword in ['auth', 'permission', 'forbidden']):
            return ErrorCategory.AUTHENTICATION
        
        if context.operation and 'business' in context.operation:
            return ErrorCategory.BUSINESS_LOGIC
        
        if any(keyword in error_type for keyword in ['system', 'os', 'memory']):
            return ErrorCategory.SYSTEM
        
        return ErrorCategory.UNKNOWN
    
    async def _flush_loop(self):
        """Periodically flush error buffer"""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in flush loop: {exc}")
    
    async def _flush_buffer(self):
        """Flush error buffer to storage"""
        if not self._error_buffer:
            return
        
        errors_to_flush = self._error_buffer[:]
        self._error_buffer.clear()
        
        for error_record in errors_to_flush:
            await self._store_error(error_record)
    
    async def _store_error(self, error_record: Dict[str, Any]):
        """Store error record"""
        error_id = error_record['id']
        context = error_record['context']
        fingerprint = context['fingerprint']
        
        # Store error details
        details_key = f"error_tracking:details:{error_id}"
        await redis_client.setex(
            details_key,
            self.retention_days * 86400,
            json.dumps(error_record)
        )
        
        # Update error group
        date_key = datetime.utcnow().strftime('%Y%m%d')
        groups_key = f"error_tracking:groups:{date_key}"
        
        # Get existing group data
        group_data = await redis_client.hget(groups_key, fingerprint)
        if group_data:
            group = json.loads(group_data)
            group['count'] += 1
            group['last_seen'] = context['timestamp']
            if context['user_id'] and context['user_id'] not in group['affected_users']:
                group['affected_users'].append(context['user_id'])
        else:
            group = {
                'count': 1,
                'first_seen': context['timestamp'],
                'last_seen': context['timestamp'],
                'error_type': context['error_type'],
                'error_message': context['error_message'],
                'category': error_record['category'],
                'severity': error_record['severity'],
                'affected_users': [context['user_id']] if context['user_id'] else []
            }
        
        await redis_client.hset(groups_key, fingerprint, json.dumps(group))
        await redis_client.expire(groups_key, 86400 * 7)  # 7 days
        
        # Update daily count
        daily_key = f"error_tracking:daily:{date_key}:{fingerprint}"
        await redis_client.incr(daily_key)
        await redis_client.expire(daily_key, 86400 * 30)  # 30 days
    
    async def _update_metrics(self, context: ErrorContext, severity: ErrorSeverity, category: ErrorCategory):
        """Update error metrics"""
        hour_key = datetime.utcnow().strftime('%Y%m%d%H')
        metrics_key = f"error_tracking:metrics:{hour_key}"
        
        # Increment counters
        await redis_client.hincrby(metrics_key, 'total', 1)
        await redis_client.hincrby(metrics_key, f"severity:{severity.value}", 1)
        await redis_client.hincrby(metrics_key, f"category:{category.value}", 1)
        
        # Track unique errors
        await redis_client.sadd(f"{metrics_key}:fingerprints", context.fingerprint)
        
        # Track affected users
        if context.user_id:
            await redis_client.sadd(f"{metrics_key}:users", context.user_id)
        
        await redis_client.expire(metrics_key, 86400 * 7)  # 7 days
    
    async def _get_metrics(self, start_time: datetime) -> Dict[str, Any]:
        """Get aggregated metrics"""
        metrics = {
            'by_severity': defaultdict(int),
            'by_category': defaultdict(int),
            'total': 0,
            'unique_errors': set(),
            'affected_users': set()
        }
        
        # Aggregate hourly metrics
        current_time = datetime.utcnow()
        while current_time > start_time:
            hour_key = current_time.strftime('%Y%m%d%H')
            metrics_key = f"error_tracking:metrics:{hour_key}"
            
            # Get metrics for this hour
            hour_metrics = await redis_client.hgetall(metrics_key)
            
            for key, value in hour_metrics.items():
                if key.startswith('severity:'):
                    severity = key.replace('severity:', '')
                    metrics['by_severity'][severity] += int(value)
                elif key.startswith('category:'):
                    category = key.replace('category:', '')
                    metrics['by_category'][category] += int(value)
                elif key == 'total':
                    metrics['total'] += int(value)
            
            # Get unique errors and users
            fingerprints = await redis_client.smembers(f"{metrics_key}:fingerprints")
            metrics['unique_errors'].update(fingerprints)
            
            users = await redis_client.smembers(f"{metrics_key}:users")
            metrics['affected_users'].update(users)
            
            current_time -= timedelta(hours=1)
        
        # Calculate error rate (errors per hour)
        hours_elapsed = (datetime.utcnow() - start_time).total_seconds() / 3600
        metrics['error_rate'] = metrics['total'] / hours_elapsed if hours_elapsed > 0 else 0
        
        return {
            'by_severity': dict(metrics['by_severity']),
            'by_category': dict(metrics['by_category']),
            'total': metrics['total'],
            'unique_errors': len(metrics['unique_errors']),
            'affected_users': len(metrics['affected_users']),
            'error_rate': round(metrics['error_rate'], 2)
        }
    
    async def _get_recent_critical_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent critical errors"""
        # Get from recent errors in buffer
        critical_errors = []
        
        # Search in today's groups
        date_key = datetime.utcnow().strftime('%Y%m%d')
        groups_key = f"error_tracking:groups:{date_key}"
        groups = await redis_client.hgetall(groups_key)
        
        for fingerprint, data in groups.items():
            group_data = json.loads(data)
            if group_data['severity'] == ErrorSeverity.CRITICAL.value:
                critical_errors.append({
                    'fingerprint': fingerprint,
                    'error_type': group_data['error_type'],
                    'error_message': group_data['error_message'],
                    'last_seen': group_data['last_seen'],
                    'count': group_data['count']
                })
        
        # Sort by last seen
        critical_errors.sort(key=lambda x: x['last_seen'], reverse=True)
        
        return critical_errors[:limit]
    
    async def _send_alert(self, context: ErrorContext, error_id: str):
        """Send alert for critical errors"""
        alert_key = f"error_tracking:alerts:{datetime.utcnow().strftime('%Y%m%d')}"
        alert_data = {
            'error_id': error_id,
            'error_type': context.error_type,
            'error_message': context.error_message,
            'operation': context.operation,
            'user_id': context.user_id,
            'timestamp': context.timestamp.isoformat(),
            'fingerprint': context.fingerprint
        }
        
        await redis_client.lpush(alert_key, json.dumps(alert_data))
        await redis_client.expire(alert_key, 86400)  # 24 hours
        
        logger.critical(
            f"CRITICAL ERROR: {context.error_type} in {context.operation or 'unknown operation'}",
            extra={
                'error_id': error_id,
                'fingerprint': context.fingerprint,
                'user_id': context.user_id
            }
        )


# Global error tracker instance
error_tracker = ErrorTracker()


# FastAPI error handler integration
from fastapi import FastAPI
from fastapi.responses import JSONResponse


def setup_error_tracking(app: FastAPI):
    """Setup error tracking for FastAPI application"""
    
    @app.exception_handler(Exception)
    async def error_tracking_handler(request: Request, exc: Exception):
        # Track the error
        error_id = await error_tracker.track_error(
            error=exc,
            request=request,
            user_id=getattr(request.state, 'user_id', None),
            operation=f"{request.method} {request.url.path}"
        )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "error_id": error_id,
                "message": "An unexpected error occurred. Please try again later."
            }
        )
    
    @app.on_event("startup")
    async def startup_error_tracker():
        await error_tracker.start()
    
    @app.on_event("shutdown")
    async def shutdown_error_tracker():
        await error_tracker.stop()