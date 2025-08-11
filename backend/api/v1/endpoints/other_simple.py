"""
Other simplified endpoints for API keys, notifications, webhooks, search, media.
"""
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import CurrentUser

router = APIRouter(tags=["misc"])


# API Keys
@router.get("/api-keys")
async def list_api_keys(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """List API keys (returns empty list)."""
    return {"keys": [], "total": 0}


# Notifications
@router.get("/notifications")
async def list_notifications(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """List notifications (returns empty list)."""
    return {"notifications": [], "total": 0}


@router.get("/push-notifications/preferences")
async def get_notification_preferences(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get notification preferences."""
    return {
        "email_enabled": True,
        "push_enabled": False,
        "sms_enabled": False
    }


# Webhooks
@router.get("/webhooks")
async def list_webhooks(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """List webhooks (returns empty list)."""
    return {"webhooks": [], "total": 0}


# Search
@router.get("/search")
async def global_search(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., description="Search query")
):
    """Global search (returns empty results)."""
    return {
        "results": [],
        "total": 0,
        "query": q
    }


# Media
@router.post("/media-upload/upload-url")
async def get_upload_url(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get media upload URL (returns mock URL)."""
    return {
        "upload_url": "https://example.com/upload",
        "expires_at": datetime.now().isoformat()
    }


# Translations
@router.get("/translations")
async def get_translations(
    db: AsyncSession = Depends(get_db)
):
    """Get translations (returns basic translations) - no auth required."""
    return {
        "en": {
            "welcome": "Welcome",
            "logout": "Logout"
        }
    }