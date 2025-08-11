"""
External OAuth integration endpoints.
Handles OAuth flow with Google, Instagram, and other external providers.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import secrets
import logging
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from oauth.consumer import (
    OAuthProviderRegistry,
    ExternalOAuthManager,
    oauth_provider_registry
)
from oauth.compatibility import get_current_user, CurrentUser
from oauth.multitenancy import get_current_agency, AgencyContext
from models.user import User
from core.database import get_db
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["External OAuth"])


# Redis client for state storage
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.get("/connect/{provider}")
async def connect_provider(
    provider: str,
    request: Request,
    return_url: Optional[str] = Query(None, description="URL to return after OAuth"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser),
    agency: AgencyContext = Depends(get_current_agency)
):
    """
    Initiate OAuth flow with an external provider.
    
    Args:
        provider: Provider name (google, instagram, etc.)
        return_url: URL to redirect after OAuth completion
    """
    try:
        # Get provider from registry
        oauth_provider = oauth_provider_registry.get_provider(provider)
        
        if not oauth_provider:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider}' is not supported or not configured"
            )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in Redis with user info (expires in 10 minutes)
        state_data = {
            "user_id": str(current_user.id),
            "agency_id": str(agency.agency_id),
            "provider": provider,
            "return_url": return_url or "/dashboard",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await redis_client.setex(
            f"oauth_state:{state}",
            600,  # 10 minutes
            json.dumps(state_data)
        )
        
        # Get authorization URL
        auth_url, _ = await oauth_provider.get_authorization_url(state)
        
        logger.info(f"User {current_user.id} initiating OAuth with {provider}")
        
        return RedirectResponse(url=auth_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth with {provider}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect with {provider}"
        )


@router.get("/callback/{provider}")
async def provider_callback(
    provider: str,
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback from external provider.
    
    Args:
        provider: Provider name
        code: Authorization code
        state: State parameter for CSRF protection
        error: Error code if authorization failed
        error_description: Error description
    """
    try:
        # Check for errors
        if error:
            logger.error(f"OAuth error from {provider}: {error} - {error_description}")
            return RedirectResponse(
                url=f"/error?message=OAuth+failed:+{error}",
                status_code=302
            )
        
        # Validate state
        if not state:
            raise HTTPException(
                status_code=400,
                detail="Missing state parameter"
            )
        
        # Retrieve state from Redis
        state_key = f"oauth_state:{state}"
        state_json = await redis_client.get(state_key)
        
        if not state_json:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired state"
            )
        
        import json
        state_data = json.loads(state_json)
        
        # Delete state from Redis (one-time use)
        await redis_client.delete(state_key)
        
        # Validate provider matches
        if state_data["provider"] != provider:
            raise HTTPException(
                status_code=400,
                detail="Provider mismatch"
            )
        
        # Get provider from registry
        oauth_provider = oauth_provider_registry.get_provider(provider)
        
        if not oauth_provider:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider}' not configured"
            )
        
        # Exchange code for token
        token_data = await oauth_provider.exchange_code_for_token(code)
        
        # Get user info from provider
        user_info = await oauth_provider.get_user_info(token_data["access_token"])
        parsed_info = await oauth_provider.parse_user_info(user_info)
        
        # Link external account
        manager = ExternalOAuthManager(db)
        
        expires_at = None
        if "expires_in" in token_data:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_data["expires_in"]
            )
        
        await manager.link_external_account(
            user_id=state_data["user_id"],
            agency_id=state_data["agency_id"],
            provider=provider,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            raw_data={
                "token_data": token_data,
                "user_info": parsed_info
            }
        )
        
        logger.info(f"Successfully linked {provider} account for user {state_data['user_id']}")
        
        # Redirect to return URL
        return RedirectResponse(
            url=state_data.get("return_url", "/dashboard"),
            status_code=302
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {e}")
        return RedirectResponse(
            url=f"/error?message=OAuth+callback+failed",
            status_code=302
        )


@router.post("/disconnect/{provider}")
async def disconnect_provider(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser)
):
    """
    Disconnect an external OAuth provider.
    
    Args:
        provider: Provider name to disconnect
    """
    try:
        manager = ExternalOAuthManager(db)
        
        # Check if account is linked
        token = await manager.get_external_token(
            user_id=str(current_user.id),
            provider=provider
        )
        
        if not token:
            raise HTTPException(
                status_code=404,
                detail=f"No {provider} account linked"
            )
        
        # TODO: Optionally revoke token with provider
        # This would require provider-specific implementation
        
        # Unlink account
        success = await manager.unlink_external_account(
            user_id=str(current_user.id),
            provider=provider
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to disconnect account"
            )
        
        logger.info(f"User {current_user.id} disconnected {provider} account")
        
        return JSONResponse(
            content={
                "message": f"Successfully disconnected {provider} account"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect {provider}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to disconnect provider"
        )


@router.get("/providers")
async def list_providers():
    """
    List all available OAuth providers.
    """
    providers = []
    
    for provider_name in oauth_provider_registry.list_providers():
        provider = oauth_provider_registry.get_provider(provider_name)
        providers.append({
            "name": provider_name,
            "display_name": provider_name.title(),
            "enabled": True,
            "scope": provider.scope
        })
    
    # Add disabled providers for UI completeness
    all_providers = ["google", "instagram", "microsoft", "onlyfans"]
    for provider_name in all_providers:
        if provider_name not in oauth_provider_registry.list_providers():
            providers.append({
                "name": provider_name,
                "display_name": provider_name.title(),
                "enabled": False,
                "scope": None
            })
    
    return JSONResponse(content={"providers": providers})


@router.get("/accounts")
async def list_connected_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser)
):
    """
    List all connected external accounts for the current user.
    """
    try:
        manager = ExternalOAuthManager(db)
        accounts = await manager.get_user_external_accounts(str(current_user.id))
        
        # Enhance with provider info
        enhanced_accounts = []
        for account in accounts:
            provider = oauth_provider_registry.get_provider(account["provider"])
            enhanced_accounts.append({
                **account,
                "display_name": account["provider"].title(),
                "can_refresh": provider is not None and account.get("needs_refresh", False)
            })
        
        return JSONResponse(
            content={
                "accounts": enhanced_accounts,
                "user_id": str(current_user.id)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to list connected accounts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve connected accounts"
        )


@router.post("/refresh/{provider}")
async def refresh_provider_token(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser)
):
    """
    Refresh token for an external provider.
    
    Args:
        provider: Provider name
    """
    try:
        manager = ExternalOAuthManager(db)
        
        # Refresh the token
        token = await manager.refresh_external_token(
            user_id=str(current_user.id),
            provider=provider
        )
        
        if not token:
            raise HTTPException(
                status_code=404,
                detail=f"No {provider} account linked or refresh failed"
            )
        
        return JSONResponse(
            content={
                "message": f"Successfully refreshed {provider} token",
                "expires_at": token.expires_at.isoformat() if token.expires_at else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh {provider} token: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh token"
        )


@router.get("/test/{provider}")
async def test_provider_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser)
):
    """
    Test connection to an external provider.
    
    Args:
        provider: Provider name
    """
    try:
        manager = ExternalOAuthManager(db)
        
        # Get token
        token = await manager.get_external_token(
            user_id=str(current_user.id),
            provider=provider
        )
        
        if not token:
            return JSONResponse(
                content={
                    "connected": False,
                    "message": f"No {provider} account linked"
                }
            )
        
        # Check if token needs refresh
        if token.needs_refresh():
            # Try to refresh
            token = await manager.refresh_external_token(
                user_id=str(current_user.id),
                provider=provider
            )
            
            if not token:
                return JSONResponse(
                    content={
                        "connected": False,
                        "message": "Token expired and refresh failed"
                    }
                )
        
        # Get provider
        oauth_provider = oauth_provider_registry.get_provider(provider)
        
        if not oauth_provider:
            return JSONResponse(
                content={
                    "connected": False,
                    "message": f"Provider {provider} not configured"
                }
            )
        
        # Try to get user info as a test
        try:
            user_info = await oauth_provider.get_user_info(token.access_token)
            
            return JSONResponse(
                content={
                    "connected": True,
                    "message": "Connection successful",
                    "user_info": await oauth_provider.parse_user_info(user_info)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to get user info from {provider}: {e}")
            return JSONResponse(
                content={
                    "connected": False,
                    "message": f"Connection test failed: {str(e)}"
                }
            )
        
    except Exception as e:
        logger.error(f"Failed to test {provider} connection: {e}")
        raise HTTPException(
            status_code=500,
            detail="Connection test failed"
        )