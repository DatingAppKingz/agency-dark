"""API key audit logging service."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import uuid

from core.logger import get_logger
from core.database import get_db
from models.base import Base, BaseModel

logger = get_logger(__name__)


class AuditAction(str, Enum):
    """Types of audit actions."""
    # API Key lifecycle
    CREATE = "api_key.create"
    UPDATE = "api_key.update"
    DELETE = "api_key.delete"
    ROTATE = "api_key.rotate"
    ENABLE = "api_key.enable"
    DISABLE = "api_key.disable"
    
    # Access and usage
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    
    # Sync operations
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"
    
    # Security events
    INVALID_KEY_ATTEMPT = "security.invalid_key"
    IP_BLOCKED = "security.ip_blocked"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


class APIKeyAuditLog(BaseModel):
    """API key audit log entries."""
    __tablename__ = "api_key_audit_logs"
    
    # Relationships
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Audit details
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(Text, nullable=True)
    
    # Event data
    metadata = Column(JSON, default=dict, nullable=False)
    changes = Column(JSON, nullable=True)  # For update actions
    error_message = Column(Text, nullable=True)  # For failed actions
    
    # Request context
    request_id = Column(String(100), nullable=True)
    request_path = Column(String(500), nullable=True)
    request_method = Column(String(10), nullable=True)
    
    def __repr__(self):
        return f"<APIKeyAuditLog {self.action} at {self.created_at}>"


class APIAuditLogger:
    """Service for logging API key audit events."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        api_key_id: str,
        action: AuditAction,
        user_id: Optional[str] = None,
        agency_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        request_context: Optional[Dict[str, str]] = None
    ) -> APIKeyAuditLog:
        """
        Log an audit action for an API key.
        
        Args:
            api_key_id: API key ID
            action: Action performed
            user_id: User who performed the action
            agency_id: Agency ID
            ip_address: Client IP address
            user_agent: Client user agent
            metadata: Additional metadata
            changes: Changes made (for updates)
            error_message: Error message (for failures)
            request_context: Request context (id, path, method)
            
        Returns:
            Created audit log entry
        """
        log_entry = APIKeyAuditLog(
            api_key_id=api_key_id,
            user_id=user_id,
            agency_id=agency_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            changes=changes,
            error_message=error_message,
            request_id=request_context.get("request_id") if request_context else None,
            request_path=request_context.get("path") if request_context else None,
            request_method=request_context.get("method") if request_context else None
        )
        
        self.db.add(log_entry)
        await self.db.flush()
        
        # Log to application logger for monitoring
        logger.info(
            f"API key audit: {action}",
            extra={
                "api_key_id": api_key_id,
                "action": action,
                "user_id": user_id,
                "ip_address": ip_address,
                "metadata": metadata
            }
        )
        
        return log_entry
    
    async def get_logs(
        self,
        api_key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agency_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[APIKeyAuditLog]:
        """
        Get audit logs with filters.
        
        Args:
            api_key_id: Filter by API key
            user_id: Filter by user
            agency_id: Filter by agency
            action: Filter by action type
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            offset: Result offset
            
        Returns:
            List of audit log entries
        """
        query = select(APIKeyAuditLog)
        
        # Apply filters
        conditions = []
        if api_key_id:
            conditions.append(APIKeyAuditLog.api_key_id == api_key_id)
        if user_id:
            conditions.append(APIKeyAuditLog.user_id == user_id)
        if agency_id:
            conditions.append(APIKeyAuditLog.agency_id == agency_id)
        if action:
            conditions.append(APIKeyAuditLog.action == action)
        if start_date:
            conditions.append(APIKeyAuditLog.created_at >= start_date)
        if end_date:
            conditions.append(APIKeyAuditLog.created_at <= end_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by newest first
        query = query.order_by(desc(APIKeyAuditLog.created_at))
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_security_events(
        self,
        agency_id: str,
        hours: int = 24
    ) -> List[APIKeyAuditLog]:
        """
        Get recent security-related audit events.
        
        Args:
            agency_id: Agency ID
            hours: Hours to look back
            
        Returns:
            List of security audit events
        """
        security_actions = [
            AuditAction.ACCESS_DENIED,
            AuditAction.RATE_LIMIT_EXCEEDED,
            AuditAction.INVALID_KEY_ATTEMPT,
            AuditAction.IP_BLOCKED,
            AuditAction.SUSPICIOUS_ACTIVITY
        ]
        
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(APIKeyAuditLog).where(
            and_(
                APIKeyAuditLog.agency_id == agency_id,
                APIKeyAuditLog.action.in_(security_actions),
                APIKeyAuditLog.created_at >= start_date
            )
        ).order_by(desc(APIKeyAuditLog.created_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_activity_summary(
        self,
        api_key_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get activity summary for an API key.
        
        Args:
            api_key_id: API key ID
            days: Days to summarize
            
        Returns:
            Activity summary
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all logs for the period
        logs = await self.get_logs(
            api_key_id=api_key_id,
            start_date=start_date,
            limit=1000
        )
        
        # Summarize by action
        action_counts = {}
        error_count = 0
        unique_ips = set()
        
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
            if log.error_message:
                error_count += 1
            if log.ip_address:
                unique_ips.add(log.ip_address)
        
        # Get recent errors
        recent_errors = [
            {
                "timestamp": log.created_at.isoformat(),
                "action": log.action,
                "error": log.error_message
            }
            for log in logs[:10]
            if log.error_message
        ]
        
        return {
            "api_key_id": api_key_id,
            "period_days": days,
            "total_events": len(logs),
            "action_counts": action_counts,
            "error_count": error_count,
            "unique_ips": len(unique_ips),
            "recent_errors": recent_errors,
            "last_activity": logs[0].created_at.isoformat() if logs else None
        }


class AuditLoggerMiddleware:
    """Middleware to automatically log API key actions."""
    
    @staticmethod
    async def log_api_access(
        request,
        api_key_id: str,
        granted: bool,
        reason: Optional[str] = None
    ):
        """Log API access attempt."""
        from fastapi import Request
        
        async for db in get_db():
            try:
                logger_service = APIAuditLogger(db)
                
                # Get request details
                client_ip = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")
                
                # Determine action
                action = AuditAction.ACCESS_GRANTED if granted else AuditAction.ACCESS_DENIED
                
                # Log the action
                await logger_service.log_action(
                    api_key_id=api_key_id,
                    action=action,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    metadata={
                        "reason": reason,
                        "path": str(request.url.path),
                        "method": request.method
                    },
                    request_context={
                        "request_id": getattr(request.state, "request_id", None),
                        "path": str(request.url.path),
                        "method": request.method
                    }
                )
                
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to log API access: {e}")
                await db.rollback()
            finally:
                await db.close()
                break