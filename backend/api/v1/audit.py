"""
Audit log management endpoints.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import csv
import io
import json

from core.database import get_db
from core.security_v2 import get_current_user
from core.audit.audit_service import audit_service
from models.audit_log import (
    AuditLog, AuditAction, AuditSeverity, 
    AuditLogRetentionPolicy, AuditLogExport, AuditLogAlert
)
from models.user import User, UserRole
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


# Pydantic models

class AuditLogResponse(BaseModel):
    """Audit log response model."""
    id: str
    timestamp: datetime
    user_id: Optional[str]
    user_email: Optional[str]
    agency_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    description: Optional[str]
    severity: str
    risk_score: Optional[int]
    ip_address: Optional[str]
    duration_ms: Optional[int]
    flagged: bool
    
    class Config:
        from_attributes = True


class AuditLogDetailResponse(AuditLogResponse):
    """Detailed audit log response with full data."""
    changes: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    user_agent: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]
    correlation_id: Optional[str]
    impersonator_id: Optional[str]
    api_key_id: Optional[str]


class AuditSearchRequest(BaseModel):
    """Request for searching audit logs."""
    start_date: Optional[datetime] = Field(None, description="Start date for search")
    end_date: Optional[datetime] = Field(None, description="End date for search")
    actions: Optional[List[str]] = Field(None, description="Filter by actions")
    user_ids: Optional[List[str]] = Field(None, description="Filter by user IDs")
    resource_types: Optional[List[str]] = Field(None, description="Filter by resource types")
    resource_ids: Optional[List[str]] = Field(None, description="Filter by resource IDs")
    severities: Optional[List[str]] = Field(None, description="Filter by severities")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")
    text_search: Optional[str] = Field(None, description="Full text search")
    flagged_only: bool = Field(False, description="Only show flagged entries")
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AuditSearchResponse(BaseModel):
    """Response for audit log search."""
    logs: List[AuditLogResponse]
    total_count: int
    limit: int
    offset: int


class UserActivitySummaryResponse(BaseModel):
    """User activity summary response."""
    user_id: str
    period_days: int
    total_actions: int
    action_breakdown: Dict[str, int]
    daily_activity: List[Dict[str, Any]]
    high_risk_events: int


class RetentionPolicyRequest(BaseModel):
    """Request to create/update retention policy."""
    name: str
    description: Optional[str]
    action_pattern: Optional[str]
    resource_type_pattern: Optional[str]
    severity: Optional[str]
    retention_days: int = Field(..., ge=1, le=3650)  # 1 day to 10 years
    delete_after_export: bool = False
    compliance_requirement: Optional[str]
    priority: int = Field(0, ge=0, le=100)


class RetentionPolicyResponse(BaseModel):
    """Retention policy response."""
    id: str
    name: str
    description: Optional[str]
    retention_days: int
    is_active: bool
    priority: int
    compliance_requirement: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditAlertRequest(BaseModel):
    """Request to create/update audit alert."""
    name: str
    description: Optional[str]
    action_pattern: Optional[str]
    threshold_count: Optional[int]
    threshold_minutes: Optional[int]
    severity_threshold: Optional[str]
    risk_score_threshold: Optional[int]
    notify_emails: Optional[List[str]]
    notify_webhook: Optional[str]
    notify_in_app: bool = True


class AuditAlertResponse(BaseModel):
    """Audit alert response."""
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    last_triggered: Optional[datetime]
    trigger_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Endpoints

@router.post("/search", response_model=AuditSearchResponse)
async def search_audit_logs(
    request: AuditSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search audit logs with filters.
    
    Permissions:
    - Super Admin: Can search all logs
    - Others: Can only search their own logs
    """
    # Convert string enums to actual enums
    actions = None
    if request.actions:
        try:
            actions = [AuditAction(action) for action in request.actions]
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {e}"
            )
    
    severities = None
    if request.severities:
        try:
            severities = [AuditSeverity(sev) for sev in request.severities]
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {e}"
            )
    
    # Search logs
    logs, total_count = await audit_service.search(
        db=db,
        user=current_user,
        start_date=request.start_date,
        end_date=request.end_date,
        actions=actions,
        user_ids=request.user_ids,
        resource_types=request.resource_types,
        resource_ids=request.resource_ids,
        severities=severities,
        ip_address=request.ip_address,
        text_search=request.text_search,
        flagged_only=request.flagged_only,
        limit=request.limit,
        offset=request.offset
    )
    
    # Convert to response models
    log_responses = []
    for log in logs:
        # Load user relationship for email
        await db.refresh(log, ["user"])
        
        log_responses.append(AuditLogResponse(
            id=str(log.id),
            timestamp=log.timestamp,
            user_id=str(log.user_id) if log.user_id else None,
            user_email=log.user.email if log.user else None,
            agency_id=str(log.agency_id) if log.agency_id else None,
            action=log.action.value,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            resource_name=log.resource_name,
            description=log.description,
            severity=log.severity.value,
            risk_score=log.risk_score,
            ip_address=log.ip_address,
            duration_ms=log.duration_ms,
            flagged=log.flagged
        ))
    
    return AuditSearchResponse(
        logs=log_responses,
        total_count=total_count,
        limit=request.limit,
        offset=request.offset
    )


@router.get("/{audit_id}", response_model=AuditLogDetailResponse)
async def get_audit_log(
    audit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed audit log entry."""
    # Get audit log
    from sqlalchemy import select
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == audit_id)
    )
    audit_log = result.scalar_one_or_none()
    
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN and str(audit_log.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this audit log"
        )
    
    # Load relationships
    await db.refresh(audit_log, ["user"])
    
    return AuditLogDetailResponse(
        id=str(audit_log.id),
        timestamp=audit_log.timestamp,
        user_id=str(audit_log.user_id) if audit_log.user_id else None,
        user_email=audit_log.user.email if audit_log.user else None,
        agency_id=str(audit_log.agency_id) if audit_log.agency_id else None,
        action=audit_log.action.value,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        resource_name=audit_log.resource_name,
        description=audit_log.description,
        changes=audit_log.changes,
        metadata=audit_log.metadata,
        severity=audit_log.severity.value,
        risk_score=audit_log.risk_score,
        ip_address=audit_log.ip_address,
        user_agent=audit_log.user_agent,
        session_id=audit_log.session_id,
        request_id=audit_log.request_id,
        correlation_id=audit_log.correlation_id,
        duration_ms=audit_log.duration_ms,
        flagged=audit_log.flagged,
        impersonator_id=str(audit_log.impersonator_id) if audit_log.impersonator_id else None,
        api_key_id=str(audit_log.api_key_id) if audit_log.api_key_id else None
    )


@router.post("/{audit_id}/flag", status_code=status.HTTP_204_NO_CONTENT)
async def flag_audit_log(
    audit_id: str,
    reason: str = Body(..., description="Reason for flagging"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Flag an audit log entry for review."""
    # Only admins can flag
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can flag audit logs"
        )
    
    # Get audit log
    from sqlalchemy import select
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == audit_id)
    )
    audit_log = result.scalar_one_or_none()
    
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    # Flag it
    audit_log.flagged = True
    if not audit_log.metadata:
        audit_log.metadata = {}
    audit_log.metadata["flag_reason"] = reason
    audit_log.metadata["flagged_by"] = str(current_user.id)
    audit_log.metadata["flagged_at"] = datetime.utcnow().isoformat()
    
    await db.commit()
    
    # Log the flagging action
    await audit_service.log(
        db=db,
        action=AuditAction.SUSPICIOUS_ACTIVITY,
        user=current_user,
        resource_type="audit_log",
        resource_id=audit_id,
        description=f"Flagged audit log: {reason}",
        severity=AuditSeverity.WARNING
    )


@router.get("/users/{user_id}/activity", response_model=UserActivitySummaryResponse)
async def get_user_activity_summary(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get activity summary for a user."""
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN and str(user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other users' activity"
        )
    
    summary = await audit_service.get_user_activity_summary(
        db=db,
        user_id=user_id,
        days=days
    )
    
    return UserActivitySummaryResponse(**summary)


@router.post("/export")
async def export_audit_logs(
    request: AuditSearchRequest,
    format: str = Query("csv", description="Export format (csv, json)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export audit logs in various formats."""
    # Only admins can export
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can export audit logs"
        )
    
    # Get logs (with higher limit for export)
    request.limit = min(request.limit * 10, 10000)  # Max 10k records
    
    # Convert string enums
    actions = None
    if request.actions:
        actions = [AuditAction(action) for action in request.actions]
    
    severities = None
    if request.severities:
        severities = [AuditSeverity(sev) for sev in request.severities]
    
    logs, _ = await audit_service.search(
        db=db,
        user=current_user,
        start_date=request.start_date,
        end_date=request.end_date,
        actions=actions,
        user_ids=request.user_ids,
        resource_types=request.resource_types,
        resource_ids=request.resource_ids,
        severities=severities,
        ip_address=request.ip_address,
        text_search=request.text_search,
        flagged_only=request.flagged_only,
        limit=request.limit,
        offset=request.offset
    )
    
    # Create export record
    export_record = AuditLogExport(
        start_date=request.start_date or datetime.utcnow() - timedelta(days=30),
        end_date=request.end_date or datetime.utcnow(),
        exported_by_id=current_user.id,
        filters={
            "actions": request.actions,
            "user_ids": request.user_ids,
            "severities": request.severities,
            "text_search": request.text_search
        },
        record_count=len(logs),
        purpose=f"Manual export by {current_user.email}",
        compliance_tags=["manual_export"]
    )
    db.add(export_record)
    await db.commit()
    
    # Export based on format
    if format == "json":
        # JSON export
        data = [log.to_dict() for log in logs]
        content = json.dumps(data, indent=2, default=str)
        
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
    
    else:
        # CSV export (default)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "timestamp", "user_email", "action", "resource_type",
                "resource_id", "description", "severity", "risk_score",
                "ip_address", "duration_ms"
            ]
        )
        writer.writeheader()
        
        for log in logs:
            await db.refresh(log, ["user"])
            writer.writerow({
                "timestamp": log.timestamp.isoformat(),
                "user_email": log.user.email if log.user else "system",
                "action": log.action.value,
                "resource_type": log.resource_type or "",
                "resource_id": log.resource_id or "",
                "description": log.description or "",
                "severity": log.severity.value,
                "risk_score": log.risk_score or 0,
                "ip_address": log.ip_address or "",
                "duration_ms": log.duration_ms or 0
            })
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


# Admin-only endpoints

@router.get("/retention-policies", response_model=List[RetentionPolicyResponse], dependencies=[Depends(get_current_user)])
async def list_retention_policies(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List audit log retention policies."""
    from sqlalchemy import select
    
    query = select(AuditLogRetentionPolicy)
    if is_active is not None:
        query = query.where(AuditLogRetentionPolicy.is_active == is_active)
    query = query.order_by(AuditLogRetentionPolicy.priority.desc())
    
    result = await db.execute(query)
    policies = result.scalars().all()
    
    return [
        RetentionPolicyResponse(
            id=str(policy.id),
            name=policy.name,
            description=policy.description,
            retention_days=policy.retention_days,
            is_active=policy.is_active,
            priority=policy.priority,
            compliance_requirement=policy.compliance_requirement,
            created_at=policy.created_at
        )
        for policy in policies
    ]


@router.post("/retention-policies", response_model=RetentionPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_retention_policy(
    request: RetentionPolicyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new retention policy (Super Admin only)."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create retention policies"
        )
    
    # Create policy
    policy = AuditLogRetentionPolicy(
        name=request.name,
        description=request.description,
        action_pattern=request.action_pattern,
        resource_type_pattern=request.resource_type_pattern,
        severity=AuditSeverity(request.severity) if request.severity else None,
        retention_days=request.retention_days,
        delete_after_export=request.delete_after_export,
        compliance_requirement=request.compliance_requirement,
        priority=request.priority,
        created_by_id=current_user.id
    )
    
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    
    return RetentionPolicyResponse(
        id=str(policy.id),
        name=policy.name,
        description=policy.description,
        retention_days=policy.retention_days,
        is_active=policy.is_active,
        priority=policy.priority,
        compliance_requirement=policy.compliance_requirement,
        created_at=policy.created_at
    )


@router.get("/alerts", response_model=List[AuditAlertResponse], dependencies=[Depends(get_current_user)])
async def list_audit_alerts(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List audit alerts."""
    from sqlalchemy import select
    
    query = select(AuditLogAlert)
    if is_active is not None:
        query = query.where(AuditLogAlert.is_active == is_active)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return [
        AuditAlertResponse(
            id=str(alert.id),
            name=alert.name,
            description=alert.description,
            is_active=alert.is_active,
            last_triggered=alert.last_triggered,
            trigger_count=alert.trigger_count,
            created_at=alert.created_at
        )
        for alert in alerts
    ]


@router.post("/alerts", response_model=AuditAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_alert(
    request: AuditAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new audit alert (Admin only)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create audit alerts"
        )
    
    # Create alert
    alert = AuditLogAlert(
        name=request.name,
        description=request.description,
        action_pattern=request.action_pattern,
        threshold_count=request.threshold_count,
        threshold_minutes=request.threshold_minutes,
        severity_threshold=AuditSeverity(request.severity_threshold) if request.severity_threshold else None,
        risk_score_threshold=request.risk_score_threshold,
        notify_emails=request.notify_emails,
        notify_webhook=request.notify_webhook,
        notify_in_app=request.notify_in_app,
        created_by_id=current_user.id
    )
    
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    
    return AuditAlertResponse(
        id=str(alert.id),
        name=alert.name,
        description=alert.description,
        is_active=alert.is_active,
        last_triggered=alert.last_triggered,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at
    )