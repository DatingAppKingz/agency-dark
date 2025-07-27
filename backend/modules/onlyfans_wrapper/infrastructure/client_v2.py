"""
OnlyFans API client implementation using the External API Framework.
"""
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime
from decimal import Decimal
import json

from core.external_api import (
    BaseAPIClient, APIConfig, APICredentials,
    APIError, APIValidationError,
    log_api_call
)
from core.external_api.rate_limit import MultiRateLimiter

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


class OnlyFansAPIException(APIError):
    """OnlyFans-specific API exception"""
    pass


class OnlyFansClient(BaseAPIClient, IOnlyFansClient):
    """OnlyFans API client using External API Framework"""
    
    def __init__(self, config: OnlyFansConfig):
        # Convert OnlyFansConfig to APIConfig
        api_config = APIConfig(
            name="onlyfans",
            base_url=str(config.base_url),
            timeout=config.timeout,
            max_retries=config.max_retries,
            rate_limit=60,  # Conservative default
            credentials=APICredentials(api_key=config.api_key),
            custom_headers={}
        )
        
        # Add custom headers if provided
        if config.cookie:
            api_config.custom_headers['Cookie'] = config.cookie
        if config.x_bc:
            api_config.custom_headers['X-BC'] = config.x_bc
            
        # Initialize rate limiter with OnlyFans limits
        # OnlyFans has strict rate limits, especially for mass operations
        rate_limiter = MultiRateLimiter({
            60: 60,       # 60 requests per minute
            3600: 1000,   # 1000 requests per hour
            86400: 10000  # 10000 requests per day
        })
        
        super().__init__(api_config)
        self.onlyfans_config = config
        self.rate_limiter = rate_limiter
        self._authenticated = False
        
    def get_default_headers(self) -> Dict[str, str]:
        """Get default headers for OnlyFans API"""
        headers = {
            'User-Agent': self.onlyfans_config.user_agent or 'AgencyDark/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Add API key
        if self.config.credentials and self.config.credentials.api_key:
            headers['X-API-Key'] = self.config.credentials.api_key.get_secret_value()
            
        # Add custom headers from config
        headers.update(self.config.custom_headers)
        
        return headers
        
    async def authenticate(self) -> bool:
        """Authenticate with OnlyFans API"""
        try:
            # Test authentication by getting profile
            await self.get_profile()
            self._authenticated = True
            return True
        except APIError:
            self._authenticated = False
            return False
            
    def _parse_error(self, data: Dict[str, Any], status_code: int) -> APIError:
        """Parse OnlyFans-specific error format"""
        try:
            error = OnlyFansAPIError(**data)
            return OnlyFansAPIException(
                message=error.message or error.error,
                code=error.code,
                details=data
            )
        except Exception:
            # Fallback to generic error parsing
            return super()._extract_error_message(data)
            
    @log_api_call
    async def get_profile(self, username: Optional[str] = None) -> OnlyFansProfile:
        """Get profile information"""
        await self.rate_limiter.acquire()
        
        endpoint = f"/profile/{username}" if username else "/profile/me"
        response = await self.get(endpoint)
        return OnlyFansProfile(**response)
        
    @log_api_call
    async def update_profile(
        self,
        name: Optional[str] = None,
        about: Optional[str] = None,
        subscription_price: Optional[Decimal] = None
    ) -> OnlyFansProfile:
        """Update profile information"""
        await self.rate_limiter.acquire()
        
        data = {}
        if name is not None:
            data["name"] = name
        if about is not None:
            data["about"] = about
        if subscription_price is not None:
            data["price"] = str(subscription_price)
            
        response = await self.patch("/profile/me", data=data)
        return OnlyFansProfile(**response)
        
    @log_api_call
    async def get_fans(
        self,
        limit: int = 100,
        offset: int = 0,
        filter_type: Optional[str] = None
    ) -> List[OnlyFansFan]:
        """Get list of fans/subscribers"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset
        }
        if filter_type:
            params["type"] = filter_type
            
        response = await self.get("/fans", params=params)
        items = response.get("list", [])
        return [OnlyFansFan(**item) for item in items]
        
    @log_api_call
    async def get_fan(self, fan_id: str) -> OnlyFansFan:
        """Get specific fan details"""
        await self.rate_limiter.acquire()
        
        response = await self.get(f"/fans/{fan_id}")
        return OnlyFansFan(**response)
        
    @log_api_call
    async def restrict_fan(self, fan_id: str) -> bool:
        """Restrict a fan from viewing content"""
        await self.rate_limiter.acquire()
        
        try:
            await self.post(f"/fans/{fan_id}/restrict")
            return True
        except APIError:
            return False
            
    @log_api_call
    async def unrestrict_fan(self, fan_id: str) -> bool:
        """Remove restriction from a fan"""
        await self.rate_limiter.acquire()
        
        try:
            await self.post(f"/fans/{fan_id}/unrestrict")
            return True
        except APIError:
            return False
            
    @log_api_call
    async def get_posts(
        self,
        limit: int = 100,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[OnlyFansPost]:
        """Get posts from timeline"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset,
            "skip_archived": not include_archived
        }
        
        response = await self.get("/posts", params=params)
        items = response.get("list", [])
        return [OnlyFansPost(**item) for item in items]
        
    @log_api_call
    async def create_post(
        self,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansPost:
        """Create a new post"""
        await self.rate_limiter.acquire()
        
        data = {}
        if text:
            data["text"] = text
        if media_ids:
            data["mediaIds"] = media_ids
        if price is not None:
            data["price"] = str(price)
        if is_paid:
            data["isPaid"] = is_paid
            
        response = await self.post("/posts", data=data)
        return OnlyFansPost(**response)
        
    @log_api_call
    async def delete_post(self, post_id: str) -> bool:
        """Delete a post"""
        await self.rate_limiter.acquire()
        
        try:
            await self.delete(f"/posts/{post_id}")
            return True
        except APIError:
            return False
            
    @log_api_call
    async def get_messages(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansMessage]:
        """Get messages/chats"""
        await self.rate_limiter.acquire()
        
        endpoint = f"/chats/{user_id}/messages" if user_id else "/chats"
        params = {
            "limit": limit,
            "offset": offset
        }
        
        response = await self.get(endpoint, params=params)
        items = response.get("list", [])
        return [OnlyFansMessage(**item) for item in items]
        
    @log_api_call
    async def send_message(
        self,
        user_id: str,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansMessage:
        """Send a message to a user"""
        await self.rate_limiter.acquire()
        
        data = {
            "userId": user_id
        }
        if text:
            data["text"] = text
        if media_ids:
            data["mediaIds"] = media_ids
        if price is not None:
            data["price"] = str(price)
            data["isPaid"] = True
        elif is_paid:
            data["isPaid"] = is_paid
            
        response = await self.post("/messages", data=data)
        return OnlyFansMessage(**response)
        
    @log_api_call
    async def send_mass_message(
        self,
        user_ids: List[str],
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Send mass message to multiple users"""
        # Mass messages have stricter rate limits
        await self.rate_limiter.acquire(tokens=len(user_ids))
        
        data = {
            "userIds": user_ids
        }
        if text:
            data["text"] = text
        if media_ids:
            data["mediaIds"] = media_ids
        if price is not None:
            data["price"] = str(price)
            
        return await self.post("/messages/mass", data=data)
        
    @log_api_call
    async def get_transactions(
        self,
        type_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansTransaction]:
        """Get financial transactions"""
        await self.rate_limiter.acquire()
        
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
            
        response = await self.get("/transactions", params=params)
        items = response.get("list", [])
        return [OnlyFansTransaction(**item) for item in items]
        
    @log_api_call
    async def get_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> OnlyFansStatistics:
        """Get account statistics"""
        await self.rate_limiter.acquire()
        
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat()
        }
        
        response = await self.get("/statistics", params=params)
        # Add period dates to the response
        response["period_start"] = start_date
        response["period_end"] = end_date
        return OnlyFansStatistics(**response)
        
    @log_api_call
    async def upload_media(
        self,
        file: BinaryIO,
        media_type: str,
        filename: Optional[str] = None
    ) -> OnlyFansMedia:
        """Upload media file"""
        await self.rate_limiter.acquire()
        
        # For file uploads, we need special handling
        # The base client needs to support multipart/form-data
        # For now, we'll create a custom request
        files = {
            'file': (filename or 'upload', file, f'{media_type}/*')
        }
        data = {
            'type': media_type
        }
        
        # Use the session directly for file upload
        async with self.session.post(
            f"{self.config.base_url}/media/upload",
            data=data,
            files=files
        ) as response:
            if response.status >= 400:
                error_data = await response.json()
                raise self._parse_error(error_data, response.status)
                
            result = await response.json()
            return OnlyFansMedia(**result)
            
    @log_api_call
    async def get_vault(
        self,
        limit: int = 100,
        offset: int = 0,
        media_type: Optional[str] = None
    ) -> List[OnlyFansVault]:
        """Get vault items"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset
        }
        if media_type:
            params["type"] = media_type
            
        response = await self.get("/vault", params=params)
        items = response.get("list", [])
        return [OnlyFansVault(**item) for item in items]
        
    @log_api_call
    async def create_list(self, name: str) -> OnlyFansList:
        """Create a custom list"""
        await self.rate_limiter.acquire()
        
        response = await self.post("/lists", data={"name": name})
        return OnlyFansList(**response)
        
    @log_api_call
    async def add_to_list(self, list_id: str, user_ids: List[str]) -> bool:
        """Add users to a custom list"""
        await self.rate_limiter.acquire()
        
        try:
            await self.post(
                f"/lists/{list_id}/users",
                data={"userIds": user_ids}
            )
            return True
        except APIError:
            return False
            
    @log_api_call
    async def get_notifications(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansNotification]:
        """Get notifications"""
        await self.rate_limiter.acquire()
        
        params = {
            "limit": limit,
            "offset": offset
        }
        
        response = await self.get("/notifications", params=params)
        items = response.get("list", [])
        return [OnlyFansNotification(**item) for item in items]
        
    @log_api_call
    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark notification as read"""
        await self.rate_limiter.acquire()
        
        try:
            await self.post(f"/notifications/{notification_id}/read")
            return True
        except APIError:
            return False