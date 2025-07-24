"""
Webhook handlers for real-time updates from external APIs.
"""
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.redis import redis_client
from core.domain.models import ModelProfile, Fan
from modules.api_orchestration.application.orchestrator import APIOrchestrator


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256"
) -> bool:
    """Verify webhook signature to ensure authenticity."""
    expected = hmac.new(
        secret.encode(),
        payload,
        getattr(hashlib, algorithm)
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/inflow/{model_id}")
async def handle_inflow_webhook(
    model_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle webhooks from Inflow API.
    
    Webhook events:
    - subscriber.new
    - subscriber.renewed
    - subscriber.expired
    - message.received
    - tip.received
    """
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile or not model_profile.inflow_api_key:
        raise HTTPException(status_code=404, detail="Model not found or Inflow not configured")
    
    # Get webhook payload
    payload = await request.body()
    
    # Verify signature if webhook secret is configured
    if model_profile.inflow_webhook_secret:
        signature = request.headers.get("X-Inflow-Signature", "")
        if not verify_webhook_signature(
            payload,
            signature,
            model_profile.inflow_webhook_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse webhook data
    data = await request.json()
    event_type = data.get("event")
    event_data = data.get("data", {})
    
    logger.info(f"Received Inflow webhook: {event_type} for model {model_id}")
    
    # Handle different event types
    if event_type == "subscriber.new":
        await handle_new_subscriber(db, model_profile, event_data, "inflow")
    elif event_type == "subscriber.renewed":
        await handle_subscriber_renewed(db, model_profile, event_data)
    elif event_type == "subscriber.expired":
        await handle_subscriber_expired(db, model_profile, event_data)
    elif event_type == "message.received":
        await handle_new_message(db, model_profile, event_data, "inflow")
    elif event_type == "tip.received":
        await handle_tip_received(db, model_profile, event_data)
    else:
        logger.warning(f"Unknown Inflow webhook event: {event_type}")
    
    return {"status": "ok"}


@router.post("/onlyfans/{model_id}")
async def handle_onlyfans_webhook(
    model_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle webhooks from OnlyFans API.
    
    Webhook events:
    - subscription.create
    - subscription.renew
    - subscription.expire
    - message.create
    - tip.create
    - post.purchase
    """
    # Get model profile
    result = await db.execute(
        select(ModelProfile).where(ModelProfile.id == model_id)
    )
    model_profile = result.scalar_one_or_none()
    
    if not model_profile or not model_profile.onlyfans_api_key:
        raise HTTPException(status_code=404, detail="Model not found or OnlyFans not configured")
    
    # Get webhook payload
    payload = await request.body()
    
    # Verify signature if webhook secret is configured
    if model_profile.onlyfans_webhook_secret:
        signature = request.headers.get("X-OnlyFans-Signature", "")
        if not verify_webhook_signature(
            payload,
            signature,
            model_profile.onlyfans_webhook_secret,
            algorithm="sha1"  # OnlyFans uses SHA1
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse webhook data
    data = await request.json()
    event_type = data.get("type")
    event_data = data.get("data", {})
    
    logger.info(f"Received OnlyFans webhook: {event_type} for model {model_id}")
    
    # Handle different event types
    if event_type == "subscription.create":
        await handle_new_subscriber(db, model_profile, event_data, "onlyfans")
    elif event_type == "subscription.renew":
        await handle_subscriber_renewed(db, model_profile, event_data)
    elif event_type == "subscription.expire":
        await handle_subscriber_expired(db, model_profile, event_data)
    elif event_type == "message.create":
        await handle_new_message(db, model_profile, event_data, "onlyfans")
    elif event_type == "tip.create":
        await handle_tip_received(db, model_profile, event_data)
    elif event_type == "post.purchase":
        await handle_post_purchase(db, model_profile, event_data)
    else:
        logger.warning(f"Unknown OnlyFans webhook event: {event_type}")
    
    return {"status": "ok"}


async def handle_new_subscriber(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any],
    source: str
):
    """Handle new subscriber event."""
    try:
        # Extract fan data based on source
        if source == "inflow":
            fan_external_id = data.get("subscriber_id")
            username = data.get("username")
            display_name = data.get("display_name")
        else:  # onlyfans
            fan_external_id = data.get("user_id")
            username = data.get("username")
            display_name = data.get("name")
        
        # Check if fan already exists
        query = select(Fan).where(
            Fan.model_id == model_profile.id,
            Fan.username == username
        )
        result = await db.execute(query)
        fan = result.scalar_one_or_none()
        
        if not fan:
            # Create new fan
            fan = Fan(
                model_id=model_profile.id,
                username=username,
                display_name=display_name,
                is_subscriber=True,
                is_paying=True,
                subscribed_at=datetime.utcnow()
            )
            db.add(fan)
        else:
            # Update existing fan
            fan.is_subscriber = True
            fan.is_paying = True
            fan.subscribed_at = datetime.utcnow()
        
        # Update source-specific ID
        if source == "onlyfans":
            fan.onlyfans_user_id = fan_external_id
        
        await db.commit()
        
        # Trigger notification
        await notify_new_subscriber(model_profile, fan)
        
    except Exception as e:
        logger.error(f"Failed to handle new subscriber: {e}")
        await db.rollback()


async def handle_subscriber_renewed(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any]
):
    """Handle subscriber renewal event."""
    # Similar implementation to handle_new_subscriber
    # Update subscription expiry date
    pass


async def handle_subscriber_expired(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any]
):
    """Handle subscriber expiration event."""
    try:
        username = data.get("username")
        
        # Find fan
        query = select(Fan).where(
            Fan.model_id == model_profile.id,
            Fan.username == username
        )
        result = await db.execute(query)
        fan = result.scalar_one_or_none()
        
        if fan:
            fan.is_subscriber = False
            fan.is_paying = False
            fan.expires_at = datetime.utcnow()
            await db.commit()
            
            # Trigger notification
            await notify_subscriber_expired(model_profile, fan)
        
    except Exception as e:
        logger.error(f"Failed to handle subscriber expiration: {e}")
        await db.rollback()


async def handle_new_message(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any],
    source: str
):
    """Handle new message event."""
    try:
        # Extract message data
        message_id = data.get("message_id") or data.get("id")
        sender_username = data.get("sender_username") or data.get("from_user", {}).get("username")
        text = data.get("text") or data.get("content")
        
        # Store message notification in Redis for real-time delivery
        notification = {
            "type": "new_message",
            "model_id": str(model_profile.id),
            "source": source,
            "message_id": message_id,
            "sender": sender_username,
            "text": text[:100] if text else None,  # First 100 chars
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish to Redis channel for Socket.IO
        channel = f"notifications:{model_profile.agency_id}"
        await redis_client.publish(channel, notification)
        
        # Trigger full message sync
        orchestrator = APIOrchestrator(db)
        await orchestrator.sync_all_data(
            model_profile,
            sync_inflow=(source == "inflow"),
            sync_onlyfans=(source == "onlyfans")
        )
        
    except Exception as e:
        logger.error(f"Failed to handle new message: {e}")


async def handle_tip_received(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any]
):
    """Handle tip received event."""
    try:
        amount = data.get("amount", 0)
        tipper_username = data.get("username") or data.get("from_user", {}).get("username")
        
        # Find fan
        query = select(Fan).where(
            Fan.model_id == model_profile.id,
            Fan.username == tipper_username
        )
        result = await db.execute(query)
        fan = result.scalar_one_or_none()
        
        if fan:
            fan.tip_count += 1
            fan.total_spent += amount
            await db.commit()
        
        # Send notification
        notification = {
            "type": "tip_received",
            "model_id": str(model_profile.id),
            "amount": amount,
            "from": tipper_username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        channel = f"notifications:{model_profile.agency_id}"
        await redis_client.publish(channel, notification)
        
    except Exception as e:
        logger.error(f"Failed to handle tip: {e}")
        await db.rollback()


async def handle_post_purchase(
    db: AsyncSession,
    model_profile: ModelProfile,
    data: Dict[str, Any]
):
    """Handle post purchase event (OnlyFans specific)."""
    try:
        amount = data.get("amount", 0)
        buyer_username = data.get("from_user", {}).get("username")
        post_id = data.get("post_id")
        
        # Find fan
        query = select(Fan).where(
            Fan.model_id == model_profile.id,
            Fan.username == buyer_username
        )
        result = await db.execute(query)
        fan = result.scalar_one_or_none()
        
        if fan:
            fan.ppv_purchased_count += 1
            fan.total_spent += amount
            await db.commit()
        
        # Send notification
        notification = {
            "type": "post_purchased",
            "model_id": str(model_profile.id),
            "amount": amount,
            "from": buyer_username,
            "post_id": post_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        channel = f"notifications:{model_profile.agency_id}"
        await redis_client.publish(channel, notification)
        
    except Exception as e:
        logger.error(f"Failed to handle post purchase: {e}")
        await db.rollback()


async def notify_new_subscriber(model_profile: ModelProfile, fan: Fan):
    """Send notification for new subscriber."""
    notification = {
        "type": "new_subscriber",
        "model_id": str(model_profile.id),
        "fan_id": str(fan.id),
        "username": fan.username,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    channel = f"notifications:{model_profile.agency_id}"
    await redis_client.publish(channel, notification)


async def notify_subscriber_expired(model_profile: ModelProfile, fan: Fan):
    """Send notification for expired subscriber."""
    notification = {
        "type": "subscriber_expired",
        "model_id": str(model_profile.id),
        "fan_id": str(fan.id),
        "username": fan.username,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    channel = f"notifications:{model_profile.agency_id}"
    await redis_client.publish(channel, notification)