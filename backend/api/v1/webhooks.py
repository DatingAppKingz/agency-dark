"""
Webhook management API endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import aiohttp

from core.database import get_db
from core.auth.dependencies import get_current_user
from modules.users.domain.models import User
from core.webhooks.webhook_models import (
    Webhook, WebhookCreate, WebhookUpdate, WebhookResponse,
    WebhookDeliveryResponse, WebhookEvent
)
from core.webhooks.webhook_manager import webhook_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    webhook_data: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new webhook
    """
    # Verify user has permission
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Agency membership required")
    
    # Test webhook URL is reachable
    try:
        test_result = await webhook_manager.sender.test_webhook(
            str(webhook_data.url), 
            timeout=10
        )
        if not test_result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Webhook URL test failed: {test_result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to test webhook URL: {str(e)}"
        )
    
    # Create webhook
    webhook = await webhook_manager.create_webhook(
        agency_id=UUID(current_user.agency_id),
        url=str(webhook_data.url),
        events=webhook_data.events,
        description=webhook_data.description,
        custom_headers=webhook_data.custom_headers,
        db=db
    )
    
    # Update webhook configuration
    updates = {
        "is_active": webhook_data.is_active,
        "retry_enabled": webhook_data.retry_enabled,
        "max_retries": webhook_data.max_retries,
        "timeout_seconds": webhook_data.timeout_seconds
    }
    
    webhook = await webhook_manager.update_webhook(
        webhook.id, updates, db
    )
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        description=webhook.description,
        is_active=webhook.is_active,
        retry_enabled=webhook.retry_enabled,
        max_retries=webhook.max_retries,
        timeout_seconds=webhook.timeout_seconds,
        custom_headers=webhook.custom_headers,
        total_deliveries=webhook.total_deliveries,
        successful_deliveries=webhook.successful_deliveries,
        failed_deliveries=webhook.failed_deliveries,
        last_delivery_at=webhook.last_delivery_at,
        last_success_at=webhook.last_success_at,
        last_failure_at=webhook.last_failure_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at
    )


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    is_active: Optional[bool] = None,
    event: Optional[WebhookEvent] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all webhooks for the agency
    """
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Agency membership required")
    
    # Build query
    query = select(Webhook).where(Webhook.agency_id == current_user.agency_id)
    
    if is_active is not None:
        query = query.where(Webhook.is_active == is_active)
    
    if event:
        query = query.where(Webhook.events.contains([event.value]))
    
    query = query.order_by(Webhook.created_at.desc())
    
    result = await db.execute(query)
    webhooks = result.scalars().all()
    
    return [
        WebhookResponse(
            id=webhook.id,
            url=webhook.url,
            events=webhook.events,
            description=webhook.description,
            is_active=webhook.is_active,
            retry_enabled=webhook.retry_enabled,
            max_retries=webhook.max_retries,
            timeout_seconds=webhook.timeout_seconds,
            custom_headers=webhook.custom_headers,
            total_deliveries=webhook.total_deliveries,
            successful_deliveries=webhook.successful_deliveries,
            failed_deliveries=webhook.failed_deliveries,
            last_delivery_at=webhook.last_delivery_at,
            last_success_at=webhook.last_success_at,
            last_failure_at=webhook.last_failure_at,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at
        )
        for webhook in webhooks
    ]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific webhook
    """
    webhook = await db.get(Webhook, webhook_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if webhook.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        description=webhook.description,
        is_active=webhook.is_active,
        retry_enabled=webhook.retry_enabled,
        max_retries=webhook.max_retries,
        timeout_seconds=webhook.timeout_seconds,
        custom_headers=webhook.custom_headers,
        total_deliveries=webhook.total_deliveries,
        successful_deliveries=webhook.successful_deliveries,
        failed_deliveries=webhook.failed_deliveries,
        last_delivery_at=webhook.last_delivery_at,
        last_success_at=webhook.last_success_at,
        last_failure_at=webhook.last_failure_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at
    )


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    webhook_update: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a webhook
    """
    webhook = await db.get(Webhook, webhook_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if webhook.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Test new URL if provided
    if webhook_update.url:
        try:
            test_result = await webhook_manager.sender.test_webhook(
                str(webhook_update.url),
                timeout=10
            )
            if not test_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Webhook URL test failed: {test_result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to test webhook URL: {str(e)}"
            )
    
    # Update webhook
    updates = webhook_update.dict(exclude_unset=True)
    if "url" in updates:
        updates["url"] = str(updates["url"])
    if "events" in updates:
        updates["events"] = [e.value if hasattr(e, 'value') else e for e in updates["events"]]
    
    webhook = await webhook_manager.update_webhook(webhook_id, updates, db)
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        description=webhook.description,
        is_active=webhook.is_active,
        retry_enabled=webhook.retry_enabled,
        max_retries=webhook.max_retries,
        timeout_seconds=webhook.timeout_seconds,
        custom_headers=webhook.custom_headers,
        total_deliveries=webhook.total_deliveries,
        successful_deliveries=webhook.successful_deliveries,
        failed_deliveries=webhook.failed_deliveries,
        last_delivery_at=webhook.last_delivery_at,
        last_success_at=webhook.last_success_at,
        last_failure_at=webhook.last_failure_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a webhook
    """
    webhook = await db.get(Webhook, webhook_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if webhook.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await webhook_manager.delete_webhook(webhook_id, db)
    
    return {"message": "Webhook deleted successfully"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a test event to the webhook
    """
    webhook = await db.get(Webhook, webhook_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if webhook.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Send test event
    test_result = await webhook_manager.sender.test_webhook(
        webhook.url,
        timeout=webhook.timeout_seconds
    )
    
    if not test_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=f"Test failed: {test_result.get('error', 'Unknown error')}"
        )
    
    return {
        "success": True,
        "response_time_ms": test_result["response_time_ms"],
        "status_code": test_result["status_code"],
        "message": "Test webhook sent successfully"
    }


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def get_webhook_deliveries(
    webhook_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get delivery history for a webhook
    """
    webhook = await db.get(Webhook, webhook_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if webhook.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    deliveries = await webhook_manager.get_webhook_deliveries(
        webhook_id, limit, offset, db
    )
    
    return [
        WebhookDeliveryResponse(
            id=delivery.id,
            webhook_id=delivery.webhook_id,
            event_type=delivery.event_type,
            event_id=delivery.event_id,
            status=delivery.status,
            attempts=delivery.attempts,
            response_status_code=delivery.response_status_code,
            response_time_ms=delivery.response_time_ms,
            error_message=delivery.error_message,
            created_at=delivery.created_at,
            delivered_at=delivery.delivered_at
        )
        for delivery in deliveries
    ]


@router.post("/retry-failed")
async def retry_failed_webhooks(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retry failed webhook deliveries (admin only)
    """
    # Check if user is admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Schedule retry task
    background_tasks.add_task(
        webhook_manager.retry_failed_deliveries,
        db
    )
    
    return {"message": "Failed webhook retry scheduled"}


# Example webhook payload documentation endpoints
@router.get("/docs/events")
async def get_webhook_events():
    """
    Get list of available webhook events and their payload schemas
    """
    from core.webhooks.webhook_models import (
        MessageWebhookPayload, PaymentWebhookPayload, FanWebhookPayload
    )
    
    return {
        "events": [
            {
                "event": event.value,
                "description": event.name.replace("_", " ").title(),
                "category": event.value.split(".")[0]
            }
            for event in WebhookEvent
        ],
        "payload_examples": {
            "message": MessageWebhookPayload.schema()["properties"]["data"]["example"],
            "payment": PaymentWebhookPayload.schema()["properties"]["data"]["example"],
            "fan": FanWebhookPayload.schema()["properties"]["data"]["example"]
        }
    }


@router.get("/docs/signature")
async def get_signature_verification_docs():
    """
    Get webhook signature verification documentation
    """
    return {
        "algorithm": "HMAC-SHA256",
        "header": "X-Webhook-Signature",
        "format": "sha256=<hex_digest>",
        "example_code": {
            "python": """import hmac
import hashlib

def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)""",
            "javascript": """const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
    const expected = 'sha256=' + crypto
        .createHmac('sha256', secret)
        .update(payload)
        .digest('hex');
    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(signature)
    );
}"""
        }
    }
