"""Generic webhook receiver endpoints."""

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from pydantic import BaseModel

from core.database import get_db
from services.webhook_service import WebhookService
from core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class WebhookResponse(BaseModel):
    status: str
    message: str = "Webhook received"
    provider: Optional[str] = None
    event_type: Optional[str] = None


@router.post("/webhooks/{provider}", response_model=WebhookResponse)
async def receive_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_agency_id: Optional[str] = Header(None, description="Agency ID for multi-tenant routing")
):
    """
    Generic webhook receiver endpoint.
    
    Supported providers:
    - onlyfans: OnlyFans webhooks
    - stripe: Stripe payment webhooks
    - inflow: Inflow API webhooks
    - custom: Custom webhooks
    
    The webhook will be validated based on provider-specific signature
    and forwarded to configured webhook URLs.
    """
    # Validate provider
    supported_providers = ["onlyfans", "stripe", "inflow", "custom"]
    if provider not in supported_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider}. Supported: {', '.join(supported_providers)}"
        )
    
    # Get request data
    body = await request.body()
    headers = dict(request.headers)
    
    # Parse agency ID if provided
    agency_id = None
    if x_agency_id:
        try:
            agency_id = int(x_agency_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid agency ID")
    
    # Process webhook
    service = WebhookService(db)
    
    try:
        result = await service.receive_webhook(
            provider=provider,
            headers=headers,
            body=body,
            agency_id=agency_id
        )
        
        return WebhookResponse(
            status="success",
            provider=provider,
            message=f"Webhook from {provider} processed successfully"
        )
        
    except Exception as e:
        logger.error(
            f"Webhook processing failed",
            extra={
                "provider": provider,
                "agency_id": agency_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        # Return success to prevent webhook retry storms
        # Error is logged for investigation
        return WebhookResponse(
            status="received",
            provider=provider,
            message="Webhook received (processing error logged)"
        )


@router.post("/webhooks/{provider}/{identifier}", response_model=WebhookResponse)
async def receive_webhook_with_identifier(
    provider: str,
    identifier: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook receiver with identifier (e.g., model ID, customer ID).
    
    This endpoint is for backwards compatibility with existing webhook
    configurations that include an identifier in the URL.
    """
    # Get request data
    body = await request.body()
    headers = dict(request.headers)
    
    # Add identifier to headers for processing
    headers["X-Webhook-Identifier"] = identifier
    
    # Process webhook
    service = WebhookService(db)
    
    try:
        result = await service.receive_webhook(
            provider=provider,
            headers=headers,
            body=body
        )
        
        return WebhookResponse(
            status="success",
            provider=provider,
            message=f"Webhook from {provider} for {identifier} processed"
        )
        
    except Exception as e:
        logger.error(
            f"Webhook processing failed",
            extra={
                "provider": provider,
                "identifier": identifier,
                "error": str(e)
            },
            exc_info=True
        )
        
        return WebhookResponse(
            status="received",
            provider=provider,
            message="Webhook received (processing error logged)"
        )


@router.get("/webhooks/test/{provider}")
async def test_webhook_endpoint(
    provider: str,
    event_type: str = "test.event",
    db: AsyncSession = Depends(get_db)
):
    """
    Test webhook endpoint for debugging.
    
    This endpoint simulates a webhook from the specified provider
    for testing webhook configuration and processing.
    """
    # Create test payload based on provider
    test_payloads = {
        "stripe": {
            "id": "evt_test_webhook",
            "object": "event",
            "api_version": "2023-10-16",
            "created": 1234567890,
            "data": {
                "object": {
                    "id": "test_123",
                    "object": "test",
                    "amount": 1000,
                    "currency": "usd"
                }
            },
            "livemode": False,
            "pending_webhooks": 1,
            "request": {
                "id": None,
                "idempotency_key": None
            },
            "type": event_type
        },
        "onlyfans": {
            "type": event_type,
            "data": {
                "user_id": "123456",
                "username": "testuser",
                "amount": 50.00,
                "message": "Test webhook"
            },
            "timestamp": "2024-01-31T12:00:00Z"
        },
        "inflow": {
            "event": event_type,
            "data": {
                "subscriber_id": "sub_123",
                "username": "testfan",
                "display_name": "Test Fan",
                "amount": 25.00
            },
            "webhook_id": "wh_test_123"
        },
        "custom": {
            "event_type": event_type,
            "data": {
                "test": True,
                "message": "This is a test webhook"
            },
            "timestamp": "2024-01-31T12:00:00Z"
        }
    }
    
    if provider not in test_payloads:
        raise HTTPException(
            status_code=400,
            detail=f"No test payload available for provider: {provider}"
        )
    
    # Process test webhook
    service = WebhookService(db)
    
    try:
        import json
        body = json.dumps(test_payloads[provider]).encode()
        
        # Create test headers
        headers = {
            "Content-Type": "application/json",
            "X-Test-Webhook": "true"
        }
        
        result = await service.receive_webhook(
            provider=provider,
            headers=headers,
            body=body
        )
        
        return {
            "status": "success",
            "message": f"Test webhook for {provider} processed",
            "payload": test_payloads[provider]
        }
        
    except Exception as e:
        logger.error(f"Test webhook failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Test webhook processing failed: {str(e)}"
        )