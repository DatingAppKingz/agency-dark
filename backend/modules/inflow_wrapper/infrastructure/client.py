"""
Inflow API client implementation.

This module implements the actual HTTP client for interacting with Inflow API.
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
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
        
        # OAuth2 authentication
        if self.config.auth_method == "oauth2":
            return await self._authenticate_oauth2()
        
        # JWT authentication
        if self.config.auth_method == "jwt":
            return await self._authenticate_jwt()
        
        raise NotImplementedError(f"Auth method {self.config.auth_method} not implemented")
    
    async def _authenticate_oauth2(self) -> bool:
        """Authenticate using OAuth2."""
        if not all([self.config.client_id, self.config.client_secret, self.config.token_url]):
            raise ValueError("OAuth2 requires client_id, client_secret, and token_url")
        
        # Check if we have a valid token
        if self.config.access_token and self.config.token_expires_at:
            if self.config.token_expires_at > datetime.utcnow():
                self._auth_headers = {"Authorization": f"Bearer {self.config.access_token}"}
                return True
            elif self.config.refresh_token:
                # Try to refresh the token
                return await self._refresh_oauth2_token()
        
        # Request new token using client credentials
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.config.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                        "scope": self.config.scope or ""
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                
                token_data = response.json()
                self.config.access_token = token_data["access_token"]
                self.config.refresh_token = token_data.get("refresh_token")
                
                # Calculate expiration
                expires_in = token_data.get("expires_in", 3600)
                self.config.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                self._auth_headers = {"Authorization": f"Bearer {self.config.access_token}"}
                return True
                
            except Exception as e:
                logger.error(f"OAuth2 authentication failed: {e}")
                return False
    
    async def _refresh_oauth2_token(self) -> bool:
        """Refresh OAuth2 token."""
        if not self.config.refresh_token:
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.config.refresh_token,
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                
                token_data = response.json()
                self.config.access_token = token_data["access_token"]
                if "refresh_token" in token_data:
                    self.config.refresh_token = token_data["refresh_token"]
                
                expires_in = token_data.get("expires_in", 3600)
                self.config.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                self._auth_headers = {"Authorization": f"Bearer {self.config.access_token}"}
                return True
                
            except Exception as e:
                logger.error(f"OAuth2 token refresh failed: {e}")
                return False
    
    async def _authenticate_jwt(self) -> bool:
        """Authenticate using JWT."""
        if not self.config.jwt_secret:
            raise ValueError("JWT authentication requires jwt_secret")
        
        try:
            import jwt
            
            # Create JWT token
            payload = {
                "iss": "agency-dark",
                "sub": self.config.api_key or "default",
                "exp": datetime.utcnow() + timedelta(seconds=self.config.jwt_expiration),
                "iat": datetime.utcnow()
            }
            
            token = jwt.encode(
                payload,
                self.config.jwt_secret,
                algorithm=self.config.jwt_algorithm
            )
            
            self._auth_headers = {"Authorization": f"Bearer {token}"}
            
            # Verify by getting current user
            await self.get_current_user()
            return True
            
        except Exception as e:
            logger.error(f"JWT authentication failed: {e}")
            return False
    
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
        # Open file and prepare multipart data
        with open(file_path, 'rb') as f:
            files = {
                'file': (file_path.split('/')[-1], f, f'application/{content_type}')
            }
            data = {
                'title': title,
                'content_type': content_type,
                'description': description or '',
                'price': price or 0,
                'is_ppv': is_ppv
            }
            
            response = await self._make_request(
                "POST",
                "/api/v1/content",
                files=files,
                data=data
            )
            
        return InflowContent(**response.json())
    
    async def upload_media(
        self,
        file: BinaryIO,
        media_type: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload media file for messages or content."""
        files = {
            'file': (filename or 'upload', file, f'{media_type}/*')
        }
        data = {
            'type': media_type
        }
        
        response = await self._make_request(
            "POST",
            "/api/v1/media/upload",
            files=files,
            data=data
        )
        
        return response.json()
    
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
        signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """Verify webhook signature using HMAC-SHA256."""
        import hmac
        import hashlib
        import json
        
        # Use provided secret or config secret
        secret = webhook_secret or self.config.webhook_secret
        if not secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True
        
        # Convert payload to canonical JSON string
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (remove any prefix like "sha256=")
        provided_signature = signature.split('=')[-1] if '=' in signature else signature
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, provided_signature)