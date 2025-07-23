"""
Inflow API client implementation.

This module implements the actual HTTP client for interacting with Inflow API.
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

import httpx
from httpx import AsyncClient, Response, HTTPError

from ..domain.interfaces import IInflowClient
from ..domain.schemas import (
    InflowConfig,
    InflowUser,
    InflowContent,
    InflowMessage,
    InflowSubscription,
    InflowTransaction,
    InflowAnalytics,
    InflowAPIError
)


logger = logging.getLogger(__name__)


class InflowAPIException(Exception):
    """Exception raised by Inflow API client."""
    
    def __init__(self, error: InflowAPIError, status_code: int = 500):
        self.error = error
        self.status_code = status_code
        super().__init__(f"Inflow API Error: {error.message}")


class InflowClient(IInflowClient):
    """HTTP client for Inflow API."""
    
    def __init__(self, config: InflowConfig):
        self.config = config
        self._client: Optional[AsyncClient] = None
        self._auth_headers: Dict[str, str] = {}
        
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
            self._client = AsyncClient(
                base_url=str(self.config.base_url),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "User-Agent": "AgencyDark/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Response:
        """Make HTTP request with retry logic."""
        await self._ensure_client()
        
        # Add authentication headers
        headers = kwargs.get("headers", {})
        headers.update(self._auth_headers)
        kwargs["headers"] = headers
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.request(method, endpoint, **kwargs)
                
                # Check for API errors
                if response.status_code >= 400:
                    error_data = response.json()
                    error = InflowAPIError(**error_data)
                    raise InflowAPIException(error, response.status_code)
                
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
        """Authenticate with Inflow API."""
        if self.config.auth_method == "api_key" and self.config.api_key:
            self._auth_headers = {"X-API-Key": self.config.api_key}
            
            # Verify authentication by getting current user
            try:
                await self.get_current_user()
                return True
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                return False
        
        # TODO: Implement OAuth2 and JWT authentication
        raise NotImplementedError(f"Auth method {self.config.auth_method} not implemented")
    
    async def get_current_user(self) -> InflowUser:
        """Get the authenticated user's information."""
        response = await self._make_request("GET", "/api/v1/users/me")
        data = response.json()
        return InflowUser(**data)
    
    async def get_user(self, user_id: str) -> InflowUser:
        """Get a specific user by ID."""
        response = await self._make_request("GET", f"/api/v1/users/{user_id}")
        data = response.json()
        return InflowUser(**data)
    
    async def list_subscribers(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True
    ) -> List[InflowSubscription]:
        """List subscribers for a creator."""
        params = {
            "limit": limit,
            "offset": offset,
            "active_only": active_only
        }
        response = await self._make_request(
            "GET",
            f"/api/v1/creators/{creator_id}/subscribers",
            params=params
        )
        data = response.json()
        return [InflowSubscription(**item) for item in data.get("items", [])]
    
    async def get_subscription(self, subscription_id: str) -> InflowSubscription:
        """Get a specific subscription by ID."""
        response = await self._make_request("GET", f"/api/v1/subscriptions/{subscription_id}")
        data = response.json()
        return InflowSubscription(**data)
    
    async def list_content(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        content_type: Optional[str] = None
    ) -> List[InflowContent]:
        """List content for a creator."""
        params = {
            "limit": limit,
            "offset": offset
        }
        if content_type:
            params["content_type"] = content_type
            
        response = await self._make_request(
            "GET",
            f"/api/v1/creators/{creator_id}/content",
            params=params
        )
        data = response.json()
        return [InflowContent(**item) for item in data.get("items", [])]
    
    async def create_content(
        self,
        title: str,
        content_type: str,
        file_path: str,
        description: Optional[str] = None,
        price: Optional[float] = None,
        is_ppv: bool = False
    ) -> InflowContent:
        """Create new content."""
        # TODO: Implement file upload
        # This would typically involve multipart form data
        raise NotImplementedError("Content creation not yet implemented")
    
    async def delete_content(self, content_id: str) -> bool:
        """Delete content by ID."""
        response = await self._make_request("DELETE", f"/api/v1/content/{content_id}")
        return response.status_code == 204
    
    async def list_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowMessage]:
        """List messages in a conversation or with a specific user."""
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if conversation_id:
            endpoint = f"/api/v1/conversations/{conversation_id}/messages"
        elif user_id:
            endpoint = f"/api/v1/messages"
            params["user_id"] = user_id
        else:
            endpoint = "/api/v1/messages"
            
        response = await self._make_request("GET", endpoint, params=params)
        data = response.json()
        return [InflowMessage(**item) for item in data.get("items", [])]
    
    async def send_message(
        self,
        recipient_id: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        price: Optional[float] = None
    ) -> InflowMessage:
        """Send a message to a user."""
        payload = {
            "recipient_id": recipient_id,
            "content": content,
            "attachments": attachments or [],
            "is_ppv": price is not None,
            "price": price
        }
        
        response = await self._make_request("POST", "/api/v1/messages", json=payload)
        data = response.json()
        return InflowMessage(**data)
    
    async def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        response = await self._make_request(
            "POST",
            f"/api/v1/messages/{message_id}/read"
        )
        return response.status_code == 200
    
    async def list_transactions(
        self,
        user_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowTransaction]:
        """List financial transactions."""
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if user_id:
            params["user_id"] = user_id
        if transaction_type:
            params["type"] = transaction_type
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
            
        response = await self._make_request("GET", "/api/v1/transactions", params=params)
        data = response.json()
        return [InflowTransaction(**item) for item in data.get("items", [])]
    
    async def get_analytics(
        self,
        creator_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> InflowAnalytics:
        """Get analytics for a creator within a date range."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        response = await self._make_request(
            "GET",
            f"/api/v1/creators/{creator_id}/analytics",
            params=params
        )
        data = response.json()
        return InflowAnalytics(**data)
    
    async def register_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a webhook endpoint."""
        payload = {
            "url": url,
            "events": events,
            "secret": secret
        }
        
        response = await self._make_request("POST", "/api/v1/webhooks", json=payload)
        return response.json()
    
    async def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature."""
        # TODO: Implement webhook signature verification
        # This typically involves HMAC-SHA256 with the webhook secret
        raise NotImplementedError("Webhook verification not yet implemented")