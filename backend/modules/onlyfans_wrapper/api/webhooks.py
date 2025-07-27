"""
OnlyFans webhook API endpoints
"""
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.dependencies import get_db, get_current_user
from core.domain.models import User
from core.external_api.webhooks import WebhookProcessor

from ..infrastructure.factory import create_onlyfans_webhook_handler
from ..infrastructure.webhooks import get_event_handler_mapping


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/onlyfans", tags=["onlyfans-webhooks"])

# Global webhook processor
webhook_processor = WebhookProcessor(max_workers=5)


@router.on_event("startup")
async def startup_webhook_processor():
    """Start webhook processor on app startup"""
    await webhook_processor.start()
    logger.info("OnlyFans webhook processor started")


@router.on_event("shutdown")
async def shutdown_webhook_processor():
    """Stop webhook processor on app shutdown"""
    await webhook_processor.stop()
    logger.info("OnlyFans webhook processor stopped")


@router.post("/events")
async def handle_onlyfans_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming OnlyFans webhook events
    
    This endpoint receives and processes webhook events from OnlyFans.
    Events are processed asynchronously in the background.
    """
    try:
        # Create webhook handler
        handler = create_onlyfans_webhook_handler()
        
        # Get webhook secret from environment or config
        import os
        webhook_secret = os.getenv("ONLYFANS_WEBHOOK_SECRET", "")
        
        # Handle the webhook request
        result = await handler.handle_webhook(request, webhook_secret)
        
        # Get the parsed event from the handler
        body = await request.body()
        payload = await request.json()
        event = handler.parse_event(payload)
        
        # Get event handlers
        event_handlers = get_event_handler_mapping(db)
        
        # Find handler for this event type
        event_handler = event_handlers.get(event.type)
        
        if event_handler:
            # Process webhook asynchronously
            await webhook_processor.add_webhook(event_handler, event)
            logger.info(f"Queued OnlyFans webhook event: {event.type} (ID: {event.id})")
        else:
            logger.warning(f"No handler for OnlyFans webhook event type: {event.type}")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling OnlyFans webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/config", dependencies=[Depends(get_current_user)])
async def get_webhook_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get webhook configuration for OnlyFans
    
    Returns the webhook URL and available event types.
    Requires authentication.
    """
    # Check if user has permission to view webhook config
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    import os
    base_url = os.getenv("API_BASE_URL", "https://api.yourdomain.com")
    
    return {
        "webhook_url": f"{base_url}/api/v1/webhooks/onlyfans/events",
        "available_events": [
            "subscription.create",
            "subscription.renew",
            "subscription.cancel",
            "tip",
            "message.purchase",
            "post.purchase",
            "stream.tip",
            "referral.transaction",
            "chargeback"
        ],
        "signature_header": "x-onlyfans-signature",
        "signature_format": "sha256=<signature>"
    }


@router.post("/test", dependencies=[Depends(get_current_user)])
async def test_webhook_handler(
    event_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Test webhook handler with a sample event
    
    This endpoint allows testing webhook handlers without actual events from OnlyFans.
    Requires admin permissions.
    """
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can test webhooks")
        
    # Create a test event
    from datetime import datetime
    from core.external_api.webhooks import WebhookEvent
    
    test_event = WebhookEvent(
        id=f"test_{datetime.utcnow().timestamp()}",
        type=event_type,
        timestamp=datetime.utcnow(),
        data={
            "test": True,
            "creator_id": str(current_user.id),
            "user_id": "test_fan_123",
            "amount": 10.00,
            "currency": "USD",
            "message": "This is a test event"
        }
    )
    
    # Get event handlers
    event_handlers = get_event_handler_mapping(db)
    
    # Find handler for this event type
    event_handler = event_handlers.get(event_type)
    
    if not event_handler:
        raise HTTPException(status_code=404, detail=f"No handler for event type: {event_type}")
        
    try:
        # Execute handler directly (not async)
        await event_handler(test_event)
        
        return {
            "status": "success",
            "message": f"Test event {event_type} processed successfully",
            "event_id": test_event.id
        }
    except Exception as e:
        logger.error(f"Error in test webhook handler: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Handler error: {str(e)}")


@router.get("/stats", dependencies=[Depends(get_current_user)])
async def get_webhook_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get webhook processing statistics
    
    Returns information about webhook processing queue and workers.
    Requires authentication.
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    return {
        "queue_size": webhook_processor.queue.qsize(),
        "max_workers": webhook_processor.max_workers,
        "active_workers": len([w for w in webhook_processor.workers if not w.done()]),
        "is_running": webhook_processor.running
    }