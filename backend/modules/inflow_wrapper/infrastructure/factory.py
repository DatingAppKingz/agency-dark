"""
Factory for creating Inflow API clients
"""
import os
from typing import Optional

from core.external_api import APIConfigManager
from core.database import AsyncSession

from ..domain.schemas import InflowConfig
from .client_v2 import InflowClient, InflowWebhookHandler


async def create_inflow_client(
    db: Optional[AsyncSession] = None,
    config: Optional[InflowConfig] = None
) -> InflowClient:
    """
    Create an Inflow API client
    
    Args:
        db: Database session for loading config
        config: Direct config (overrides DB/env)
    
    Returns:
        Configured InflowClient instance
    """
    if config:
        return InflowClient(config)
        
    # Try to load from database if session provided
    if db:
        config_manager = APIConfigManager(db)
        api_config = await config_manager.get_config("inflow")
        
        if api_config:
            # Convert APIConfig to InflowConfig
            inflow_config = InflowConfig(
                base_url=api_config.base_url,
                api_key=api_config.credentials.api_key.get_secret_value() if api_config.credentials and api_config.credentials.api_key else None,
                timeout=api_config.timeout,
                max_retries=api_config.max_retries,
                auth_method="api_key" if api_config.credentials and api_config.credentials.api_key else "none"
            )
            return InflowClient(inflow_config)
    
    # Fall back to environment variables
    base_url = os.getenv("INFLOW_BASE_URL", "https://api.inflow.com")
    api_key = os.getenv("INFLOW_API_KEY")
    
    if not api_key:
        raise ValueError("Inflow API key not found in config or environment")
        
    inflow_config = InflowConfig(
        base_url=base_url,
        api_key=api_key,
        timeout=int(os.getenv("INFLOW_TIMEOUT", "30")),
        max_retries=int(os.getenv("INFLOW_MAX_RETRIES", "3")),
        auth_method="api_key"
    )
    
    return InflowClient(inflow_config)


def create_inflow_webhook_handler(webhook_secret: Optional[str] = None) -> InflowWebhookHandler:
    """
    Create an Inflow webhook handler
    
    Args:
        webhook_secret: Webhook secret for signature verification
        
    Returns:
        Configured InflowWebhookHandler instance
    """
    if not webhook_secret:
        webhook_secret = os.getenv("INFLOW_WEBHOOK_SECRET")
        
    if not webhook_secret:
        raise ValueError("Inflow webhook secret not provided")
        
    return InflowWebhookHandler(webhook_secret)