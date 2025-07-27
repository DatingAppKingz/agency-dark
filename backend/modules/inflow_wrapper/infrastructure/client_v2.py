"""
Inflow API client implementation using the External API Framework.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import hmac
import hashlib

from core.external_api import (
    BaseAPIClient, APIConfig, APICredentials,
    APIError, APIValidationError,
    log_api_call
)
from core.external_api.rate_limit import MultiRateLimiter
from core.external_api.webhooks import HMACWebhookHandler, WebhookEvent

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


class InflowAPIException(APIError):
    """Inflow-specific API exception"""
    pass


class InflowClient(BaseAPIClient, IInflowClient):
    """Inflow API client using External API Framework"""
    
    def __init__(self, config: InflowConfig):
        # Convert InflowConfig to APIConfig
        api_config = APIConfig(
            name="inflow",
            base_url=str(config.base_url),
            timeout=config.timeout,
            max_retries=config.max_retries,
            rate_limit=60,  # 60 requests per minute default
            credentials=APICredentials(api_key=config.api_key)
        )
        
        # Initialize rate limiter with Inflow's limits
        rate_limiter = MultiRateLimiter({
            60: 60,      # 60 requests per minute
            3600: 1000   # 1000 requests per hour
        })
        
        super().__init__(api_config)
        self.inflow_config = config
        self.rate_limiter = rate_limiter
        self._authenticated = False
        
    def get_default_headers(self) -> Dict[str, str]:
        """Get default headers for Inflow API"""
        headers = {
            'User-Agent': 'AgencyDark/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Add API key if available
        if self.config.credentials and self.config.credentials.api_key:
            headers['X-API-Key'] = self.config.credentials.api_key.get_secret_value()
            
        return headers
        
    async def authenticate(self) -> bool:
        """Authenticate with Inflow API"""
        if self.inflow_config.auth_method == "api_key":
            # Verify API key by getting current user
            try:
                await self.get_current_user()
                self._authenticated = True
                return True
            except APIError:
                self._authenticated = False
                return False
                
        # TODO: Implement OAuth2 and JWT authentication
        raise NotImplementedError(f"Auth method {self.inflow_config.auth_method} not implemented")
        
    def _parse_error(self, data: Dict[str, Any], status_code: int) -> APIError:
        """Parse Inflow-specific error format"""
        try:
            error = InflowAPIError(**data)
            return InflowAPIException(
                message=error.message,
                code=error.code,
                details=data
            )
        except Exception:
            # Fallback to generic error parsing
            return super()._extract_error_message(data)
            
    @log_api_call
    async def get_current_user(self) -> InflowUser:
        """Get the authenticated user's information"""
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        response = await self.get("/api/v1/users/me")
        return InflowUser(**response)
        
    @log_api_call
    async def get_user(self, user_id: str) -> InflowUser:
        """Get a specific user by ID"""
        await self.rate_limiter.acquire()
        
        response = await self.get(f"/api/v1/users/{user_id}")
        return InflowUser(**response)
        
    @log_api_call
    async def list_subscribers(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True
    ) -> List[InflowSubscription]:
        """List subscribers for a creator"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset,
            "active_only": active_only
        }
        
        response = await self.get(
            f"/api/v1/creators/{creator_id}/subscribers",
            params=params
        )
        
        items = response.get("items", [])
        return [InflowSubscription(**item) for item in items]
        
    @log_api_call
    async def get_subscription(self, subscription_id: str) -> InflowSubscription:
        """Get a specific subscription by ID"""
        await self.rate_limiter.acquire()
        
        response = await self.get(f"/api/v1/subscriptions/{subscription_id}")
        return InflowSubscription(**response)
        
    @log_api_call
    async def list_content(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        content_type: Optional[str] = None
    ) -> List[InflowContent]:
        """List content for a creator"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset
        }
        if content_type:
            params["content_type"] = content_type
            
        response = await self.get(
            f"/api/v1/creators/{creator_id}/content",
            params=params
        )
        
        items = response.get("items", [])
        return [InflowContent(**item) for item in items]
        
    @log_api_call
    async def create_content(
        self,
        title: str,
        content_type: str,
        file_path: str,
        description: Optional[str] = None,
        price: Optional[float] = None,
        is_ppv: bool = False
    ) -> InflowContent:
        """Create new content"""
        await self.rate_limiter.acquire()
        
        # For file uploads, we need to use multipart/form-data
        # This requires special handling in the base client
        data = {
            "title": title,
            "content_type": content_type,
            "description": description,
            "price": price,
            "is_ppv": is_ppv
        }
        
        # TODO: Implement file upload support in base client
        # For now, we'll send the file path and let the API handle it
        data["file_path"] = file_path
        
        response = await self.post("/api/v1/content", data=data)
        return InflowContent(**response)
        
    @log_api_call
    async def delete_content(self, content_id: str) -> bool:
        """Delete content by ID"""
        await self.rate_limiter.acquire()
        
        try:
            await self.delete(f"/api/v1/content/{content_id}")
            return True
        except APIError:
            return False
            
    @log_api_call
    async def list_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowMessage]:
        """List messages in a conversation or with a specific user"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if conversation_id:
            endpoint = f"/api/v1/conversations/{conversation_id}/messages"
        elif user_id:
            endpoint = "/api/v1/messages"
            params["user_id"] = user_id
        else:
            endpoint = "/api/v1/messages"
            
        response = await self.get(endpoint, params=params)
        items = response.get("items", [])
        return [InflowMessage(**item) for item in items]
        
    @log_api_call
    async def send_message(
        self,
        recipient_id: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        price: Optional[float] = None
    ) -> InflowMessage:
        """Send a message to a user"""
        await self.rate_limiter.acquire()
        
        data = {
            "recipient_id": recipient_id,
            "content": content,
            "attachments": attachments or [],
            "is_ppv": price is not None,
            "price": price
        }
        
        response = await self.post("/api/v1/messages", data=data)
        return InflowMessage(**response)
        
    @log_api_call
    async def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        await self.rate_limiter.acquire()
        
        try:
            await self.post(f"/api/v1/messages/{message_id}/read")
            return True
        except APIError:
            return False
            
    @log_api_call
    async def list_transactions(
        self,
        user_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowTransaction]:
        """List financial transactions"""
        await self.rate_limiter.acquire()
        
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
            
        response = await self.get("/api/v1/transactions", params=params)
        items = response.get("items", [])
        return [InflowTransaction(**item) for item in items]
        
    @log_api_call
    async def get_analytics(
        self,
        creator_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> InflowAnalytics:
        """Get analytics for a creator within a date range"""
        await self.rate_limiter.acquire()
        
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        response = await self.get(
            f"/api/v1/creators/{creator_id}/analytics",
            params=params
        )
        
        return InflowAnalytics(**response)
        
    @log_api_call
    async def register_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a webhook endpoint"""
        await self.rate_limiter.acquire()
        
        data = {
            "url": url,
            "events": events,
            "secret": secret
        }
        
        return await self.post("/api/v1/webhooks", data=data)
        
    async def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature"""
        if not self.inflow_config.webhook_secret:
            return False
            
        # Inflow uses HMAC-SHA256 for webhook signatures
        expected = hmac.new(
            self.inflow_config.webhook_secret.encode('utf-8'),
            str(payload).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)


class InflowWebhookHandler(HMACWebhookHandler):
    """Webhook handler for Inflow events"""
    
    def __init__(self, webhook_secret: str):
        super().__init__(
            api_name="inflow",
            signature_header="x-inflow-signature",
            hash_algorithm="sha256"
        )
        self.webhook_secret = webhook_secret
        
    def parse_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse Inflow webhook payload"""
        return WebhookEvent(
            id=payload.get('event_id', 'unknown'),
            type=payload.get('event_type', 'unknown'),
            timestamp=datetime.fromisoformat(payload.get('timestamp', datetime.utcnow().isoformat())),
            data=payload.get('data', {})
        )
        
    async def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Inflow webhook signature"""
        # Inflow includes the timestamp in the signature
        # Format: t=timestamp,v1=signature
        parts = signature.split(',')
        timestamp = None
        sig_value = None
        
        for part in parts:
            key, value = part.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                sig_value = value
                
        if not timestamp or not sig_value:
            return False
            
        # Construct signed payload
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        
        # Calculate expected signature
        expected = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, sig_value)