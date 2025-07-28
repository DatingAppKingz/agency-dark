"""
Audit logging for security and compliance
"""
import json
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
import asyncio
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from core.database import Base
from core.logging import logger
from core.domain.models import User


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password.change"
    PASSWORD_RESET = "auth.password.reset"
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    
    # Authorization events
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"
    PERMISSION_CHANGED = "authz.permission.changed"
    ROLE_CHANGED = "authz.role.changed"
    
    # Data events
    DATA_CREATE = "data.create"
    DATA_READ = "data.read"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    
    # API events
    API_KEY_CREATED = "api.key.created"
    API_KEY_REVOKED = "api.key.revoked"
    API_KEY_USED = "api.key.used"
    WEBHOOK_CREATED = "webhook.created"
    WEBHOOK_UPDATED = "webhook.updated"
    WEBHOOK_DELETED = "webhook.deleted"
    
    # Security events
    SECURITY_ALERT = "security.alert"
    SUSPICIOUS_ACTIVITY = "security.suspicious"
    IP_BLOCKED = "security.ip.blocked"
    RATE_LIMIT_EXCEEDED = "security.rate_limit"
    
    # Admin events
    ADMIN_ACTION = "admin.action"
    CONFIG_CHANGED = "admin.config.changed"
    USER_CREATED = "admin.user.created"
    USER_UPDATED = "admin.user.updated"
    USER_DELETED = "admin.user.deleted"
    
    # Financial events
    PAYMENT_PROCESSED = "financial.payment.processed"
    REFUND_ISSUED = "financial.refund.issued"
    SUBSCRIPTION_CHANGED = "financial.subscription.changed"


class AuditLog(Base):
    """Audit log database model"""
    __tablename__ = "audit_logs"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Event details
    event_type = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    description = Column(String)
    severity = Column(String, default="info")  # info, warning, error, critical
    
    # Actor information
    user_id = Column(PG_UUID(as_uuid=True), nullable=True)
    user_email = Column(String)
    user_role = Column(String)
    agency_id = Column(PG_UUID(as_uuid=True), nullable=True)
    
    # Request context
    ip_address = Column(String)
    user_agent = Column(String)
    request_id = Column(String)
    session_id = Column(String)
    
    # Resource information
    resource_type = Column(String)  # e.g., "user", "transaction", "message"
    resource_id = Column(String)
    resource_name = Column(String)
    
    # Additional data
    metadata = Column(JSON, default={})
    old_values = Column(JSON)  # For update events
    new_values = Column(JSON)  # For update events
    
    # Compliance fields
    data_classification = Column(String)  # e.g., "pii", "financial", "public"
    retention_days = Column(Integer, default=2555)  # 7 years default
    is_archived = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_severity', 'severity'),
    )


class AuditLogger:
    """Service for logging audit events"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._buffer: List[AuditLog] = []
        self._buffer_size = 100
        self._flush_interval = 5.0  # seconds
        self._last_flush = time.time()
    
    async def log_event(
        self,
        event_type: AuditEventType,
        event_name: str,
        description: Optional[str] = None,
        user: Optional[User] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        data_classification: Optional[str] = None
    ):
        """Log an audit event"""
        audit_log = AuditLog(
            event_type=event_type.value if isinstance(event_type, AuditEventType) else event_type,
            event_name=event_name,
            description=description,
            severity=severity,
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_role=user.role.value if user and hasattr(user.role, 'value') else str(user.role) if user else None,
            agency_id=user.agency_id if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            resource_name=resource_name,
            metadata=metadata or {},
            old_values=old_values,
            new_values=new_values,
            data_classification=data_classification,
            timestamp=datetime.utcnow()
        )
        
        # Add to buffer
        self._buffer.append(audit_log)
        
        # Flush if buffer is full or time has elapsed
        if len(self._buffer) >= self._buffer_size or (time.time() - self._last_flush) > self._flush_interval:
            await self.flush()
    
    async def flush(self):
        """Flush buffered audit logs to database"""
        if not self._buffer:
            return
        
        try:
            self.db.add_all(self._buffer)
            await self.db.commit()
            logger.info(f"Flushed {len(self._buffer)} audit logs to database")
            self._buffer.clear()
            self._last_flush = time.time()
        except Exception as e:
            logger.error(f"Failed to flush audit logs: {e}")
            await self.db.rollback()
    
    async def log_login(
        self,
        user: User,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: Optional[str] = None
    ):
        """Log login attempt"""
        await self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED,
            event_name=f"User login {'succeeded' if success else 'failed'}",
            description=failure_reason if not success else None,
            user=user if success else None,
            metadata={
                "email": user.email if user else None,
                "failure_reason": failure_reason
            },
            severity="info" if success else "warning",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    async def log_data_access(
        self,
        user: User,
        action: str,  # create, read, update, delete
        resource_type: str,
        resource_id: str,
        resource_name: Optional[str] = None,
        data_classification: str = "internal",
        ip_address: Optional[str] = None
    ):
        """Log data access event"""
        event_type_map = {
            "create": AuditEventType.DATA_CREATE,
            "read": AuditEventType.DATA_READ,
            "update": AuditEventType.DATA_UPDATE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT
        }
        
        await self.log_event(
            event_type=event_type_map.get(action, AuditEventType.DATA_READ),
            event_name=f"{action.capitalize()} {resource_type}",
            user=user,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            data_classification=data_classification,
            ip_address=ip_address
        )
    
    async def log_api_key_event(
        self,
        user: User,
        action: str,  # created, revoked, used
        api_key_id: str,
        api_key_name: str,
        ip_address: Optional[str] = None
    ):
        """Log API key event"""
        event_type_map = {
            "created": AuditEventType.API_KEY_CREATED,
            "revoked": AuditEventType.API_KEY_REVOKED,
            "used": AuditEventType.API_KEY_USED
        }
        
        await self.log_event(
            event_type=event_type_map.get(action, AuditEventType.API_KEY_USED),
            event_name=f"API key {action}",
            user=user,
            resource_type="api_key",
            resource_id=api_key_id,
            resource_name=api_key_name,
            ip_address=ip_address
        )
    
    async def log_security_event(
        self,
        event_name: str,
        description: str,
        severity: str = "warning",
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log security event"""
        await self.log_event(
            event_type=AuditEventType.SECURITY_ALERT,
            event_name=event_name,
            description=description,
            severity=severity,
            user=user,
            ip_address=ip_address,
            metadata=metadata
        )
    
    async def query_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Query audit logs with filters"""
        query = select(AuditLog)
        
        conditions = []
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if event_type:
            conditions.append(AuditLog.event_type == event_type)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if severity:
            conditions.append(AuditLog.severity == severity)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def archive_old_logs(self, days: int = 2555):
        """Archive logs older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            text("""
                UPDATE audit_logs 
                SET is_archived = true 
                WHERE timestamp < :cutoff_date AND is_archived = false
            """),
            {"cutoff_date": cutoff_date}
        )
        
        await self.db.commit()
        logger.info(f"Archived {result.rowcount} audit logs older than {days} days")


# Audit logging decorator
def audit_log(
    event_type: AuditEventType,
    resource_type: Optional[str] = None,
    data_classification: str = "internal"
):
    """Decorator to automatically log function calls"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract context from arguments
            # This is a simplified example - adjust based on your needs
            from fastapi import Request
            
            request = None
            user = None
            
            # Find request and user in args/kwargs
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, 'email'):  # Assuming User object
                    user = arg
            
            # Get user from kwargs if not in args
            user = user or kwargs.get('current_user') or kwargs.get('user')
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Log the event
            if request and hasattr(request.state, 'db'):
                audit_logger = AuditLogger(request.state.db)
                await audit_logger.log_event(
                    event_type=event_type,
                    event_name=f"{func.__name__} called",
                    user=user,
                    resource_type=resource_type,
                    data_classification=data_classification,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get('user-agent'),
                    metadata={
                        "function": func.__name__,
                        "module": func.__module__
                    }
                )
                await audit_logger.flush()
            
            return result
        return wrapper
    return decorator


# Example usage
"""
@audit_log(AuditEventType.DATA_UPDATE, resource_type="user", data_classification="pii")
async def update_user_profile(user_id: str, data: dict, current_user: User):
    # Function implementation
    pass
"""