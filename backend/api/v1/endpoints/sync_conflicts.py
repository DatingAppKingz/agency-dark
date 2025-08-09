"""Sync conflict management endpoints."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from pydantic import BaseModel
import uuid

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from models.user import User
from models.sync_conflict_log import SyncConflictLog
from models.api_key import APIKey
from services.sync.conflict_resolver import ConflictType, ResolutionAction
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sync/conflicts")


class ConflictListResponse(BaseModel):
    """Conflict list item."""
    id: str
    sync_job_id: Optional[str]
    api_key_id: Optional[str]
    api_key_name: Optional[str]
    conflict_type: str
    entity_type: str
    local_id: str
    remote_id: str
    field_conflicts: Optional[List[Dict[str, Any]]]
    resolution_action: str
    manual_review_required: bool
    resolved_at: Optional[str]
    resolved_by: Optional[str]
    auto_resolved: bool
    created_at: str


class ConflictDetailResponse(BaseModel):
    """Detailed conflict information."""
    id: str
    sync_job_id: Optional[str]
    api_key_id: Optional[str]
    api_key_name: Optional[str]
    conflict_type: str
    entity_type: str
    local_id: str
    remote_id: str
    field_conflicts: Optional[List[Dict[str, Any]]]
    local_data_snapshot: Optional[Dict[str, Any]]
    remote_data_snapshot: Optional[Dict[str, Any]]
    resolution_action: str
    resolved_data: Optional[Dict[str, Any]]
    merge_conflicts: Optional[List[Dict[str, Any]]]
    manual_review_required: bool
    resolved_at: Optional[str]
    resolved_by: Optional[str]
    auto_resolved: bool
    resolution_notes: Optional[str]
    created_at: str
    updated_at: str


class ResolveConflictRequest(BaseModel):
    """Request to resolve a conflict."""
    resolution_action: ResolutionAction
    resolved_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ConflictStatsResponse(BaseModel):
    """Conflict statistics."""
    total_conflicts: int
    pending_manual_review: int
    auto_resolved: int
    manually_resolved: int
    conflicts_by_type: Dict[str, int]
    conflicts_by_entity: Dict[str, int]
    conflicts_by_action: Dict[str, int]
    conflicts_last_24h: int
    conflicts_last_7d: int


@router.get("/", response_model=List[ConflictListResponse])
async def list_conflicts(
    api_key_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    conflict_type: Optional[ConflictType] = None,
    manual_review_only: bool = False,
    unresolved_only: bool = False,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List sync conflicts with filtering options.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Build query
    query = select(SyncConflictLog).where(
        SyncConflictLog.agency_id == current_user.agency_id
    )
    
    # Apply filters
    if api_key_id:
        query = query.where(SyncConflictLog.api_key_id == api_key_id)
    if entity_type:
        query = query.where(SyncConflictLog.entity_type == entity_type)
    if conflict_type:
        query = query.where(SyncConflictLog.conflict_type == conflict_type)
    if manual_review_only:
        query = query.where(SyncConflictLog.manual_review_required == True)
    if unresolved_only:
        query = query.where(SyncConflictLog.resolved_at.is_(None))
    if start_date:
        query = query.where(SyncConflictLog.created_at >= start_date)
    if end_date:
        query = query.where(SyncConflictLog.created_at <= end_date)
    
    # Add ordering and pagination
    query = query.order_by(SyncConflictLog.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await db.execute(query)
    conflicts = result.scalars().all()
    
    # Get API key names
    api_key_ids = [c.api_key_id for c in conflicts if c.api_key_id]
    api_keys_map = {}
    if api_key_ids:
        api_keys_result = await db.execute(
            select(APIKey).where(APIKey.id.in_(api_key_ids))
        )
        api_keys_map = {str(k.id): k.name for k in api_keys_result.scalars()}
    
    # Build response
    response = []
    for conflict in conflicts:
        response.append(ConflictListResponse(
            id=str(conflict.id),
            sync_job_id=conflict.sync_job_id,
            api_key_id=str(conflict.api_key_id) if conflict.api_key_id else None,
            api_key_name=api_keys_map.get(str(conflict.api_key_id)) if conflict.api_key_id else None,
            conflict_type=conflict.conflict_type.value,
            entity_type=conflict.entity_type,
            local_id=conflict.local_id,
            remote_id=conflict.remote_id,
            field_conflicts=conflict.field_conflicts,
            resolution_action=conflict.resolution_action.value,
            manual_review_required=conflict.manual_review_required,
            resolved_at=conflict.resolved_at.isoformat() if conflict.resolved_at else None,
            resolved_by=str(conflict.resolved_by) if conflict.resolved_by else None,
            auto_resolved=conflict.auto_resolved,
            created_at=conflict.created_at.isoformat()
        ))
    
    return response


@router.get("/stats", response_model=ConflictStatsResponse)
async def get_conflict_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get conflict statistics.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Total conflicts
    total_result = await db.execute(
        select(func.count(SyncConflictLog.id)).where(
            SyncConflictLog.agency_id == current_user.agency_id
        )
    )
    total_conflicts = total_result.scalar() or 0
    
    # Pending manual review
    pending_result = await db.execute(
        select(func.count(SyncConflictLog.id)).where(
            and_(
                SyncConflictLog.agency_id == current_user.agency_id,
                SyncConflictLog.manual_review_required == True,
                SyncConflictLog.resolved_at.is_(None)
            )
        )
    )
    pending_manual_review = pending_result.scalar() or 0
    
    # Auto resolved
    auto_resolved_result = await db.execute(
        select(func.count(SyncConflictLog.id)).where(
            and_(
                SyncConflictLog.agency_id == current_user.agency_id,
                SyncConflictLog.auto_resolved == True
            )
        )
    )
    auto_resolved = auto_resolved_result.scalar() or 0
    
    # Manually resolved
    manually_resolved = total_conflicts - auto_resolved - pending_manual_review
    
    # Conflicts by type
    type_result = await db.execute(
        select(
            SyncConflictLog.conflict_type,
            func.count(SyncConflictLog.id)
        ).where(
            SyncConflictLog.agency_id == current_user.agency_id
        ).group_by(SyncConflictLog.conflict_type)
    )
    conflicts_by_type = {
        row[0].value: row[1] for row in type_result if row[0]
    }
    
    # Conflicts by entity
    entity_result = await db.execute(
        select(
            SyncConflictLog.entity_type,
            func.count(SyncConflictLog.id)
        ).where(
            SyncConflictLog.agency_id == current_user.agency_id
        ).group_by(SyncConflictLog.entity_type)
    )
    conflicts_by_entity = dict(entity_result)
    
    # Conflicts by action
    action_result = await db.execute(
        select(
            SyncConflictLog.resolution_action,
            func.count(SyncConflictLog.id)
        ).where(
            SyncConflictLog.agency_id == current_user.agency_id
        ).group_by(SyncConflictLog.resolution_action)
    )
    conflicts_by_action = {
        row[0].value: row[1] for row in action_result if row[0]
    }
    
    # Recent conflicts
    time_24h_ago = datetime.utcnow() - timedelta(hours=24)
    time_7d_ago = datetime.utcnow() - timedelta(days=7)
    
    conflicts_24h_result = await db.execute(
        select(func.count(SyncConflictLog.id)).where(
            and_(
                SyncConflictLog.agency_id == current_user.agency_id,
                SyncConflictLog.created_at >= time_24h_ago
            )
        )
    )
    conflicts_last_24h = conflicts_24h_result.scalar() or 0
    
    conflicts_7d_result = await db.execute(
        select(func.count(SyncConflictLog.id)).where(
            and_(
                SyncConflictLog.agency_id == current_user.agency_id,
                SyncConflictLog.created_at >= time_7d_ago
            )
        )
    )
    conflicts_last_7d = conflicts_7d_result.scalar() or 0
    
    return ConflictStatsResponse(
        total_conflicts=total_conflicts,
        pending_manual_review=pending_manual_review,
        auto_resolved=auto_resolved,
        manually_resolved=manually_resolved,
        conflicts_by_type=conflicts_by_type,
        conflicts_by_entity=conflicts_by_entity,
        conflicts_by_action=conflicts_by_action,
        conflicts_last_24h=conflicts_last_24h,
        conflicts_last_7d=conflicts_last_7d
    )


@router.get("/{conflict_id}", response_model=ConflictDetailResponse)
async def get_conflict_detail(
    conflict_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific conflict.
    
    Requires sync read permission.
    """
    # Check permission
    check_permission(current_user, "sync", "read")
    
    # Get conflict
    conflict = await db.get(SyncConflictLog, conflict_id)
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found"
        )
    
    if conflict.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this conflict"
        )
    
    # Get API key name
    api_key_name = None
    if conflict.api_key_id:
        api_key = await db.get(APIKey, conflict.api_key_id)
        if api_key:
            api_key_name = api_key.name
    
    return ConflictDetailResponse(
        id=str(conflict.id),
        sync_job_id=conflict.sync_job_id,
        api_key_id=str(conflict.api_key_id) if conflict.api_key_id else None,
        api_key_name=api_key_name,
        conflict_type=conflict.conflict_type.value,
        entity_type=conflict.entity_type,
        local_id=conflict.local_id,
        remote_id=conflict.remote_id,
        field_conflicts=conflict.field_conflicts,
        local_data_snapshot=conflict.local_data_snapshot,
        remote_data_snapshot=conflict.remote_data_snapshot,
        resolution_action=conflict.resolution_action.value,
        resolved_data=conflict.resolved_data,
        merge_conflicts=conflict.merge_conflicts,
        manual_review_required=conflict.manual_review_required,
        resolved_at=conflict.resolved_at.isoformat() if conflict.resolved_at else None,
        resolved_by=str(conflict.resolved_by) if conflict.resolved_by else None,
        auto_resolved=conflict.auto_resolved,
        resolution_notes=conflict.resolution_notes,
        created_at=conflict.created_at.isoformat(),
        updated_at=conflict.updated_at.isoformat()
    )


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    request: ResolveConflictRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually resolve a conflict.
    
    Requires sync write permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    # Get conflict
    conflict = await db.get(SyncConflictLog, conflict_id)
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found"
        )
    
    if conflict.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to resolve this conflict"
        )
    
    if conflict.resolved_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conflict already resolved"
        )
    
    # Update conflict
    conflict.resolution_action = request.resolution_action
    conflict.resolved_data = request.resolved_data
    conflict.resolution_notes = request.notes
    conflict.resolved_by = current_user.id
    conflict.resolved_at = datetime.utcnow()
    conflict.auto_resolved = False
    conflict.manual_review_required = False
    
    await db.commit()
    
    logger.info(
        f"Conflict {conflict_id} manually resolved",
        extra={
            "user_id": current_user.id,
            "action": request.resolution_action.value,
            "entity_type": conflict.entity_type,
            "local_id": conflict.local_id
        }
    )
    
    return {
        "success": True,
        "message": f"Conflict resolved with action: {request.resolution_action.value}"
    }


@router.post("/bulk-resolve")
async def bulk_resolve_conflicts(
    conflict_ids: List[str] = Body(...),
    resolution_action: ResolutionAction = Body(...),
    notes: Optional[str] = Body(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk resolve multiple conflicts with the same action.
    
    Requires sync write permission.
    """
    # Check permission
    check_permission(current_user, "sync", "write")
    
    # Get conflicts
    result = await db.execute(
        select(SyncConflictLog).where(
            and_(
                SyncConflictLog.id.in_(conflict_ids),
                SyncConflictLog.agency_id == current_user.agency_id,
                SyncConflictLog.resolved_at.is_(None)
            )
        )
    )
    conflicts = result.scalars().all()
    
    if not conflicts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No unresolved conflicts found"
        )
    
    # Resolve conflicts
    resolved_count = 0
    for conflict in conflicts:
        conflict.resolution_action = resolution_action
        conflict.resolution_notes = notes
        conflict.resolved_by = current_user.id
        conflict.resolved_at = datetime.utcnow()
        conflict.auto_resolved = False
        conflict.manual_review_required = False
        resolved_count += 1
    
    await db.commit()
    
    logger.info(
        f"Bulk resolved {resolved_count} conflicts",
        extra={
            "user_id": current_user.id,
            "action": resolution_action.value,
            "conflict_count": resolved_count
        }
    )
    
    return {
        "success": True,
        "resolved_count": resolved_count,
        "message": f"Resolved {resolved_count} conflicts with action: {resolution_action.value}"
    }