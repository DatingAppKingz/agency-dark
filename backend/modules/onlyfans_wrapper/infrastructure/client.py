"""
OnlyFans API client implementation.

This module implements the HTTP client for interacting with OnlyFansAPI.com.
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin

import httpx
from httpx import AsyncClient, Response, HTTPError

from ..domain.interfaces import IOnlyFansClient
from ..domain.schemas import (
    OnlyFansConfig,
    OnlyFansProfile,
    OnlyFansFan,
    OnlyFansPost,
    OnlyFansMessage,
    OnlyFansTransaction,
    OnlyFansStatistics,
    OnlyFansMedia,
    OnlyFansVault,
    OnlyFansList,
    OnlyFansNotification,
    OnlyFansAPIError
)


logger = logging.getLogger(__name__)


class OnlyFansAPIException(Exception):
    """Exception raised by OnlyFans API client."""
    
    def __init__(self, error: OnlyFansAPIError, status_code: int = 500):
        self.error = error
        self.status_code = status_code
        super().__init__(f"OnlyFans API Error: {error.message or error.error}")


class OnlyFansClient(IOnlyFansClient):
    """HTTP client for OnlyFans API."""
    
    def __init__(self, config: OnlyFansConfig):
        self.config = config
        self._client: Optional[AsyncClient] = None
        self._authenticated = False
        
    async def __aenter__(self):
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if not self._client:
            headers = {
                "User-Agent": self.config.user_agent or "AgencyDark/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.config.api_key
            }
            
            # Add OnlyFans specific headers if provided
            if self.config.cookie:
                headers["Cookie"] = self.config.cookie
            if self.config.x_bc:
                headers["X-BC"] = self.config.x_bc
                
            self._client = AsyncClient(
                base_url=str(self.config.base_url),
                timeout=self.config.timeout,
                headers=headers
            )
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Response:
        """Make HTTP request with retry logic."""
        await self._ensure_client()
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.request(method, endpoint, **kwargs)
                
                # Check for API errors
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        error = OnlyFansAPIError(**error_data)
                    except:
                        error = OnlyFansAPIError(
                            error=f"HTTP {response.status_code}",
                            message=response.text
                        )
                    raise OnlyFansAPIException(error, response.status_code)
                
                response.raise_for_status()
                return response
                
            except HTTPError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.config.max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {self.config.max_retries} attempts: {e}")
        
        raise last_error
    
    async def authenticate(self) -> bool:
        """Authenticate with OnlyFans API."""
        try:
            # Test authentication by getting profile
            await self.get_profile()
            self._authenticated = True
            return True
        except Exception as e:
            logger.error(f"OnlyFans authentication failed: {e}")
            return False
    
    async def get_profile(self, username: Optional[str] = None) -> OnlyFansProfile:
        """Get profile information."""
        endpoint = f"/profile/{username}" if username else "/profile/me"
        response = await self._make_request("GET", endpoint)
        data = response.json()
        return OnlyFansProfile(**data)
    
    async def update_profile(
        self,
        name: Optional[str] = None,
        about: Optional[str] = None,
        subscription_price: Optional[Decimal] = None
    ) -> OnlyFansProfile:
        """Update profile information."""
        payload = {}
        if name is not None:
            payload["name"] = name
        if about is not None:
            payload["about"] = about
        if subscription_price is not None:
            payload["price"] = str(subscription_price)
            
        response = await self._make_request("PATCH", "/profile/me", json=payload)
        data = response.json()
        return OnlyFansProfile(**data)
    
    async def get_fans(
        self,
        limit: int = 100,
        offset: int = 0,
        filter_type: Optional[str] = None
    ) -> List[OnlyFansFan]:
        """Get list of fans/subscribers."""
        params = {
            "limit": limit,
            "offset": offset
        }
        if filter_type:
            params["type"] = filter_type
            
        response = await self._make_request("GET", "/fans", params=params)
        data = response.json()
        return [OnlyFansFan(**item) for item in data.get("list", [])]
    
    async def get_fan(self, fan_id: str) -> OnlyFansFan:
        """Get specific fan details."""
        response = await self._make_request("GET", f"/fans/{fan_id}")
        data = response.json()
        return OnlyFansFan(**data)
    
    async def restrict_fan(self, fan_id: str) -> bool:
        """Restrict a fan from viewing content."""
        response = await self._make_request("POST", f"/fans/{fan_id}/restrict")
        return response.status_code == 200
    
    async def unrestrict_fan(self, fan_id: str) -> bool:
        """Remove restriction from a fan."""
        response = await self._make_request("POST", f"/fans/{fan_id}/unrestrict")
        return response.status_code == 200
    
    async def get_posts(
        self,
        limit: int = 100,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[OnlyFansPost]:
        """Get posts from timeline."""
        params = {
            "limit": limit,
            "offset": offset,
            "skip_archived": not include_archived
        }
        
        response = await self._make_request("GET", "/posts", params=params)
        data = response.json()
        return [OnlyFansPost(**item) for item in data.get("list", [])]
    
    async def create_post(
        self,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansPost:
        """Create a new post."""
        payload = {}
        if text:
            payload["text"] = text
        if media_ids:
            payload["mediaIds"] = media_ids
        if price is not None:
            payload["price"] = str(price)
        if is_paid:
            payload["isPaid"] = is_paid
            
        response = await self._make_request("POST", "/posts", json=payload)
        data = response.json()
        return OnlyFansPost(**data)
    
    async def delete_post(self, post_id: str) -> bool:
        """Delete a post."""
        response = await self._make_request("DELETE", f"/posts/{post_id}")
        return response.status_code in [200, 204]
    
    async def get_messages(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansMessage]:
        """Get messages/chats."""
        endpoint = f"/chats/{user_id}/messages" if user_id else "/chats"
        params = {
            "limit": limit,
            "offset": offset
        }
        
        response = await self._make_request("GET", endpoint, params=params)
        data = response.json()
        return [OnlyFansMessage(**item) for item in data.get("list", [])]
    
    async def send_message(
        self,
        user_id: str,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansMessage:
        """Send a message to a user."""
        payload = {
            "userId": user_id
        }
        if text:
            payload["text"] = text
        if media_ids:
            payload["mediaIds"] = media_ids
        if price is not None:
            payload["price"] = str(price)
            payload["isPaid"] = True
        elif is_paid:
            payload["isPaid"] = is_paid
            
        response = await self._make_request("POST", "/messages", json=payload)
        data = response.json()
        return OnlyFansMessage(**data)
    
    async def send_mass_message(
        self,
        user_ids: List[str],
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Send mass message to multiple users."""
        payload = {
            "userIds": user_ids
        }
        if text:
            payload["text"] = text
        if media_ids:
            payload["mediaIds"] = media_ids
        if price is not None:
            payload["price"] = str(price)
            
        response = await self._make_request("POST", "/messages/mass", json=payload)
        return response.json()
    
    async def get_transactions(
        self,
        type_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansTransaction]:
        """Get financial transactions."""
        params = {
            "limit": limit,
            "offset": offset
        }
        if type_filter:
            params["type"] = type_filter
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()
            
        response = await self._make_request("GET", "/transactions", params=params)
        data = response.json()
        return [OnlyFansTransaction(**item) for item in data.get("list", [])]
    
    async def get_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> OnlyFansStatistics:
        """Get account statistics."""
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat()
        }
        
        response = await self._make_request("GET", "/statistics", params=params)
        data = response.json()
        # Add period dates to the response
        data["period_start"] = start_date
        data["period_end"] = end_date
        return OnlyFansStatistics(**data)
    
    async def upload_media(
        self,
        file: BinaryIO,
        media_type: str,
        filename: Optional[str] = None
    ) -> OnlyFansMedia:
        """Upload media file."""
        files = {
            "file": (filename or "upload", file, f"{media_type}/*")
        }
        data = {
            "type": media_type
        }
        
        response = await self._make_request(
            "POST",
            "/media/upload",
            files=files,
            data=data
        )
        data = response.json()
        return OnlyFansMedia(**data)
    
    async def get_vault(
        self,
        limit: int = 100,
        offset: int = 0,
        media_type: Optional[str] = None
    ) -> List[OnlyFansVault]:
        """Get vault items."""
        params = {
            "limit": limit,
            "offset": offset
        }
        if media_type:
            params["type"] = media_type
            
        response = await self._make_request("GET", "/vault", params=params)
        data = response.json()
        return [OnlyFansVault(**item) for item in data.get("list", [])]
    
    async def create_list(self, name: str) -> OnlyFansList:
        """Create a custom list."""
        payload = {"name": name}
        response = await self._make_request("POST", "/lists", json=payload)
        data = response.json()
        return OnlyFansList(**data)
    
    async def add_to_list(self, list_id: str, user_ids: List[str]) -> bool:
        """Add users to a custom list."""
        payload = {"userIds": user_ids}
        response = await self._make_request(
            "POST",
            f"/lists/{list_id}/users",
            json=payload
        )
        return response.status_code == 200
    
    async def get_notifications(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansNotification]:
        """Get notifications."""
        params = {
            "limit": limit,
            "offset": offset
        }
        
        response = await self._make_request("GET", "/notifications", params=params)
        data = response.json()
        return [OnlyFansNotification(**item) for item in data.get("list", [])]
    
    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        response = await self._make_request(
            "POST",
            f"/notifications/{notification_id}/read"
        )
        return response.status_code == 200