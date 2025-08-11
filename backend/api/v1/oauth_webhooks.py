"""
OAuth webhook handlers for external provider events.
Handles token revocation, account deactivation, and security alerts.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from oauth.models import ExternalOAuthToken
from oauth.consumer import ExternalOAuthManager
from core.database import get_db
from core.config import settings
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/oauth", tags=["OAuth Webhooks"])


class WebhookValidator:
    """
    Validates webhook signatures from OAuth providers.
    """
    
    @staticmethod
    def validate_google_webhook(
        request_body: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Validate Google webhook signature.
        """
        expected = hmac.new(
            secret.encode(),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def validate_instagram_webhook(
        request_body: bytes,
        signature: str,
        app_secret: str
    ) -> bool:
        """
        Validate Instagram/Facebook webhook signature.
        """
        expected = hmac.new(
            app_secret.encode(),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        expected_signature = f"sha256={expected}"
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def validate_microsoft_webhook(
        request_body: bytes,
        validation_token: Optional[str],
        client_state: Optional[str]
    ) -> bool:
        """
        Validate Microsoft webhook.
        Microsoft uses validation tokens for subscription confirmation.
        """
        if validation_token:
            # This is a subscription validation request
            return True
        
        # Validate client state if provided
        if client_state:
            expected_state = getattr(settings, "MICROSOFT_WEBHOOK_STATE", None)
            return client_state == expected_state
        
        return True
    
    @staticmethod
    def validate_ip_address(
        client_ip: str,
        provider: str
    ) -> bool:
        """
        Validate webhook source IP address.
        """
        # Provider IP ranges (should be maintained and updated)
        provider_ips = {
            "google": [
                # Google's webhook IP ranges
                "74.125.0.0/16",
                "209.85.128.0/17",
                "216.58.192.0/19"
            ],
            "instagram": [
                # Facebook/Instagram IP ranges
                "31.13.24.0/21",
                "66.220.144.0/20",
                "69.63.176.0/20"
            ],
            "microsoft": [
                # Microsoft Azure IP ranges
                "13.64.0.0/11",
                "20.33.0.0/16",
                "40.64.0.0/10"
            ]
        }
        
        # For development, allow all IPs
        if settings.ENVIRONMENT == "development":
            return True
        
        # Check if IP is in provider's range
        import ipaddress
        client_addr = ipaddress.ip_address(client_ip)
        
        for ip_range in provider_ips.get(provider, []):
            if client_addr in ipaddress.ip_network(ip_range):
                return True
        
        logger.warning(f"Webhook from unexpected IP: {client_ip} for provider {provider}")
        return False


@router.post("/google")
async def google_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_google_signature: Optional[str] = Header(None)
):
    """
    Handle Google OAuth webhooks.
    """
    try:
        # Get request body
        body = await request.body()
        
        # Validate signature
        if x_google_signature:
            secret = getattr(settings, "GOOGLE_WEBHOOK_SECRET", None)
            if secret:
                validator = WebhookValidator()
                if not validator.validate_google_webhook(body, x_google_signature, secret):
                    logger.warning("Invalid Google webhook signature")
                    raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook data
        data = json.loads(body)
        event_type = data.get("type")
        
        if event_type == "token.revoked":
            await handle_token_revocation(
                provider="google",
                user_identifier=data.get("sub"),
                db=db
            )
        
        elif event_type == "account.removed":
            await handle_account_removal(
                provider="google",
                user_identifier=data.get("sub"),
                db=db
            )
        
        return JSONResponse(content={"status": "ok"})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Google webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Google webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/instagram")
async def instagram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    Handle Instagram/Facebook OAuth webhooks.
    """
    try:
        # Get request body
        body = await request.body()
        
        # Validate signature
        if x_hub_signature_256:
            app_secret = getattr(settings, "INSTAGRAM_CLIENT_SECRET", None)
            if app_secret:
                validator = WebhookValidator()
                if not validator.validate_instagram_webhook(body, x_hub_signature_256, app_secret):
                    logger.warning("Invalid Instagram webhook signature")
                    raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook data
        data = json.loads(body)
        
        # Instagram uses a different webhook structure
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                field = change.get("field")
                value = change.get("value")
                
                if field == "permission":
                    # Permission revoked
                    await handle_permission_change(
                        provider="instagram",
                        user_id=entry.get("id"),
                        permissions=value,
                        db=db
                    )
                
                elif field == "account_status":
                    # Account status change
                    if value.get("status") == "deleted":
                        await handle_account_removal(
                            provider="instagram",
                            user_identifier=entry.get("id"),
                            db=db
                        )
        
        return JSONResponse(content={"status": "ok"})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Instagram webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Instagram webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/instagram")
async def instagram_webhook_verify(
    hub_mode: str,
    hub_challenge: str,
    hub_verify_token: str
):
    """
    Verify Instagram webhook subscription.
    """
    # Verify the token matches our configured token
    expected_token = getattr(settings, "INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "verify_token")
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Instagram webhook subscription verified")
        return Response(content=hub_challenge, media_type="text/plain")
    
    logger.warning(f"Invalid Instagram webhook verification: {hub_verify_token}")
    raise HTTPException(status_code=403, detail="Invalid verification token")


@router.post("/microsoft")
async def microsoft_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    validation_token: Optional[str] = None
):
    """
    Handle Microsoft OAuth webhooks.
    """
    # Handle subscription validation
    if validation_token:
        return Response(content=validation_token, media_type="text/plain")
    
    try:
        # Get request body
        body = await request.body()
        data = json.loads(body)
        
        # Process notifications
        for notification in data.get("value", []):
            resource = notification.get("resource")
            change_type = notification.get("changeType")
            
            if change_type == "deleted":
                # User or resource deleted
                user_id = resource.split("/")[-1] if resource else None
                if user_id:
                    await handle_account_removal(
                        provider="microsoft",
                        user_identifier=user_id,
                        db=db
                    )
        
        return JSONResponse(content={"status": "ok"})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Microsoft webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Microsoft webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/onlyfans")
async def onlyfans_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_onlyfans_signature: Optional[str] = Header(None)
):
    """
    Handle OnlyFans webhooks (placeholder for future implementation).
    """
    try:
        # Get request body
        body = await request.body()
        
        # TODO: Implement OnlyFans webhook signature validation
        # when their API becomes available
        
        # Parse webhook data
        data = json.loads(body)
        event_type = data.get("event")
        
        logger.info(f"Received OnlyFans webhook: {event_type}")
        
        # Placeholder for future event handling
        if event_type == "creator.subscription.cancelled":
            # Handle subscription cancellation
            pass
        elif event_type == "creator.account.suspended":
            # Handle account suspension
            pass
        
        return JSONResponse(content={"status": "ok"})
        
    except Exception as e:
        logger.error(f"OnlyFans webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# Helper functions for webhook processing

async def handle_token_revocation(
    provider: str,
    user_identifier: str,
    db: AsyncSession
):
    """
    Handle token revocation event from provider.
    """
    try:
        # Find tokens for this provider and user
        result = await db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.provider == provider
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            # Mark token as revoked
            token.expires_at = datetime.now(timezone.utc)
            logger.info(f"Revoked {provider} token for user {token.user_id}")
        
        await db.commit()
        
    except Exception as e:
        logger.error(f"Failed to handle token revocation: {e}")
        await db.rollback()


async def handle_account_removal(
    provider: str,
    user_identifier: str,
    db: AsyncSession
):
    """
    Handle account removal event from provider.
    """
    try:
        # Find and remove all tokens for this provider
        result = await db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.provider == provider
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            await db.delete(token)
            logger.info(f"Removed {provider} token for user {token.user_id}")
        
        await db.commit()
        
        # TODO: Notify user about disconnection
        
    except Exception as e:
        logger.error(f"Failed to handle account removal: {e}")
        await db.rollback()


async def handle_permission_change(
    provider: str,
    user_id: str,
    permissions: Dict[str, Any],
    db: AsyncSession
):
    """
    Handle permission change event from provider.
    """
    try:
        # Update token scope based on permission changes
        result = await db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.provider == provider
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            # Update scope based on new permissions
            new_scope = []
            for perm, granted in permissions.items():
                if granted:
                    new_scope.append(perm)
            
            token.scope = " ".join(new_scope)
            logger.info(f"Updated {provider} token scope for user {token.user_id}")
        
        await db.commit()
        
    except Exception as e:
        logger.error(f"Failed to handle permission change: {e}")
        await db.rollback()


@router.post("/security-alert")
async def security_alert_webhook(
    request: Request,
    provider: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle security alerts from OAuth providers.
    """
    try:
        # Get request body
        body = await request.body()
        data = json.loads(body)
        
        alert_type = data.get("type")
        severity = data.get("severity", "medium")
        affected_users = data.get("affected_users", [])
        
        logger.warning(
            f"Security alert from {provider}: {alert_type} "
            f"(severity: {severity}, affected users: {len(affected_users)})"
        )
        
        # Handle different alert types
        if alert_type == "suspicious_activity":
            # Revoke tokens for affected users
            for user_id in affected_users:
                await handle_token_revocation(provider, user_id, db)
        
        elif alert_type == "data_breach":
            # Force token refresh for all users of this provider
            result = await db.execute(
                select(ExternalOAuthToken).where(
                    ExternalOAuthToken.provider == provider
                )
            )
            tokens = result.scalars().all()
            
            for token in tokens:
                # Mark tokens as needing refresh
                token.expires_at = datetime.now(timezone.utc)
            
            await db.commit()
        
        # TODO: Send notifications to affected users
        # TODO: Log security event for audit
        
        return JSONResponse(content={"status": "acknowledged"})
        
    except Exception as e:
        logger.error(f"Security alert webhook error: {e}")
        raise HTTPException(status_code=500, detail="Alert processing failed")


@router.get("/health")
async def webhook_health():
    """
    Health check endpoint for webhook service.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "handlers": [
                "google",
                "instagram",
                "microsoft",
                "onlyfans"
            ]
        }
    )