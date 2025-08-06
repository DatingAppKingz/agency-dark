"""Email preferences API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr

from core.database import get_db
from models.user import User
from models.email_preferences import EmailPreferences
from core.dependencies import CurrentUser
from services.email_notifications import EmailNotificationService
from services.email_queue import EmailQueueService
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class EmailPreferencesUpdate(BaseModel):
    """Email preferences update model."""
    email_enabled: Optional[bool] = None
    email_address: Optional[EmailStr] = None
    
    # Notification categories
    account_updates: Optional[bool] = None
    security_alerts: Optional[bool] = None
    model_approval: Optional[bool] = None
    model_updates: Optional[bool] = None
    payout_created: Optional[bool] = None
    payout_approved: Optional[bool] = None
    payout_completed: Optional[bool] = None
    invoice_created: Optional[bool] = None
    payment_received: Optional[bool] = None
    daily_summary: Optional[bool] = None
    weekly_report: Optional[bool] = None
    monthly_statement: Optional[bool] = None
    product_updates: Optional[bool] = None
    tips_and_tricks: Optional[bool] = None
    promotional_offers: Optional[bool] = None
    chat_notifications: Optional[bool] = None
    mention_notifications: Optional[bool] = None
    
    # Frequency settings
    notification_frequency: Optional[str] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class EmailPreferencesResponse(BaseModel):
    """Email preferences response model."""
    user_id: int
    email_enabled: bool
    email_address: Optional[str]
    account_updates: bool
    security_alerts: bool
    model_approval: bool
    model_updates: bool
    payout_created: bool
    payout_approved: bool
    payout_completed: bool
    invoice_created: bool
    payment_received: bool
    daily_summary: bool
    weekly_report: bool
    monthly_statement: bool
    product_updates: bool
    tips_and_tricks: bool
    promotional_offers: bool
    chat_notifications: bool
    mention_notifications: bool
    notification_frequency: str
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    timezone: str
    language: str
    unsubscribe_token: str
    unsubscribed_at: Optional[str]

    class Config:
        from_attributes = True


@router.get("/preferences", response_model=EmailPreferencesResponse)
async def get_email_preferences(
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get current user's email preferences."""
    service = EmailNotificationService(db)
    prefs = await service._get_user_preferences(current_user.id)
    
    return EmailPreferencesResponse.model_validate(prefs)


@router.put("/preferences", response_model=EmailPreferencesResponse)
async def update_email_preferences(
    updates: EmailPreferencesUpdate,
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Update email preferences."""
    service = EmailNotificationService(db)
    
    # Convert to dict and remove None values
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    prefs = await service.update_preferences(current_user.id, update_dict)
    
    return EmailPreferencesResponse.model_validate(prefs)


@router.post("/unsubscribe")
async def unsubscribe(
    token: str = Query(..., description="Unsubscribe token"),
    reason: Optional[str] = Query(None, description="Reason for unsubscribing"),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from emails using token."""
    service = EmailNotificationService(db)
    
    success = await service.unsubscribe_user(token, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe token")
    
    return {"message": "Successfully unsubscribed from email notifications"}


@router.post("/resubscribe")
async def resubscribe(
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Resubscribe to email notifications."""
    prefs = await db.scalar(
        select(EmailPreferences).where(EmailPreferences.user_id == current_user.id)
    )
    
    if not prefs:
        raise HTTPException(status_code=404, detail="Email preferences not found")
    
    prefs.email_enabled = True
    prefs.unsubscribed_at = None
    prefs.unsubscribe_reason = None
    
    await db.commit()
    
    return {"message": "Successfully resubscribed to email notifications"}


@router.get("/queue/stats")
async def get_email_queue_stats(
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get email queue statistics (admin only)."""
    if current_user.role not in ['super_admin', 'agency_owner']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    queue_service = EmailQueueService(db)
    stats = await queue_service.get_queue_stats()
    
    return stats


@router.post("/test")
async def send_test_email(
    template_id: str = Query("welcome", description="Template to test"),
    to_email: Optional[EmailStr] = Query(None, description="Override recipient email"),
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Send test email (admin only)."""
    if current_user.role != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can send test emails")
    
    service = EmailNotificationService(db)
    
    # Use provided email or current user's email
    recipient = to_email or current_user.email
    
    success = await service.send_test_email(recipient, template_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test email")
    
    return {
        "message": "Test email sent successfully",
        "recipient": recipient,
        "template": template_id
    }


@router.post("/process-queue")
async def process_email_queue(
    batch_size: int = Query(100, le=1000),
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Manually process email queue (admin only)."""
    if current_user.role != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can process email queue")
    
    queue_service = EmailQueueService(db)
    results = await queue_service.process_queue(batch_size)
    
    return results


@router.post("/retry-failed")
async def retry_failed_emails(
    current_user: User = CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Retry failed emails (admin only)."""
    if current_user.role != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can retry failed emails")
    
    queue_service = EmailQueueService(db)
    results = await queue_service.retry_failed_emails()
    
    return results