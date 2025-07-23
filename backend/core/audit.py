"""
Security audit logging system.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import json
from enum import Enum

from backend.core.database import Base
from backend.core.redis import redis_client
import logging

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_RESET = "password_reset"
    
    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    ROLE_CHANGED = "role_changed"
    
    # Data access
    DATA_READ = "data_read"
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_EXPORTED = "data_exported"
    
    # Security events
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    API_KEY_USED = "api_key_used"
    
    # Financial events
    PAYMENT_PROCESSED = "payment_processed"
    PAYOUT_INITIATED = "payout_initiated"
    COMMISSION_CALCULATED = "commission_calculated"
    
    # Integration events
    WEBHOOK_RECEIVED = "webhook_received"
    API_CALL_MADE = "api_call_made"
    SYNC_PERFORMED = "sync_performed"


class AuditLog(Base):
    """Audit log model for security tracking."""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)
    event_category = Column(String(50), nullable=False)
    description = Column(Text)
    
    # Actor information
    user_id = Column(UUID(as_uuid=True), index=True)
    username = Column(String(100))
    user_role = Column(String(50))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Target information
    target_type = Column(String(100))  # e.g., "user", "model", "fan"
    target_id = Column(String(100))
    target_name = Column(String(200))
    
    # Additional context
    metadata = Column(JSON)
    
    # Tracking
    agency_id = Column(UUID(as_uuid=True), index=True)
    session_id = Column(String(100))
    request_id = Column(String(100))
    
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_user_agency', 'user_id', 'agency_id'),
    )


class AuditLogger:
    """Service for logging audit events."""
    
    def __init__(self):
        self.redis_buffer_key = "audit:buffer"
        self.redis_buffer_size = 100
        self.redis_flush_interval = 300  # 5 minutes
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agency_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ):
        """Log an audit event."""
        try:
            # Determine event category
            category = self._get_event_category(event_type)
            
            # Create audit log entry
            audit_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type.value,
                "event_category": category,
                "description": description or self._get_event_description(event_type),
                "user_id": str(user_id) if user_id else None,
                "username": username,
                "user_role": user_role,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "target_type": target_type,
                "target_id": target_id,
                "target_name": target_name,
                "metadata": metadata,
                "agency_id": str(agency_id) if agency_id else None,
                "session_id": session_id,
                "request_id": request_id
            }
            
            # Buffer in Redis for batch processing
            await self._buffer_event(audit_entry)
            
            # Log critical events immediately
            if self._is_critical_event(event_type):
                await self._persist_event(audit_entry, db)
                logger.warning(f"Critical audit event: {event_type.value} - {description}")
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")
    
    async def _buffer_event(self, event: Dict[str, Any]):
        """Buffer event in Redis for batch processing."""
        await redis_client.lpush(self.redis_buffer_key, json.dumps(event))
        
        # Check if we should flush
        buffer_size = await redis_client.llen(self.redis_buffer_key)
        if buffer_size >= self.redis_buffer_size:
            await self.flush_buffer()
    
    async def flush_buffer(self, db: Optional[AsyncSession] = None):
        """Flush buffered events to database."""
        try:
            # Get all buffered events
            events = []
            while True:
                event_json = await redis_client.rpop(self.redis_buffer_key)
                if not event_json:
                    break
                events.append(json.loads(event_json))
            
            if events and db:
                # Batch insert
                for event in events:
                    await self._persist_event(event, db)
                
                logger.info(f"Flushed {len(events)} audit events to database")
            
        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {str(e)}")
    
    async def _persist_event(self, event: Dict[str, Any], db: Optional[AsyncSession]):
        """Persist event to database."""
        if not db:
            return
        
        audit_log = AuditLog(
            id=uuid.UUID(event["id"]),
            timestamp=datetime.fromisoformat(event["timestamp"]),
            event_type=event["event_type"],
            event_category=event["event_category"],
            description=event["description"],
            user_id=uuid.UUID(event["user_id"]) if event["user_id"] else None,
            username=event["username"],
            user_role=event["user_role"],
            ip_address=event["ip_address"],
            user_agent=event["user_agent"],
            target_type=event["target_type"],
            target_id=event["target_id"],
            target_name=event["target_name"],
            metadata=event["metadata"],
            agency_id=uuid.UUID(event["agency_id"]) if event["agency_id"] else None,
            session_id=event["session_id"],
            request_id=event["request_id"]
        )
        
        db.add(audit_log)
        await db.commit()
    
    def _get_event_category(self, event_type: AuditEventType) -> str:
        """Get category for event type."""
        if event_type.value.startswith("login") or event_type.value.startswith("logout"):
            return "authentication"
        elif event_type.value.startswith("user_"):
            return "user_management"
        elif event_type.value.startswith("data_"):
            return "data_access"
        elif event_type.value.startswith("payment") or event_type.value.startswith("payout"):
            return "financial"
        elif event_type in [AuditEventType.PERMISSION_DENIED, AuditEventType.RATE_LIMIT_EXCEEDED, 
                           AuditEventType.SUSPICIOUS_ACTIVITY]:
            return "security"
        else:
            return "system"
    
    def _get_event_description(self, event_type: AuditEventType) -> str:
        """Get default description for event type."""
        descriptions = {
            AuditEventType.LOGIN_SUCCESS: "User successfully logged in",
            AuditEventType.LOGIN_FAILED: "Failed login attempt",
            AuditEventType.LOGOUT: "User logged out",
            AuditEventType.TOKEN_REFRESH: "Authentication token refreshed",
            AuditEventType.PASSWORD_RESET: "Password reset requested",
            AuditEventType.USER_CREATED: "New user account created",
            AuditEventType.USER_UPDATED: "User account updated",
            AuditEventType.USER_DELETED: "User account deleted",
            AuditEventType.ROLE_CHANGED: "User role changed",
            AuditEventType.PERMISSION_DENIED: "Access denied due to insufficient permissions",
            AuditEventType.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
            AuditEventType.SUSPICIOUS_ACTIVITY: "Suspicious activity detected",
        }
        return descriptions.get(event_type, event_type.value.replace("_", " ").title())
    
    def _is_critical_event(self, event_type: AuditEventType) -> bool:
        """Check if event is critical and should be logged immediately."""
        critical_events = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.USER_DELETED,
            AuditEventType.ROLE_CHANGED,
            AuditEventType.PAYMENT_PROCESSED,
            AuditEventType.PAYOUT_INITIATED,
        ]
        return event_type in critical_events
    
    async def query_logs(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """Query audit logs with filters."""
        query = select(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()


# Global audit logger instance
audit_logger = AuditLogger()