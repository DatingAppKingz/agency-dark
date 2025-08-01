"""Generic webhook receiver service with signature validation and processing."""

import json
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import httpx

from core.logger import get_logger
from models.webhook import Webhook, WebhookDelivery, WebhookStatus
from core.errors import ValidationError as AppValidationError

logger = get_logger(__name__)


class WebhookService:
    """Service for receiving and processing webhooks."""
    
    SIGNATURE_ALGORITHMS = {
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Raw request body
            signature: Signature from headers
            secret: Webhook secret
            algorithm: Hash algorithm (sha1, sha256, sha512)
            
        Returns:
            True if signature is valid
        """
        if algorithm not in self.SIGNATURE_ALGORITHMS:
            raise AppValidationError(f"Unsupported algorithm: {algorithm}")
        
        # Calculate expected signature
        hash_func = self.SIGNATURE_ALGORITHMS[algorithm]
        expected = hmac.new(
            secret.encode(),
            payload,
            hash_func
        ).hexdigest()
        
        # Compare signatures (timing-safe)
        return hmac.compare_digest(expected, signature)
    
    def verify_stripe_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        tolerance: int = 300
    ) -> bool:
        """
        Verify Stripe webhook signature with timestamp validation.
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header
            secret: Webhook endpoint secret
            tolerance: Max age in seconds
            
        Returns:
            True if signature is valid and not expired
        """
        # Parse Stripe signature format
        elements = {}
        for element in signature.split(","):
            key, value = element.split("=", 1)
            elements[key] = value
        
        if "t" not in elements or "v1" not in elements:
            return False
        
        # Check timestamp
        timestamp = int(elements["t"])
        if abs(datetime.utcnow().timestamp() - timestamp) > tolerance:
            return False
        
        # Verify signature
        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, elements["v1"])
    
    def generate_signature(
        self,
        payload: bytes,
        secret: str,
        algorithm: str = "sha256"
    ) -> str:
        """
        Generate webhook signature.
        
        Args:
            payload: Request body
            secret: Webhook secret
            algorithm: Hash algorithm
            
        Returns:
            Hex-encoded signature
        """
        if algorithm not in self.SIGNATURE_ALGORITHMS:
            raise AppValidationError(f"Unsupported algorithm: {algorithm}")
        
        hash_func = self.SIGNATURE_ALGORITHMS[algorithm]
        return hmac.new(
            secret.encode(),
            payload,
            hash_func
        ).hexdigest()
    
    async def receive_webhook(
        self,
        provider: str,
        headers: Dict[str, str],
        body: bytes,
        agency_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Receive and validate incoming webhook.
        
        Args:
            provider: Webhook provider (onlyfans, stripe, inflow, etc.)
            headers: Request headers
            body: Raw request body
            agency_id: Optional agency ID for filtering
            
        Returns:
            Processed webhook data
        """
        # Parse body
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise AppValidationError("Invalid JSON payload")
        
        # Get signature header based on provider
        signature_headers = {
            "onlyfans": "X-OnlyFans-Signature",
            "stripe": "Stripe-Signature",
            "inflow": "X-Inflow-Signature",
            "custom": "X-Webhook-Signature"
        }
        
        signature_header = signature_headers.get(provider, "X-Webhook-Signature")
        signature = headers.get(signature_header, "")
        
        # Verify signature if configured
        webhook_configs = await self._get_webhook_configs(provider, agency_id)
        
        for config in webhook_configs:
            if config.secret:
                # Provider-specific verification
                if provider == "stripe":
                    valid = self.verify_stripe_signature(body, signature, config.secret)
                elif provider == "onlyfans":
                    valid = self.verify_signature(body, signature, config.secret, "sha1")
                else:
                    valid = self.verify_signature(body, signature, config.secret)
                
                if not valid:
                    logger.warning(
                        f"Invalid webhook signature for {provider}",
                        extra={"agency_id": agency_id, "config_id": config.id}
                    )
                    continue
            
            # Process webhook
            await self._process_webhook(config, provider, data, headers)
        
        return {
            "status": "received",
            "provider": provider,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _get_webhook_configs(
        self,
        provider: str,
        agency_id: Optional[int] = None
    ) -> List[Webhook]:
        """Get active webhook configurations for provider."""
        stmt = select(Webhook).where(
            and_(
                Webhook.status == WebhookStatus.ACTIVE,
                Webhook.is_active == True
            )
        )
        
        if agency_id:
            stmt = stmt.where(Webhook.agency_id == agency_id)
        
        result = await self.db.execute(stmt)
        webhooks = result.scalars().all()
        
        # Filter by provider events
        provider_events = {
            "onlyfans": ["subscription.", "message.", "tip.", "post."],
            "stripe": ["payment.", "charge.", "invoice.", "subscription."],
            "inflow": ["subscriber.", "message.", "tip."]
        }
        
        filtered = []
        for webhook in webhooks:
            # Check if webhook subscribes to provider events
            if "*" in webhook.events:
                filtered.append(webhook)
            else:
                for event_prefix in provider_events.get(provider, []):
                    if any(event.startswith(event_prefix) for event in webhook.events):
                        filtered.append(webhook)
                        break
        
        return filtered
    
    async def _process_webhook(
        self,
        config: Webhook,
        provider: str,
        data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> None:
        """Process webhook and create delivery record."""
        # Determine event type
        event_type = self._extract_event_type(provider, data)
        
        # Check if webhook is subscribed to this event
        if not config.is_subscribed_to(event_type):
            return
        
        # Create delivery record
        delivery = WebhookDelivery(
            webhook_id=config.id,
            event=event_type,
            payload=data
        )
        
        try:
            # Forward to configured URL
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                # Prepare headers
                forward_headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Provider": provider,
                    "X-Webhook-Event": event_type,
                    "X-Webhook-ID": str(delivery.id),
                    **config.headers
                }
                
                # Send request
                start_time = datetime.utcnow()
                response = await client.post(
                    config.url,
                    json=data,
                    headers=forward_headers
                )
                
                # Update delivery record
                delivery.status_code = response.status_code
                delivery.response_body = response.text[:2000]  # Limit response size
                delivery.response_time_ms = int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                )
                delivery.is_successful = 200 <= response.status_code < 300
                
                # Update webhook stats
                config.total_calls += 1
                if delivery.is_successful:
                    config.successful_calls += 1
                else:
                    config.failed_calls += 1
                config.last_called_at = datetime.utcnow().isoformat()
                
        except Exception as e:
            # Handle delivery failure
            delivery.is_successful = False
            delivery.error_message = str(e)[:500]
            
            # Update webhook stats
            config.total_calls += 1
            config.failed_calls += 1
            config.last_error = str(e)[:500]
            
            # Schedule retry if configured
            if delivery.attempt_count < config.max_retries:
                delivery.next_retry_at = (
                    datetime.utcnow() + timedelta(minutes=5 * delivery.attempt_count)
                ).isoformat()
            
            logger.error(
                f"Webhook delivery failed",
                extra={
                    "webhook_id": config.id,
                    "event": event_type,
                    "error": str(e)
                }
            )
        
        # Save delivery record
        self.db.add(delivery)
        await self.db.commit()
        
        logger.info(
            f"Webhook processed",
            extra={
                "webhook_id": config.id,
                "event": event_type,
                "success": delivery.is_successful,
                "response_time_ms": delivery.response_time_ms
            }
        )
    
    def _extract_event_type(self, provider: str, data: Dict[str, Any]) -> str:
        """Extract event type from webhook data."""
        if provider == "stripe":
            return data.get("type", "unknown")
        elif provider == "onlyfans":
            return data.get("type", "unknown")
        elif provider == "inflow":
            return data.get("event", "unknown")
        else:
            return data.get("event_type") or data.get("type") or "unknown"
    
    async def retry_failed_deliveries(self) -> int:
        """Retry failed webhook deliveries."""
        # Find deliveries that need retry
        now = datetime.utcnow()
        stmt = select(WebhookDelivery).where(
            and_(
                WebhookDelivery.is_successful == False,
                WebhookDelivery.next_retry_at != None,
                WebhookDelivery.next_retry_at <= now.isoformat()
            )
        )
        
        result = await self.db.execute(stmt)
        deliveries = result.scalars().all()
        
        retried = 0
        for delivery in deliveries:
            # Get webhook config
            webhook = await self.db.get(Webhook, delivery.webhook_id)
            if not webhook or not webhook.is_active:
                continue
            
            # Increment attempt count
            delivery.attempt_count += 1
            
            try:
                # Retry delivery
                async with httpx.AsyncClient(timeout=webhook.timeout_seconds) as client:
                    response = await client.post(
                        webhook.url,
                        json=delivery.payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Event": delivery.event,
                            "X-Webhook-Retry": str(delivery.attempt_count),
                            **webhook.headers
                        }
                    )
                    
                    delivery.status_code = response.status_code
                    delivery.response_body = response.text[:2000]
                    delivery.is_successful = 200 <= response.status_code < 300
                    
                    if delivery.is_successful:
                        webhook.successful_calls += 1
                    else:
                        webhook.failed_calls += 1
                    
            except Exception as e:
                delivery.error_message = str(e)[:500]
                webhook.failed_calls += 1
                
                # Schedule next retry if not exceeded
                if delivery.attempt_count < webhook.max_retries:
                    delivery.next_retry_at = (
                        datetime.utcnow() + timedelta(minutes=5 * delivery.attempt_count)
                    ).isoformat()
                else:
                    delivery.next_retry_at = None  # No more retries
            
            retried += 1
        
        if retried > 0:
            await self.db.commit()
        
        return retried