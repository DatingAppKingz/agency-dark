"""Background task management endpoints."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from celery.result import AsyncResult

from core.database import get_db
from core.security import get_current_active_user
from core.rbac import check_permission
from core.celery_app import celery_app, get_task_info, cancel_task
from models.user import User
from models.task_result import TaskResult, TaskStatus
from schemas.tasks import (
    TaskResponse,
    TaskListResponse,
    TaskCreateRequest,
    ExportRequest,
    TaskStatsResponse
)
from tasks.export_tasks import export_agency_data, export_model_data, generate_financial_report
from tasks.media_tasks import process_image, process_video, process_pending_media
from tasks.notification_tasks import send_email, send_alert
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List background tasks.
    
    - Filter by status, type, date range
    - Paginated results
    - Sorted by creation date (newest first)
    """
    # Check permission
    check_permission(current_user, "tasks", "read")
    
    # Build query
    query = select(TaskResult).where(
        TaskResult.user_id == current_user.id
    )
    
    # Apply filters
    if status:
        query = query.where(TaskResult.status == status)
    
    if task_type:
        query = query.where(TaskResult.task_name.contains(task_type))
    
    if created_after:
        query = query.where(TaskResult.created_at >= created_after)
    
    if created_before:
        query = query.where(TaskResult.created_at <= created_before)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply sorting and pagination
    query = query.order_by(TaskResult.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Get current status from Celery
    task_responses = []
    for task in tasks:
        celery_info = get_task_info(task.task_id)
        task_responses.append(TaskResponse.from_orm(task, celery_info))
    
    return TaskListResponse(
        items=task_responses,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get task details."""
    # Get task from database
    task = await db.get(TaskResult, task_id)
    
    if not task:
        # Try to get from Celery directly
        celery_info = get_task_info(task_id)
        if celery_info['status'] == 'PENDING':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Create temporary task object
        task = TaskResult(
            task_id=task_id,
            task_name="Unknown",
            status=TaskStatus(celery_info['status']),
            created_at=datetime.utcnow()
        )
    else:
        # Check ownership
        if task.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get current status from Celery
    celery_info = get_task_info(task_id)
    
    return TaskResponse.from_orm(task, celery_info)


@router.delete("/{task_id}")
async def cancel_task_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a running task."""
    # Check permission
    check_permission(current_user, "tasks", "cancel")
    
    # Get task
    task = await db.get(TaskResult, task_id)
    
    if task:
        # Check ownership
        if task.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot cancel task you don't own"
            )
    
    # Cancel task
    success = cancel_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel task"
        )
    
    # Update task status in database
    if task:
        task.status = TaskStatus.REVOKED
        task.completed_at = datetime.utcnow()
        await db.commit()
    
    return {"message": "Task cancelled successfully"}


@router.post("/export/agency", response_model=TaskResponse)
async def create_agency_export(
    request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create agency data export task.
    
    Exports all agency data to a downloadable file.
    """
    # Check permission
    check_permission(current_user, "export", "create")
    
    # Create task
    task = export_agency_data.delay(
        str(current_user.agency_id),
        str(current_user.id),
        request.dict()
    )
    
    # Store task in database
    task_result = TaskResult(
        task_id=task.id,
        task_name="export_agency_data",
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        status=TaskStatus.PENDING,
        params=request.dict()
    )
    
    db.add(task_result)
    await db.commit()
    await db.refresh(task_result)
    
    return TaskResponse.from_orm(task_result, get_task_info(task.id))


@router.post("/export/model/{model_id}", response_model=TaskResponse)
async def create_model_export(
    model_id: str,
    request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create model data export task."""
    # Check permission
    check_permission(current_user, "export", "create")
    
    # Verify model belongs to agency
    # TODO: Add model ownership check
    
    # Create task
    task = export_model_data.delay(
        model_id,
        str(current_user.id),
        request.dict()
    )
    
    # Store task in database
    task_result = TaskResult(
        task_id=task.id,
        task_name="export_model_data",
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        status=TaskStatus.PENDING,
        params={**request.dict(), "model_id": model_id}
    )
    
    db.add(task_result)
    await db.commit()
    await db.refresh(task_result)
    
    return TaskResponse.from_orm(task_result, get_task_info(task.id))


@router.post("/export/financial-report", response_model=TaskResponse)
async def create_financial_report(
    report_type: str = Query(..., regex="^(revenue_summary|commission_report|payout_report|tax_report)$"),
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create financial report generation task."""
    # Check permission
    check_permission(current_user, "reports", "create")
    
    # Create task
    task = generate_financial_report.delay(
        str(current_user.agency_id),
        str(current_user.id),
        report_type,
        date_from.isoformat(),
        date_to.isoformat()
    )
    
    # Store task in database
    task_result = TaskResult(
        task_id=task.id,
        task_name="generate_financial_report",
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        status=TaskStatus.PENDING,
        params={
            "report_type": report_type,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat()
        }
    )
    
    db.add(task_result)
    await db.commit()
    await db.refresh(task_result)
    
    return TaskResponse.from_orm(task_result, get_task_info(task.id))


@router.post("/media/reprocess/{media_id}", response_model=TaskResponse)
async def reprocess_media(
    media_id: str,
    processing_options: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Reprocess a media file."""
    # Check permission
    check_permission(current_user, "media", "update")
    
    # Get media and verify ownership
    from models.media import Media
    media = await db.get(Media, media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    if media.uploaded_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot reprocess media you don't own"
        )
    
    # Create appropriate task based on media type
    if media.media_type.value == 'image':
        task = process_image.delay(media_id, processing_options)
        task_name = "process_image"
    elif media.media_type.value == 'video':
        task = process_video.delay(media_id, processing_options)
        task_name = "process_video"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media type not supported for reprocessing"
        )
    
    # Store task in database
    task_result = TaskResult(
        task_id=task.id,
        task_name=task_name,
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        status=TaskStatus.PENDING,
        params={
            "media_id": media_id,
            "processing_options": processing_options
        }
    )
    
    db.add(task_result)
    await db.commit()
    await db.refresh(task_result)
    
    return TaskResponse.from_orm(task_result, get_task_info(task.id))


@router.get("/stats/summary", response_model=TaskStatsResponse)
async def get_task_stats(
    time_range: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get task statistics."""
    # Check permission
    check_permission(current_user, "tasks", "read")
    
    # Calculate time range
    now = datetime.utcnow()
    if time_range == "1h":
        start_time = now - timedelta(hours=1)
    elif time_range == "24h":
        start_time = now - timedelta(days=1)
    elif time_range == "7d":
        start_time = now - timedelta(days=7)
    else:  # 30d
        start_time = now - timedelta(days=30)
    
    # Get task counts by status
    query = select(
        TaskResult.status,
        func.count(TaskResult.id).label('count')
    ).where(
        and_(
            TaskResult.user_id == current_user.id,
            TaskResult.created_at >= start_time
        )
    ).group_by(TaskResult.status)
    
    result = await db.execute(query)
    status_counts = {row.status: row.count for row in result}
    
    # Get task counts by type
    query = select(
        TaskResult.task_name,
        func.count(TaskResult.id).label('count')
    ).where(
        and_(
            TaskResult.user_id == current_user.id,
            TaskResult.created_at >= start_time
        )
    ).group_by(TaskResult.task_name)
    
    result = await db.execute(query)
    type_counts = {row.task_name: row.count for row in result}
    
    # Get average execution time
    query = select(
        func.avg(
            func.extract('epoch', TaskResult.completed_at - TaskResult.created_at)
        ).label('avg_duration')
    ).where(
        and_(
            TaskResult.user_id == current_user.id,
            TaskResult.created_at >= start_time,
            TaskResult.status == TaskStatus.SUCCESS,
            TaskResult.completed_at.isnot(None)
        )
    )
    
    avg_duration = await db.scalar(query) or 0
    
    return TaskStatsResponse(
        time_range=time_range,
        total_tasks=sum(status_counts.values()),
        status_breakdown=status_counts,
        type_breakdown=type_counts,
        average_duration_seconds=round(avg_duration, 2),
        success_rate=round(
            status_counts.get(TaskStatus.SUCCESS, 0) / sum(status_counts.values()) * 100
            if status_counts else 0,
            2
        )
    )


@router.post("/test/email")
async def test_email_task(
    to_email: str,
    subject: str = "Test Email",
    current_user: User = Depends(get_current_active_user)
):
    """Test email sending (admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Send test email
    task = send_email.delay(
        to_email,
        subject,
        'test_email',
        {
            'user': current_user.dict(),
            'timestamp': datetime.utcnow().isoformat()
        }
    )
    
    return {
        "task_id": task.id,
        "message": "Test email task created"
    }


@router.post("/test/alert")
async def test_alert_task(
    alert_type: str = "test",
    severity: str = "info",
    current_user: User = Depends(get_current_active_user)
):
    """Test alert sending (admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Send test alert
    task = send_alert.delay(
        alert_type,
        severity,
        "Test Alert",
        "This is a test alert message",
        str(current_user.agency_id),
        str(current_user.id),
        {"test": True}
    )
    
    return {
        "task_id": task.id,
        "message": "Test alert task created"
    }