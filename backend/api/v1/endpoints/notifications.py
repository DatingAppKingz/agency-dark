"""Notification API endpoints."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from core.database import get_db
from core.security import get_current_active_user
from core.rbac import check_permission
from services.notification_service import NotificationService
from models.user import User
from models.notification import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationEvent, NotificationType, NotificationStatus, NotificationPriority
)
from schemas.notification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
    BulkNotificationCreate, BulkNotificationResponse,
    NotificationTemplateCreate, NotificationTemplateUpdate, NotificationTemplateResponse,
    NotificationPreferenceUpdate, NotificationPreferenceResponse,
    NotificationEventResponse, NotificationStats, TestNotificationRequest
)
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create a new notification.
    
    Permissions:
    - notifications:create
    """
    # Check permission
    check_permission(current_user, "notifications", "create")
    
    # Initialize service
    service = NotificationService(db)
    
    # Create notification
    notification = await service.create_notification(
        notification_data,
        str(current_user.agency_id),
        send_immediately=True
    )
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create notification"
        )
    
    return NotificationResponse.from_orm(notification)


@router.post("/bulk", response_model=BulkNotificationResponse)
async def create_bulk_notifications(
    bulk_data: BulkNotificationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create bulk notifications.
    
    Send notifications to multiple recipients at once.
    
    Permissions:
    - notifications:create
    - notifications:bulk (for large batches)
    """
    # Check permission
    check_permission(current_user, "notifications", "create")
    
    # Check bulk permission for large batches
    total_recipients = len(bulk_data.user_ids or []) + len(bulk_data.emails or []) + len(bulk_data.phones or [])
    if total_recipients > 100:
        check_permission(current_user, "notifications", "bulk")
    
    # Initialize service
    service = NotificationService(db)
    
    # Create bulk notifications
    result = await service.create_bulk_notifications(
        bulk_data,
        str(current_user.agency_id)
    )
    
    return BulkNotificationResponse(**result)


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[NotificationType] = None,
    status: Optional[NotificationStatus] = None,
    priority: Optional[NotificationPriority] = None,
    user_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List notifications.
    
    Permissions:
    - notifications:read (own notifications)
    - notifications:read_all (all agency notifications)
    """
    # Build query
    query = select(Notification).where(
        Notification.agency_id == current_user.agency_id
    )
    
    # Filter by user if not admin
    if not check_permission(current_user, "notifications", "read_all", raise_error=False):
        query = query.where(Notification.user_id == current_user.id)
    elif user_id:
        query = query.where(Notification.user_id == user_id)
    
    # Apply filters
    if type:
        query = query.where(Notification.type == type)
    if status:
        query = query.where(Notification.status == status)
    if priority:
        query = query.where(Notification.priority == priority)
    if date_from:
        query = query.where(Notification.created_at >= date_from)
    if date_to:
        query = query.where(Notification.created_at <= date_to)
    
    # Order and paginate
    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [NotificationResponse.from_orm(n) for n in notifications]


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notification details.
    
    Permissions:
    - notifications:read (own)
    - notifications:read_all (any)
    """
    notification = await db.get(Notification, notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Check ownership
    if notification.user_id != current_user.id:
        check_permission(current_user, "notifications", "read_all")
    
    # Mark as opened if recipient is viewing
    if notification.user_id == current_user.id and notification.status == NotificationStatus.DELIVERED:
        service = NotificationService(db)
        await service.mark_as_opened(notification_id)
    
    return NotificationResponse.from_orm(notification)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: str,
    update_data: NotificationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update notification.
    
    Permissions:
    - notifications:update
    """
    check_permission(current_user, "notifications", "update")
    
    notification = await db.get(Notification, notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(notification, field, value)
    
    await db.commit()
    await db.refresh(notification)
    
    return NotificationResponse.from_orm(notification)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete notification.
    
    Permissions:
    - notifications:delete
    """
    check_permission(current_user, "notifications", "delete")
    
    notification = await db.get(Notification, notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    await db.delete(notification)
    await db.commit()
    
    return {"message": "Notification deleted successfully"}


# Template endpoints
@router.post("/templates", response_model=NotificationTemplateResponse)
async def create_template(
    template_data: NotificationTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create notification template.
    
    Permissions:
    - notification_templates:create
    """
    check_permission(current_user, "notification_templates", "create")
    
    # Create template
    template = NotificationTemplate(
        **template_data.dict(),
        agency_id=current_user.agency_id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return NotificationTemplateResponse.from_orm(template)


@router.get("/templates", response_model=List[NotificationTemplateResponse])
async def list_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[NotificationType] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List notification templates.
    
    Permissions:
    - notification_templates:read
    """
    check_permission(current_user, "notification_templates", "read")
    
    # Build query
    query = select(NotificationTemplate).where(
        NotificationTemplate.agency_id == current_user.agency_id
    )
    
    # Apply filters
    if type:
        query = query.where(NotificationTemplate.type == type)
    if is_active is not None:
        query = query.where(NotificationTemplate.is_active == is_active)
    
    # Order and paginate
    query = query.order_by(NotificationTemplate.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return [NotificationTemplateResponse.from_orm(t) for t in templates]


@router.get("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notification template.
    
    Permissions:
    - notification_templates:read
    """
    check_permission(current_user, "notification_templates", "read")
    
    template = await db.get(NotificationTemplate, template_id)
    
    if not template or template.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return NotificationTemplateResponse.from_orm(template)


@router.patch("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def update_template(
    template_id: str,
    update_data: NotificationTemplateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update notification template.
    
    Permissions:
    - notification_templates:update
    """
    check_permission(current_user, "notification_templates", "update")
    
    template = await db.get(NotificationTemplate, template_id)
    
    if not template or template.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Don't allow updating system templates
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update system templates"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(template, field, value)
    
    await db.commit()
    await db.refresh(template)
    
    return NotificationTemplateResponse.from_orm(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete notification template.
    
    Permissions:
    - notification_templates:delete
    """
    check_permission(current_user, "notification_templates", "delete")
    
    template = await db.get(NotificationTemplate, template_id)
    
    if not template or template.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Don't allow deleting system templates
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system templates"
        )
    
    await db.delete(template)
    await db.commit()
    
    return {"message": "Template deleted successfully"}


# Preference endpoints
@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences
        preferences = NotificationPreference(
            user_id=current_user.id,
            email_enabled=True,
            sms_enabled=True,
            push_enabled=True,
            in_app_enabled=True,
            categories={
                "marketing": True,
                "transactions": True,
                "messages": True,
                "system": True,
                "security": True
            },
            timezone="UTC"
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return NotificationPreferenceResponse.from_orm(preferences)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences(
    update_data: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification preferences."""
    # Get or create preferences
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        preferences = NotificationPreference(user_id=current_user.id)
        db.add(preferences)
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        if field == "categories" and preferences.categories:
            # Merge categories
            current_categories = preferences.categories
            current_categories.update(value)
            preferences.categories = current_categories
        else:
            setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    
    return NotificationPreferenceResponse.from_orm(preferences)


# Event endpoints
@router.get("/{notification_id}/events", response_model=List[NotificationEventResponse])
async def list_notification_events(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List notification events.
    
    Permissions:
    - notifications:read (own)
    - notifications:read_all (any)
    """
    # Check notification exists and user has access
    notification = await db.get(Notification, notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if notification.user_id != current_user.id:
        check_permission(current_user, "notifications", "read_all")
    
    # Get events
    result = await db.execute(
        select(NotificationEvent).where(
            NotificationEvent.notification_id == notification_id
        ).order_by(NotificationEvent.created_at.desc())
    )
    events = result.scalars().all()
    
    return [NotificationEventResponse.from_orm(e) for e in events]


@router.post("/{notification_id}/click")
async def track_notification_click(
    notification_id: str,
    link: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Track notification click."""
    notification = await db.get(Notification, notification_id)
    
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Mark as clicked
    service = NotificationService(db)
    await service.mark_as_clicked(notification_id, link)
    
    return {"message": "Click tracked successfully"}


# Statistics
@router.get("/stats/summary", response_model=NotificationStats)
async def get_notification_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get notification statistics.
    
    Permissions:
    - notifications:stats
    """
    check_permission(current_user, "notifications", "stats")
    
    service = NotificationService(db)
    stats = await service.get_notification_stats(
        str(current_user.agency_id),
        start_date,
        end_date
    )
    
    return NotificationStats(**stats)


# Test notification
@router.post("/test")
async def send_test_notification(
    test_data: TestNotificationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send test notification to current user.
    
    Permissions:
    - notifications:test
    """
    check_permission(current_user, "notifications", "test")
    
    # Create test notification
    notification_data = NotificationCreate(
        type=test_data.type,
        user_id=str(current_user.id),
        subject=test_data.subject or "Test Notification",
        content=test_data.content or "This is a test notification",
        html_content=test_data.html_content,
        template_id=test_data.template_id,
        template_data=test_data.template_data,
        metadata={"test": True}
    )
    
    # Send notification
    service = NotificationService(db)
    notification = await service.create_notification(
        notification_data,
        str(current_user.agency_id),
        send_immediately=True
    )
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send test notification"
        )
    
    return {
        "message": "Test notification sent successfully",
        "notification_id": str(notification.id)
    }