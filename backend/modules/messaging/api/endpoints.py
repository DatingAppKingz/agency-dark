"""
API endpoints for messaging module.
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import CurrentUser, require_role
from core.domain.models import UserRole
from modules.messaging.domain.schemas import (
    # Templates
    MessageTemplateCreate, MessageTemplateUpdate, MessageTemplateResponse,
    # Bulk Messages
    BulkMessageCreate, BulkMessageUpdate, BulkMessageResponse,
    BulkMessageStats, RecipientListResponse,
    # Scheduled Messages
    MessageScheduleCreate, MessageScheduleUpdate, MessageScheduleResponse,
    # Canned Responses
    CannedResponseCreate, CannedResponseUpdate, CannedResponseResponse,
    # Analytics
    MessageAnalytics
)
from modules.messaging.domain.models import MessageStatus, TemplateCategory
from modules.messaging.application.template_service import TemplateService
from modules.messaging.application.bulk_message_service import BulkMessageService
from modules.messaging.application.scheduling_service import SchedulingService
from modules.messaging.application.canned_response_service import CannedResponseService

router = APIRouter()

# Initialize services
template_service = TemplateService()
bulk_message_service = BulkMessageService()
scheduling_service = SchedulingService()
canned_response_service = CannedResponseService()


# Template Endpoints
@router.post("/templates", response_model=MessageTemplateResponse)
async def create_template(
    data: MessageTemplateCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Create a new message template."""
    return await template_service.create_template(
        data, current_user.agency_id, current_user.id, db
    )


@router.get("/templates", response_model=List[MessageTemplateResponse])
async def list_templates(
    category: Optional[TemplateCategory] = None,
    is_global: Optional[bool] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    skip: int = 0,
    limit: int = 20,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """List message templates."""
    return await template_service.list_templates(
        agency_id=current_user.agency_id,
        user_id=current_user.id,
        category=category,
        is_global=is_global,
        search=search,
        tags=tags,
        skip=skip,
        limit=limit,
        db=db
    )


@router.get("/templates/popular", response_model=List[MessageTemplateResponse])
async def get_popular_templates(
    category: Optional[TemplateCategory] = None,
    limit: int = 10,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """Get most popular templates."""
    return await template_service.get_popular_templates(
        current_user.agency_id, category, limit, db
    )


@router.get("/templates/{template_id}", response_model=MessageTemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get a template by ID."""
    return await template_service.get_template(
        template_id, current_user.agency_id, db
    )


@router.put("/templates/{template_id}", response_model=MessageTemplateResponse)
async def update_template(
    template_id: UUID,
    data: MessageTemplateUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update a template."""
    return await template_service.update_template(
        template_id, data, current_user.agency_id, db
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Delete a template."""
    await template_service.delete_template(
        template_id, current_user.agency_id, db
    )
    return {"message": "Template deleted successfully"}


@router.post("/templates/{template_id}/duplicate", response_model=MessageTemplateResponse)
async def duplicate_template(
    template_id: UUID,
    new_name: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Duplicate a template."""
    return await template_service.duplicate_template(
        template_id, new_name, current_user.agency_id, current_user.id, db
    )


@router.post("/templates/validate")
async def validate_template(
    content: str,
    variables: Optional[dict] = None
):
    """Validate template content and test variable substitution."""
    return await template_service.validate_template_content(content, variables)


# Bulk Message Endpoints
@router.post("/bulk-messages", response_model=BulkMessageResponse)
async def create_bulk_message(
    data: BulkMessageCreate,
    current_user: CurrentUser = Depends(require_role([UserRole.MODEL, UserRole.AGENCY_ADMIN, UserRole.AGENCY_OWNER])),
    db: AsyncSession = Depends(get_db)
):
    """Create a bulk message campaign."""
    return await bulk_message_service.create_bulk_message(
        data, current_user.agency_id, current_user.id, db
    )


@router.get("/bulk-messages", response_model=List[BulkMessageResponse])
async def list_bulk_messages(
    model_id: Optional[UUID] = None,
    status: Optional[MessageStatus] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """List bulk message campaigns."""
    return await bulk_message_service.list_bulk_messages(
        current_user.agency_id, model_id, status, skip, limit, db
    )


@router.get("/bulk-messages/{message_id}", response_model=BulkMessageResponse)
async def get_bulk_message(
    message_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get a bulk message campaign."""
    return await bulk_message_service.get_bulk_message(
        message_id, current_user.agency_id, db
    )


@router.put("/bulk-messages/{message_id}", response_model=BulkMessageResponse)
async def update_bulk_message(
    message_id: UUID,
    data: BulkMessageUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update a bulk message campaign."""
    return await bulk_message_service.update_bulk_message(
        message_id, data, current_user.agency_id, db
    )


@router.post("/bulk-messages/{message_id}/cancel", response_model=BulkMessageResponse)
async def cancel_bulk_message(
    message_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a bulk message campaign."""
    return await bulk_message_service.cancel_bulk_message(
        message_id, current_user.agency_id, db
    )


@router.get("/bulk-messages/{message_id}/stats", response_model=BulkMessageStats)
async def get_bulk_message_stats(
    message_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a bulk message campaign."""
    return await bulk_message_service.get_message_stats(
        message_id, current_user.agency_id, db
    )


@router.get("/bulk-messages/{message_id}/recipients", response_model=RecipientListResponse)
async def get_bulk_message_recipients(
    message_id: UUID,
    status_filter: Optional[MessageStatus] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """Get recipients for a bulk message."""
    return await bulk_message_service.get_recipients(
        message_id, current_user.agency_id, status_filter, skip, limit, db
    )


# Scheduled Message Endpoints
@router.post("/scheduled-messages", response_model=MessageScheduleResponse)
async def create_scheduled_message(
    data: MessageScheduleCreate,
    current_user: CurrentUser = Depends(require_role([UserRole.MODEL, UserRole.CHATTER])),
    db: AsyncSession = Depends(get_db)
):
    """Create a scheduled message."""
    return await scheduling_service.create_scheduled_message(
        data, current_user.agency_id, current_user.id, db
    )


@router.get("/scheduled-messages", response_model=List[MessageScheduleResponse])
async def list_scheduled_messages(
    model_id: Optional[UUID] = None,
    fan_id: Optional[UUID] = None,
    status: Optional[MessageStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """List scheduled messages."""
    return await scheduling_service.list_scheduled_messages(
        current_user.agency_id, model_id, fan_id, status,
        date_from, date_to, skip, limit, db
    )


@router.get("/scheduled-messages/{schedule_id}", response_model=MessageScheduleResponse)
async def get_scheduled_message(
    schedule_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get a scheduled message."""
    return await scheduling_service.get_scheduled_message(
        schedule_id, current_user.agency_id, db
    )


@router.put("/scheduled-messages/{schedule_id}", response_model=MessageScheduleResponse)
async def update_scheduled_message(
    schedule_id: UUID,
    data: MessageScheduleUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update a scheduled message."""
    return await scheduling_service.update_scheduled_message(
        schedule_id, data, current_user.agency_id, db
    )


@router.delete("/scheduled-messages/{schedule_id}")
async def cancel_scheduled_message(
    schedule_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a scheduled message."""
    await scheduling_service.cancel_scheduled_message(
        schedule_id, current_user.agency_id, db
    )
    return {"message": "Scheduled message cancelled"}


@router.get("/scheduled-messages/calendar/{model_id}")
async def get_calendar_view(
    model_id: UUID,
    start_date: datetime,
    end_date: datetime,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get calendar view of scheduled messages."""
    return await scheduling_service.get_calendar_view(
        current_user.agency_id, model_id, start_date, end_date, db
    )


# Canned Response Endpoints
@router.post("/canned-responses", response_model=CannedResponseResponse)
async def create_canned_response(
    data: CannedResponseCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Create a canned response."""
    return await canned_response_service.create_canned_response(
        data, current_user.agency_id, current_user.id, db
    )


@router.get("/canned-responses", response_model=List[CannedResponseResponse])
async def list_canned_responses(
    category: Optional[str] = None,
    search: Optional[str] = None,
    include_agency_wide: bool = True,
    skip: int = 0,
    limit: int = 20,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db)
):
    """List canned responses."""
    return await canned_response_service.list_canned_responses(
        current_user.agency_id, current_user.id, category,
        search, include_agency_wide, skip, limit, db
    )


@router.get("/canned-responses/search")
async def search_canned_responses(
    shortcut: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Search canned responses by shortcut."""
    response = await canned_response_service.get_by_shortcut(
        shortcut, current_user.agency_id, current_user.id, db
    )
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canned response not found"
        )
    return response


@router.put("/canned-responses/{response_id}", response_model=CannedResponseResponse)
async def update_canned_response(
    response_id: UUID,
    data: CannedResponseUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update a canned response."""
    return await canned_response_service.update_canned_response(
        response_id, data, current_user.agency_id, current_user.id, db
    )


@router.delete("/canned-responses/{response_id}")
async def delete_canned_response(
    response_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Delete a canned response."""
    await canned_response_service.delete_canned_response(
        response_id, current_user.agency_id, current_user.id, db
    )
    return {"message": "Canned response deleted"}


# Analytics Endpoints
@router.get("/analytics", response_model=MessageAnalytics)
async def get_message_analytics(
    days: int = 30,
    current_user: CurrentUser = Depends(require_role([UserRole.AGENCY_ADMIN, UserRole.AGENCY_OWNER])),
    db: AsyncSession = Depends(get_db)
):
    """Get messaging analytics."""
    # This would aggregate data from various sources
    # For now, return mock data
    return MessageAnalytics(
        total_messages_sent=1234,
        total_bulk_campaigns=45,
        avg_open_rate=68.5,
        avg_click_rate=12.3,
        total_scheduled=89,
        total_templates=156,
        most_used_templates=[
            {"name": "Welcome Message", "usage": 234},
            {"name": "Special Offer", "usage": 189}
        ],
        peak_sending_hours=[
            {"hour": 20, "count": 456},
            {"hour": 21, "count": 523}
        ],
        platform_breakdown={
            "onlyfans": 1100,
            "fansly": 134
        }
    )


@router.get("/templates/analytics")
async def get_template_analytics(
    days: int = 30,
    current_user: CurrentUser = Depends(require_role([UserRole.AGENCY_ADMIN, UserRole.AGENCY_OWNER])),
    db: AsyncSession = Depends(get_db)
):
    """Get template usage analytics."""
    return await template_service.get_template_analytics(
        current_user.agency_id, days, db
    )