"""Webhook queue management endpoints."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from models.user import User
from services.webhook_queue import enqueue_webhook, get_webhook_processor, QueuePriority
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/queue")


class WebhookEnqueueRequest(BaseModel):
    """Request to enqueue webhook."""
    event: str
    payload: dict
    webhook_ids: Optional[List[int]] = None
    priority: QueuePriority = QueuePriority.NORMAL


class WebhookEnqueueResponse(BaseModel):
    """Response from webhook enqueue."""
    task_ids: List[str]
    count: int


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""
    queue_sizes: dict
    workers: dict
    running: bool


@router.post("/enqueue", response_model=WebhookEnqueueResponse)
async def enqueue_webhook_endpoint(
    request: WebhookEnqueueRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enqueue webhook for delivery.
    
    Requires admin or manager role.
    """
    # Check permission
    check_permission(current_user, "webhooks", "write")
    
    try:
        # Enqueue webhook
        task_ids = await enqueue_webhook(
            event=request.event,
            payload=request.payload,
            webhook_ids=request.webhook_ids,
            priority=request.priority
        )
        
        return WebhookEnqueueResponse(
            task_ids=task_ids,
            count=len(task_ids)
        )
    
    except Exception as e:
        logger.error(f"Failed to enqueue webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get webhook queue statistics.
    
    Requires authentication.
    """
    try:
        processor = await get_webhook_processor()
        stats = processor.get_stats()
        
        return QueueStatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/test")
async def test_webhook_delivery(
    webhook_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Test webhook delivery by sending a test event.
    
    Requires admin role.
    """
    # Check permission
    check_permission(current_user, "webhooks", "admin")
    
    try:
        # Create test payload
        test_payload = {
            "event": "test.webhook",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "message": "This is a test webhook delivery",
                "user": current_user.email
            }
        }
        
        # Enqueue test webhook
        task_ids = await enqueue_webhook(
            event="test.webhook",
            payload=test_payload,
            webhook_ids=[webhook_id],
            priority=QueuePriority.HIGH
        )
        
        return {
            "message": "Test webhook enqueued",
            "task_id": task_ids[0] if task_ids else None
        }
    
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )