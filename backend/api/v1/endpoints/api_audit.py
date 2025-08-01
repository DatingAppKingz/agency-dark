"""API key audit log endpoints."""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.security import get_current_active_user
from core.rbac import check_permission
from models.user import User
from services.api_audit_logger import APIAuditLogger, AuditAction
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/api-keys/{api_key_id}/audit")


class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: int
    api_key_id: str
    user_id: Optional[str]
    agency_id: str
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: dict
    changes: Optional[dict]
    error_message: Optional[str]
    request_id: Optional[str]
    request_path: Optional[str]
    request_method: Optional[str]
    created_at: str


class AuditSummaryResponse(BaseModel):
    """Audit activity summary."""
    api_key_id: str
    period_days: int
    total_events: int
    action_counts: dict
    error_count: int
    unique_ips: int
    recent_errors: List[dict]
    last_activity: Optional[str]


class SecurityEventsResponse(BaseModel):
    """Security events response."""
    events: List[AuditLogResponse]
    total_count: int
    critical_count: int


@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    api_key_id: str,
    action: Optional[AuditAction] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs for an API key.
    
    Requires API key read permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "read")
    
    # Verify API key ownership
    from services.api_key_service import APIKeyService
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this API key"
        )
    
    # Get audit logs
    audit_logger = APIAuditLogger(db)
    logs = await audit_logger.get_logs(
        api_key_id=api_key_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return [
        AuditLogResponse(
            id=log.id,
            api_key_id=str(log.api_key_id),
            user_id=str(log.user_id) if log.user_id else None,
            agency_id=str(log.agency_id),
            action=log.action,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            metadata=log.metadata or {},
            changes=log.changes,
            error_message=log.error_message,
            request_id=log.request_id,
            request_path=log.request_path,
            request_method=log.request_method,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    api_key_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit activity summary for an API key.
    
    Requires API key read permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "read")
    
    # Verify API key ownership
    from services.api_key_service import APIKeyService
    api_key_service = APIKeyService(db)
    api_key = await api_key_service.get_by_id(api_key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this API key"
        )
    
    # Get summary
    audit_logger = APIAuditLogger(db)
    summary = await audit_logger.get_activity_summary(api_key_id, days)
    
    return AuditSummaryResponse(**summary)


@router.get("/security-events", response_model=SecurityEventsResponse)
async def get_security_events(
    api_key_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent security events for an API key.
    
    Requires API key read permission.
    """
    # Check permission
    check_permission(current_user, "api_keys", "read")
    
    # Get security events for the agency
    audit_logger = APIAuditLogger(db)
    events = await audit_logger.get_security_events(
        agency_id=str(current_user.agency_id),
        hours=hours
    )
    
    # Filter for specific API key
    api_key_events = [e for e in events if str(e.api_key_id) == api_key_id]
    
    # Count critical events
    critical_actions = [
        AuditAction.INVALID_KEY_ATTEMPT,
        AuditAction.IP_BLOCKED,
        AuditAction.SUSPICIOUS_ACTIVITY
    ]
    critical_count = sum(1 for e in api_key_events if e.action in critical_actions)
    
    return SecurityEventsResponse(
        events=[
            AuditLogResponse(
                id=log.id,
                api_key_id=str(log.api_key_id),
                user_id=str(log.user_id) if log.user_id else None,
                agency_id=str(log.agency_id),
                action=log.action,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                metadata=log.metadata or {},
                changes=log.changes,
                error_message=log.error_message,
                request_id=log.request_id,
                request_path=log.request_path,
                request_method=log.request_method,
                created_at=log.created_at.isoformat()
            )
            for log in api_key_events
        ],
        total_count=len(api_key_events),
        critical_count=critical_count
    )