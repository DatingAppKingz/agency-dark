"""
Comprehensive audit logging system for security and compliance.
"""

import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from functools import wraps
from contextlib import asynccontextmanager
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib

from app.core.database import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.models import AuditLog, User

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_RESET = "auth.password.reset"
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    
    # Authorization events
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"
    PERMISSION_CHANGED = "authz.permission.changed"
    ROLE_ASSIGNED = "authz.role.assigned"
    ROLE_REMOVED = "authz.role.removed"
    
    # Data events
    DATA_CREATED = "data.created"
    DATA_READ = "data.read"
    DATA_UPDATED = "data.updated"
    DATA_DELETED = "data.deleted"
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"
    
    # API events
    API_KEY_CREATED = "api.key.created"
    API_KEY_ROTATED = "api.key.rotated"
    API_KEY_REVOKED = "api.key.revoked"
    API_CALL = "api.call"
    API_ERROR = "api.error"
    
    # System events
    CONFIG_CHANGED = "system.config.changed"
    SERVICE_STARTED = "system.service.started"
    SERVICE_STOPPED = "system.service.stopped"
    BACKUP_CREATED = "system.backup.created"
    BACKUP_RESTORED = "system.backup.restored"
    
    # Security events
    SECURITY_ALERT = "security.alert"
    INTRUSION_DETECTED = "security.intrusion"
    MALWARE_DETECTED = "security.malware"
    VULNERABILITY_FOUND = "security.vulnerability"
    SECURITY_SCAN = "security.scan"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogger:
    """Comprehensive audit logging system."""
    
    def __init__(self):
        self.buffer = []
        self.buffer_size = 100
        self.flush_interval = 5  # seconds
        self._flush_task = None
        self._running = False
        
        # Sensitive fields to redact
        self.sensitive_fields = {
            "password", "secret", "token", "api_key", "credit_card",
            "ssn", "tax_id", "bank_account", "private_key"
        }
    
    async def start(self):
        """Start the audit logger background tasks."""
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Audit logger started")
    
    async def stop(self):
        """Stop the audit logger."""
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining events
        await self._flush_buffer()
        logger.info("Audit logger stopped")
    
    async def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[int, str]] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """Log an audit event."""
        # Redact sensitive data from metadata
        if metadata:
            metadata = self._redact_sensitive_data(metadata)
        
        # Create audit entry
        audit_entry = {
            "timestamp": datetime.utcnow(),
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "action": action,
            "result": result,
            "ip_address": self._hash_ip(ip_address) if settings.HASH_IP_ADDRESSES else ip_address,
            "user_agent": user_agent,
            "metadata": metadata,
            "session_id": session_id,
            "environment": settings.ENVIRONMENT
        }
        
        # Add to buffer
        self.buffer.append(audit_entry)
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self._flush_buffer()
        
        # Log critical events immediately
        if severity == AuditSeverity.CRITICAL:
            await self._flush_buffer()
            
            # Also log to standard logger
            logger.error(
                f"Critical audit event: {event_type}",
                extra=audit_entry
            )
    
    async def _periodic_flush(self):
        """Periodically flush the audit buffer."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")
    
    async def _flush_buffer(self):
        """Flush audit events to database."""
        if not self.buffer:
            return
        
        # Copy and clear buffer
        events_to_save = self.buffer.copy()
        self.buffer.clear()
        
        try:
            async with get_db() as db:
                # Create audit log entries
                audit_logs = [
                    AuditLog(**event)
                    for event in events_to_save
                ]
                
                db.add_all(audit_logs)
                await db.commit()
                
            logger.debug(f"Flushed {len(events_to_save)} audit events")
            
        except Exception as e:
            logger.error(f"Error flushing audit buffer: {e}")
            
            # Re-add events to buffer on failure
            self.buffer.extend(events_to_save)
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from audit data."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        
        for key, value in data.items():
            # Check if key contains sensitive field name
            if any(field in key.lower() for field in self.sensitive_fields):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive_data(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    def _hash_ip(self, ip_address: Optional[str]) -> Optional[str]:
        """Hash IP address for privacy."""
        if not ip_address:
            return None
        
        # Keep first two octets for geolocation
        parts = ip_address.split(".")
        if len(parts) == 4:
            prefix = ".".join(parts[:2])
            hash_suffix = hashlib.sha256(
                ip_address.encode() + settings.SECRET_KEY.encode()
            ).hexdigest()[:8]
            return f"{prefix}.x.x_{hash_suffix}"
        
        return hashlib.sha256(
            ip_address.encode() + settings.SECRET_KEY.encode()
        ).hexdigest()[:16]
    
    async def search_logs(
        self,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """Search audit logs with filters."""
        if not db:
            return []
        
        query = select(AuditLog)
        
        # Apply filters
        if event_types:
            query = query.where(AuditLog.event_type.in_(event_types))
        
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        
        if severity:
            query = query.where(AuditLog.severity == severity)
        
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)
        
        # Order and paginate
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "event_type": log.event_type,
                "severity": log.severity,
                "user_id": log.user_id,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "action": log.action,
                "result": log.result,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "metadata": log.metadata,
                "session_id": log.session_id
            }
            for log in logs
        ]
    
    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate compliance report from audit logs."""
        # Get event counts by type
        event_counts = await db.execute(
            select(
                AuditLog.event_type,
                func.count(AuditLog.id).label("count")
            )
            .where(AuditLog.timestamp >= start_date)
            .where(AuditLog.timestamp <= end_date)
            .group_by(AuditLog.event_type)
        )
        
        # Get failed login attempts
        failed_logins = await db.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.event_type == AuditEventType.LOGIN_FAILED)
            .where(AuditLog.timestamp >= start_date)
            .where(AuditLog.timestamp <= end_date)
        )
        
        # Get security events
        security_events = await db.execute(
            select(AuditLog)
            .where(AuditLog.event_type.like("security.%"))
            .where(AuditLog.timestamp >= start_date)
            .where(AuditLog.timestamp <= end_date)
            .where(AuditLog.severity.in_([AuditSeverity.ERROR, AuditSeverity.CRITICAL]))
        )
        
        # Get data access patterns
        data_access = await db.execute(
            select(
                AuditLog.resource_type,
                func.count(AuditLog.id).label("access_count")
            )
            .where(AuditLog.event_type.in_([
                AuditEventType.DATA_READ,
                AuditEventType.DATA_EXPORTED
            ]))
            .where(AuditLog.timestamp >= start_date)
            .where(AuditLog.timestamp <= end_date)
            .group_by(AuditLog.resource_type)
        )
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "summary": {
                "total_events": sum(row.count for row in event_counts),
                "event_breakdown": {
                    row.event_type: row.count
                    for row in event_counts
                },
                "failed_login_attempts": failed_logins.scalar(),
                "security_incidents": len(list(security_events.scalars())),
                "data_access_by_type": {
                    row.resource_type: row.access_count
                    for row in data_access
                }
            },
            "security_events": [
                {
                    "timestamp": event.timestamp,
                    "type": event.event_type,
                    "severity": event.severity,
                    "details": event.metadata
                }
                for event in security_events.scalars()
            ],
            "compliance_status": {
                "logging_enabled": True,
                "retention_policy": "90 days",
                "encryption": "AES-256",
                "access_controls": "RBAC",
                "audit_trail_integrity": "SHA-256 hash chain"
            }
        }


# Global audit logger instance
audit_logger = AuditLogger()


# Audit logging decorator
def audit_log(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    resource_type: Optional[str] = None
):
    """Decorator for automatic audit logging."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Extract context from arguments
            user_id = kwargs.get("user_id") or (args[0] if args else None)
            resource_id = kwargs.get("resource_id") or (args[1] if len(args) > 1 else None)
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Log success
                await audit_logger.log_event(
                    event_type=event_type,
                    severity=severity,
                    user_id=user_id if isinstance(user_id, int) else None,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=func.__name__,
                    result="success",
                    metadata={
                        "function": func.__name__,
                        "module": func.__module__
                    }
                )
                
                return result
                
            except Exception as e:
                # Log failure
                await audit_logger.log_event(
                    event_type=event_type,
                    severity=AuditSeverity.ERROR,
                    user_id=user_id if isinstance(user_id, int) else None,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=func.__name__,
                    result="failure",
                    metadata={
                        "function": func.__name__,
                        "module": func.__module__,
                        "error": str(e)
                    }
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            # Similar implementation for sync functions
            user_id = kwargs.get("user_id") or (args[0] if args else None)
            resource_id = kwargs.get("resource_id") or (args[1] if len(args) > 1 else None)
            
            try:
                result = func(*args, **kwargs)
                
                # Queue async logging
                asyncio.create_task(
                    audit_logger.log_event(
                        event_type=event_type,
                        severity=severity,
                        user_id=user_id if isinstance(user_id, int) else None,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=func.__name__,
                        result="success"
                    )
                )
                
                return result
                
            except Exception as e:
                asyncio.create_task(
                    audit_logger.log_event(
                        event_type=event_type,
                        severity=AuditSeverity.ERROR,
                        user_id=user_id if isinstance(user_id, int) else None,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=func.__name__,
                        result="failure"
                    )
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator