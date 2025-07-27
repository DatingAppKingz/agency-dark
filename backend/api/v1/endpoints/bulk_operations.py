"""
Bulk operations API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.bulk_operations.models import (
    BulkOperation, BulkOperationItem, BulkOperationLog,
    BulkOperationType, BulkOperationStatus, BulkOperationTemplate,
    BulkOperationSchedule, BulkOperationLimit
)
from core.bulk_operations.bulk_processor import bulk_processor, BulkOperationProgress
from core.domain.schemas import BaseResponse

router = APIRouter(prefix="/bulk-operations", tags=["bulk-operations"])


# Schemas
class BulkOperationCreate(BaseModel):
    """Create a new bulk operation."""
    operation_type: BulkOperationType
    entity_type: str = Field(..., description="Type of entities (users, models, etc.)")
    entity_ids: List[UUID] = Field(..., description="IDs of entities to operate on")
    operation_params: Dict[str, Any] = Field(default_factory=dict)
    validation_rules: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None


class BulkOperationResponse(BaseModel):
    """Bulk operation response."""
    id: UUID
    operation_type: str
    status: str
    entity_type: str
    total_count: int
    processed_count: int
    success_count: int
    failed_count: int
    progress_percentage: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_summary: Optional[str]
    can_rollback: bool


class BulkOperationItemResponse(BaseModel):
    """Bulk operation item details."""
    id: UUID
    entity_id: UUID
    status: str
    processed_at: Optional[datetime]
    error_message: Optional[str]
    validation_errors: Optional[Dict[str, Any]]
    changes: Optional[Dict[str, Any]]


class BulkTemplateCreate(BaseModel):
    """Create a bulk operation template."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    operation_type: BulkOperationType
    default_params: Dict[str, Any]
    validation_rules: Optional[Dict[str, Any]] = None
    selection_criteria: Optional[Dict[str, Any]] = None


class BulkScheduleCreate(BaseModel):
    """Create a scheduled bulk operation."""
    name: str = Field(..., min_length=1, max_length=100)
    template_id: UUID
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    timezone: str = Field("UTC")
    entity_selection: Dict[str, Any] = Field(..., description="Criteria for selecting entities")
    max_entities_per_run: Optional[int] = None
    notify_on_completion: bool = True
    notify_on_failure: bool = True
    notification_emails: Optional[List[str]] = None


class BulkLimitUpdate(BaseModel):
    """Update bulk operation limits."""
    max_entities_per_operation: Optional[int] = None
    max_operations_per_day: Optional[int] = None
    max_operations_per_hour: Optional[int] = None
    max_concurrent_operations: Optional[int] = None
    is_unlimited: bool = False
    valid_until: Optional[datetime] = None


# Endpoints

@router.post("/", response_model=BulkOperationResponse)
async def create_bulk_operation(
    operation: BulkOperationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """Create a new bulk operation."""
    # Check permissions based on operation type
    required_roles = {
        BulkOperationType.USER_DELETE: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
        BulkOperationType.USER_ACTIVATE: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        BulkOperationType.MODEL_ASSIGN: [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
        BulkOperationType.PAYOUT_SCHEDULE: [UserRole.AGENCY_OWNER],
    }
    
    allowed_roles = required_roles.get(
        operation.operation_type,
        [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.AGENCY_MEMBER]
    )
    
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions for this operation")
    
    # Create operation
    bulk_op = await bulk_processor.create_operation(
        operation_type=operation.operation_type,
        entity_type=operation.entity_type,
        entity_ids=[str(id) for id in operation.entity_ids],
        params=operation.operation_params,
        user=current_user,
        session=db,
        scheduled_at=operation.scheduled_at,
        validation_rules=operation.validation_rules
    )
    
    if operation.notes:
        bulk_op.notes = operation.notes
        await db.commit()
    
    return BulkOperationResponse(
        id=bulk_op.id,
        operation_type=bulk_op.operation_type.value,
        status=bulk_op.status.value,
        entity_type=bulk_op.entity_type,
        total_count=bulk_op.total_count,
        processed_count=bulk_op.processed_count,
        success_count=bulk_op.success_count,
        failed_count=bulk_op.failed_count,
        progress_percentage=bulk_op.progress_percentage,
        created_at=bulk_op.created_at,
        started_at=bulk_op.started_at,
        completed_at=bulk_op.completed_at,
        error_summary=bulk_op.error_summary,
        can_rollback=bulk_op.can_rollback
    )


@router.get("/", response_model=List[BulkOperationResponse])
async def list_bulk_operations(
    status: Optional[BulkOperationStatus] = None,
    operation_type: Optional[BulkOperationType] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[BulkOperationResponse]:
    """List bulk operations."""
    query = select(BulkOperation)
    
    # Filter by agency unless super admin
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(BulkOperation.agency_id == current_user.agency_id)
    
    # Additional filters
    if status:
        query = query.where(BulkOperation.status == status)
    if operation_type:
        query = query.where(BulkOperation.operation_type == operation_type)
    
    # Order and paginate
    query = query.order_by(BulkOperation.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    return [
        BulkOperationResponse(
            id=op.id,
            operation_type=op.operation_type.value,
            status=op.status.value,
            entity_type=op.entity_type,
            total_count=op.total_count,
            processed_count=op.processed_count,
            success_count=op.success_count,
            failed_count=op.failed_count,
            progress_percentage=op.progress_percentage,
            created_at=op.created_at,
            started_at=op.started_at,
            completed_at=op.completed_at,
            error_summary=op.error_summary,
            can_rollback=op.can_rollback
        )
        for op in operations
    ]


@router.get("/{operation_id}", response_model=BulkOperationResponse)
async def get_bulk_operation(
    operation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """Get bulk operation details."""
    result = await db.execute(
        select(BulkOperation).where(BulkOperation.id == operation_id)
    )
    operation = result.scalar_one_or_none()
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN and operation.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return BulkOperationResponse(
        id=operation.id,
        operation_type=operation.operation_type.value,
        status=operation.status.value,
        entity_type=operation.entity_type,
        total_count=operation.total_count,
        processed_count=operation.processed_count,
        success_count=operation.success_count,
        failed_count=operation.failed_count,
        progress_percentage=operation.progress_percentage,
        created_at=operation.created_at,
        started_at=operation.started_at,
        completed_at=operation.completed_at,
        error_summary=operation.error_summary,
        can_rollback=operation.can_rollback
    )


@router.get("/{operation_id}/progress", response_model=BulkOperationProgress)
async def get_operation_progress(
    operation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationProgress:
    """Get real-time progress of a bulk operation."""
    # Verify access
    result = await db.execute(
        select(BulkOperation.agency_id).where(BulkOperation.id == operation_id)
    )
    agency_id = result.scalar_one_or_none()
    
    if not agency_id:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await bulk_processor.get_progress(str(operation_id), db)


@router.get("/{operation_id}/items", response_model=List[BulkOperationItemResponse])
async def get_operation_items(
    operation_id: UUID,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[BulkOperationItemResponse]:
    """Get items of a bulk operation."""
    # Verify access
    result = await db.execute(
        select(BulkOperation.agency_id).where(BulkOperation.id == operation_id)
    )
    agency_id = result.scalar_one_or_none()
    
    if not agency_id:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get items
    query = select(BulkOperationItem).where(BulkOperationItem.operation_id == operation_id)
    
    if status:
        query = query.where(BulkOperationItem.status == status)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return [
        BulkOperationItemResponse(
            id=item.id,
            entity_id=item.entity_id,
            status=item.status,
            processed_at=item.processed_at,
            error_message=item.error_message,
            validation_errors=item.validation_errors,
            changes=item.changes
        )
        for item in items
    ]


@router.get("/{operation_id}/logs")
async def get_operation_logs(
    operation_id: UUID,
    level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get logs of a bulk operation."""
    # Verify access
    result = await db.execute(
        select(BulkOperation.agency_id).where(BulkOperation.id == operation_id)
    )
    agency_id = result.scalar_one_or_none()
    
    if not agency_id:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get logs
    query = select(BulkOperationLog).where(BulkOperationLog.operation_id == operation_id)
    
    if level:
        query = query.where(BulkOperationLog.log_level == level)
    
    query = query.order_by(BulkOperationLog.timestamp.desc()).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": str(log.id),
            "level": log.log_level,
            "message": log.message,
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "batch_number": log.batch_number
        }
        for log in logs
    ]


@router.post("/{operation_id}/cancel", response_model=BaseResponse)
async def cancel_operation(
    operation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Cancel a running bulk operation."""
    success = await bulk_processor.cancel_operation(
        str(operation_id),
        current_user,
        db
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Operation cannot be cancelled")
    
    return BaseResponse(
        success=True,
        message="Operation cancellation requested"
    )


@router.post("/{operation_id}/rollback", response_model=BaseResponse)
async def rollback_operation(
    operation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Rollback a completed bulk operation."""
    try:
        success = await bulk_processor.rollback_operation(
            str(operation_id),
            current_user,
            db
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Operation rollback failed")
        
        return BaseResponse(
            success=True,
            message="Operation rolled back successfully"
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates", response_model=BaseResponse)
async def create_template(
    template: BulkTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Create a bulk operation template."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if name exists
    result = await db.execute(
        select(BulkOperationTemplate).where(
            and_(
                BulkOperationTemplate.name == template.name,
                BulkOperationTemplate.agency_id == current_user.agency_id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template name already exists")
    
    # Create template
    new_template = BulkOperationTemplate(
        name=template.name,
        description=template.description,
        operation_type=template.operation_type,
        default_params=template.default_params,
        validation_rules=template.validation_rules,
        selection_criteria=template.selection_criteria,
        created_by_id=current_user.id,
        agency_id=current_user.agency_id
    )
    
    db.add(new_template)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message=f"Template '{template.name}' created successfully"
    )


@router.get("/templates")
async def list_templates(
    operation_type: Optional[BulkOperationType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List available bulk operation templates."""
    query = select(BulkOperationTemplate).where(
        or_(
            BulkOperationTemplate.is_system == True,
            BulkOperationTemplate.agency_id == current_user.agency_id
        )
    )
    
    if operation_type:
        query = query.where(BulkOperationTemplate.operation_type == operation_type)
    
    query = query.where(BulkOperationTemplate.is_active == True)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return [
        {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "operation_type": template.operation_type.value,
            "default_params": template.default_params,
            "is_system": template.is_system,
            "usage_count": template.usage_count
        }
        for template in templates
    ]


@router.post("/schedules", response_model=BaseResponse)
async def create_schedule(
    schedule: BulkScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Create a scheduled bulk operation."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify template exists and belongs to agency
    result = await db.execute(
        select(BulkOperationTemplate).where(
            and_(
                BulkOperationTemplate.id == schedule.template_id,
                or_(
                    BulkOperationTemplate.is_system == True,
                    BulkOperationTemplate.agency_id == current_user.agency_id
                )
            )
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create schedule
    new_schedule = BulkOperationSchedule(
        name=schedule.name,
        template_id=schedule.template_id,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        entity_selection=schedule.entity_selection,
        max_entities_per_run=schedule.max_entities_per_run,
        notify_on_completion=schedule.notify_on_completion,
        notify_on_failure=schedule.notify_on_failure,
        notification_emails=schedule.notification_emails,
        created_by_id=current_user.id,
        agency_id=current_user.agency_id
    )
    
    # TODO: Calculate next run time based on cron expression
    
    db.add(new_schedule)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message=f"Schedule '{schedule.name}' created successfully"
    )


@router.get("/limits")
async def get_operation_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get bulk operation limits for current user/agency."""
    # Get user-specific limits
    user_limits = await db.execute(
        select(BulkOperationLimit).where(
            BulkOperationLimit.user_id == current_user.id
        )
    )
    user_limit = user_limits.scalars().all()
    
    # Get agency limits
    agency_limits = await db.execute(
        select(BulkOperationLimit).where(
            BulkOperationLimit.agency_id == current_user.agency_id
        )
    )
    agency_limit = agency_limits.scalars().all()
    
    return {
        "user_limits": [
            {
                "operation_type": limit.operation_type.value if limit.operation_type else "all",
                "max_entities_per_operation": limit.max_entities_per_operation,
                "max_operations_per_day": limit.max_operations_per_day,
                "max_operations_per_hour": limit.max_operations_per_hour,
                "operations_today": limit.operations_today,
                "operations_this_hour": limit.operations_this_hour,
                "is_unlimited": limit.is_unlimited
            }
            for limit in user_limit
        ],
        "agency_limits": [
            {
                "operation_type": limit.operation_type.value if limit.operation_type else "all",
                "max_entities_per_operation": limit.max_entities_per_operation,
                "max_operations_per_day": limit.max_operations_per_day,
                "max_operations_per_hour": limit.max_operations_per_hour,
                "is_unlimited": limit.is_unlimited
            }
            for limit in agency_limit
        ]
    }


@router.put("/limits/{user_id}", response_model=BaseResponse)
async def update_user_limits(
    user_id: UUID,
    limits: BulkLimitUpdate,
    operation_type: Optional[BulkOperationType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Update bulk operation limits for a user."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get or create limit
    query = select(BulkOperationLimit).where(
        and_(
            BulkOperationLimit.user_id == user_id,
            BulkOperationLimit.operation_type == operation_type
        )
    )
    result = await db.execute(query)
    limit = result.scalar_one_or_none()
    
    if not limit:
        limit = BulkOperationLimit(
            user_id=user_id,
            operation_type=operation_type
        )
        db.add(limit)
    
    # Update limits
    if limits.max_entities_per_operation is not None:
        limit.max_entities_per_operation = limits.max_entities_per_operation
    if limits.max_operations_per_day is not None:
        limit.max_operations_per_day = limits.max_operations_per_day
    if limits.max_operations_per_hour is not None:
        limit.max_operations_per_hour = limits.max_operations_per_hour
    if limits.max_concurrent_operations is not None:
        limit.max_concurrent_operations = limits.max_concurrent_operations
    
    limit.is_unlimited = limits.is_unlimited
    limit.valid_until = limits.valid_until
    
    await db.commit()
    
    return BaseResponse(
        success=True,
        message="Limits updated successfully"
    )


@router.get("/statistics")
async def get_bulk_statistics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get bulk operation statistics."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    
    # Base query
    base_query = select(BulkOperation).where(BulkOperation.created_at >= since)
    
    if current_user.role != UserRole.SUPER_ADMIN:
        base_query = base_query.where(BulkOperation.agency_id == current_user.agency_id)
    
    # Total operations
    total_result = await db.execute(
        select(func.count(BulkOperation.id)).select_from(base_query.subquery())
    )
    total_operations = total_result.scalar() or 0
    
    # By status
    status_result = await db.execute(
        select(
            BulkOperation.status,
            func.count(BulkOperation.id)
        )
        .select_from(base_query.subquery())
        .group_by(BulkOperation.status)
    )
    
    status_breakdown = {
        row[0].value: row[1] for row in status_result
    }
    
    # By type
    type_result = await db.execute(
        select(
            BulkOperation.operation_type,
            func.count(BulkOperation.id),
            func.sum(BulkOperation.total_count),
            func.sum(BulkOperation.success_count),
            func.sum(BulkOperation.failed_count)
        )
        .select_from(base_query.subquery())
        .group_by(BulkOperation.operation_type)
    )
    
    type_breakdown = [
        {
            "operation_type": row[0].value,
            "count": row[1],
            "total_entities": row[2] or 0,
            "success_entities": row[3] or 0,
            "failed_entities": row[4] or 0
        }
        for row in type_result
    ]
    
    # Average processing time
    time_result = await db.execute(
        select(
            func.avg(
                func.extract('epoch', BulkOperation.completed_at - BulkOperation.started_at)
            )
        )
        .select_from(base_query.subquery())
        .where(
            and_(
                BulkOperation.started_at.isnot(None),
                BulkOperation.completed_at.isnot(None)
            )
        )
    )
    avg_processing_seconds = time_result.scalar() or 0
    
    return {
        "total_operations": total_operations,
        "status_breakdown": status_breakdown,
        "type_breakdown": type_breakdown,
        "average_processing_seconds": avg_processing_seconds,
        "time_range_days": days
    }