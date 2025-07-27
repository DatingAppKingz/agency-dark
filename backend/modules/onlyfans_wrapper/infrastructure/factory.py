"""
Factory for creating OnlyFans API clients
"""
import os
from typing import Optional

from core.external_api import APIConfigManager
from core.database import AsyncSession

from ..domain.schemas import OnlyFansConfig
from .client_v2 import OnlyFansClient
from .webhooks import OnlyFansWebhookHandler


async def create_onlyfans_client(
    db: Optional[AsyncSession] = None,
    config: Optional[OnlyFansConfig] = None
) -> OnlyFansClient:
    """
    Create an OnlyFans API client
    
    Args:
        db: Database session for loading config
        config: Direct config (overrides DB/env)
    
    Returns:
        Configured OnlyFansClient instance
    """
    if config:
        return OnlyFansClient(config)
        
    # Try to load from database if session provided
    if db:
        config_manager = APIConfigManager(db)
        api_config = await config_manager.get_config("onlyfans")
        
        if api_config:
            # Convert APIConfig to OnlyFansConfig
            onlyfans_config = OnlyFansConfig(
                base_url=api_config.base_url,
                api_key=api_config.credentials.api_key.get_secret_value() if api_config.credentials and api_config.credentials.api_key else None,
                timeout=api_config.timeout,
                max_retries=api_config.max_retries,
                cookie=api_config.custom_headers.get('Cookie'),
                x_bc=api_config.custom_headers.get('X-BC')
            )
            return OnlyFansClient(onlyfans_config)
    
    # Fall back to environment variables
    base_url = os.getenv("ONLYFANS_BASE_URL", "https://onlyfansapi.com/api/v1")
    api_key = os.getenv("ONLYFANS_API_KEY")
    
    if not api_key:
        raise ValueError("OnlyFans API key not found in config or environment")
        
    onlyfans_config = OnlyFansConfig(
        base_url=base_url,
        api_key=api_key,
        timeout=int(os.getenv("ONLYFANS_TIMEOUT", "30")),
        max_retries=int(os.getenv("ONLYFANS_MAX_RETRIES", "3")),
        cookie=os.getenv("ONLYFANS_COOKIE"),
        x_bc=os.getenv("ONLYFANS_X_BC")
    )
    
    return OnlyFansClient(onlyfans_config)


def create_onlyfans_webhook_handler(webhook_secret: Optional[str] = None) -> OnlyFansWebhookHandler:
    """
    Create an OnlyFans webhook handler
    
    Args:
        webhook_secret: Webhook secret for signature verification
        
    Returns:
        Configured OnlyFansWebhookHandler instance
    """
    if not webhook_secret:
        webhook_secret = os.getenv("ONLYFANS_WEBHOOK_SECRET")
        
    if not webhook_secret:
        raise ValueError("OnlyFans webhook secret not provided")
        
    return OnlyFansWebhookHandler(webhook_secret)